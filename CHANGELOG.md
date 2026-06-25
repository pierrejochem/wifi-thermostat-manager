# Changelog

## 1.4.1
- Surface failed commands instead of silently reverting: when the cloud rejects a
  setpoint or mode change, the dashboard now shows an error toast and the value
  snaps back, and the API returns a real error (502) instead of a false success.

## 1.4.0
- New dashboard design — "Heatmap of the home". Every room sits on a cold→hot
  thermal scale bar (current marker + target tick), tiles tint by state
  (ember when heating, cool when idle, dimmed when off), and the header shows
  the home at a glance (average temperature, rooms calling for heat). Bricolage
  Grotesque + Geist Mono typography; dark-first with a light variant.

## 1.3.3
- Fix cloud commands failing with "token is expired": when a command fails,
  rebuild from Home Assistant's current token and retry once (the status path
  already self-healed; commands now do too).

## 1.3.2
- Add full supported-code catalog to debug

## 1.3.1
- Cloud control: correctly handle battery TRVs that have no `switch` code — on/off
  is read from and written to the `mode` enum (off/manual/auto), and the heating
  indicator comes from the valve `work_state` instead of assuming a switch. Mains
  thermostats with a real `switch` keep working as before.
- With `log_level: debug`, log every device's full raw Tuya status (all codes and
  values) each poll, to make device-specific mapping easy to inspect.

## 1.3.0
- Control imported Tuya thermostats through the Tuya cloud (via Home Assistant's
  existing Tuya credentials) instead of local tinytuya, which is unreachable for
  many devices. Existing imported Tuya devices migrate to cloud control
  automatically on startup.

## 1.2.2
- Fix add-on image build failing on low-power hosts (e.g. Raspberry Pi): ship a
  pre-built frontend bundle (`app/static/dist`) and drop the in-image Node build
  stage, so the image build is just Python again. Rebuild the bundle with
  `cd frontend && npm run build` before committing UI changes.

## 1.2.1
- Import dialog: allow importing battery devices (TRVs) again — they are no
  longer excluded, just marked with a "battery" badge. Redesigned the device
  list as a table with a select-all checkbox and online/offline status column.

## 1.2.0
- Rebuild the dashboard as a Vite + React + TypeScript app (same look and
  behavior). Built in a multi-stage Docker image; the runtime image is
  unchanged in size (no Node).

## 1.1.8
- Keep only locally-controllable thermostats: battery devices (radiator TRVs)
  are detected by their `battery_*` status code and shown as non-importable
  ("battery · use HA Tuya"), and skipped server-side on import. They are
  cloud-only and can't be reached over the LAN — use HA's Tuya integration.

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
