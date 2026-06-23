#!/usr/bin/with-contenv bashio
# ---------------------------------------------------------------------------
# WiFi Thermostat Manager - container entrypoint
# Resolves MQTT connection details (auto-detected broker or manual config)
# and exports the runtime configuration for the Python app.
# ---------------------------------------------------------------------------
set -e

bashio::log.info "Starting WiFi Thermostat Manager..."

# --- Logging --------------------------------------------------------------
export LOG_LEVEL="$(bashio::config 'log_level')"

# --- MQTT: prefer manual config, otherwise ask the Supervisor -------------
MQTT_HOST="$(bashio::config 'mqtt_host')"
MQTT_PORT="$(bashio::config 'mqtt_port')"
MQTT_USER="$(bashio::config 'mqtt_username')"
MQTT_PASS="$(bashio::config 'mqtt_password')"

if bashio::var.is_empty "${MQTT_HOST}"; then
    if bashio::services.available "mqtt"; then
        bashio::log.info "Using MQTT broker auto-discovered from the Supervisor."
        MQTT_HOST="$(bashio::services 'mqtt' 'host')"
        MQTT_PORT="$(bashio::services 'mqtt' 'port')"
        MQTT_USER="$(bashio::services 'mqtt' 'username')"
        MQTT_PASS="$(bashio::services 'mqtt' 'password')"
    else
        bashio::log.warning "No MQTT host configured and no broker offered by the Supervisor."
        bashio::log.warning "Install the Mosquitto add-on or set mqtt_host in the options."
    fi
else
    bashio::log.info "Using MQTT broker from add-on options: ${MQTT_HOST}:${MQTT_PORT}"
fi

export MQTT_HOST MQTT_PORT MQTT_USER MQTT_PASS
export DISCOVERY_PREFIX="$(bashio::config 'discovery_prefix')"
export BASE_TOPIC="$(bashio::config 'base_topic')"
export POLL_INTERVAL="$(bashio::config 'poll_interval')"
export INGRESS_PORT="8099"
export DATA_DIR="/data"

cd /app
exec python3 main.py
