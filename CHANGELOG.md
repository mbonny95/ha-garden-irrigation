# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.1] - 2026-11-27

### Fixed
- Custom cards failing with "Custom element doesn't exist" after upgrading
  from v1: Home Assistant serves `/local` files with a 31-day browser cache,
  so the cards' internal imports (shared module and editors) could load the
  cached v1 files. Internal imports now carry the version (`?v=2.0.1`).

## [2.0.0] - 2026-11-26

Complete rewrite. v1 configuration and data are not migrated: remove the v1
integration before installing. Design: `docs/v2-spec.md`.

### Added
- Any number of zones, as config subentries (add/edit from the integration
  page); one device per zone.
- FAO-56 model as a pure Python package (`model/`): Penman-Monteith ET0
  validated against the manual's examples, optional Hargreaves fallback,
  monthly Kc profiles, FAO-56 soil table, optional p adjustment for ETc.
- Daily weather from the recorder's long-term hourly statistics, with unit
  conversion (°F, mph, inHg, in… supported) and catch-up of missed days.
- Application rate per water source (mains, rainwater tank) per zone;
  minutes per source and cycle-and-soak blocks sized by soil.
- Actions `record_irrigation` (minutes or mm) and `set_deficit`.
- Optional soil moisture sensor with user dry/wet thresholds and optional
  forecast rain from a `weather` entity, both as warnings only.
- Repairs for weather sources that did not cover a day.
- Rewritten custom cards (overview + zone with record form) and example
  dashboard.

### Changed
- Minimum interval, weekly cap and block size are warnings, not
  constraints; the weekly cap is off by default.
- A day without ET0 is applied with ETc = 0 (rain and irrigation only) and
  flagged incomplete.
- One storage file per installation (365-day history).
- Minimum Home Assistant version 2026.2; compatible with the single-entry
  device registry of Home Assistant 2026.10+ (tested on 2026.2 and 2026.10).

### Removed
- Local weather accumulators, calibration/monitoring modes, the 14-day
  WH51 calibration, the 20:00 preview, start/end cycle buttons and selects.

## [v1, unreleased changes]

### Removed
- The entire notification system: `TelegramNotifier`/`PersistentNotificationNotifier`
  (`notify.py`, removed), the Telegram config-flow step and its config keys,
  the morning report, the evening preview report, cycle-recorded
  confirmations, the `test_telegram` service, and the notify-only WH51
  battery/signal/wind/rain-during-cycle advisories. The integration no longer
  sends any message anywhere.
- The `telegram_not_configured`/`telegram_target_invalid`/`telegram_send_failed`
  Repair issues (nothing left to misconfigure).

### Changed
- The config flow is now four steps instead of five (no Telegram step).
- Diagnostics no longer redact a Telegram target (there is none left to redact).

Stale WH51/weather-data detection is unchanged and still surfaces as a
Repair issue (Settings → System → Repairs) - only the notification/report
layer on top of it was removed.

## [0.1.0] - 2026-07-13

Initial decision-support release: reads existing weather/soil-moisture
entities, computes a local FAO-56 water balance, recommends irrigation, logs
manually-executed cycles, and notifies over Telegram (with a
persistent-notification fallback). **Does not actuate any hardware.**

### Added
- Milestone 1: repository scaffold, CI toolchain, manifest, multi-step config
  flow (position/FAO data, rain, WH51 zones, zone distribution, optional
  Telegram), skeleton coordinator, diagnostic `data_quality` sensor.
- Milestone 2: daily weather aggregation — persistent, reset-aware
  accumulators fed by live state-change events, bounded one-shot recorder
  backfill on restart, midnight roll anchored to the local day.
- Milestone 3: the FAO-56 Penman–Monteith daily ET0 engine, with no automatic
  fallback when fundamental inputs are missing.
- Milestone 4: the per-zone water balance engine — ETc, effective rain, TAW/
  RAW, the once-per-day idempotent deficit update, the sliding 7-day
  recorded-irrigation figure.
- Milestone 5: the full `sensor` platform (ET0, and per-zone ETc/deficit/TAW/
  RAW/effective rain/7-day irrigation).
- Milestone 6: the `garden_irrigation.record_irrigation` action, the
  365-day-retention manual-cycle event log, idempotent double-submission
  guarding, uncalibrated-source handling.
- Milestone 7: the recommendation engine (final + 20:00 preview,
  explainable reasons/limits/warnings, WH51 device-relative soft signal,
  block-plan for multi-block cycles), the 20:00/05:30 scheduler triggers, and
  the `needs_irrigation`/`weekly_cap_reached` binary sensors.
- Milestone 8: the abstract notifier (Telegram, degrading to persistent
  notifications), the morning report, Repair issues (Telegram
  misconfiguration/failure, stale WH51/weather data), and periodic
  wind/battery/signal advisories.
- Milestone 9: `select.mode` (`calibration`/`monitoring` only — no
  `automation` mode), the explicit per-zone WH51 calibration
  start/finish-override buttons, the optional declared
  cycle-in-progress flow (`select.active_cycle_zone`, start/end cycle
  buttons, `binary_sensor.irrigation_in_progress`), and the rain-during-cycle
  advisory.
- Milestone 10: example Lovelace dashboard (core cards only), full README,
  `docs/agronomy.md`/`docs/calibration.md`/`docs/fao56.md`.
