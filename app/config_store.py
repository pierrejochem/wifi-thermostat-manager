"""Persistent storage for thermostat definitions.

Thermostats are stored as a JSON list in ``/data/thermostats.json`` so they
survive add-on restarts and updates.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from typing import Any

log = logging.getLogger("wtm.store")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
STORE_PATH = os.path.join(DATA_DIR, "thermostats.json")

_lock = threading.Lock()


def _read() -> list[dict[str, Any]]:
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError) as err:
        log.error("Could not read %s: %s", STORE_PATH, err)
        return []


def _write(items: list[dict[str, Any]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2)
    os.replace(tmp, STORE_PATH)  # atomic on POSIX


def list_all() -> list[dict[str, Any]]:
    with _lock:
        return _read()


def get(thermostat_id: str) -> dict[str, Any] | None:
    return next((t for t in list_all() if t["id"] == thermostat_id), None)


def add(definition: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        items = _read()
        definition["id"] = definition.get("id") or uuid.uuid4().hex[:12]
        items.append(definition)
        _write(items)
        log.info("Added thermostat %s (%s)", definition.get("name"), definition["id"])
        return definition


def update(thermostat_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        items = _read()
        for item in items:
            if item["id"] == thermostat_id:
                item.update(changes)
                item["id"] = thermostat_id  # never allow id to be overwritten
                _write(items)
                return item
    return None


def delete(thermostat_id: str) -> bool:
    with _lock:
        items = _read()
        new_items = [t for t in items if t["id"] != thermostat_id]
        if len(new_items) == len(items):
            return False
        _write(new_items)
        log.info("Deleted thermostat %s", thermostat_id)
        return True


_CLOUD_CODES = {
    "current": "temp_current", "target": "temp_set",
    "mode": "mode", "switch": "switch",
}
_LOCAL_ONLY_KEYS = ("local_key", "address", "version", "dps")


def migrate_tuya_to_cloud() -> int:
    """Convert stored local ``tuya`` devices to cloud-controlled ``tuya_cloud``.

    Local control is unreliable for many Tuya thermostats; cloud control works
    through Home Assistant's credentials. Existing devices are converted in
    place (type changed, default status codes applied, ``temp_divisor`` kept,
    local-only fields dropped). Returns the number migrated; idempotent.
    """
    with _lock:
        items = _read()
        migrated = 0
        for item in items:
            if item.get("type") != "tuya":
                continue
            item["type"] = "tuya_cloud"
            item.setdefault("temp_divisor", 2)
            item["codes"] = {**_CLOUD_CODES, **(item.get("codes") or {})}
            for key in _LOCAL_ONLY_KEYS:
                item.pop(key, None)
            migrated += 1
        if migrated:
            _write(items)
            log.info("Migrated %d Tuya device(s) to cloud control", migrated)
        return migrated
