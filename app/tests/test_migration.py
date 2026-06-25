import importlib, json, os


def test_migrate_tuya_to_cloud(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import config_store
    importlib.reload(config_store)   # pick up DATA_DIR
    store = tmp_path / "thermostats.json"
    store.write_text(json.dumps([
        {"id": "1", "type": "tuya", "name": "Local", "device_id": "bf1",
         "local_key": "k", "address": "Auto", "version": "3.3", "temp_divisor": 10,
         "dps": {"target": "16"}},
        {"id": "2", "type": "rest", "name": "Rest", "status_url": "http://x"},
        {"id": "3", "type": "tuya_cloud", "name": "AlreadyCloud", "device_id": "bf3"},
    ]))

    n = config_store.migrate_tuya_to_cloud()
    assert n == 1

    items = {d["id"]: d for d in config_store.list_all()}
    mig = items["1"]
    assert mig["type"] == "tuya_cloud"
    assert mig["temp_divisor"] == 10                      # preserved
    assert mig["codes"]["target"] == "temp_set"           # default codes applied
    for gone in ("local_key", "address", "version", "dps"):
        assert gone not in mig
    assert items["2"]["type"] == "rest"                   # untouched
    assert items["3"]["type"] == "tuya_cloud"             # untouched

    # Idempotent: a second run migrates nothing.
    assert config_store.migrate_tuya_to_cloud() == 0
    importlib.reload(config_store)                        # reset module DATA_DIR
