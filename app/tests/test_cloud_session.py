import ha_import
import cloud_session


class FakeDevice:
    def __init__(self, device_id, status):
        self.id = device_id
        self.status = status
        self.online = True


class FakeManager:
    def __init__(self, devices, raise_on_update=None):
        self.device_map = {d.id: d for d in devices}
        self._raise = raise_on_update
        self.update_calls = 0
        self.sent = []

    def update_device_cache(self):
        self.update_calls += 1
        if self._raise:
            raise self._raise

    def send_commands(self, device_id, commands):
        self.sent.append((device_id, commands))


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def _session(monkeypatch, managers, entries=None):
    entries = entries or [{"terminal_id": f"t{i}"} for i in range(len(managers))]
    monkeypatch.setattr(ha_import, "read_tuya_entries", lambda path: entries)
    it = iter(managers)
    monkeypatch.setattr(ha_import, "_build_manager", lambda creds: next(it))
    clock = Clock()
    return cloud_session.CloudSession(config_entries_path="/x", min_refresh_interval=20.0, clock=clock), clock


def test_status_returns_device_status(monkeypatch):
    mgr = FakeManager([FakeDevice("d1", {"temp_set": 220})])
    sess, _ = _session(monkeypatch, [mgr])
    assert sess.status("d1") == {"temp_set": 220}
    assert sess.status("nope") is None


def test_device_codes_lists_full_catalog(monkeypatch):
    dev = FakeDevice("d1", {"temp_set": 220})
    dev.status_range = {"temp_set": object(), "work_state": object(), "mode": object()}
    dev.function = {"temp_set": object(), "mode": object()}
    sess, _ = _session(monkeypatch, [FakeManager([dev])])
    cat = sess.device_codes("d1")
    assert cat["status"] == ["temp_set"]
    assert cat["status_range"] == ["mode", "temp_set", "work_state"]
    assert cat["function"] == ["mode", "temp_set"]
    assert sess.device_codes("nope") is None


def test_status_throttles_cache_refresh(monkeypatch):
    mgr = FakeManager([FakeDevice("d1", {"x": 1})])
    sess, clock = _session(monkeypatch, [mgr])
    sess.status("d1")
    sess.status("d1")          # within interval -> no new refresh
    assert mgr.update_calls == 1
    clock.t += 25             # past the interval
    sess.status("d1")
    assert mgr.update_calls == 2


def test_send_routes_to_owning_manager(monkeypatch):
    m1 = FakeManager([FakeDevice("a", {})])
    m2 = FakeManager([FakeDevice("b", {})])
    sess, _ = _session(monkeypatch, [m1, m2])
    assert sess.send("b", [{"code": "temp_set", "value": 5}]) is True
    assert m2.sent == [("b", [{"code": "temp_set", "value": 5}])]
    assert m1.sent == []


def test_send_unknown_device_returns_false(monkeypatch):
    sess, _ = _session(monkeypatch, [FakeManager([FakeDevice("a", {})])])
    assert sess.send("ghost", [{"code": "x", "value": 1}]) is False


def test_auth_failure_rebuilds_once_then_unavailable(monkeypatch):
    builds = {"n": 0}
    monkeypatch.setattr(ha_import, "read_tuya_entries", lambda path: [{"terminal_id": "t"}])

    def build(creds):
        builds["n"] += 1
        return FakeManager([FakeDevice("d1", {"x": 1})], raise_on_update=RuntimeError("401"))

    monkeypatch.setattr(ha_import, "_build_manager", build)
    sess = cloud_session.CloudSession(config_entries_path="/x")
    assert sess.status("d1") is None      # cache never populated
    assert builds["n"] == 2               # initial build + one rebuild


def test_no_tuya_entry_unavailable(monkeypatch):
    def raise_nf(path):
        raise ha_import.TuyaEntryNotFound("none")
    monkeypatch.setattr(ha_import, "read_tuya_entries", raise_nf)
    sess = cloud_session.CloudSession(config_entries_path="/x")
    assert sess.status("d1") is None
