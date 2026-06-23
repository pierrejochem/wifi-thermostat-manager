#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Local dev runner for WiFi Thermostat Manager.
#
# Replaces the Home Assistant Supervisor + bashio entrypoint (run.sh) so the
# Flask app can run on a plain workstation. Creates a venv, installs deps,
# points the app at the local Mosquitto broker (dev/docker-compose.yml) and a
# local ./dev/data directory, then runs app/main.py directly.
#
#   ./dev/run-dev.sh          # start the app (assumes broker already up)
#   START_BROKER=1 ./dev/run-dev.sh   # also bring up the docker broker first
# ---------------------------------------------------------------------------
set -euo pipefail

DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${DEV_DIR}")"
VENV_DIR="${DEV_DIR}/.venv"
DATA_DIR="${DEV_DIR}/data"

# --- optional: start the local MQTT broker --------------------------------
if [ "${START_BROKER:-0}" = "1" ]; then
    echo ">> Starting local MQTT broker (docker compose)..."
    docker compose -f "${DEV_DIR}/docker-compose.yml" up -d
fi

# --- venv + deps ----------------------------------------------------------
if [ ! -d "${VENV_DIR}" ]; then
    echo ">> Creating venv at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo ">> Installing requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r "${ROOT_DIR}/requirements.txt"

# --- runtime env (mirrors what run.sh exports inside the container) -------
mkdir -p "${DATA_DIR}"
export LOG_LEVEL="${LOG_LEVEL:-debug}"
export MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export MQTT_USER="${MQTT_USER:-}"
export MQTT_PASS="${MQTT_PASS:-}"
export DISCOVERY_PREFIX="${DISCOVERY_PREFIX:-homeassistant}"
export BASE_TOPIC="${BASE_TOPIC:-wtm}"
export POLL_INTERVAL="${POLL_INTERVAL:-30}"
export INGRESS_PORT="${INGRESS_PORT:-8099}"
export DATA_DIR

echo ">> Dashboard will be at http://127.0.0.1:${INGRESS_PORT}"
cd "${ROOT_DIR}/app"
exec python3 main.py
