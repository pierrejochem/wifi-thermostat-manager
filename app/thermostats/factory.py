"""Build a concrete driver instance from a stored definition."""
from __future__ import annotations

from typing import Any

from .base import BaseThermostat
from .generic_rest import RestThermostat
from .tuya import TuyaThermostat
from .tuya_cloud import TuyaCloudThermostat

_REGISTRY = {
    "tuya": TuyaThermostat,
    "tuya_cloud": TuyaCloudThermostat,
    "rest": RestThermostat,
}


def supported_types() -> list[str]:
    return list(_REGISTRY)


def create(definition: dict[str, Any]) -> BaseThermostat:
    driver_type = definition.get("type", "tuya")
    cls = _REGISTRY.get(driver_type)
    if cls is None:
        raise ValueError(f"Unknown thermostat type: {driver_type!r}")
    return cls(definition)
