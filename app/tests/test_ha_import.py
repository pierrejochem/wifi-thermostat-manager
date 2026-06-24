"""Unit tests for ha_import — no Flask, no network, no real SDK."""
import importlib
import json
import os
from types import SimpleNamespace

import pytest

import ha_import


def _fake_device(device_id, category, name="Device", local_key="key", ip="1.2.3.4",
                 online=True, local_strategy=None, status_range=None, status=None):
    return SimpleNamespace(
        id=device_id, category=category, name=name, local_key=local_key,
        ip=ip, online=online,
        local_strategy=local_strategy or {}, status_range=status_range or {},
        status=status or {},
    )


# Mirrors the real TRV-607/608 metadata: target=DP16, current=DP24, mode=DP2,
# scale 1 (=> divide by 10).
TRV_STRATEGY = {
    "2": {"status_code": "mode"},
    "16": {"status_code": "temp_set"},
    "24": {"status_code": "temp_current"},
    "40": {"status_code": "child_lock"},
}
# Mirrors tuya_sharing.device.DeviceStatusRange: an object whose JSON spec is
# in the `values` attribute (NOT a dict with `.get`).
def _status_range(code, spec):
    return SimpleNamespace(code=code, type="Integer", values=spec, report_type=None)


TRV_STATUS_RANGE = {
    "temp_set": _status_range("temp_set", '{"unit":"\\u2103","min":50,"max":350,"scale":1,"step":5}'),
    "temp_current": _status_range("temp_current", '{"unit":"\\u2103","min":-300,"max":1000,"scale":1,"step":5}'),
}


class _FakeManager:
    """Stand-in for tuya_sharing.Manager."""

    def __init__(self, devices, raise_on_update=None, homes=1):
        self.device_map = {d.id: d for d in devices}
        self.user_homes = list(range(homes))
        self._raise = raise_on_update
        self.refreshed = False

    def update_device_cache(self):
        if self._raise:
            raise self._raise

    # If this ever gets called the test should fail loudly: we must not refresh.
    def refresh_mq(self):  # pragma: no cover
        self.refreshed = True


# --- core.config_entries parsing -------------------------------------------

def _write_entries(tmp_path, entries):
    storage = tmp_path / ".storage"
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / "core.config_entries"
    path.write_text(json.dumps({"data": {"entries": entries}}))
    return str(path)


TUYA_DATA = {
    "user_code": "uc", "terminal_id": "tid", "endpoint": "https://x",
    "token_info": {"access_token": "a", "refresh_token": "r"},
}


def test_read_tuya_entry_extracts_data(tmp_path):
    path = _write_entries(tmp_path, [
        {"domain": "hue", "data": {"host": "1.1.1.1"}},
        {"domain": "tuya", "data": TUYA_DATA},
    ])
    assert ha_import.read_tuya_entry(path) == TUYA_DATA


def test_read_tuya_entry_not_found(tmp_path):
    path = _write_entries(tmp_path, [{"domain": "hue", "data": {}}])
    with pytest.raises(ha_import.TuyaEntryNotFound):
        ha_import.read_tuya_entry(path)


def test_read_tuya_entry_missing_file():
    with pytest.raises(ha_import.TuyaEntryNotFound):
        ha_import.read_tuya_entry("/no/such/path/core.config_entries")


def test_read_tuya_entry_missing_fields(tmp_path):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": {"user_code": "uc"}}])
    with pytest.raises(ha_import.HaImportError):
        ha_import.read_tuya_entry(path)


def test_read_tuya_entries_returns_all(tmp_path):
    e1 = {**TUYA_DATA, "terminal_id": "t1"}
    e2 = {**TUYA_DATA, "terminal_id": "t2"}
    path = _write_entries(tmp_path, [
        {"domain": "tuya", "data": e1},
        {"domain": "hue", "data": {}},
        {"domain": "tuya", "data": e2},
    ])
    entries = ha_import.read_tuya_entries(path)
    assert [e["terminal_id"] for e in entries] == ["t1", "t2"]


# --- fetch_thermostats ------------------------------------------------------

def test_fetch_filters_categories(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    devices = [
        _fake_device("wk1", "wk"),          # thermostat
        _fake_device("trv1", "wkf"),        # radiator valve
        _fake_device("ac1", "kt"),          # AC-style climate
        _fake_device("heat1", "qn"),        # heater
        _fake_device("wh1", "rs"),          # water heater
        _fake_device("dbl1", "dbl"),        # electric heater
        _fake_device("sensor1", "wsdcg"),   # temp/humidity sensor — must drop
        _fake_device("switch1", "kg"),      # switch — must drop
    ]
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: _FakeManager(devices))
    result = ha_import.fetch_thermostats(path)
    ids = {r["device_id"] for r in result}
    # Matches the categories Home Assistant's own Tuya climate platform handles.
    assert ids == {"wk1", "trv1", "ac1", "heat1", "wh1", "dbl1"}


def test_discover_reports_seen_categories(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    devices = [_fake_device("wk1", "wk"), _fake_device("s1", "kg"), _fake_device("s2", "kg")]
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: _FakeManager(devices))
    result = ha_import.discover(path)
    assert {d["device_id"] for d in result["devices"]} == {"wk1"}
    assert result["total"] == 3
    assert result["seen_categories"] == {"wk": 1, "kg": 2}


def test_extra_categories_env_override(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    devices = [_fake_device("weird1", "xyz")]
    monkeypatch.setenv("TUYA_THERMOSTAT_CATEGORIES", "xyz, abc")
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: _FakeManager(devices))
    result = ha_import.fetch_thermostats(path)
    assert {r["device_id"] for r in result} == {"weird1"}


def test_fetch_already_added_flag(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    devices = [_fake_device("wk1", "wk"), _fake_device("wk2", "wk")]
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: _FakeManager(devices))
    result = ha_import.fetch_thermostats(path, already_added_ids={"wk1"})
    by_id = {r["device_id"]: r for r in result}
    assert by_id["wk1"]["already_added"] is True
    assert by_id["wk2"]["already_added"] is False


def test_fetch_token_error_maps(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    mgr = _FakeManager([], raise_on_update=RuntimeError("401 token invalid"))
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: mgr)
    with pytest.raises(ha_import.TuyaTokenError):
        ha_import.fetch_thermostats(path)


def test_discover_aggregates_multiple_entries(tmp_path, monkeypatch):
    # Two linked Tuya accounts; the thermostat lives under the SECOND one.
    e1 = {**TUYA_DATA, "terminal_id": "t1"}
    e2 = {**TUYA_DATA, "terminal_id": "t2"}
    path = _write_entries(tmp_path, [
        {"domain": "tuya", "data": e1},
        {"domain": "tuya", "data": e2},
    ])
    managers = {
        "t1": _FakeManager([]),                          # empty account (the bug)
        "t2": _FakeManager([_fake_device("wkB", "wk")]),  # has the thermostat
    }
    monkeypatch.setattr(ha_import, "_build_manager",
                        lambda creds: managers[creds["terminal_id"]])
    result = ha_import.discover(path)
    assert {d["device_id"] for d in result["devices"]} == {"wkB"}
    assert result["entries"] == 2
    assert result["homes"] == 2


def test_discover_skips_failed_entry(tmp_path, monkeypatch):
    e1 = {**TUYA_DATA, "terminal_id": "t1"}
    e2 = {**TUYA_DATA, "terminal_id": "t2"}
    path = _write_entries(tmp_path, [
        {"domain": "tuya", "data": e1},
        {"domain": "tuya", "data": e2},
    ])
    managers = {
        "t1": _FakeManager([], raise_on_update=RuntimeError("401")),
        "t2": _FakeManager([_fake_device("wkB", "wk")]),
    }
    monkeypatch.setattr(ha_import, "_build_manager",
                        lambda creds: managers[creds["terminal_id"]])
    result = ha_import.discover(path)
    assert {d["device_id"] for d in result["devices"]} == {"wkB"}


# --- normalize / to_definition ---------------------------------------------

def test_normalize_address_default(tmp_path, monkeypatch):
    path = _write_entries(tmp_path, [{"domain": "tuya", "data": TUYA_DATA}])
    devices = [_fake_device("wk1", "wk", ip=None)]
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: _FakeManager(devices))
    row = ha_import.fetch_thermostats(path)[0]
    assert row["address"] == "Auto"
    assert row["local_key"] == "key"
    assert row["online"] is True


def test_to_definition_defaults():
    item = {"device_id": "wk1", "name": "Hall", "local_key": "k", "address": "Auto"}
    definition = ha_import.to_definition(item)
    assert definition == {
        "type": "tuya", "name": "Hall", "device_id": "wk1", "local_key": "k",
        "address": "Auto", "version": "3.3", "temp_divisor": 2,
    }


def test_derive_dp_map_and_scale():
    device = _fake_device("trv1", "wk", local_strategy=TRV_STRATEGY,
                           status_range=TRV_STATUS_RANGE)
    cfg = ha_import._derive_tuya_config(device)
    assert cfg["dps"] == {"current": "24", "target": "16", "mode": "2"}
    assert cfg["temp_divisor"] == 10
    assert cfg["min_temp"] == 5
    assert cfg["max_temp"] == 35
    assert cfg["temp_step"] == 0.5


def test_normalize_includes_derived_config():
    device = _fake_device("trv1", "wk", local_strategy=TRV_STRATEGY,
                           status_range=TRV_STATUS_RANGE)
    row = ha_import._normalize(device, set())
    assert row["dps"]["target"] == "16"
    assert row["temp_divisor"] == 10


def test_to_definition_carries_derived_config():
    item = {
        "device_id": "trv1", "name": "TRV", "local_key": "k", "address": "Auto",
        "dps": {"current": "24", "target": "16", "mode": "2"},
        "temp_divisor": 10, "min_temp": 5, "max_temp": 35, "temp_step": 0.5,
    }
    definition = ha_import.to_definition(item)
    assert definition["temp_divisor"] == 10
    assert definition["dps"] == {"current": "24", "target": "16", "mode": "2"}
    assert definition["min_temp"] == 5 and definition["max_temp"] == 35
    assert definition["version"] == "3.3"


def test_derive_handles_no_metadata():
    # A device with no local_strategy yields no derived keys (driver defaults).
    cfg = ha_import._derive_tuya_config(_fake_device("x", "wk"))
    assert cfg == {}


def test_battery_device_flagged():
    trv = _fake_device("trv1", "wk", status={"temp_set": 220, "battery_percentage": 100})
    mains = _fake_device("th1", "wk", status={"temp_set": 220, "temp_current": 253})
    assert ha_import._normalize(trv, set())["battery"] is True
    assert ha_import._normalize(mains, set())["battery"] is False


def test_battery_detected_in_status_range():
    trv = _fake_device("trv1", "wk",
                       status_range={"battery_state": _status_range("battery_state", "{}")})
    assert ha_import._normalize(trv, set())["battery"] is True


# --- HA_CONFIG_DIR env override --------------------------------------------

def test_config_path_honours_env(monkeypatch):
    monkeypatch.setenv("HA_CONFIG_DIR", "/custom/ha")
    reloaded = importlib.reload(ha_import)
    try:
        assert reloaded.CONFIG_ENTRIES_PATH == os.path.join(
            "/custom/ha", ".storage", "core.config_entries"
        )
    finally:
        monkeypatch.delenv("HA_CONFIG_DIR", raising=False)
        importlib.reload(ha_import)