"""Local-control driver for Tuya-based WiFi thermostats.

Most inexpensive WiFi smart thermostats (Moes, Beca, Avatto, the BHT-002 /
BAC-002 families, and many white-label clones) speak the Tuya local protocol.
They are controlled here directly over the LAN with ``tinytuya`` — no cloud
round-trip — using the device id, local key and IP address.

Tuya devices expose their features as numbered "data points" (DPs). The exact
numbers and scaling differ between models, so every DP and the temperature
scale are configurable per thermostat, with defaults that match the common
BHT-style floor thermostats.
"""
from __future__ import annotations

import logging
from typing import Any

from .base import MODE_AUTO, MODE_HEAT, MODE_OFF, BaseThermostat

log = logging.getLogger("wtm.driver.tuya")

try:
    import tinytuya
except ImportError:  # pragma: no cover - lib always present in the container
    tinytuya = None


# Sensible defaults for BHT-002 / common Moes-Beca thermostats.
DEFAULT_DPS = {
    "power": "1",      # bool: device on/off
    "target": "2",     # target temperature (scaled)
    "current": "3",    # measured temperature (scaled)
    "mode": "4",       # "manual" / "auto" (scheduled)
    "heating": None,   # optional bool/state DP that is true while the relay is closed
}


class TuyaThermostat(BaseThermostat):
    driver_type = "tuya"

    def __init__(self, definition: dict[str, Any]):
        super().__init__(definition)
        self.device_id: str = definition["device_id"]
        self.local_key: str = definition["local_key"]
        self.address: str = definition.get("address", "Auto")
        self.version: float = float(definition.get("version", 3.3))
        # Many BHT models report 21.0 °C as the integer 42, hence divisor 2.
        self.temp_divisor: float = float(definition.get("temp_divisor", 2))
        self.dps: dict[str, Any] = {**DEFAULT_DPS, **definition.get("dps", {})}

        self._device = None

    # -- connection -------------------------------------------------------
    def _connect(self):
        if tinytuya is None:
            raise RuntimeError("tinytuya is not installed")
        if self._device is None:
            dev = tinytuya.Device(
                self.device_id, self.address, self.local_key, version=self.version
            )
            dev.set_socketPersistent(True)
            dev.set_socketTimeout(5)
            self._device = dev
        return self._device

    def _scale_in(self, raw: Any) -> float | None:
        try:
            return round(float(raw) / self.temp_divisor, 2)
        except (TypeError, ValueError):
            return None

    def _scale_out(self, temperature: float) -> int:
        return int(round(temperature * self.temp_divisor))

    # -- protocol hooks ---------------------------------------------------
    def refresh(self) -> None:
        try:
            data = self._connect().status()
        except Exception as err:  # noqa: BLE001 - never let a poll crash the loop
            log.debug("[%s] status failed: %s", self.name, err)
            self.state.available = False
            self._device = None  # force reconnect next time
            return

        dps = (data or {}).get("dps")
        if not dps:
            self.state.available = False
            return

        self.state.available = True
        self.state.current_temperature = self._scale_in(dps.get(self.dps["current"]))
        self.state.target_temperature = self._scale_in(dps.get(self.dps["target"]))

        powered = bool(dps.get(self.dps["power"], True))
        raw_mode = dps.get(self.dps["mode"])
        if not powered:
            self.state.hvac_mode = MODE_OFF
        elif str(raw_mode).lower() in ("auto", "1", "program"):
            self.state.hvac_mode = MODE_AUTO if MODE_AUTO in self.supported_modes else MODE_HEAT
        else:
            self.state.hvac_mode = MODE_HEAT

        self.state.hvac_action = self._derive_action(dps, powered)

    def _derive_action(self, dps: dict[str, Any], powered: bool) -> str:
        if not powered:
            return "off"
        heating_dp = self.dps.get("heating")
        if heating_dp is not None and heating_dp in dps:
            return "heating" if bool(dps[heating_dp]) else "idle"
        # Fall back to comparing measured vs target temperature.
        cur, tgt = self.state.current_temperature, self.state.target_temperature
        if cur is not None and tgt is not None:
            return "heating" if cur < tgt else "idle"
        return "idle"

    def set_target_temperature(self, temperature: float) -> None:
        temperature = self.clamp(temperature)
        self._connect().set_value(self.dps["target"], self._scale_out(temperature))
        self.state.target_temperature = temperature

    def set_hvac_mode(self, mode: str) -> None:
        dev = self._connect()
        if mode == MODE_OFF:
            dev.set_value(self.dps["power"], False)
            self.state.hvac_mode = MODE_OFF
            return
        # Any "on" mode powers the device first.
        dev.set_value(self.dps["power"], True)
        if self.dps.get("mode"):
            dev.set_value(self.dps["mode"], "auto" if mode == MODE_AUTO else "manual")
        self.state.hvac_mode = mode
