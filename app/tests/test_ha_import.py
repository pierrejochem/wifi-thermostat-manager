"""Unit tests for ha_import — no Flask, no network, no real SDK."""
import importlib
import json
import os
from types import SimpleNamespace

import pytest

import ha_import


def _fake_device(device_id, category, name="Device", local_key="key", ip="1.2.3.4",
                 online=True):
    return SimpleNamespace(
        id=device_id, category=category, name=name, local_key=local_key,
        ip=ip, online=online,
    )


class _FakeManager:
    """Stand-in for tuya_sharing.Manager."""

    def __init__(self, devices, raise_on_update=None):
        self.device_map = {d.id: d for d in devices}
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