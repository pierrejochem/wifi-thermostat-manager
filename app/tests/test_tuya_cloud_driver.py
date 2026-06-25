import thermostats.tuya_cloud as drv
from thermostats import factory


class FakeSession:
    def __init__(self, status=None):
        self._status = status
        self.sent = []
    def status(self, device_id):
        return self._status
    def send(self, device_id, commands):
        self.sent.append((device_id, commands))
        return True


def _device(monkeypatch, status, definition=None):
    monkeypatch.setattr(drv, "SESSION", FakeSession(status))
    definition = definition or {
        "id": "x", "device_id": "bf1", "type": "tuya_cloud",
        "temp_divisor": 10, "min_temp": 5, "max_temp": 35, "temp_step": 0.5,
    }
    return drv.TuyaCloudThermostat(definition)


def test_refresh_maps_status_with_scale(monkeypatch):
    d = _device(monkeypatch, {"temp_current": 253, "temp_set": 220,
                              "switch": True, "mode": "manual"})
    d.refresh()
    assert d.state.available is True
    assert d.state.current_temperature == 25.3
    assert d.state.target_temperature == 22.0
    assert d.state.hvac_mode == "heat"
    assert d.state.hvac_action == "idle"   # 25.3 >= 22.0


def test_refresh_heating_when_below_target(monkeypatch):
    d = _device(monkeypatch, {"temp_current": 180, "temp_set": 220, "switch": True})
    d.refresh()
    assert d.state.hvac_action == "heating"


def test_refresh_off_when_switch_false(monkeypatch):
    d = _device(monkeypatch, {"temp_current": 200, "temp_set": 220, "switch": False})
    d.refresh()
    assert d.state.hvac_mode == "off"
    assert d.state.hvac_action == "off"


def test_refresh_unavailable_when_no_status(monkeypatch):
    d = _device(monkeypatch, None)
    d.refresh()
    assert d.state.available is False


def test_set_target_sends_scaled_command(monkeypatch):
    d = _device(monkeypatch, {})
    d.set_target_temperature(21.5)
    assert drv.SESSION.sent == [("bf1", [{"code": "temp_set", "value": 215}])]
    assert d.state.target_temperature == 21.5


def test_set_mode_off_and_heat(monkeypatch):
    d = _device(monkeypatch, {})
    d.set_hvac_mode("off")
    d.set_hvac_mode("heat")
    assert drv.SESSION.sent[0] == ("bf1", [{"code": "switch", "value": False}])
    assert drv.SESSION.sent[1] == ("bf1", [{"code": "switch", "value": True}])


def test_factory_creates_cloud_driver():
    obj = factory.create({"id": "x", "device_id": "bf1", "type": "tuya_cloud"})
    assert isinstance(obj, drv.TuyaCloudThermostat)
    assert "tuya_cloud" in factory.supported_types()
