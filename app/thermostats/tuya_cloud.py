"""Cloud-control driver for Tuya thermostats.

Reads state and sends commands through the Tuya cloud (via the shared
``CloudSession``), using the credentials Home Assistant's Tuya integration
already stored. Use this for devices that are not reachable over the local
network (e.g. cloud-only firmware, or where another client holds the single
local connection).

The cloud reports status keyed by Tuya *code* (``temp_set``, ``temp_current``,
``mode``, ``switch``), not by local DP number, so this driver maps by code.
"""
from __future__ import annotations

import logging
from typing import Any

from cloud_session import CloudSession

from .base import MODE_AUTO, MODE_HEAT, MODE_OFF, BaseThermostat

log = logging.getLogger("wtm.driver.tuya_cloud")

DEFAULT_CODES = {
    "current": "temp_current",
    "target": "temp_set",
    "mode": "mode",
    "switch": "switch",
}

# One cloud session shared by every cloud device in the process.
SESSION = CloudSession()


class TuyaCloudThermostat(BaseThermostat):
    driver_type = "tuya_cloud"

    def __init__(self, definition: dict[str, Any]):
        super().__init__(definition)
        self.device_id: str = definition["device_id"]
        self.temp_divisor: float = float(definition.get("temp_divisor", 2))
        self.codes: dict[str, str] = {**DEFAULT_CODES, **(definition.get("codes") or {})}

    def _scale_in(self, raw: Any) -> float | None:
        try:
            return round(float(raw) / self.temp_divisor, 2)
        except (TypeError, ValueError):
            return None

    def _scale_out(self, temperature: float) -> int:
        return int(round(temperature * self.temp_divisor))

    def refresh(self) -> None:
        status = SESSION.status(self.device_id)
        if status is None:
            self.state.available = False
            return
        self.state.available = True
        self.state.current_temperature = self._scale_in(status.get(self.codes["current"]))
        self.state.target_temperature = self._scale_in(status.get(self.codes["target"]))

        powered = bool(status.get(self.codes["switch"], True))
        raw_mode = str(status.get(self.codes["mode"], "")).lower()
        if not powered:
            self.state.hvac_mode = MODE_OFF
        elif raw_mode in ("auto", "program") and MODE_AUTO in self.supported_modes:
            self.state.hvac_mode = MODE_AUTO
        else:
            self.state.hvac_mode = MODE_HEAT
        self.state.hvac_action = self._derive_action(powered)

    def _derive_action(self, powered: bool) -> str:
        if not powered:
            return "off"
        cur, tgt = self.state.current_temperature, self.state.target_temperature
        if cur is not None and tgt is not None:
            return "heating" if cur < tgt else "idle"
        return "idle"

    def set_target_temperature(self, temperature: float) -> None:
        temperature = self.clamp(temperature)
        if SESSION.send(self.device_id,
                        [{"code": self.codes["target"], "value": self._scale_out(temperature)}]):
            self.state.target_temperature = temperature

    def set_hvac_mode(self, mode: str) -> None:
        if mode == MODE_OFF:
            if SESSION.send(self.device_id, [{"code": self.codes["switch"], "value": False}]):
                self.state.hvac_mode = MODE_OFF
            return
        if SESSION.send(self.device_id, [{"code": self.codes["switch"], "value": True}]):
            self.state.hvac_mode = mode
