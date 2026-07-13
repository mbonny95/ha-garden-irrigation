# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
