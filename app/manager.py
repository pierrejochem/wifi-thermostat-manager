"""Central manager: owns every thermostat driver, polls them on a schedule,
and routes commands coming from either the dashboard or Home Assistant (MQTT).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import config_store
from mqtt_client import MqttBridge
from thermostats import factory
from thermostats.base import VALID_MODES, BaseThermostat

log = logging.getLogger("wtm.manager")


class ThermostatManager:
    def __init__(self, mqtt_bridge: MqttBridge, poll_interval: int = 30):
        self.mqtt = mqtt_bridge
        self.poll_interval = max(5, int(poll_interval))
        self._devices: dict[str, BaseThermostat] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.mqtt.set_command_handler(self._on_mqtt_command)

    # -- startup ----------------------------------------------------------
    def load_from_store(self) -> None:
        for definition in config_store.list_all():
            self._instantiate(definition)
        log.info("Loaded %d thermostat(s) from storage", len(self._devices))

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="poll", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _instantiate(self, definition: dict[str, Any]) -> BaseThermostat:
        device = factory.create(definition)
        self._devices[device.id] = device
        self.mqtt.publish_discovery(device)
        return device

    # -- polling ----------------------------------------------------------
    def _loop(self) -> None:
        # Small initial delay so MQTT has time to connect before first publish.
        self._stop.wait(2)
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.poll_interval)

    def poll_once(self) -> None:
        for device in list(self._devices.values()):
            try:
                device.refresh()
                self.mqtt.publish_state(device)
            except Exception as err:  # noqa: BLE001
                log.error("Polling %s failed: %s", device.name, err)

    # -- CRUD (used by the dashboard API) ---------------------------------
    def list_devices(self) -> list[dict[str, Any]]:
        return [d.as_dict() for d in self._devices.values()]

    def get_device(self, thermostat_id: str) -> BaseThermostat | None:
        return self._devices.get(thermostat_id)

    def add_device(self, definition: dict[str, Any]) -> dict[str, Any]:
        saved = config_store.add(definition)
        with self._lock:
            device = self._instantiate(saved)
        # Poll immediately so the UI/HA show fresh values right away.
        threading.Thread(target=self._refresh_one, args=(device,), daemon=True).start()
        return device.as_dict()

    def update_device(self, thermostat_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        saved = config_store.update(thermostat_id, changes)
        if saved is None:
            return None
        with self._lock:
            old = self._devices.pop(thermostat_id, None)
            if old is not None:
                self.mqtt.remove_discovery(thermostat_id)
            device = self._instantiate(saved)
        threading.Thread(target=self._refresh_one, args=(device,), daemon=True).start()
        return device.as_dict()

    def delete_device(self, thermostat_id: str) -> bool:
        if not config_store.delete(thermostat_id):
            return False
        with self._lock:
            self._devices.pop(thermostat_id, None)
        self.mqtt.remove_discovery(thermostat_id)
        return True

    def _refresh_one(self, device: BaseThermostat) -> None:
        try:
            device.refresh()
            self.mqtt.publish_state(device)
        except Exception as err:  # noqa: BLE001
            log.debug("Immediate refresh of %s failed: %s", device.name, err)

    # -- commands ---------------------------------------------------------
    def command_set_temperature(self, thermostat_id: str, temperature: float) -> bool:
        device = self._devices.get(thermostat_id)
        if not device:
            return False
        device.set_target_temperature(float(temperature))
        self.mqtt.publish_state(device)
        return True

    def command_set_mode(self, thermostat_id: str, mode: str) -> bool:
        device = self._devices.get(thermostat_id)
        if not device or mode not in VALID_MODES:
            return False
        device.set_hvac_mode(mode)
        self.mqtt.publish_state(device)
        return True

    def _on_mqtt_command(self, thermostat_id: str, command: str, payload: str) -> None:
        """Handle a command that arrived from Home Assistant over MQTT."""
        log.debug("MQTT command %s/%s = %s", thermostat_id, command, payload)
        try:
            if command == "target":
                self.command_set_temperature(thermostat_id, float(payload))
            elif command == "mode":
                self.command_set_mode(thermostat_id, payload.strip())
        except Exception as err:  # noqa: BLE001
            log.error("MQTT command failed: %s", err)
