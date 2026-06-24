# Changelog

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
