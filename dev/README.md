# Local dev environment

Run the add-on's Flask app on a plain workstation, without the Home Assistant
Supervisor. A Docker Mosquitto container stands in for the Supervisor-managed
MQTT broker; env vars stand in for what `run.sh` / bashio would export.

## Start

```bash
# 1. start the local MQTT broker
docker compose -f dev/docker-compose.yml up -d

# 2. create venv, install deps, run the app
./dev/run-dev.sh
```

Or do both in one go:

```bash
START_BROKER=1 ./dev/run-dev.sh
```

Dashboard: http://127.0.0.1:8099  ·  API health: http://127.0.0.1:8099/api/health

## What it sets up

- `docker-compose.yml` + `mosquitto.conf` — anonymous broker on `1883` (ws `9001`).
- `run-dev.sh` — venv at `dev/.venv`, installs `requirements.txt`, exports the
  same env the container entrypoint sets, persists state to `dev/data/`.
- `dev/data/` — local `/data` replacement (`thermostats.json` lives here).

## Override defaults

Any env var can be overridden inline:

```bash
INGRESS_PORT=8100 LOG_LEVEL=info ./dev/run-dev.sh
```

## Smoke test

```bash
curl -s localhost:8099/api/health
curl -s -XPOST localhost:8099/api/thermostats -H 'Content-Type: application/json' \
  -d '{"name":"Living Room","type":"tuya","device_id":"abc","local_key":"xyz"}'
# watch HA discovery + state on the broker:
docker exec wtm-dev-mqtt mosquitto_sub -h localhost -t '#' -v
```

A `tuya` device shows `available:false` until it can reach a real device on the
LAN — expected. The `rest` type can point at any local mock HTTP server.

## Stop / reset

```bash
docker compose -f dev/docker-compose.yml down   # stop broker
rm -f dev/data/thermostats.json                 # wipe saved thermostats
rm -rf dev/.venv                                 # rebuild deps from scratch
```
