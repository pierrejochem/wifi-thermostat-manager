"""Import Tuya thermostats straight from Home Assistant.

If Home Assistant already runs the official **Tuya integration**, it has
authenticated against Tuya and stored everything we need to list the user's
devices — including each device's ``local_key`` and ``ip``. We reuse those
stored credentials so the user can add thermostats with zero manual input:
no Device ID or Local Key to hunt down.

The credentials live in Home Assistant's config-entry store
(``<config>/.storage/core.config_entries``). We read them, rebuild a
``tuya_sharing.Manager`` exactly like the integration does, and ask it for the
device list.

Token safety
------------
We reuse Home Assistant's ``terminal_id``/``token_info``. Triggering a token
*refresh* would rotate the refresh token and desync Home Assistant until it
reloads, so we do a single ``update_device_cache()`` and never refresh or write
anything back. The add-on mounts the HA config dir read-only, which is the hard
guard against an accidental write-back.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("wtm.ha_import")

HA_CONFIG_DIR = os.environ.get("HA_CONFIG_DIR", "/homeassistant")
CONFIG_ENTRIES_PATH = os.path.join(HA_CONFIG_DIR, ".storage", "core.config_entries")

# The client id the official Home Assistant Tuya integration registers with.
# Reusing it is what makes HA's stored token valid for our Manager.
TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"

# Tuya device categories Home Assistant's own Tuya integration treats as
# climate entities (see HA core tuya/climate.py). Matching this set means we
# show every thermostat-like device HA already recognizes, not just a subset:
#   wk = thermostat, wkf = radiator valve / wall-hung furnace, kt = AC,
#   qn = heater, rs = water heater, dbl = electric heater.
THERMOSTAT_CATEGORIES = {"dbl", "kt", "qn", "rs", "wk", "wkf"}


def _categories() -> set[str]:
    """Categories treated as thermostats, plus any from the env override.

    ``TUYA_THERMOSTAT_CATEGORIES`` (comma-separated) lets a user surface an
    unusual category without rebuilding, in case their device reports one we
    don't list above.
    """
    extra = os.environ.get("TUYA_THERMOSTAT_CATEGORIES", "")
    return THERMOSTAT_CATEGORIES | {c.strip() for c in extra.split(",") if c.strip()}

# Keys we expect inside the tuya config entry's ``data`` block.
_REQUIRED_CREDS = ("user_code", "terminal_id", "endpoint", "token_info")


class HaImportError(Exception):
    """Base class for any failure while importing from Home Assistant."""


class TuyaEntryNotFound(HaImportError):
    """No Tuya integration config entry was found in Home Assistant."""


class TuyaTokenError(HaImportError):
    """Home Assistant's stored Tuya token was rejected (expired/invalid)."""


class TuyaSdkMissing(HaImportError):
    """The ``tuya_sharing`` SDK is not installed in the container."""


def read_tuya_entry(path: str = CONFIG_ENTRIES_PATH) -> dict[str, Any]:
    """Return the ``data`` block of Home Assistant's Tuya config entry.

    Raises ``TuyaEntryNotFound`` if there is no tuya entry, or ``HaImportError``
    if the storage file is unreadable / malformed / missing expected keys.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            store = json.load(fh)
    except FileNotFoundError as err:
        raise TuyaEntryNotFound(
            "Home Assistant config store not found. Is the add-on allowed to "
            "read the Home Assistant configuration directory?"
        ) from err
    except (OSError, ValueError) as err:
        raise HaImportError(f"Could not read Home Assistant config store: {err}") from err

    entries = (store.get("data") or {}).get("entries") or []
    for entry in entries:
        if entry.get("domain") == "tuya":
            data = entry.get("data") or {}
            missing = [k for k in _REQUIRED_CREDS if not data.get(k)]
            if missing:
                raise HaImportError(
                    "Tuya integration entry is missing expected fields: "
                    + ", ".join(missing)
                )
            return data
    raise TuyaEntryNotFound(
        "No Tuya integration found in Home Assistant. Set up the official Tuya "
        "integration first, then try importing again."
    )


def _build_manager(creds: dict[str, Any]):
    """Rebuild a ``tuya_sharing.Manager`` from HA's stored credentials."""
    try:
        from tuya_sharing import Manager
    except ImportError as err:  # pragma: no cover - SDK present in container
        raise TuyaSdkMissing(
            "The tuya-device-sharing-sdk is not installed."
        ) from err
    return Manager(
        TUYA_CLIENT_ID,
        creds["user_code"],
        creds["terminal_id"],
        creds["endpoint"],
        creds["token_info"],
    )


def discover(
    path: str = CONFIG_ENTRIES_PATH,
    *,
    already_added_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Discover Tuya devices via Home Assistant's stored creds.

    Returns ``{devices, seen_categories, total}`` where ``devices`` are the
    thermostat-like ones (normalized) and ``seen_categories`` is a histogram of
    every category found. The histogram lets the caller explain an empty result
    ("found 12 devices, none are thermostats") instead of failing silently.

    Does a single device-list fetch and never refreshes/persists the token.
    """
    already = set(already_added_ids or ())
    categories = _categories()
    creds = read_tuya_entry(path)
    manager = _build_manager(creds)
    try:
        manager.update_device_cache()
    except TuyaSdkMissing:
        raise
    except Exception as err:  # noqa: BLE001 - SDK raises a wide range of errors
        # Most failures here are an expired/invalid token. Surface a clear,
        # actionable message rather than retrying (which could trigger a
        # refresh and desync Home Assistant).
        raise TuyaTokenError(
            "Home Assistant's Tuya token was rejected. Open (or reload) the "
            "Tuya integration in Home Assistant so it refreshes the token, "
            f"then try again. ({err})"
        ) from err

    devices: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for device in manager.device_map.values():
        category = getattr(device, "category", None)
        seen[category] = seen.get(category, 0) + 1
        if category in categories:
            devices.append(_normalize(device, already))

    total = sum(seen.values())
    log.info(
        "HA Tuya discovery: %d device(s) total, %d thermostat(s); categories=%s",
        total, len(devices), seen,
    )
    return {"devices": devices, "seen_categories": seen, "total": total}


def fetch_thermostats(
    path: str = CONFIG_ENTRIES_PATH,
    *,
    already_added_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """List the user's Tuya thermostats (thin wrapper over ``discover``)."""
    return discover(path, already_added_ids=already_added_ids)["devices"]


def _normalize(device: Any, already_ids: set[str]) -> dict[str, Any]:
    """Turn a tuya_sharing ``CustomerDevice`` into our import row."""
    device_id = device.id
    ip = getattr(device, "ip", None)
    return {
        "device_id": device_id,
        "name": getattr(device, "name", None) or device_id,
        "local_key": getattr(device, "local_key", ""),
        # tinytuya scans the LAN when address is "Auto"; safer than a stale IP.
        "address": ip or "Auto",
        "category": getattr(device, "category", None),
        "online": bool(getattr(device, "online", False)),
        "already_added": device_id in already_ids,
    }


def to_definition(item: dict[str, Any]) -> dict[str, Any]:
    """Map a normalized import row to a Tuya thermostat definition.

    ``CustomerDevice`` carries no protocol version or temperature scale, so we
    fall back to the Tuya driver's defaults (3.3 / divisor 2). The user can
    adjust both in the edit dialog if readings look wrong.
    """
    return {
        "type": "tuya",
        "name": item["name"],
        "device_id": item["device_id"],
        "local_key": item["local_key"],
        "address": item.get("address") or "Auto",
        "version": "3.3",
        "temp_divisor": 2,
    }