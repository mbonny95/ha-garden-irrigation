# Graph Report - garden-irrigation  (2026-07-15)

## Corpus Check
- 59 files · ~51,584 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1224 nodes · 2895 edges · 72 communities (51 shown, 21 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 196 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8db1094a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Diagnostics & Test Fixtures
- Button Platform (Cycle & Calibration)
- Water Balance Engine
- Binary Sensor Platform
- FAO-56 ET0 Engine
- Zone Sensors (Deficit & Rain)
- Coordinator: Operational State
- Scheduler Tests
- Select Platform (Mode & Cycle Zone)
- Config Flow
- Project Governance & Milestones
- Scheduler: Advisory Monitors
- ET0 Sensor & Tests
- Recommendation Engine Tests
- Telegram Notifier & Tests
- Recommendation: Block Plan & WH51
- Irrigation Event Log
- Repair Issues
- Notifier Abstraction
- Weather: Rain & Time-Weighted Accumulators
- Weather: Snapshot Persistence
- Weather Aggregator Core
- Irrigation Log: Aggregates
- Recommendation Engine Core
- Rain Accumulator Tests
- Weather Backfill & Midnight Tests
- Integration Manifest
- Constants & Coordinator Init
- Base Entity & Device Info
- Integration Setup/Unload
- Weather: Live State-Change Handling
- Recommendation: WH51 Reading
- Data Quality Sensor
- Telegram Send Logic
- Scheduler Setup
- Test Fixtures Bootstrap
- Package Root
- Agronomy: water balance, TAW/RAW, effective rain, weekly cap
- GardenIrrigationStore
- test_init.py
- Irrigation7dZoneSensor
- CLAUDE.md — garden_irrigation
- _IrrigationRecord
- Pre-commit Configuration
- [0.1.0] - 2026-07-13
- test_init.py
- README.md
- Milestone 10: Dashboard & Docs
- Milestone 1: Scaffold & CI Toolchain
- Milestone 7: Recommendation Engine
- Milestone 8: Notifier & Repairs
- Milestone 9: Modes & Calibration Override
- CLAUDE.md Project Instructions
- GardenIrrigationCoordinator (single source of truth)
- Abstract Notifier Adapter Pattern
- Reset-aware Rain Accumulator
- Dashboards README
- Agronomy Documentation
- Water Deficit Balance Formula
- WH51 14-day Automatic Calibration Window
- FAO-56 Penman-Monteith ET0
- FAO-56 ET0 Documentation
- Allen, Pereira, Raes, Smith (1998) — FAO Irrigation and Drainage Paper 56
- Docs Index README
- Bug Report Template
- _FinalizedField
- async_get_config_entry_diagnostics
- ._et0_result
- .__init__

## God Nodes (most connected - your core abstractions)
1. `GardenIrrigationCoordinator` - 118 edges
2. `ZoneBalanceResult` - 46 edges
3. `setup_mock_weather_states()` - 44 edges
4. `GardenIrrigationStore` - 42 edges
5. `_coordinator()` - 38 edges
6. `WeatherAggregator` - 32 edges
7. `user_step_input()` - 32 edges
8. `BalanceEngine` - 31 edges
9. `compute_et0()` - 30 edges
10. `_coordinator()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Validate Workflow (hassfest/HACS)` --semantically_similar_to--> `Pre-commit Configuration`  [INFERRED] [semantically similar]
  .github/workflows/validate.yaml → .pre-commit-config.yaml
- `test_zone_agronomy_params_taw_raw()` --calls--> `ZoneAgronomyParams`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/balance.py
- `test_test_telegram_has_no_side_effects_on_irrigation_domain()` --indirect_call--> `GardenIrrigationCoordinator`  [INFERRED]
  tests/test_init.py → custom_components/garden_irrigation/coordinator.py
- `test_zone_sensor_unique_ids_and_translation_keys()` --indirect_call--> `EtcZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py
- `test_zone_sensor_units_and_state_classes()` --indirect_call--> `EtcZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py

## Import Cycles
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/__init__.py`
- 4-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`

## Hyperedges (group relationships)
- **CI / Quality Gate Toolchain** — github_workflows_lint_lint_workflow, github_workflows_test_test_workflow, github_workflows_validate_validate_workflow, pre_commit_config_pre_commit_config, requirements_test_requirements_test [INFERRED 0.85]
- **Cross-linked Project Documentation Set** — readme_readme, docs_readme_docs_readme, docs_agronomy_agronomy_doc, docs_calibration_calibration_doc, docs_fao56_fao56_doc, claude_claude_md [EXTRACTED 1.00]
- **Milestone 9 Feature Set (modes, calibration override, declared cycle)** — claude_modes_calibration_monitoring, claude_declared_manual_cycle, docs_calibration_wh51_manual_override, changelog_milestone_9_modes_calibration [EXTRACTED 1.00]

## Communities (72 total, 21 thin omitted)

### Community 0 - "Diagnostics & Test Fixtures"
Cohesion: 0.16
Nodes (24): Constants for the garden_irrigation integration.  Config-flow keys and defaults,, Diagnostics support for garden_irrigation., Any, rain_step_input(), Shared mock entity ids and step-input builders for garden_irrigation tests., Valid input for config-flow step (b): rain., Valid input for config-flow step (c): WH51 per zone., Valid input for config-flow step (d): zone names/areas/distribution. (+16 more)

### Community 1 - "Button Platform (Cycle & Calibration)"
Cohesion: 0.06
Nodes (53): ButtonEntity, async_setup_entry(), _CalibrationOverrideButton, EndCycleButton, FinishCalibrationButton, AddEntitiesCallback, Any, ConfigEntry (+45 more)

### Community 2 - "Water Balance Engine"
Cohesion: 0.15
Nodes (13): BalanceEngine, _local_day_bounds(), date, datetime, Local [00:00:00.000000, 23:59:59.999999] bounds for a calendar day., Owns the per-zone water balance for one config entry.      Not an entity: plain, Force an immediate (non-debounced) persistence flush., Return the currently stored deficit for `zone_id`, unmodified. (+5 more)

### Community 3 - "Binary Sensor Platform"
Cohesion: 0.07
Nodes (53): BinarySensorEntity, async_setup_entry(), IrrigationInProgressSensor, NeedsIrrigationZoneSensor, AddEntitiesCallback, Any, ConfigEntry, HomeAssistant (+45 more)

### Community 4 - "FAO-56 ET0 Engine"
Cohesion: 0.09
Nodes (40): compute_et0(), _extraterrestrial_radiation_mj(), _incomplete_result(), _net_longwave_radiation_mj(), _pressure_from_altitude_kpa(), _psychrometric_constant(), date, FAO-56 Penman-Monteith daily reference evapotranspiration (ET0) engine.  Milesto (+32 more)

### Community 5 - "Zone Sensors (Deficit & Rain)"
Cohesion: 0.10
Nodes (31): Outcome of one `process_daily_balance` call for a single zone/day., ZoneBalanceResult, ET0Result, Daily ET0 plus every intermediate FAO-56 term, for diagnosis and tests.      Whe, IrrigationAggregate, A derived (never persisted) sum over a subset of the event log., async_setup_entry(), DeficitZoneSensor (+23 more)

### Community 6 - "Coordinator: Operational State"
Cohesion: 0.08
Nodes (23): GardenIrrigationCoordinator, Any, Start the weather listeners, restore the balance, register the         record_ir, Set the operational mode (calibration/monitoring) - UX/status only,         neve, Set which zone `async_start_cycle` will target next., Declare a manual cycle active for `selected_cycle_zone`, now.          Purely de, Clear the declared-active-cycle state., Stop the weather aggregator's listeners and force a final flush.          Extend (+15 more)

### Community 7 - "Scheduler Tests"
Cohesion: 0.12
Nodes (51): SimpleNamespace, HomeAssistant, Register mock states for every entity a full config flow run needs., setup_mock_weather_states(), _coordinator(), _issue(), Any, HomeAssistant (+43 more)

### Community 8 - "Select Platform (Mode & Cycle Zone)"
Cohesion: 0.09
Nodes (34): ActiveCycleZoneSelect, async_setup_entry(), ModeSelect, AddEntitiesCallback, ConfigEntry, HomeAssistant, Select platform for garden_irrigation.  Milestone 9 scope only:   - `select.mode, Set up the garden_irrigation select platform. (+26 more)

### Community 9 - "Config Flow"
Cohesion: 0.08
Nodes (30): ConfigFlow, _entity_selector(), GardenIrrigationConfigFlow, GardenIrrigationOptionsFlow, Any, ConfigEntry, Config flow for garden_irrigation.  Five ordered steps, per the approved plan:, Validate a set of entity_id fields; return an errors dict for the form. (+22 more)

### Community 10 - "Project Governance & Milestones"
Cohesion: 0.20
Nodes (10): Declared Manual Cycle In Progress, Rationale: Estimates vs Measurements Labeling, Modes: calibration / monitoring (select.mode), Golden Rule: v1 Never Actuates Hardware, record_irrigation Action, services.yaml (record_irrigation schema), Garden Irrigation Lovelace Dashboard, Weekly Irrigation Cap (30mm default) (+2 more)

### Community 11 - "Scheduler: Advisory Monitors"
Cohesion: 0.06
Nodes (49): async_reload_entry(), async_setup_entry(), async_unload_entry(), ConfigEntry, HomeAssistant, The garden_irrigation integration.  Milestone 2: entry setup/unload/reload wirin, Set up garden_irrigation from a config entry., Unload a config entry and its platforms. (+41 more)

### Community 12 - "ET0 Sensor & Tests"
Cohesion: 0.14
Nodes (28): Et0DailySensor, Daily FAO-56 reference evapotranspiration for the current in-progress day., _full_entry_data(), Any, HomeAssistant, Tests for the garden_irrigation sensor platform (Milestones 1 and 5)., Every sensor described by the plan's data-backed subset exists after setup., unique_id/translation_key/translation_placeholders are stable and per-zone. (+20 more)

### Community 13 - "Recommendation Engine Tests"
Cohesion: 0.16
Nodes (38): _balance_result(), _coordinator(), Any, date, HomeAssistant, Tests for the garden_irrigation recommendation engine (Milestone 7)., (A) `0 < cap_remaining_mm < deficit_mm`: the recommendation is capped     to wha, (B) Exact boundary: `cap_remaining_mm == deficit_mm` covers the whole     defici (+30 more)

### Community 14 - "Telegram Notifier & Tests"
Cohesion: 0.06
Nodes (60): ABC, Notifier, PersistentNotificationNotifier, Any, ConfigEntry, Notifier abstraction for garden_irrigation.  Milestone 8 scope only: an abstract, Abstract notifier: send a message, degrading cleanly on any failure., Send `message`. Must never raise - failures degrade internally. (+52 more)

### Community 15 - "Recommendation: Block Plan & WH51"
Cohesion: 0.16
Nodes (27): _engine(), Any, HomeAssistant, Tests for the garden_irrigation per-zone water balance engine (Milestone 4)., Heavy rain: eff_rain capped at (prev_deficit + ETc), never "banked" beyond it., Irrigation larger than the day's remaining need clamps deficit at 0., A single very dry day cannot push the deficit past TAW., Regression: the production coordinator always applies `day = yesterday`     (coo (+19 more)

### Community 16 - "Irrigation Event Log"
Cohesion: 0.08
Nodes (23): _area_m2(), IrrigationEvent, IrrigationLog, _mm_per_minute(), Any, ConfigEntry, datetime, HomeAssistant (+15 more)

### Community 17 - "Repair Issues"
Cohesion: 0.08
Nodes (28): attr(), clamp(), classifyZoneStatus(), escapeHtml(), fireMoreInfo(), formatLiters(), formatMm(), getState() (+20 more)

### Community 18 - "Notifier Abstraction"
Cohesion: 0.18
Nodes (8): Per-zone water balance engine for garden_irrigation.  Milestone 4 scope only: ET, ConfigEntry, HomeAssistant, Coordinator for garden_irrigation.  Milestone 2 added the WeatherAggregator (acc, Return the user-configured display name for `zone_id`.      Re-implemented here, Initialize the coordinator for a single config entry., _zone_name(), Persistence wrapper for garden_irrigation.  Wraps `helpers.storage.Store`. Domai

### Community 19 - "Weather: Rain & Time-Weighted Accumulators"
Cohesion: 0.19
Nodes (7): datetime, Close the previous interval up to `ts`, then open a new one at `value`., Time-weighted mean including the still-open interval up to `as_of`., Time integral in MJ/m² including the still-open interval up to `as_of`., Close the day at `midnight`, then reset, carrying the last known         value f, Process one raw reading, updating daily_mm per the reset rules above., Non-destructive view of the current (in-progress) day, as of `as_of`.

### Community 20 - "Weather: Snapshot Persistence"
Cohesion: 0.14
Nodes (8): Any, Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Serialize for the daily_history Store buffer., Restore from a previously persisted dict (see to_dict)., Restore persisted/backfilled state and start listening for updates.

### Community 21 - "Weather Aggregator Core"
Cohesion: 0.17
Nodes (7): DailyWeatherSnapshot, date, Return today's total and reset it; the raw baseline is NOT reset         (the ph, A read-only view of one calendar day's aggregates (finalized or live-so-far)., Stop listening and force an immediate (non-debounced) persistence flush., Finalize the closed day into history, reset accumulators, force-flush., Return the finalized snapshot for `target_date`, if it's in the buffer.

### Community 22 - "Irrigation Log: Aggregates"
Cohesion: 0.18
Nodes (10): Auto-discovery limitations (`getStubConfig`), Data-quality / Repairs banner, Example configuration, File structure, Garden Irrigation — Lovelace custom cards, Installation, Known gaps against the backend (do not silently work around — flagged instead), What this is (and isn't) (+2 more)

### Community 23 - "Recommendation Engine Core"
Cohesion: 0.20
Nodes (7): ConfigEntry, HomeAssistant, Build the engine with per-zone deficit/ledger starting empty., Per-zone agronomy parameters (options-flow configurable in a later milestone)., Total Available Water [mm]., Readily Available Water [mm]., ZoneAgronomyParams

### Community 24 - "Rain Accumulator Tests"
Cohesion: 0.18
Nodes (20): _RainAccumulator, Daily weather aggregation for garden_irrigation.  Milestone 2 scope only: local,, Running min/max and a time-weighted sum (sum of value * dt_seconds) for one fiel, Reset-aware daily rain accumulator.      Strictly increasing timestamps (out-of-, _TimeWeightedAccumulator, Tests for garden_irrigation weather aggregation (Milestone 2)., A sensor republishing the same value (heartbeat) must not add rain., test_rain_finalize_and_reset_keeps_raw_baseline() (+12 more)

### Community 25 - "Weather Backfill & Midnight Tests"
Cohesion: 0.28
Nodes (17): Owns the daily weather accumulators for one config entry.      Not an entity: th, WeatherAggregator, _full_entry_data(), Any, HomeAssistant, When there's no persisted state for today, a bounded recorder backfill     recon, No recorder loaded: setup must not raise, and simply starts empty., If today's state was already restored from Store, backfill must be     skipped e (+9 more)

### Community 26 - "Integration Manifest"
Cohesion: 0.13
Nodes (14): after_dependencies, codeowners, config_flow, documentation, domain, integration_type, iot_class, issue_tracker (+6 more)

### Community 27 - "Constants & Coordinator Init"
Cohesion: 0.15
Nodes (10): HomeAssistant, Build the engine with an empty WH51 calibration baseline., GardenIrrigationStore, Any, HomeAssistant, Thin async wrapper around a versioned, debounced Store file., Create a store bound to `key` (e.g. "garden_irrigation.state")., Load persisted data, or an empty dict if nothing was saved yet. (+2 more)

### Community 28 - "Base Entity & Device Info"
Cohesion: 0.20
Nodes (7): GardenIrrigationEntity, ConfigEntry, Shared base entity for garden_irrigation., Base entity: single shared device, entity-only names (has_entity_name)., Bind the entity to the coordinator and the owning config entry., Single logical device: this integration does not control hardware., DeviceInfo

### Community 29 - "Integration Setup/Unload"
Cohesion: 0.16
Nodes (20): Valid input for config-flow step (a): position + FAO-56 weather., user_step_input(), _advance_to_create_entry(), HomeAssistant, Tests for the garden_irrigation multi-step config flow., A non-sensor entity_id must be rejected with entity_wrong_domain., An incompatible unit_of_measurement must be rejected., Battery/signal/wind_gust are optional: omitting them is not an error. (+12 more)

### Community 30 - "Weather: Live State-Change Handling"
Cohesion: 0.22
Nodes (7): _parse_float(), Bounded, one-shot recorder backfill for today only (never a loop).          Only, Return the numeric value of a state, or None if unknown/unavailable/invalid., Event, EventStateChangedData, State, test_parse_float_rejects_unknown_unavailable_and_invalid()

### Community 31 - "Recommendation: WH51 Reading"
Cohesion: 0.10
Nodes (27): _area_m2(), _block_plan(), BlockPlanEntry, _classify_wh51(), _current_taw_raw_mm(), _mm_per_minute(), ConfigEntry, datetime (+19 more)

### Community 32 - "Data Quality Sensor"
Cohesion: 0.29
Nodes (5): DataQualitySensor, Always available in Milestone 1 (never unavailable)., Return `not_configured` pre-refresh, `initializing` afterwards., Diagnostic sensor reporting overall data-quality status.      Milestone 1: alway, SensorEntity

### Community 33 - "Telegram Send Logic"
Cohesion: 0.08
Nodes (24): Declared cycle in progress (optional), Development, Disclaimer, Documentation, ⚠️ Estimates vs. measurements, ET0 / ETc, garden-irrigation, HACS (+16 more)

### Community 34 - "Scheduler Setup"
Cohesion: 0.17
Nodes (29): _coordinator(), _full_entry_data(), Any, HomeAssistant, Tests for the garden_irrigation manual irrigation-cycle log (Milestone 6)., An uncalibrated-tank cycle sends exactly one notification naming the     zone/so, Sanity check that the two branches (calibrated/uncalibrated) actually     produc, An uncalibrated event still counts toward `count`, but contributes     nothing t (+21 more)

### Community 35 - "Test Fixtures Bootstrap"
Cohesion: 0.50
Nodes (3): auto_enable_custom_integrations(), Shared pytest fixtures for garden_irrigation tests., Make custom_components discoverable by Home Assistant in every test.

### Community 39 - "Agronomy: water balance, TAW/RAW, effective rain, weekly cap"
Cohesion: 0.10
Nodes (17): Agronomy: water balance, TAW/RAW, effective rain, weekly cap, Deficit, Effective rain, Recorded irrigation and the weekly cap, TAW / RAW, Uncalibrated sources, The automatic 14-day window (Milestone 7), The explicit override (Milestone 9) (+9 more)

### Community 40 - "GardenIrrigationStore"
Cohesion: 0.38
Nodes (3): GardenIrrigationOverviewCardEditor, LABELS, SCHEMA

### Community 41 - "test_init.py"
Cohesion: 0.38
Nodes (3): GardenIrrigationZoneCardEditor, LABELS, SCHEMA

### Community 42 - "Irrigation7dZoneSensor"
Cohesion: 0.27
Nodes (6): Irrigation7dZoneSensor, User-recorded irrigation over the trailing sliding 7x24h window.      Reads irri, Per-source aggregate over the trailing 7x24h window, as of now., The configured weekly cap, from the last balance result if known.          Falls, Recorded irrigation in mm over the trailing 7 days, all sources summed., Per-source breakdown plus the weekly cap context.

### Community 43 - "CLAUDE.md — garden_irrigation"
Cohesion: 0.22
Nodes (8): Architecture invariants, CLAUDE.md — garden_irrigation, Config, Conventions, Golden rules (never violate), graphify, Water/agronomy model (do not "simplify" away), Workflow guardrails

### Community 44 - "_IrrigationRecord"
Cohesion: 0.24
Nodes (6): _IrrigationRecord, Any, One user-recorded irrigation entry (mm already converted from minutes).      Mil, Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Restore persisted deficit/last-balance-date/irrigation ledger.

### Community 45 - "Pre-commit Configuration"
Cohesion: 0.40
Nodes (5): Lint Workflow (CI), Test Workflow (CI), Validate Workflow (hassfest/HACS), Pre-commit Configuration, README

### Community 46 - "[0.1.0] - 2026-07-13"
Cohesion: 0.50
Nodes (3): [0.1.0] - 2026-07-13, Added, Changelog

### Community 47 - "test_init.py"
Cohesion: 0.22
Nodes (15): _full_entry_data(), HomeAssistant, Tests for garden_irrigation entry setup/unload/reload., A provided `message` is forwarded verbatim instead of the default., The service never records irrigation, never touches the balance     ledger, and, The entry loads cleanly and creates/removes its coordinator on unload., Reloading the entry (e.g. after an options change) succeeds cleanly., The service exists once the entry is loaded, and is torn down on unload. (+7 more)

### Community 68 - "_FinalizedField"
Cohesion: 0.33
Nodes (4): _FinalizedField, Time-weighted mean over the closed interval., Time integral in MJ/m² (for solar irradiance in W/m²)., A closed-out time-weighted field, ready to become a daily history entry.

### Community 69 - "async_get_config_entry_diagnostics"
Cohesion: 0.40
Nodes (5): async_get_config_entry_diagnostics(), Any, ConfigEntry, HomeAssistant, Return diagnostics for a config entry, with Telegram target redacted.

### Community 71 - ".__init__"
Cohesion: 0.40
Nodes (3): ConfigEntry, HomeAssistant, Build the entity map from the config entry; accumulators start empty.

## Knowledge Gaps
- **103 isolated node(s):** `domain`, `name`, `recorder`, `@mbonny95`, `config_flow` (+98 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GardenIrrigationCoordinator` connect `Coordinator: Operational State` to `Diagnostics & Test Fixtures`, `Button Platform (Cycle & Calibration)`, `Water Balance Engine`, `Binary Sensor Platform`, `Zone Sensors (Deficit & Rain)`, `Scheduler Tests`, `Select Platform (Mode & Cycle Zone)`, `Scheduler: Advisory Monitors`, `ET0 Sensor & Tests`, `Recommendation Engine Tests`, `Telegram Notifier & Tests`, `Recommendation: Block Plan & WH51`, `Irrigation Event Log`, `Notifier Abstraction`, `Weather Backfill & Midnight Tests`, `Constants & Coordinator Init`, `Base Entity & Device Info`, `Recommendation: WH51 Reading`, `Data Quality Sensor`, `Scheduler Setup`, `Irrigation7dZoneSensor`, `test_init.py`?**
  _High betweenness centrality (0.273) - this node is a cross-community bridge._
- **Why does `GardenIrrigationStore` connect `Constants & Coordinator Init` to `Button Platform (Cycle & Calibration)`, `Water Balance Engine`, `Binary Sensor Platform`, `_FinalizedField`, `Zone Sensors (Deficit & Rain)`, `Coordinator: Operational State`, `.__init__`, `_IrrigationRecord`, `Irrigation Event Log`, `Notifier Abstraction`, `Weather Aggregator Core`, `Recommendation Engine Core`, `Rain Accumulator Tests`, `Weather Backfill & Midnight Tests`, `Recommendation: WH51 Reading`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `compute_et0()` connect `FAO-56 ET0 Engine` to `Notifier Abstraction`, `Weather Aggregator Core`, `Zone Sensors (Deficit & Rain)`, `Coordinator: Operational State`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `GardenIrrigationCoordinator` (e.g. with `IrrigationInProgressSensor` and `NeedsIrrigationZoneSensor`) actually correct?**
  _`GardenIrrigationCoordinator` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ZoneBalanceResult` (e.g. with `GardenIrrigationStore` and `IrrigationInProgressSensor`) actually correct?**
  _`ZoneBalanceResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `timedelta` (e.g. with `._prune_irrigation()` and `.weekly_irrigation_mm()`) actually correct?**
  _`timedelta` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `GardenIrrigationStore` (e.g. with `BalanceEngine` and `_IrrigationRecord`) actually correct?**
  _`GardenIrrigationStore` has 24 INFERRED edges - model-reasoned connections that need verification._