"""Shared Tuya cloud session.

Owns one ``tuya_sharing.Manager`` per Home Assistant Tuya config entry, built
from the credentials HA already stored (read via ``ha_import``). Used by the
``tuya_cloud`` driver to read device status and send commands through the Tuya
cloud — the same path Home Assistant's Tuya integration uses — for devices that
are not reachable over the local network.

Token handling: we ride HA's token read-only. We never refresh or persist it.
On an auth failure we rebuild the Manager from ``.storage`` once (HA keeps the
token fresh there) and retry; if it still fails the session is marked
unavailable.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import ha_import

log = logging.getLogger("wtm.cloud")


class CloudSession:
    def __init__(self, config_entries_path: str | None = None,
                 min_refresh_interval: float = 20.0, clock=time.time):
        self._path = config_entries_path or ha_import.CONFIG_ENTRIES_PATH
        self._min_interval = min_refresh_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._managers: list[Any] = []
        self._owner: dict[str, Any] = {}
        self._built = False
        self._last_refresh = 0.0

    # -- internal ---------------------------------------------------------
    def _build(self) -> None:
        self._managers = []
        self._owner = {}
        self._built = True
        try:
            creds_list = ha_import.read_tuya_entries(self._path)
        except ha_import.HaImportError as err:
            log.warning("Tuya cloud unavailable: %s", err)
            return
        for creds in creds_list:
            try:
                self._managers.append(ha_import._build_manager(creds))
            except ha_import.HaImportError as err:
                log.warning("Tuya cloud manager build failed: %s", err)

    def _refresh_caches(self) -> bool:
        ok = False
        for mgr in self._managers:
            try:
                mgr.update_device_cache()
                ok = True
                for dev_id in mgr.device_map:
                    self._owner[dev_id] = mgr
            except Exception as err:  # noqa: BLE001 - auth/network
                log.debug("Tuya cloud cache refresh failed: %s", err)
        return ok

    def _ensure_fresh(self) -> None:
        now = self._clock()
        if self._built and (now - self._last_refresh) < self._min_interval:
            return
        if not self._built:
            self._build()
        self._last_refresh = now
        if not self._managers:
            return  # no Tuya entry / config problem — nothing to refresh, don't rebuild
        if self._refresh_caches():
            return
        # Auth/refresh failure with managers present: rebuild from .storage once.
        log.info("Tuya cloud refresh failed; rebuilding from the Home Assistant token")
        self._build()
        self._last_refresh = self._clock()
        if not (self._managers and self._refresh_caches()):
            log.warning("Tuya cloud token rejected — open or reload the Tuya "
                        "integration in Home Assistant, then try again.")

    # -- public -----------------------------------------------------------
    def status(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_fresh()
            mgr = self._owner.get(device_id)
            if mgr is None:
                return None
            device = mgr.device_map.get(device_id)
            if device is None:
                return None
            return dict(getattr(device, "status", None) or {})

    def send(self, device_id: str, commands: list[dict[str, Any]]) -> bool:
        with self._lock:
            self._ensure_fresh()
            mgr = self._owner.get(device_id)
        if mgr is None:
            log.warning("Tuya cloud: unknown device %s", device_id)
            return False
        try:
            mgr.send_commands(device_id, commands)
            return True
        except Exception as err:  # noqa: BLE001
            log.error("Tuya cloud command failed for %s: %s", device_id, err)
            return False
