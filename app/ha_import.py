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


def read_tuya_entries(path: str = CONFIG_ENTRIES_PATH) -> list[dict[str, Any]]:
    """Return the ``data`` block of *every* Tuya config entry.

    Home Assistant can have more than one Tuya integration entry (e.g. two
    linked Tuya/Smart Life accounts). Each has its own devices, so we must
    query them all — reading only the first misses devices under the others.

    Raises ``TuyaEntryNotFound`` if there is no tuya entry at all, or
    ``HaImportError`` if the store is unreadable or no entry has usable creds.
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
    tuya = [e.get("data") or {} for e in entries if e.get("domain") == "tuya"]
    if not tuya:
        raise TuyaEntryNotFound(
            "No Tuya integration found in Home Assistant. Set up the official "
            "Tuya integration first, then try importing again."
        )
    usable = [d for d in tuya if all(d.get(k) for k in _REQUIRED_CREDS)]
    if not usable:
        raise HaImportError(
            "Found Tuya integration entr(ies) but none had the expected "
            "credentials (user_code, terminal_id, endpoint, token_info)."
        )
    return usable


def read_tuya_entry(path: str = CONFIG_ENTRIES_PATH) -> dict[str, Any]:
    """Return the first usable Tuya config entry (used by the status check)."""
    return read_tuya_entries(path)[0]


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

    Aggregates across *all* Tuya config entries (HA may have several linked
    accounts). Returns ``{devices, seen_categories, total, homes, entries}``;
    ``seen_categories`` is a histogram of every category found, so the caller
    can explain an empty result instead of failing silently.

    Does a single device-list fetch per entry and never refreshes/persists the
    token. If one entry's token fails it is skipped; only if *every* entry fails
    is ``TuyaTokenError`` raised.
    """
    already = set(already_added_ids or ())
    categories = _categories()
    creds_list = read_tuya_entries(path)
    # When debugging, let the SDK log raw API responses (e.g. the /homes call).
    if log.isEnabledFor(logging.DEBUG):
        logging.getLogger("tuya_sharing").setLevel(logging.DEBUG)
    log.info("HA Tuya: %d Tuya config entr(y/ies) to query", len(creds_list))

    by_id: dict[str, dict[str, Any]] = {}
    seen: dict[str, int] = {}
    homes = 0
    failures: list[str] = []

    for index, creds in enumerate(creds_list, start=1):
        token = creds.get("token_info") or {}
        log.info(
            "HA Tuya import: entry %d/%d endpoint=%s terminal=%s token expires=%s",
            index, len(creds_list), creds.get("endpoint"),
            creds.get("terminal_id"), token.get("expire_time"),
        )
        manager = _build_manager(creds)
        try:
            manager.update_device_cache()
        except TuyaSdkMissing:
            raise
        except Exception as err:  # noqa: BLE001 - SDK raises a wide range of errors
            # Skip this account (likely an expired token); keep the others.
            log.warning("HA Tuya entry %s failed: %s", creds.get("terminal_id"), err)
            failures.append(str(err))
            continue

        homes += len(getattr(manager, "user_homes", []) or [])
        for device in manager.device_map.values():
            category = getattr(device, "category", None)
            seen[category] = seen.get(category, 0) + 1
            if category in categories:
                row = _normalize(device, already)
                by_id[row["device_id"]] = row  # dedupe across accounts

    # Every account failed and none yielded data -> surface a token error.
    if failures and len(failures) == len(creds_list):
        raise TuyaTokenError(
            "Home Assistant's Tuya token(s) were rejected. Open (or reload) the "
            "Tuya integration in Home Assistant so it refreshes the token, then "
            f"try again. ({failures[0]})"
        )

    devices = list(by_id.values())
    total = sum(seen.values())
    log.info(
        "HA Tuya discovery: %d entr(ies), %d home(s), %d device(s) total, "
        "%d thermostat(s); categories=%s",
        len(creds_list), homes, total, len(devices), seen,
    )
    return {
        "devices": devices, "seen_categories": seen, "total": total,
        "homes": homes, "entries": len(creds_list),
    }


def fetch_thermostats(
    path: str = CONFIG_ENTRIES_PATH,
    *,
    already_added_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """List the user's Tuya thermostats (thin wrapper over ``discover``)."""
    return discover(path, already_added_ids=already_added_ids)["devices"]


# Map Tuya data-point status codes to the roles the local driver needs.
# Tuya models reuse these standard codes, so matching by code (not DP number)
# works across most thermostats. Fahrenheit twins are accepted as a fallback.
_CURRENT_CODES = ("temp_current", "temp_current_f")
_TARGET_CODES = ("temp_set", "temp_set_f")
_MODE_CODES = ("mode",)
_POWER_CODES = ("switch", "Power", "power", "poweron")
_HEATING_CODES = ("valve_state", "work_state", "heat_state", "heating", "valve")


def _parse_value_desc(raw: Any) -> dict[str, Any]:
    """The status_range ``value`` is a JSON string (or already a dict)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _value_spec(entry: Any) -> dict[str, Any]:
    """Extract the value spec dict from a status_range entry.

    The tuya_sharing ``DeviceStatusRange`` is an object whose JSON spec lives in
    the ``values`` attribute; tests/other shapes may use a dict with ``values``
    or ``value``. Normalize all of them to a parsed dict.
    """
    if entry is None:
        return {}
    raw = getattr(entry, "values", None)
    if raw is None and isinstance(entry, dict):
        raw = entry.get("values") or entry.get("value")
    return _parse_value_desc(raw)


def _derive_tuya_config(device: Any) -> dict[str, Any]:
    """Derive DP map, temperature scale and limits from the cloud metadata.

    Uses the device's ``local_strategy`` (DP number -> status code) and
    ``status_range`` (per-code value spec). Returns only the keys we could
    determine, so anything missing falls back to the Tuya driver's defaults.
    """
    strategy = getattr(device, "local_strategy", None) or {}
    status_range = getattr(device, "status_range", None) or {}

    code_to_dp: dict[str, str] = {}
    for dp_id, info in strategy.items():
        # local_strategy entries are plain dicts, but stay robust to objects.
        if isinstance(info, dict):
            code = info.get("status_code")
        else:
            code = getattr(info, "status_code", None)
        if code and code not in code_to_dp:
            code_to_dp[code] = str(dp_id)

    def pick(codes):
        for code in codes:
            if code in code_to_dp:
                return code_to_dp[code], code
        return None, None

    out: dict[str, Any] = {}
    dps: dict[str, Any] = {}
    cur_dp, _ = pick(_CURRENT_CODES)
    tgt_dp, tgt_code = pick(_TARGET_CODES)
    mode_dp, _ = pick(_MODE_CODES)
    power_dp, _ = pick(_POWER_CODES)
    heat_dp, _ = pick(_HEATING_CODES)
    for role, dp in (("current", cur_dp), ("target", tgt_dp), ("mode", mode_dp),
                     ("power", power_dp), ("heating", heat_dp)):
        if dp is not None:
            dps[role] = dp
    if dps:
        out["dps"] = dps

    # Cloud status is keyed by code, not DP number — resolve the role codes too.
    present = set(code_to_dp)
    if isinstance(status_range, dict):
        present |= set(status_range)
    codes: dict[str, str] = {}
    for role, candidates in (("current", _CURRENT_CODES), ("target", _TARGET_CODES),
                             ("mode", _MODE_CODES), ("switch", _POWER_CODES)):
        match = next((c for c in candidates if c in present), None)
        if match:
            codes[role] = match
    if codes:
        out["codes"] = codes

    # Temperature scale + limits come from the target setpoint's spec.
    desc = _value_spec(status_range.get(tgt_code)) if (tgt_code and hasattr(status_range, "get")) else {}
    scale = desc.get("scale")
    if scale is not None:
        try:
            divisor = 10 ** int(scale)
        except (TypeError, ValueError):
            divisor = 0
        if divisor > 0:
            out["temp_divisor"] = divisor
            for key, src in (("min_temp", "min"), ("max_temp", "max"), ("temp_step", "step")):
                if isinstance(desc.get(src), (int, float)):
                    out[key] = round(desc[src] / divisor, 2)
    return out


def _is_battery(device: Any) -> bool:
    """True if the device exposes a battery status code.

    Battery thermostats (radiator TRVs) sleep and are effectively cloud-only,
    so tinytuya local control can't reach them. A ``battery_*`` code is a far
    more reliable signal than ``category`` or ``support_local`` (both of which
    can claim local support on devices that never accept local connections).
    """
    codes: set[str] = set()
    for attr in ("status_range", "status", "function"):
        value = getattr(device, attr, None)
        if isinstance(value, dict):
            codes |= set(value.keys())
    return any("battery" in str(code).lower() for code in codes)


def _normalize(device: Any, already_ids: set[str]) -> dict[str, Any]:
    """Turn a tuya_sharing ``CustomerDevice`` into our import row."""
    device_id = device.id
    ip = getattr(device, "ip", None)
    row = {
        "device_id": device_id,
        "name": getattr(device, "name", None) or device_id,
        "local_key": getattr(device, "local_key", ""),
        # tinytuya scans the LAN when address is "Auto"; safer than a stale IP.
        "address": ip or "Auto",
        "category": getattr(device, "category", None),
        "online": bool(getattr(device, "online", False)),
        "already_added": device_id in already_ids,
        # Battery devices are cloud-only; not locally controllable here.
        "battery": _is_battery(device),
    }
    # DP map / scale / limits derived from the cloud metadata (when available).
    row.update(_derive_tuya_config(device))
    return row


# Extra keys the import may derive from cloud metadata, copied into the
# definition when present (otherwise the driver's defaults apply).
_DERIVED_KEYS = ("codes", "min_temp", "max_temp", "temp_step")


def to_definition(item: dict[str, Any]) -> dict[str, Any]:
    """Map a normalized import row to a Tuya **cloud** thermostat definition.

    Cloud control needs no local key / IP / protocol version / DP numbers — just
    the device id, the temperature scale, and the status codes (with sensible
    defaults applied by the driver).
    """
    definition: dict[str, Any] = {
        "type": "tuya_cloud",
        "name": item["name"],
        "device_id": item["device_id"],
        "temp_divisor": item.get("temp_divisor", 2),
    }
    for key in _DERIVED_KEYS:
        if key in item:
            definition[key] = item[key]
    return definition