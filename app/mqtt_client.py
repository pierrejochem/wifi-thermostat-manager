"""MQTT bridge with Home Assistant discovery.

Each thermostat is published as a Home Assistant ``climate`` entity using
MQTT discovery, so devices added in the dashboard show up automatically in
Home Assistant with full thermostat cards — current temperature, setpoint,
mode and heating/idle action — and can be driven from anywhere in HA, not just
this add-on.

Topic layout (``base`` defaults to ``wtm``)::

    <base>/<id>/availability          online | offline
    <base>/<id>/current               measured temperature
    <base>/<id>/target/state          current setpoint
    <base>/<id>/target/set            <- setpoint commands
    <base>/<id>/mode/state            off | heat | auto
    <base>/<id>/mode/set              <- mode commands
    <base>/<id>/action                off | idle | heating
"""
from __future__ import annotations

import json
import logging
from typing import Callable

import paho.mqtt.client as mqtt

log = logging.getLogger("wtm.mqtt")

CommandHandler = Callable[[str, str, str], None]  # (thermostat_id, command, payload)


class MqttBridge:
    def __init__(
        self,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        base_topic: str = "wtm",
        discovery_prefix: str = "homeassistant",
    ):
        self.host = host
        self.port = int(port)
        self.base = base_topic.strip("/")
        self.discovery_prefix = discovery_prefix.strip("/")
        self.connected = False
        self._command_handler: CommandHandler | None = None

        self._client = mqtt.Client(client_id="wifi-thermostat-manager")
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        # Bridge-level availability so HA marks everything offline if we die.
        self._client.will_set(f"{self.base}/bridge/availability", "offline", retain=True)

    # -- lifecycle --------------------------------------------------------
    def connect(self) -> None:
        if not self.host:
            log.warning("No MQTT host set; skipping MQTT (dashboard still works).")
            return
        log.info("Connecting to MQTT %s:%s", self.host, self.port)
        try:
            self._client.connect(self.host, self.port, keepalive=60)
            self._client.loop_start()
        except Exception as err:  # noqa: BLE001
            log.error("MQTT connection failed: %s", err)

    def stop(self) -> None:
        try:
            self._client.publish(f"{self.base}/bridge/availability", "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def set_command_handler(self, handler: CommandHandler) -> None:
        self._command_handler = handler

    def _on_connect(self, client, _userdata, _flags, rc):  # noqa: ANN001
        if rc != 0:
            log.error("MQTT connect refused (code %s)", rc)
            return
        self.connected = True
        log.info("MQTT connected")
        client.publish(f"{self.base}/bridge/availability", "online", retain=True)
        # Resubscribe to all command topics after a (re)connect.
        client.subscribe(f"{self.base}/+/+/set")

    def _on_message(self, _client, _userdata, msg):  # noqa: ANN001
        # Topic: <base>/<id>/<command>/set
        parts = msg.topic.split("/")
        if len(parts) != 4 or parts[0] != self.base or parts[3] != "set":
            return
        thermostat_id, command = parts[1], parts[2]
        payload = msg.payload.decode("utf-8", errors="replace")
        if self._command_handler:
            self._command_handler(thermostat_id, command, payload)

    # -- topics -----------------------------------------------------------
    def _t(self, thermostat_id: str, *suffix: str) -> str:
        return "/".join([self.base, thermostat_id, *suffix])

    # -- discovery & state ------------------------------------------------
    def publish_discovery(self, device) -> None:  # noqa: ANN001 (BaseThermostat)
        if not self.connected:
            return
        uid = f"wtm_{device.id}"
        config = {
            "name": device.name,
            "unique_id": uid,
            "object_id": uid,
            "modes": device.supported_modes,
            "min_temp": device.min_temp,
            "max_temp": device.max_temp,
            "temp_step": device.temp_step,
            "temperature_unit": "C",
            "availability_topic": self._t(device.id, "availability"),
            "current_temperature_topic": self._t(device.id, "current"),
            "temperature_state_topic": self._t(device.id, "target", "state"),
            "temperature_command_topic": self._t(device.id, "target", "set"),
            "mode_state_topic": self._t(device.id, "mode", "state"),
            "mode_command_topic": self._t(device.id, "mode", "set"),
            "action_topic": self._t(device.id, "action"),
            "device": {
                "identifiers": [uid],
                "name": device.name,
                "manufacturer": "WiFi Thermostat Manager",
                "model": device.driver_type,
            },
        }
        topic = f"{self.discovery_prefix}/climate/{uid}/config"
        self._client.publish(topic, json.dumps(config), retain=True)
        log.debug("Published discovery for %s", device.name)

    def remove_discovery(self, thermostat_id: str) -> None:
        uid = f"wtm_{thermostat_id}"
        topic = f"{self.discovery_prefix}/climate/{uid}/config"
        # Empty retained payload tells HA to forget the entity.
        self._client.publish(topic, "", retain=True)

    def publish_state(self, device) -> None:  # noqa: ANN001
        if not self.connected:
            return
        s = device.state
        pub = self._client.publish
        pub(self._t(device.id, "availability"), "online" if s.available else "offline", retain=True)
        if s.current_temperature is not None:
            pub(self._t(device.id, "current"), s.current_temperature, retain=True)
        if s.target_temperature is not None:
            pub(self._t(device.id, "target", "state"), s.target_temperature, retain=True)
        pub(self._t(device.id, "mode", "state"), s.hvac_mode, retain=True)
        pub(self._t(device.id, "action"), s.hvac_action, retain=True)
