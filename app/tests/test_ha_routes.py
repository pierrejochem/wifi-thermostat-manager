"""Tests for the /api/ha/* routes in main.py.

Importing main is side-effect-heavy (it builds the MQTT bridge and manager),
but the bridge is a no-op without an MQTT host and the poll thread is harmless,
so we point DATA_DIR at a temp dir and import once.
"""
import os
import tempfile

# Must be set before importing main (config_store reads DATA_DIR at import).
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.pop("MQTT_HOST", None)

import pytest

import ha_import
import main


@pytest.fixture
def client():
    return main.app.test_client()


@pytest.fixture(autouse=True)
def _no_dupes(monkeypatch):
    # Default: nothing already stored.
    monkeypatch.setattr(main, "_already_added_tuya_ids", lambda: set())


def _row(device_id, name="Hall", already_added=False, battery=False):
    return {
        "device_id": device_id, "name": name, "local_key": "k", "address": "Auto",
        "category": "wk", "online": True, "already_added": already_added,
        "battery": battery,
    }


# --- /api/ha/status ---------------------------------------------------------

def test_status_found(client, monkeypatch):
    monkeypatch.setattr(ha_import, "read_tuya_entry", lambda *a, **k: {"user_code": "x"})
    res = client.get("/api/ha/status")
    assert res.status_code == 200
    assert res.get_json() == {"found": True}


def test_status_not_found(client, monkeypatch):
    def _raise(*a, **k):
        raise ha_import.TuyaEntryNotFound("nope")
    monkeypatch.setattr(ha_import, "read_tuya_entry", _raise)
    res = client.get("/api/ha/status")
    assert res.status_code == 200
    assert res.get_json()["found"] is False


# --- /api/ha/devices --------------------------------------------------------

def test_devices_ok(client, monkeypatch):
    monkeypatch.setattr(ha_import, "discover", lambda **k: {
        "devices": [_row("wk1"), _row("wk2", already_added=True)],
        "seen_categories": {"wk": 2}, "total": 2,
    })
    res = client.get("/api/ha/devices")
    assert res.status_code == 200
    body = res.get_json()
    assert [d["device_id"] for d in body["devices"]] == ["wk1", "wk2"]
    assert body["seen_categories"] == {"wk": 2}
    assert body["total"] == 2


def test_devices_empty_reports_categories(client, monkeypatch):
    # Many Tuya devices present, none are thermostats -> UI can explain why.
    monkeypatch.setattr(ha_import, "discover", lambda **k: {
        "devices": [], "seen_categories": {"kg": 5, "dj": 3}, "total": 8,
    })
    res = client.get("/api/ha/devices")
    assert res.status_code == 200
    body = res.get_json()
    assert body["devices"] == []
    assert body["total"] == 8


def test_devices_token_error(client, monkeypatch):
    def _raise(**k):
        raise ha_import.TuyaTokenError("expired")
    monkeypatch.setattr(ha_import, "discover", _raise)
    res = client.get("/api/ha/devices")
    assert res.status_code == 409
    assert "expired" in res.get_json()["error"]


def test_devices_entry_not_found(client, monkeypatch):
    def _raise(**k):
        raise ha_import.TuyaEntryNotFound("none")
    monkeypatch.setattr(ha_import, "discover", _raise)
    res = client.get("/api/ha/devices")
    assert res.status_code == 404


# --- /api/ha/import ---------------------------------------------------------

def test_import_adds_selected_skips_already_added(client, monkeypatch):
    monkeypatch.setattr(ha_import, "fetch_thermostats",
                        lambda **k: [_row("wk1"), _row("wk2", already_added=True)])
    added = []

    def _add(definition):
        added.append(definition)
        return {"id": "abc123", "name": definition["name"]}

    monkeypatch.setattr(main.manager, "add_device", _add)

    res = client.post("/api/ha/import", json={"device_ids": ["wk1", "wk2"]})
    assert res.status_code == 200
    body = res.get_json()
    # wk1 imported, wk2 skipped (already added), nothing errored.
    assert [d["device_id"] for d in body["imported"]] == ["wk1"]
    assert body["skipped"] == ["wk2"]
    assert body["errors"] == []
    # add_device called exactly once, with a proper tuya definition.
    assert len(added) == 1
    assert added[0]["type"] == "tuya" and added[0]["device_id"] == "wk1"


def test_import_skips_battery_device(client, monkeypatch):
    monkeypatch.setattr(ha_import, "fetch_thermostats",
                        lambda **k: [_row("wk1"), _row("trv1", battery=True)])
    added = []
    monkeypatch.setattr(main.manager, "add_device",
                        lambda d: added.append(d) or {"id": "x", "name": d["name"]})
    res = client.post("/api/ha/import", json={"device_ids": ["wk1", "trv1"]})
    body = res.get_json()
    assert [d["device_id"] for d in body["imported"]] == ["wk1"]
    assert body["skipped"] == ["trv1"]
    assert len(added) == 1 and added[0]["device_id"] == "wk1"


def test_import_unknown_device_errors(client, monkeypatch):
    monkeypatch.setattr(ha_import, "fetch_thermostats", lambda **k: [_row("wk1")])
    monkeypatch.setattr(main.manager, "add_device",
                        lambda d: {"id": "x", "name": d["name"]})
    res = client.post("/api/ha/import", json={"device_ids": ["ghost"]})
    assert res.status_code == 200
    body = res.get_json()
    assert body["imported"] == []
    assert body["errors"][0]["device_id"] == "ghost"


def test_import_requires_device_ids(client):
    res = client.post("/api/ha/import", json={})
    assert res.status_code == 400