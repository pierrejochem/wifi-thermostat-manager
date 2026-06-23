"""Generic REST driver for WiFi thermostats with a local HTTP/JSON API.

Use this for devices that aren't Tuya-based but expose a small HTTP API on the
LAN (custom firmware, ESPHome web server, DIY controllers, etc.). It is fully
configurable: you provide the URL that returns state as JSON, the JSON keys to
read, and URL templates for the commands.

Example definition::

    {
      "type": "rest",
      "name": "Garage",
      "status_url": "http://192.168.1.50/api/state",
      "current_path": "temperature",
      "target_path": "setpoint",
      "mode_path": "mode",
      "set_temp_url": "http://192.168.1.50/api/setpoint?value={value}",
      "set_mode_url": "http://192.168.1.50/api/mode?value={mode}"
    }

``{value}`` and ``{mode}`` are substituted at call time. Dotted paths such as
``state.temp`` are supported for nested JSON.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from .base import MODE_HEAT, MODE_OFF, BaseThermostat

log = logging.getLogger("wtm.driver.rest")


def _dig(data: Any, path: str) -> Any:
    """Resolve a dotted path like ``state.temperature`` inside a dict."""
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class RestThermostat(BaseThermostat):
    driver_type = "rest"

    def __init__(self, definition: dict[str, Any]):
        super().__init__(definition)
        self.status_url: str = definition["status_url"]
        self.current_path: str = definition.get("current_path", "current_temperature")
        self.target_path: str = definition.get("target_path", "target_temperature")
        self.mode_path: str = definition.get("mode_path", "mode")
        self.set_temp_url: str = definition.get("set_temp_url", "")
        self.set_mode_url: str = definition.get("set_mode_url", "")
        self.timeout: float = float(definition.get("timeout", 5))

    def refresh(self) -> None:
        try:
            resp = requests.get(self.status_url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as err:  # noqa: BLE001
            log.debug("[%s] status failed: %s", self.name, err)
            self.state.available = False
            return

        self.state.available = True
        self.state.current_temperature = _to_float(_dig(data, self.current_path))
        self.state.target_temperature = _to_float(_dig(data, self.target_path))

        raw_mode = str(_dig(data, self.mode_path) or "").lower()
        self.state.hvac_mode = MODE_HEAT if raw_mode in ("heat", "on", "1", "true") else MODE_OFF

        cur, tgt = self.state.current_temperature, self.state.target_temperature
        if self.state.hvac_mode == MODE_OFF:
            self.state.hvac_action = "off"
        elif cur is not None and tgt is not None and cur < tgt:
            self.state.hvac_action = "heating"
        else:
            self.state.hvac_action = "idle"

    def set_target_temperature(self, temperature: float) -> None:
        temperature = self.clamp(temperature)
        if not self.set_temp_url:
            log.warning("[%s] no set_temp_url configured", self.name)
            return
        url = self.set_temp_url.format(value=temperature)
        self._command(url)
        self.state.target_temperature = temperature

    def set_hvac_mode(self, mode: str) -> None:
        if not self.set_mode_url:
            log.warning("[%s] no set_mode_url configured", self.name)
            return
        self._command(self.set_mode_url.format(mode=mode))
        self.state.hvac_mode = mode

    def _command(self, url: str) -> None:
        try:
            requests.get(url, timeout=self.timeout).raise_for_status()
        except Exception as err:  # noqa: BLE001
            log.error("[%s] command failed (%s): %s", self.name, url, err)


def _to_float(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None
