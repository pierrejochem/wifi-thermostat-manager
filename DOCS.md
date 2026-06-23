# WiFi Thermostat Manager — Documentation

## Configuration options

| Option | Default | Description |
|--------|---------|-------------|
| `mqtt_host` | _(empty)_ | Leave empty to auto-detect the Supervisor's Mosquitto broker. Set only for an external broker. |
| `mqtt_port` | `1883` | Broker port (manual brokers only). |
| `mqtt_username` / `mqtt_password` | _(empty)_ | Credentials for a manual external broker. |
| `discovery_prefix` | `homeassistant` | MQTT discovery prefix. |
| `base_topic` | `wtm` | Root topic for state/commands. |
| `poll_interval` | `30` | Seconds between device reads. |
| `log_level` | `info` | `debug`, `info`, `warning` or `error`. |

## MQTT topic layout

```
wtm/<id>/availability      online | offline
wtm/<id>/current           measured temperature
wtm/<id>/target/state      current setpoint
wtm/<id>/target/set     <- setpoint command  (from HA)
wtm/<id>/mode/state        off | heat | auto
wtm/<id>/mode/set       <- mode command      (from HA)
wtm/<id>/action            off | idle | heating
```

## Tuya data points (advanced)

If a Tuya thermostat reports wrong values, edit its stored definition and set a
`dps` object mapping logical functions to the device's DP numbers, plus the
temperature scaling:

```json
{
  "type": "tuya",
  "name": "Living room",
  "device_id": "xxxxxxxxxxxxxxxx",
  "local_key": "xxxxxxxxxxxxxxxx",
  "address": "192.168.1.40",
  "version": "3.3",
  "temp_divisor": 2,
  "dps": { "power": "1", "target": "2", "current": "3", "mode": "4", "heating": "12" }
}
```

Find your device's DP numbers with `tinytuya` (`python -m tinytuya scan`) or the
Tuya developer platform.
