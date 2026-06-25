import os, tempfile
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.pop("MQTT_HOST", None)

import main


def test_root_serves_spa_index(tmp_path, monkeypatch):
    # Point Flask's static (dist) dir at a temp dir containing an index.html.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    monkeypatch.setitem(main.app.config, "DIST_DIR", str(dist))
    client = main.app.test_client()
    res = client.get("/")
    assert res.status_code == 200
    assert b"id=root" in res.data


def test_api_types_still_json():
    client = main.app.test_client()
    res = client.get("/api/types")
    assert res.status_code == 200
    assert "schemas" in res.get_json()
