"""Common base class and shared state model for thermostat drivers.

A driver wraps one physical device. The manager calls :meth:`refresh` on a
schedule to read state, and :meth:`set_target_temperature` / :meth:`set_hvac_mode`
when a command arrives (from the dashboard or from Home Assistant via MQTT).

Drivers only have to implement the protocol-specific bits; everything else
(state caching, clamping, serialisation) lives here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("wtm.driver")

# HVAC modes we expose to Home Assistant's climate platform.
MODE_OFF = "off"
MODE_HEAT = "heat"
MODE_AUTO = "auto"
VALID_MODES = (MODE_OFF, MODE_HEAT, MODE_AUTO)


@dataclass
class ThermostatState:
    """Snapshot of what we currently believe a device is doing."""

    available: bool = False
    current_temperature: float | None = None
    target_temperature: float | None = None
    hvac_mode: str = MODE_OFF
    # "heating" while actively calling for heat, else "idle"/"off"
    hvac_action: str = "off"

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "current_temperature": self.current_temperature,
            "target_temperature": self.target_temperature,
            "hvac_mode": self.hvac_mode,
            "hvac_action": self.hvac_action,
        }


class BaseThermostat:
    """Base class for all device drivers."""

    driver_type = "base"

    def __init__(self, definition: dict[str, Any]):
        self.id: str = definition["id"]
        self.name: str = definition.get("name", "Thermostat")
        self.definition = definition

        self.min_temp: float = float(definition.get("min_temp", 5))
        self.max_temp: float = float(definition.get("max_temp", 35))
        self.temp_step: float = float(definition.get("temp_step", 0.5))
        self.supported_modes: list[str] = definition.get(
            "supported_modes", [MODE_OFF, MODE_HEAT]
        )

        self.state = ThermostatState()

    # -- helpers ----------------------------------------------------------
    def clamp(self, temperature: float) -> float:
        return max(self.min_temp, min(self.max_temp, round(temperature, 2)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.driver_type,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "temp_step": self.temp_step,
            "supported_modes": self.supported_modes,
            "state": self.state.as_dict(),
        }

    # -- protocol hooks: override in subclasses ---------------------------
    def refresh(self) -> None:
        """Read the device and update ``self.state``. Must not raise."""
        raise NotImplementedError

    def set_target_temperature(self, temperature: float) -> None:
        raise NotImplementedError

    def set_hvac_mode(self, mode: str) -> None:
        raise NotImplementedError
