# Graph Report - .  (2026-07-13)

## Corpus Check
- Corpus is ~39,772 words - fits in a single context window. You may not need a graph.

## Summary
- 1023 nodes · 2549 edges · 39 communities (38 shown, 1 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 188 edges (avg confidence: 0.6)
- Token cost: 74,903 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `GardenIrrigationCoordinator` - 115 edges
2. `ZoneBalanceResult` - 47 edges
3. `GardenIrrigationStore` - 42 edges
4. `setup_mock_weather_states()` - 40 edges
5. `_coordinator()` - 34 edges
6. `WeatherAggregator` - 32 edges
7. `user_step_input()` - 32 edges
8. `BalanceEngine` - 31 edges
9. `compute_et0()` - 30 edges
10. `GardenIrrigationEntity` - 29 edges

## Surprising Connections (you probably didn't know these)
- `GardenIrrigationCoordinator (single source of truth)` --semantically_similar_to--> `WH51 14-day Automatic Calibration Window`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/calibration.md
- `Validate Workflow (hassfest/HACS)` --semantically_similar_to--> `Pre-commit Configuration`  [INFERRED] [semantically similar]
  .github/workflows/validate.yaml → .pre-commit-config.yaml
- `Reset-aware Rain Accumulator` --semantically_similar_to--> `WH51 14-day Automatic Calibration Window`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/calibration.md
- `test_zone_sensor_units_and_state_classes()` --indirect_call--> `EtcZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py
- `test_zone_sensor_units_and_state_classes()` --indirect_call--> `DeficitZoneSensor`  [INFERRED]
  tests/test_sensor.py → custom_components/garden_irrigation/sensor.py

## Import Cycles
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`
- 3-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/__init__.py`
- 4-file cycle: `custom_components/garden_irrigation/__init__.py -> custom_components/garden_irrigation/coordinator.py -> custom_components/garden_irrigation/scheduler.py -> custom_components/garden_irrigation/notify.py -> custom_components/garden_irrigation/__init__.py`

## Hyperedges (group relationships)
- **CI / Quality Gate Toolchain** — github_workflows_lint_lint_workflow, github_workflows_test_test_workflow, github_workflows_validate_validate_workflow, pre_commit_config_pre_commit_config, requirements_test_requirements_test [INFERRED 0.85]
- **Cross-linked Project Documentation Set** — readme_readme, docs_readme_docs_readme, docs_agronomy_agronomy_doc, docs_calibration_calibration_doc, docs_fao56_fao56_doc, claude_claude_md [EXTRACTED 1.00]
- **Milestone 9 Feature Set (modes, calibration override, declared cycle)** — claude_modes_calibration_monitoring, claude_declared_manual_cycle, docs_calibration_wh51_manual_override, changelog_milestone_9_modes_calibration [EXTRACTED 1.00]

## Communities (39 total, 1 thin omitted)

### Community 0 - "Diagnostics & Test Fixtures"
Cohesion: 0.06
Nodes (81): async_get_config_entry_diagnostics(), Any, ConfigEntry, HomeAssistant, Diagnostics support for garden_irrigation., Return diagnostics for a config entry, with Telegram target redacted., Any, rain_step_input() (+73 more)

### Community 1 - "Button Platform (Cycle & Calibration)"
Cohesion: 0.06
Nodes (57): ButtonEntity, async_setup_entry(), _CalibrationOverrideButton, EndCycleButton, FinishCalibrationButton, AddEntitiesCallback, Any, ConfigEntry (+49 more)

### Community 2 - "Water Balance Engine"
Cohesion: 0.05
Nodes (52): BalanceEngine, _IrrigationRecord, _local_day_bounds(), Any, ConfigEntry, date, datetime, HomeAssistant (+44 more)

### Community 3 - "Binary Sensor Platform"
Cohesion: 0.07
Nodes (53): BinarySensorEntity, async_setup_entry(), IrrigationInProgressSensor, NeedsIrrigationZoneSensor, AddEntitiesCallback, Any, ConfigEntry, HomeAssistant (+45 more)

### Community 4 - "FAO-56 ET0 Engine"
Cohesion: 0.07
Nodes (47): compute_et0(), _extraterrestrial_radiation_mj(), _incomplete_result(), _net_longwave_radiation_mj(), _pressure_from_altitude_kpa(), _psychrometric_constant(), date, FAO-56 Penman-Monteith daily reference evapotranspiration (ET0) engine.  Milesto (+39 more)

### Community 5 - "Zone Sensors (Deficit & Rain)"
Cohesion: 0.09
Nodes (34): Outcome of one `process_daily_balance` call for a single zone/day., ZoneBalanceResult, ET0Result, Daily ET0 plus every intermediate FAO-56 term, for diagnosis and tests.      Whe, async_setup_entry(), DeficitZoneSensor, EffectiveRainZoneSensor, EtcZoneSensor (+26 more)

### Community 6 - "Coordinator: Operational State"
Cohesion: 0.07
Nodes (23): GardenIrrigationCoordinator, Any, Start the weather listeners, restore the balance, register the         record_ir, Set the operational mode (calibration/monitoring) - UX/status only,         neve, Set which zone `async_start_cycle` will target next., Declare a manual cycle active for `selected_cycle_zone`, now.          Purely de, Clear the declared-active-cycle state., Stop the weather aggregator's listeners and force a final flush.          Extend (+15 more)

### Community 7 - "Scheduler Tests"
Cohesion: 0.15
Nodes (42): HomeAssistant, Register mock states for every entity a full config flow run needs., setup_mock_weather_states(), _coordinator(), _issue(), Any, HomeAssistant, IssueEntry (+34 more)

### Community 8 - "Select Platform (Mode & Cycle Zone)"
Cohesion: 0.09
Nodes (34): ActiveCycleZoneSelect, async_setup_entry(), ModeSelect, AddEntitiesCallback, ConfigEntry, HomeAssistant, Select platform for garden_irrigation.  Milestone 9 scope only:   - `select.mode, Set up the garden_irrigation select platform. (+26 more)

### Community 9 - "Config Flow"
Cohesion: 0.08
Nodes (30): ConfigFlow, _entity_selector(), GardenIrrigationConfigFlow, GardenIrrigationOptionsFlow, Any, ConfigEntry, Config flow for garden_irrigation.  Five ordered steps, per the approved plan:, Validate a set of entity_id fields; return an errors dict for the form. (+22 more)

### Community 10 - "Project Governance & Milestones"
Cohesion: 0.12
Nodes (37): CHANGELOG, Milestone 10: Dashboard & Docs, Milestone 1: Scaffold & CI Toolchain, Milestone 7: Recommendation Engine, Milestone 8: Notifier & Repairs, Milestone 9: Modes & Calibration Override, CLAUDE.md Project Instructions, Declared Manual Cycle In Progress (+29 more)

### Community 11 - "Scheduler: Advisory Monitors"
Cohesion: 0.11
Nodes (23): _battery_entity_id(), _entity_age(), _numeric_state(), Any, datetime, HomeAssistant, _rain_during_cycle_message(), Scheduler for garden_irrigation.  Milestone 7 added two daily local-time trigger (+15 more)

### Community 12 - "ET0 Sensor & Tests"
Cohesion: 0.13
Nodes (26): Et0DailySensor, Daily FAO-56 reference evapotranspiration for the current in-progress day., The computed ET0 in mm, or None (unknown) if incomplete/not yet run., Intermediate FAO-56 terms, for diagnosis (see et0.py ET0Result)., _full_entry_data(), Any, HomeAssistant, Tests for the garden_irrigation sensor platform (Milestones 1 and 5). (+18 more)

### Community 13 - "Recommendation Engine Tests"
Cohesion: 0.23
Nodes (28): _balance_result(), _coordinator(), Any, date, HomeAssistant, Tests for the garden_irrigation recommendation engine (Milestone 7)., A repeat (idempotent-skip) balance result is still a READY final., test_block_plan_single_block_under_15_minutes() (+20 more)

### Community 14 - "Telegram Notifier & Tests"
Cohesion: 0.19
Nodes (25): Sends via the configured Telegram target; degrades on failure/misconfiguration., TelegramNotifier, _issue(), HomeAssistant, IssueEntry, Tests for the garden_irrigation notifier abstraction (Milestone 8)., If both target styles are (inconsistently) present, entity_id wins., irrigation_log.py is untouched: the coordinator detects the new event     by dif (+17 more)

### Community 15 - "Recommendation: Block Plan & WH51"
Cohesion: 0.13
Nodes (19): _block_plan(), BlockPlanEntry, _classify_wh51(), _current_taw_raw_mm(), _mm_per_minute(), datetime, Recommendation engine for garden_irrigation.  Milestone 7 scope only: an explain, Return the configured mm/minute for `zone_id`+`source`, or None if unset.      D (+11 more)

### Community 16 - "Irrigation Event Log"
Cohesion: 0.13
Nodes (12): IrrigationEvent, IrrigationLog, Any, One persisted, user-recorded irrigation cycle., Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Owns the manual-cycle event log and the `record_irrigation` service.      Not an, Restore persisted events and register the recording service. (+4 more)

### Community 17 - "Repair Issues"
Cohesion: 0.16
Nodes (21): async_clear_all_issues(), async_clear_telegram_issues(), async_clear_weather_stale_issue(), async_clear_wh51_stale_issue(), async_create_telegram_not_configured_issue(), async_create_telegram_send_failed_issue(), async_create_telegram_target_invalid_issue(), async_create_weather_stale_issue() (+13 more)

### Community 18 - "Notifier Abstraction"
Cohesion: 0.13
Nodes (15): ABC, _language(), Notifier, PersistentNotificationNotifier, ConfigEntry, HomeAssistant, Notifier abstraction for garden_irrigation.  Milestone 8 scope only: an abstract, Render the IT/EN template `key` (see `_MESSAGES`) with `kwargs`. (+7 more)

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
Cohesion: 0.14
Nodes (13): _area_m2(), IrrigationAggregate, _mm_per_minute(), ConfigEntry, datetime, HomeAssistant, Manual irrigation-cycle recording and persistence for garden_irrigation.  Milest, Return the configured area for `zone_id` in square meters. (+5 more)

### Community 23 - "Recommendation Engine Core"
Cohesion: 0.17
Nodes (8): Any, Serialize for Store persistence., Restore from a previously persisted dict (see to_dict)., Builds explainable, read-only irrigation recommendations per zone.      Not an e, Restore the persisted WH51 calibration baseline., Force an immediate (non-debounced) persistence flush., Widen the observed [min, max] baseline with the current reading.          Sample, RecommendationEngine

### Community 24 - "Rain Accumulator Tests"
Cohesion: 0.27
Nodes (14): _RainAccumulator, Reset-aware daily rain accumulator.      Strictly increasing timestamps (out-of-, Tests for garden_irrigation weather aggregation (Milestone 2)., A sensor republishing the same value (heartbeat) must not add rain., test_rain_finalize_and_reset_keeps_raw_baseline(), test_rain_first_sample_seeds_baseline_without_delta(), test_rain_ignores_out_of_order_and_duplicate_timestamps(), test_rain_no_double_counting_on_repeated_identical_values() (+6 more)

### Community 25 - "Weather Backfill & Midnight Tests"
Cohesion: 0.27
Nodes (15): _full_entry_data(), Any, HomeAssistant, When there's no persisted state for today, a bounded recorder backfill     recon, No recorder loaded: setup must not raise, and simply starts empty., If today's state was already restored from Store, backfill must be     skipped e, test_backfill_not_used_when_today_already_persisted(), test_backfill_replays_history_when_no_persisted_state() (+7 more)

### Community 26 - "Integration Manifest"
Cohesion: 0.14
Nodes (13): after_dependencies, codeowners, config_flow, documentation, domain, iot_class, issue_tracker, name (+5 more)

### Community 27 - "Constants & Coordinator Init"
Cohesion: 0.20
Nodes (7): Constants for the garden_irrigation integration.  Config-flow keys and defaults,, ConfigEntry, HomeAssistant, Coordinator for garden_irrigation.  Milestone 2 added the WeatherAggregator (acc, Return the user-configured display name for `zone_id`.      Re-implemented here, Initialize the coordinator for a single config entry., _zone_name()

### Community 28 - "Base Entity & Device Info"
Cohesion: 0.20
Nodes (7): GardenIrrigationEntity, ConfigEntry, Shared base entity for garden_irrigation., Base entity: single shared device, entity-only names (has_entity_name)., Bind the entity to the coordinator and the owning config entry., Single logical device: this integration does not control hardware., DeviceInfo

### Community 29 - "Integration Setup/Unload"
Cohesion: 0.31
Nodes (9): async_reload_entry(), async_setup_entry(), async_unload_entry(), ConfigEntry, HomeAssistant, The garden_irrigation integration.  Milestone 2: entry setup/unload/reload wirin, Set up garden_irrigation from a config entry., Unload a config entry and its platforms. (+1 more)

### Community 30 - "Weather: Live State-Change Handling"
Cohesion: 0.22
Nodes (7): _parse_float(), Bounded, one-shot recorder backfill for today only (never a loop).          Only, Return the numeric value of a state, or None if unknown/unavailable/invalid., Event, EventStateChangedData, State, test_parse_float_rejects_unknown_unavailable_and_invalid()

### Community 31 - "Recommendation: WH51 Reading"
Cohesion: 0.22
Nodes (7): _area_m2(), ConfigEntry, HomeAssistant, Return the configured area for `zone_id` in square meters., Return the configured WH51 soil-moisture entity_id for `zone_id`., Build the engine with an empty WH51 calibration baseline., _soil_moisture_entity_id()

### Community 32 - "Data Quality Sensor"
Cohesion: 0.29
Nodes (5): DataQualitySensor, Always available in Milestone 1 (never unavailable)., Return `not_configured` pre-refresh, `initializing` afterwards., Diagnostic sensor reporting overall data-quality status.      Milestone 1: alway, SensorEntity

### Community 33 - "Telegram Send Logic"
Cohesion: 0.40
Nodes (3): Any, Return (domain, service, base_service_data) for the configured         target, o, Send via Telegram; on any failure, degrade to persistent_notification.

### Community 34 - "Scheduler Setup"
Cohesion: 0.50
Nodes (3): _parse_hms(), Register the 20:00/05:30 triggers and the periodic monitor tick., Parse a "HH:MM:SS" const.py default into (hour, minute, second).

### Community 35 - "Test Fixtures Bootstrap"
Cohesion: 0.50
Nodes (3): auto_enable_custom_integrations(), Shared pytest fixtures for garden_irrigation tests., Make custom_components discoverable by Home Assistant in every test.

## Knowledge Gaps
- **15 isolated node(s):** `domain`, `name`, `recorder`, `@mbonny95`, `config_flow` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GardenIrrigationCoordinator` connect `Coordinator: Operational State` to `Diagnostics & Test Fixtures`, `Button Platform (Cycle & Calibration)`, `Water Balance Engine`, `Binary Sensor Platform`, `Zone Sensors (Deficit & Rain)`, `Scheduler Tests`, `Select Platform (Mode & Cycle Zone)`, `Scheduler: Advisory Monitors`, `ET0 Sensor & Tests`, `Recommendation Engine Tests`, `Telegram Notifier & Tests`, `Irrigation Event Log`, `Weather Aggregator Core`, `Irrigation Log: Aggregates`, `Recommendation Engine Core`, `Constants & Coordinator Init`, `Base Entity & Device Info`, `Integration Setup/Unload`, `Data Quality Sensor`?**
  _High betweenness centrality (0.304) - this node is a cross-community bridge._
- **Why does `GardenIrrigationStore` connect `Button Platform (Cycle & Calibration)` to `Water Balance Engine`, `Binary Sensor Platform`, `FAO-56 ET0 Engine`, `Zone Sensors (Deficit & Rain)`, `Coordinator: Operational State`, `Recommendation: Block Plan & WH51`, `Irrigation Event Log`, `Weather: Rain & Time-Weighted Accumulators`, `Weather Aggregator Core`, `Irrigation Log: Aggregates`, `Recommendation Engine Core`, `Rain Accumulator Tests`, `Constants & Coordinator Init`, `Recommendation: WH51 Reading`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `WeatherAggregator` connect `Weather Aggregator Core` to `Button Platform (Cycle & Calibration)`, `FAO-56 ET0 Engine`, `Coordinator: Operational State`, `Weather: Rain & Time-Weighted Accumulators`, `Weather: Snapshot Persistence`, `Rain Accumulator Tests`, `Weather Backfill & Midnight Tests`, `Constants & Coordinator Init`, `Weather: Live State-Change Handling`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `GardenIrrigationCoordinator` (e.g. with `IrrigationInProgressSensor` and `NeedsIrrigationZoneSensor`) actually correct?**
  _`GardenIrrigationCoordinator` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `ZoneBalanceResult` (e.g. with `GardenIrrigationStore` and `IrrigationInProgressSensor`) actually correct?**
  _`ZoneBalanceResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `timedelta` (e.g. with `._prune_irrigation()` and `.weekly_irrigation_mm()`) actually correct?**
  _`timedelta` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `GardenIrrigationStore` (e.g. with `BalanceEngine` and `_IrrigationRecord`) actually correct?**
  _`GardenIrrigationStore` has 24 INFERRED edges - model-reasoned connections that need verification._