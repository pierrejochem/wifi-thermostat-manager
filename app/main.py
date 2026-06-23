"""WiFi Thermostat Manager — application entrypoint.

Starts the MQTT bridge and polling manager, then serves the dashboard and a
small JSON API through Home Assistant Ingress.
"""
from __future__ import annotations

import logging
import os
import signal

from flask import Flask, jsonify, render_template, request

from manager import ThermostatManager
from mqtt_client import MqttBridge
from thermostats import factory

# --- logging ---------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("wtm")

# --- field metadata so the dashboard can render add/edit forms -------------
TYPE_SCHEMAS = {
    "tuya": {
        "label": "Tuya (local) — Moes / Beca / Avatto / BHT-style",
        "fields": [
            {"key": "name", "label": "Name", "type": "text", "required": True},
            {"key": "device_id", "label": "Device ID", "type": "text", "required": True},
            {"key": "local_key", "label": "Local key", "type": "text", "required": True},
            {"key": "address", "label": "IP address", "type": "text", "placeholder": "192.168.1.x"},
            {"key": "version", "label": "Protocol version", "type": "select",
             "options": ["3.1", "3.2", "3.3", "3.4", "3.5"], "default": "3.3"},
            {"key": "temp_divisor", "label": "Temp scale divisor", "type": "number", "default": 2},
        ],
    },
    "rest": {
        "label": "Generic REST / HTTP (custom or DIY firmware)",
        "fields": [
            {"key": "name", "label": "Name", "type": "text", "required": True},
            {"key": "status_url", "label": "Status URL (returns JSON)", "type": "text", "required": True},
            {"key": "current_path", "label": "JSON key: current temp", "type": "text", "default": "current_temperature"},
            {"key": "target_path", "label": "JSON key: target temp", "type": "text", "default": "target_temperature"},
            {"key": "mode_path", "label": "JSON key: mode", "type": "text", "default": "mode"},
            {"key": "set_temp_url", "label": "Set-temperature URL ({value})", "type": "text"},
            {"key": "set_mode_url", "label": "Set-mode URL ({mode})", "type": "text"},
        ],
    },
}

# Fields shared by all types.
COMMON_FIELDS = [
    {"key": "min_temp", "label": "Min temp", "type": "number", "default": 5},
    {"key": "max_temp", "label": "Max temp", "type": "number", "default": 35},
    {"key": "temp_step", "label": "Step", "type": "number", "default": 0.5},
]

# --- bootstrap -------------------------------------------------------------
mqtt_bridge = MqttBridge(
    host=os.environ.get("MQTT_HOST", ""),
    port=os.environ.get("MQTT_PORT", 1883) or 1883,
    username=os.environ.get("MQTT_USER", ""),
    password=os.environ.get("MQTT_PASS", ""),
    base_topic=os.environ.get("BASE_TOPIC", "wtm"),
    discovery_prefix=os.environ.get("DISCOVERY_PREFIX", "homeassistant"),
)
mqtt_bridge.connect()

manager = ThermostatManager(
    mqtt_bridge, poll_interval=int(os.environ.get("POLL_INTERVAL", 30))
)
manager.load_from_store()
manager.start()

app = Flask(__name__, template_folder="templates", static_folder="static")


# --- pages -----------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")


# --- API -------------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify(status="ok", mqtt_connected=mqtt_bridge.connected)


@app.get("/api/types")
def types():
    return jsonify(schemas=TYPE_SCHEMAS, common_fields=COMMON_FIELDS,
                   supported=factory.supported_types())


@app.get("/api/thermostats")
def list_thermostats():
    return jsonify(thermostats=manager.list_devices(),
                   mqtt_connected=mqtt_bridge.connected)


@app.get("/api/thermostats/<thermostat_id>/config")
def get_thermostat_config(thermostat_id: str):
    import config_store
    definition = config_store.get(thermostat_id)
    if definition is None:
        return jsonify(error="not found"), 404
    return jsonify(config=definition)


@app.post("/api/thermostats")
def add_thermostat():
    definition = request.get_json(force=True, silent=True) or {}
    if not definition.get("name") or not definition.get("type"):
        return jsonify(error="name and type are required"), 400
    try:
        created = manager.add_device(definition)
    except (KeyError, ValueError) as err:
        return jsonify(error=str(err)), 400
    return jsonify(thermostat=created), 201


@app.put("/api/thermostats/<thermostat_id>")
def update_thermostat(thermostat_id: str):
    changes = request.get_json(force=True, silent=True) or {}
    updated = manager.update_device(thermostat_id, changes)
    if updated is None:
        return jsonify(error="not found"), 404
    return jsonify(thermostat=updated)


@app.delete("/api/thermostats/<thermostat_id>")
def delete_thermostat(thermostat_id: str):
    if not manager.delete_device(thermostat_id):
        return jsonify(error="not found"), 404
    return jsonify(deleted=thermostat_id)


@app.post("/api/thermostats/<thermostat_id>/temperature")
def set_temperature(thermostat_id: str):
    body = request.get_json(force=True, silent=True) or {}
    try:
        temperature = float(body["temperature"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="temperature (number) is required"), 400
    if not manager.command_set_temperature(thermostat_id, temperature):
        return jsonify(error="not found"), 404
    return jsonify(ok=True)


@app.post("/api/thermostats/<thermostat_id>/mode")
def set_mode(thermostat_id: str):
    body = request.get_json(force=True, silent=True) or {}
    mode = str(body.get("mode", ""))
    if not manager.command_set_mode(thermostat_id, mode):
        return jsonify(error="invalid mode or thermostat not found"), 400
    return jsonify(ok=True)


@app.post("/api/thermostats/<thermostat_id>/refresh")
def refresh_thermostat(thermostat_id: str):
    device = manager.get_device(thermostat_id)
    if not device:
        return jsonify(error="not found"), 404
    device.refresh()
    mqtt_bridge.publish_state(device)
    return jsonify(thermostat=device.as_dict())


# --- shutdown --------------------------------------------------------------
def _shutdown(*_):
    log.info("Shutting down...")
    manager.stop()
    mqtt_bridge.stop()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


if __name__ == "__main__":
    port = int(os.environ.get("INGRESS_PORT", 8099))
    log.info("Dashboard listening on :%d", port)
    # threaded=True so polling/commands don't block the UI.
    app.run(host="0.0.0.0", port=port, threaded=True)
