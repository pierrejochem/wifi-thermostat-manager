# Changelog

## 1.1.7
- Fix crash on import (`'DeviceStatusRange' object has no attribute 'get'`):
  read the value spec from the SDK object's `values` attribute instead of
  assuming a plain dict.
- Modernize the dashboard UI: Plus Jakarta Sans typography, glass top bar,
  softer depth and card hover, segmented mode control, visible focus rings.

## 1.1.6
- Auto-configure imported Tuya thermostats from the cloud metadata: derive the
  DP map (current/target/mode/power), temperature divisor and min/max/step from
  the device's local_strategy and status_range, instead of assuming defaults.
  Re-import a device (remove, then import) to pick up the mapping.

## 1.1.5
- Enable host networking so the add-on can reach thermostats on the LAN and
  use Tuya broadcast discovery (fixes "Device Unreachable / 905" with no values).

## 1.1.4
- Fix import finding no devices when Home Assistant has more than one Tuya
  account: query every Tuya config entry and aggregate devices across them,
  instead of only reading the first entry (which could be an empty account).

## 1.1.3
- Diagnostics for empty import lists: report the Tuya "home" count, log the
  endpoint/terminal/token-expiry, and pass through the tuya_sharing SDK's raw
  API responses when the add-on log level is set to debug. Helps pin down why
  the device list comes back empty.

## 1.1.2
- Fix add-on update being blocked: use the legacy `homeassistant_config:ro`
  map syntax for wider Supervisor compatibility (the object form was rejected
  by older Supervisor, greying out the Update button).

## 1.1.1
- Add additional thermostat categories

## 1.1.0
- Add modal for adding Tuya devices via integration
- Correct repository url
- Add screenshot to readme

## 1.0.2
- Removed the custom profile so the Supervisor's auto-generated default 
  (which permits s6's mount and init plumbing) is used instead.

## 1.0.1
- Fix add-on failing to start. The custom AppArmor profile blocked the
  s6-overlay v3 init system (`/bin/sh: can't open '/init': Permission denied`,
  then `s6-svscan: another instance is already running`).

## 1.0.0
- Initial release.
- Manage multiple WiFi smart thermostats from one dashboard.
- Tuya (local) and generic REST drivers.
- Home Assistant MQTT climate discovery with two-way control.
- Auto-detection of the Supervisor Mosquitto broker.
