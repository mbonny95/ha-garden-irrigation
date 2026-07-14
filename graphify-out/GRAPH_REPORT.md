# Graph Report - garden-irrigation  (2026-07-14)

## Corpus Check
- 53 files · ~45,163 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1133 nodes · 2689 edges · 69 communities (49 shown, 20 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 192 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0e7b9ed8`
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
- const.py
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
- ET0Result

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
- `test_test_telegram_has_no_side_effects_on_irrigation_domain()` --indirect_call--> `GardenIrrigationCoordinator`  [INFERRED]
  tests/test_init.py → custom_components/garden_irrigation/coordinator.py
- `test_zone_sensor_units_and_state_classes()` --indirect_call--> `EtcZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py
- `test_zone_sensor_units_and_state_classes()` --indirect_call--> `DeficitZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py
- `test_zone_sensor_unique_ids_and_translation_keys()` --indirect_call--> `TawZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py

## Import Cycles
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/__init__.py`
- 4-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`

## Hyperedges (group relationships)
- **CI / Quality Gate Toolchain** — github_workflows_lint_lint_workflow, github_workflows_test_test_workflow, github_workflows_validate_validate_workflow, pre_commit_config_pre_commit_config, requirements_test_requirements_test [INFERRED 0.85]
- **Cross-linked Project Documentation Set** — readme_readme, docs_readme_docs_readme, docs_agronomy_agronomy_doc, docs_calibration_calibration_doc, docs_fao56_fao56_doc, claude_claude_md [EXTRACTED 1.00]
- **Milestone 9 Feature Set (modes, calibration override, declared cycle)** — claude_modes_calibration_monitoring, claude_declared_manual_cycle, docs_calibration_wh51_manual_override, changelog_milestone_9_modes_calibration [EXTRACTED 1.00]

## Communities (69 total, 20 thin omitted)

### Community 0 - "Diagnostics & Test Fixtures"
Cohesion: 0.19
Nodes (22): Any, rain_step_input(), Shared mock entity ids and step-input builders for garden_irrigation tests., Valid input for config-flow step (b): rain., Valid input for config-flow step (c): WH51 per zone., Valid input for config-flow step (d): zone names/areas/distribution., Valid (empty/skippable) input for config-flow step (e): Telegram., soil_step_input() (+14 more)

### Community 1 - "Button Platform (Cycle & Calibration)"
Cohesion: 0.13
Nodes (35): ButtonEntity, async_setup_entry(), _CalibrationOverrideButton, EndCycleButton, FinishCalibrationButton, AddEntitiesCallback, HomeAssistant, Button platform for garden_irrigation.  Milestone 9 scope only:   - `start_cycle (+27 more)

### Community 2 - "Water Balance Engine"
Cohesion: 0.14
Nodes (14): BalanceEngine, _local_day_bounds(), date, datetime, Per-zone water balance engine for garden_irrigation.  Milestone 4 scope only: ET, Local [00:00:00.000000, 23:59:59.999999] bounds for a calendar day., Owns the per-zone water balance for one config entry.      Not an entity: plain, Force an immediate (non-debounced) persistence flush. (+6 more)

### Community 3 - "Binary Sensor Platform"
Cohesion: 0.07
Nodes (53): BinarySensorEntity, async_setup_entry(), IrrigationInProgressSensor, NeedsIrrigationZoneSensor, AddEntitiesCallback, Any, ConfigEntry, HomeAssistant (+45 more)

### Community 4 - "FAO-56 ET0 Engine"
Cohesion: 0.05
Nodes (55): Any, ConfigEntry, Coordinator for garden_irrigation.  Milestone 2 added the WeatherAggregator (acc, Compute ET0 for the current day and apply the balance for "yesterday"., Send a "cycle recorded" confirmation for any event not seen yet.          Diffs, Return the user-configured display name for `zone_id`.      Re-implemented here, _zone_name(), compute_et0() (+47 more)

### Community 5 - "Zone Sensors (Deficit & Rain)"
Cohesion: 0.17
Nodes (11): Outcome of one `process_daily_balance` call for a single zone/day., ZoneBalanceResult, Any, Shared base for the per-zone sensors backed by `coordinator.data["balance"]`., Subclasses add their own attributes on top of the common ones., Common day/applied/skipped_reason plus subclass-specific attributes., Total Available Water for the zone: (root_depth/1000) * AWC., Readily Available Water for the zone: TAW * p. (+3 more)

### Community 6 - "Coordinator: Operational State"
Cohesion: 0.09
Nodes (20): GardenIrrigationCoordinator, Start the weather listeners, restore the balance, register the         record_ir, Set the operational mode (calibration/monitoring) - UX/status only,         neve, Set which zone `async_start_cycle` will target next., Declare a manual cycle active for `selected_cycle_zone`, now.          Purely de, Clear the declared-active-cycle state., Stop the weather aggregator's listeners and force a final flush.          Extend, Event-driven coordinator (no polling: update_interval is None).      Refreshes a (+12 more)

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
Nodes (46): async_reload_entry(), async_setup_entry(), async_unload_entry(), ConfigEntry, HomeAssistant, The garden_irrigation integration.  Milestone 2: entry setup/unload/reload wirin, Set up garden_irrigation from a config entry., Unload a config entry and its platforms. (+38 more)

### Community 12 - "ET0 Sensor & Tests"
Cohesion: 0.15
Nodes (26): Et0DailySensor, Daily FAO-56 reference evapotranspiration for the current in-progress day., _full_entry_data(), Any, HomeAssistant, Tests for the garden_irrigation sensor platform (Milestones 1 and 5)., Every sensor described by the plan's data-backed subset exists after setup., Before any coordinator.data exists, zone sensors report unknown, not     a fabri (+18 more)

### Community 13 - "Recommendation Engine Tests"
Cohesion: 0.16
Nodes (38): _balance_result(), _coordinator(), Any, date, HomeAssistant, Tests for the garden_irrigation recommendation engine (Milestone 7)., (A) `0 < cap_remaining_mm < deficit_mm`: the recommendation is capped     to wha, (B) Exact boundary: `cap_remaining_mm == deficit_mm` covers the whole     defici (+30 more)

### Community 14 - "Telegram Notifier & Tests"
Cohesion: 0.08
Nodes (42): ABC, _language(), Notifier, PersistentNotificationNotifier, Any, ConfigEntry, HomeAssistant, Notifier abstraction for garden_irrigation.  Milestone 8 scope only: an abstract (+34 more)

### Community 15 - "Recommendation: Block Plan & WH51"
Cohesion: 0.12
Nodes (31): Per-zone agronomy parameters (options-flow configurable in a later milestone)., Total Available Water [mm]., Readily Available Water [mm]., ZoneAgronomyParams, _engine(), Any, HomeAssistant, Tests for the garden_irrigation per-zone water balance engine (Milestone 4). (+23 more)

### Community 16 - "Irrigation Event Log"
Cohesion: 0.08
Nodes (23): _area_m2(), IrrigationEvent, IrrigationLog, _mm_per_minute(), Any, ConfigEntry, datetime, HomeAssistant (+15 more)

### Community 17 - "Repair Issues"
Cohesion: 0.16
Nodes (21): async_clear_all_issues(), async_clear_telegram_issues(), async_clear_weather_stale_issue(), async_clear_wh51_stale_issue(), async_create_telegram_not_configured_issue(), async_create_telegram_send_failed_issue(), async_create_telegram_target_invalid_issue(), async_create_weather_stale_issue() (+13 more)

### Community 18 - "Notifier Abstraction"
Cohesion: 0.12
Nodes (17): async_setup_entry(), DeficitZoneSensor, EffectiveRainZoneSensor, EtcZoneSensor, AddEntitiesCallback, HomeAssistant, Crop evapotranspiration (ETc = ET0 * Kc) for the zone's last processed day., ETc in mm, or None until a day has actually been applied. (+9 more)

### Community 19 - "Weather: Rain & Time-Weighted Accumulators"
Cohesion: 0.15
Nodes (12): datetime, Running min/max and a time-weighted sum (sum of value * dt_seconds) for one fiel, Close the previous interval up to `ts`, then open a new one at `value`., Time-weighted mean including the still-open interval up to `as_of`., Time integral in MJ/m² including the still-open interval up to `as_of`., Close the day at `midnight`, then reset, carrying the last known         value f, Process one raw reading, updating daily_mm per the reset rules above., Non-destructive view of the current (in-progress) day, as of `as_of`. (+4 more)

### Community 20 - "Weather: Snapshot Persistence"
Cohesion: 0.14
Nodes (8): Any, Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Serialize for the daily_history Store buffer., Restore from a previously persisted dict (see to_dict)., Restore persisted/backfilled state and start listening for updates.

### Community 21 - "Weather Aggregator Core"
Cohesion: 0.15
Nodes (10): ConfigEntry, date, HomeAssistant, Return today's total and reset it; the raw baseline is NOT reset         (the ph, Owns the daily weather accumulators for one config entry.      Not an entity: th, Build the entity map from the config entry; accumulators start empty., Stop listening and force an immediate (non-debounced) persistence flush., Finalize the closed day into history, reset accumulators, force-flush. (+2 more)

### Community 22 - "Irrigation Log: Aggregates"
Cohesion: 0.22
Nodes (8): ConfigEntry, Initialize with a stable unique_id derived from the config entry., Initialize with a per-zone unique_id and translation placeholder., Initialize the per-zone start-calibration button., Initialize the per-zone finish-calibration button., Return the user-configured display name for `zone_id`.      Re-implemented here, Initialize with a stable unique_id derived from the config entry., _zone_name()

### Community 23 - "Recommendation Engine Core"
Cohesion: 0.14
Nodes (12): Any, HomeAssistant, Per-zone WH51 calibration baseline (device-relative, not VWC)., Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Builds explainable, read-only irrigation recommendations per zone.      Not an e, Build the engine with an empty WH51 calibration baseline., Restore the persisted WH51 calibration baseline. (+4 more)

### Community 24 - "Rain Accumulator Tests"
Cohesion: 0.27
Nodes (14): _RainAccumulator, Reset-aware daily rain accumulator.      Strictly increasing timestamps (out-of-, Tests for garden_irrigation weather aggregation (Milestone 2)., A sensor republishing the same value (heartbeat) must not add rain., test_rain_finalize_and_reset_keeps_raw_baseline(), test_rain_first_sample_seeds_baseline_without_delta(), test_rain_ignores_out_of_order_and_duplicate_timestamps(), test_rain_no_double_counting_on_repeated_identical_values() (+6 more)

### Community 25 - "Weather Backfill & Midnight Tests"
Cohesion: 0.27
Nodes (15): _full_entry_data(), Any, HomeAssistant, When there's no persisted state for today, a bounded recorder backfill     recon, No recorder loaded: setup must not raise, and simply starts empty., If today's state was already restored from Store, backfill must be     skipped e, test_backfill_not_used_when_today_already_persisted(), test_backfill_replays_history_when_no_persisted_state() (+7 more)

### Community 26 - "Integration Manifest"
Cohesion: 0.13
Nodes (14): after_dependencies, codeowners, config_flow, documentation, domain, integration_type, iot_class, issue_tracker (+6 more)

### Community 27 - "Constants & Coordinator Init"
Cohesion: 0.12
Nodes (13): ConfigEntry, HomeAssistant, Build the engine with per-zone deficit/ledger starting empty., HomeAssistant, Initialize the coordinator for a single config entry., GardenIrrigationStore, Any, HomeAssistant (+5 more)

### Community 28 - "Base Entity & Device Info"
Cohesion: 0.18
Nodes (8): GardenIrrigationEntity, ConfigEntry, Shared base entity for garden_irrigation., Base entity: single shared device, entity-only names (has_entity_name)., Bind the entity to the coordinator and the owning config entry., Single logical device: this integration does not control hardware., Sensor platform for garden_irrigation.  Milestone 1 added the single diagnostic, DeviceInfo

### Community 29 - "Integration Setup/Unload"
Cohesion: 0.29
Nodes (4): Any, Write `wh51_entry` for this zone into recommendation.py's own         store (sam, Restart calibration for this zone from this instant., Declare calibration finished for this zone using data observed so far.

### Community 30 - "Weather: Live State-Change Handling"
Cohesion: 0.22
Nodes (7): _parse_float(), Bounded, one-shot recorder backfill for today only (never a loop).          Only, Return the numeric value of a state, or None if unknown/unavailable/invalid., Event, EventStateChangedData, State, test_parse_float_rejects_unknown_unavailable_and_invalid()

### Community 31 - "Recommendation: WH51 Reading"
Cohesion: 0.11
Nodes (24): _area_m2(), _block_plan(), BlockPlanEntry, _classify_wh51(), _current_taw_raw_mm(), _mm_per_minute(), ConfigEntry, datetime (+16 more)

### Community 32 - "Data Quality Sensor"
Cohesion: 0.29
Nodes (5): DataQualitySensor, Always available in Milestone 1 (never unavailable)., Return `not_configured` pre-refresh, `initializing` afterwards., Diagnostic sensor reporting overall data-quality status.      Milestone 1: alway, SensorEntity

### Community 33 - "Telegram Send Logic"
Cohesion: 0.08
Nodes (24): Declared cycle in progress (optional), Development, Disclaimer, Documentation, ⚠️ Estimates vs. measurements, ET0 / ETc, garden-irrigation, HACS (+16 more)

### Community 34 - "Scheduler Setup"
Cohesion: 0.17
Nodes (28): _coordinator(), Any, HomeAssistant, Tests for the garden_irrigation manual irrigation-cycle log (Milestone 6)., An uncalibrated-tank cycle sends exactly one notification naming the     zone/so, Sanity check that the two branches (calibrated/uncalibrated) actually     produc, An uncalibrated event still counts toward `count`, but contributes     nothing t, The schema has no timestamp/backdating field at all - an attempt to     pass one (+20 more)

### Community 35 - "Test Fixtures Bootstrap"
Cohesion: 0.50
Nodes (3): auto_enable_custom_integrations(), Shared pytest fixtures for garden_irrigation tests., Make custom_components discoverable by Home Assistant in every test.

### Community 39 - "Agronomy: water balance, TAW/RAW, effective rain, weekly cap"
Cohesion: 0.10
Nodes (17): Agronomy: water balance, TAW/RAW, effective rain, weekly cap, Deficit, Effective rain, Recorded irrigation and the weekly cap, TAW / RAW, Uncalibrated sources, The automatic 14-day window (Milestone 7), The explicit override (Milestone 9) (+9 more)

### Community 40 - "GardenIrrigationStore"
Cohesion: 0.16
Nodes (20): Valid input for config-flow step (a): position + FAO-56 weather., user_step_input(), _advance_to_create_entry(), HomeAssistant, Tests for the garden_irrigation multi-step config flow., A non-sensor entity_id must be rejected with entity_wrong_domain., An incompatible unit_of_measurement must be rejected., Battery/signal/wind_gust are optional: omitting them is not an error. (+12 more)

### Community 41 - "test_init.py"
Cohesion: 0.22
Nodes (15): _full_entry_data(), HomeAssistant, Tests for garden_irrigation entry setup/unload/reload., A provided `message` is forwarded verbatim instead of the default., The service never records irrigation, never touches the balance     ledger, and, The entry loads cleanly and creates/removes its coordinator on unload., Reloading the entry (e.g. after an options change) succeeds cleanly., The service exists once the entry is loaded, and is torn down on unload. (+7 more)

### Community 42 - "Irrigation7dZoneSensor"
Cohesion: 0.23
Nodes (8): IrrigationAggregate, A derived (never persisted) sum over a subset of the event log., Irrigation7dZoneSensor, User-recorded irrigation over the trailing sliding 7x24h window.      Reads irri, Per-source aggregate over the trailing 7x24h window, as of now., The configured weekly cap, from the last balance result if known.          Falls, Recorded irrigation in mm over the trailing 7 days, all sources summed., Per-source breakdown plus the weekly cap context.

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

### Community 47 - "const.py"
Cohesion: 0.22
Nodes (7): Constants for the garden_irrigation integration.  Config-flow keys and defaults,, async_get_config_entry_diagnostics(), Any, ConfigEntry, HomeAssistant, Diagnostics support for garden_irrigation., Return diagnostics for a config entry, with Telegram target redacted.

### Community 68 - "ET0Result"
Cohesion: 0.29
Nodes (4): ET0Result, Daily ET0 plus every intermediate FAO-56 term, for diagnosis and tests.      Whe, The computed ET0 in mm, or None (unknown) if incomplete/not yet run., Intermediate FAO-56 terms, for diagnosis (see et0.py ET0Result).

## Knowledge Gaps
- **83 isolated node(s):** `domain`, `name`, `recorder`, `@mbonny95`, `config_flow` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GardenIrrigationCoordinator` connect `Coordinator: Operational State` to `Button Platform (Cycle & Calibration)`, `Water Balance Engine`, `Binary Sensor Platform`, `FAO-56 ET0 Engine`, `Zone Sensors (Deficit & Rain)`, `Scheduler Tests`, `Select Platform (Mode & Cycle Zone)`, `Scheduler: Advisory Monitors`, `ET0 Sensor & Tests`, `Recommendation Engine Tests`, `Telegram Notifier & Tests`, `Recommendation: Block Plan & WH51`, `Irrigation Event Log`, `Notifier Abstraction`, `Weather Aggregator Core`, `Irrigation Log: Aggregates`, `Recommendation Engine Core`, `Constants & Coordinator Init`, `Base Entity & Device Info`, `Data Quality Sensor`, `Scheduler Setup`, `test_init.py`, `Irrigation7dZoneSensor`, `const.py`?**
  _High betweenness centrality (0.314) - this node is a cross-community bridge._
- **Why does `GardenIrrigationStore` connect `Constants & Coordinator Init` to `Button Platform (Cycle & Calibration)`, `Water Balance Engine`, `Binary Sensor Platform`, `FAO-56 ET0 Engine`, `Zone Sensors (Deficit & Rain)`, `Coordinator: Operational State`, `Irrigation7dZoneSensor`, `_IrrigationRecord`, `Recommendation: Block Plan & WH51`, `Irrigation Event Log`, `Weather: Rain & Time-Weighted Accumulators`, `Weather Aggregator Core`, `Recommendation Engine Core`, `Rain Accumulator Tests`, `Integration Setup/Unload`, `Recommendation: WH51 Reading`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `compute_et0()` connect `FAO-56 ET0 Engine` to `ET0Result`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `GardenIrrigationCoordinator` (e.g. with `IrrigationInProgressSensor` and `NeedsIrrigationZoneSensor`) actually correct?**
  _`GardenIrrigationCoordinator` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ZoneBalanceResult` (e.g. with `GardenIrrigationStore` and `IrrigationInProgressSensor`) actually correct?**
  _`ZoneBalanceResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `timedelta` (e.g. with `._prune_irrigation()` and `.weekly_irrigation_mm()`) actually correct?**
  _`timedelta` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `GardenIrrigationStore` (e.g. with `BalanceEngine` and `_IrrigationRecord`) actually correct?**
  _`GardenIrrigationStore` has 24 INFERRED edges - model-reasoned connections that need verification._