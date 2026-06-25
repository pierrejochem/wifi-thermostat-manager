"""Cloud-control driver for Tuya thermostats.

Reads state and sends commands through the Tuya cloud (via the shared
``CloudSession``), using the credentials Home Assistant's Tuya integration
already stored. Use this for devices that are not reachable over the local
network (e.g. cloud-only firmware, or where another client holds the single
local connection).

The cloud reports status keyed by Tuya *code* (``temp_set``, ``temp_current``,
``mode``, ...), not by local DP number, so this driver maps by code.

Two on/off conventions exist and are both handled:

* Mains thermostats (BHT/Beca) have a separate ``switch`` power code; ``mode``
  selects the schedule (``manual``/``auto``).
* Battery radiator valves (TRVs) have **no** ``switch``; the ``mode`` enum
  itself carries ``off``/``manual``/``auto``, and heating is shown by a
  ``work_state`` valve code (``open``/``closed``).
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
    "switch": "switch",      # power on/off, when the model has a separate switch
    "action": "work_state",  # valve/heating state, when present
}

# Recognized values of the ``mode`` enum.
_OFF_MODES = {"off"}
_AUTO_MODES = {"auto", "program", "smart", "auto_program"}
# Recognized values of the ``work_state`` (valve) code.
_HEATING_STATES = {"open", "opened", "opening", "heating", "heat", "heat_state"}
_IDLE_STATES = {"close", "closed", "closing", "idle"}

# Value written to the ``mode`` code to turn a switchless device on (heat).
_MODE_ON_VALUE = "manual"
_MODE_OFF_VALUE = "off"

# One cloud session shared by every cloud device in the process.
SESSION = CloudSession()


class TuyaCloudThermostat(BaseThermostat):
    driver_type = "tuya_cloud"

    def __init__(self, definition: dict[str, Any]):
        super().__init__(definition)
        self.device_id: str = definition["device_id"]
        self.temp_divisor: float = float(definition.get("temp_divisor", 2))
        self.codes: dict[str, str] = {**DEFAULT_CODES, **(definition.get("codes") or {})}
        # Learned on first refresh: does the device expose a separate switch?
        self._has_switch: bool | None = None
        self._catalog_logged = False

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
        # Full raw Tuya status (every code/value) — set log_level to debug to
        # inspect exactly what the device reports.
        log.debug("[%s] (%s) cloud status: %s", self.name, self.device_id, status)
        # Once per device, also dump the full supported-code catalog (closer to
        # what the Tuya developer platform shows than the live status subset).
        if not self._catalog_logged and log.isEnabledFor(logging.DEBUG):
            self._catalog_logged = True
            log.debug("[%s] supported codes: %s", self.name, SESSION.device_codes(self.device_id))
        self.state.current_temperature = self._scale_in(status.get(self.codes["current"]))
        self.state.target_temperature = self._scale_in(status.get(self.codes["target"]))

        raw_mode = str(status.get(self.codes["mode"], "")).lower()
        switch_raw = status.get(self.codes["switch"])
        if switch_raw is not None:
            self._has_switch = True
            off = not bool(switch_raw)
        else:
            # No switch code: the mode enum carries on/off (TRV-style).
            self._has_switch = False
            off = raw_mode in _OFF_MODES

        if off:
            self.state.hvac_mode = MODE_OFF
        elif raw_mode in _AUTO_MODES and MODE_AUTO in self.supported_modes:
            self.state.hvac_mode = MODE_AUTO
        else:
            self.state.hvac_mode = MODE_HEAT
        self.state.hvac_action = self._derive_action(off, status)

    def _derive_action(self, off: bool, status: dict[str, Any]) -> str:
        if off:
            return "off"
        work = str(status.get(self.codes["action"], "")).lower()
        if work in _HEATING_STATES:
            return "heating"
        if work in _IDLE_STATES:
            return "idle"
        # No valve/work_state code — fall back to comparing temperatures.
        cur, tgt = self.state.current_temperature, self.state.target_temperature
        if cur is not None and tgt is not None:
            return "heating" if cur < tgt else "idle"
        return "idle"

    def set_target_temperature(self, temperature: float) -> bool:
        temperature = self.clamp(temperature)
        ok = SESSION.send(self.device_id,
                          [{"code": self.codes["target"], "value": self._scale_out(temperature)}])
        if ok:
            self.state.target_temperature = temperature
        return ok

    def _power_command(self, on: bool) -> dict[str, Any]:
        """Build the on/off command for this device's on/off convention."""
        if self._has_switch:
            return {"code": self.codes["switch"], "value": on}
        return {"code": self.codes["mode"],
                "value": _MODE_ON_VALUE if on else _MODE_OFF_VALUE}

    def set_hvac_mode(self, mode: str) -> bool:
        on = mode != MODE_OFF
        ok = SESSION.send(self.device_id, [self._power_command(on)])
        if ok:
            self.state.hvac_mode = mode
        return ok
