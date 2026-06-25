import os, tempfile
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.pop("MQTT_HOST", None)

import main


def test_already_added_includes_cloud_and_local(monkeypatch):
    monkeypatch.setattr(main.config_store, "list_all", lambda: [
        {"type": "tuya_cloud", "device_id": "bf1"},
        {"type": "tuya", "device_id": "bf2"},
        {"type": "rest"},
    ])
    assert main._already_added_tuya_ids() == {"bf1", "bf2"}
