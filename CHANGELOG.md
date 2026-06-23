# Changelog

## 1.0.1
- Fix add-on failing to start (`/bin/sh: can't open '/init': Permission denied`).
  AppArmor profile now grants read access to the s6-overlay init scripts and the
  bashio/with-contenv startup chain.

## 1.0.0
- Initial release.
- Manage multiple WiFi smart thermostats from one dashboard.
- Tuya (local) and generic REST drivers.
- Home Assistant MQTT climate discovery with two-way control.
- Auto-detection of the Supervisor Mosquitto broker.
