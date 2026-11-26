# Graph Report - garden-irrigation  (2026-11-26)

## Corpus Check
- 65 files · ~35,873 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 898 nodes · 1937 edges · 67 communities (46 shown, 21 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 74 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `54952294`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Diagnostics & Test Fixtures
- Button Platform (Cycle & Calibration)
- Water Balance Engine
- Binary Sensor Platform
- test_fao56.py
- Zone Sensors (Deficit & Rain)
- Coordinator: Operational State
- Scheduler Tests
- test_recommendation.py
- Config Flow
- Project Governance & Milestones
- Scheduler: Advisory Monitors
- test_balance.py
- test_daily_weather.py
- test_repairs.py
- test_coordinator.py
- coordinator.py
- Repair Issues
- GardenIrrigationCoordinator
- GardenIrrigationStore
- test_services.py
- __init__.py
- Irrigation Log: Aggregates
- services.py
- .from_subentry
- .async_schedule_daily_run
- Integration Manifest
- InstallationSensor
- balance.py
- GardenIrrigationZoneEntity
- store.py
- coordinator.py
- GardenIrrigationEntity
- Telegram Send Logic
- FAO-56 reference evapotranspiration (ET0)
- 5. Configurazione
- Package Root
- Agronomy: water balance, TAW/RAW, effective rain, weekly cap
- GardenIrrigationStore
- test_init.py
- 6. Modello agronomico
- CLAUDE.md — garden_irrigation
- Root-zone water
- Pre-commit Configuration
- [0.1.0] - 2026-07-13
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

## God Nodes (most connected - your core abstractions)
1. `GardenIrrigationCoordinator` - 45 edges
2. `ZoneSnapshot` - 29 edges
3. `recommend()` - 28 edges
4. `GardenIrrigationStore` - 28 edges
5. `penman_monteith()` - 25 edges
6. `DailyWeather` - 23 edges
7. `CoordinatorData` - 22 edges
8. `GardenIrrigationZoneCard` - 21 edges
9. `aggregate_day()` - 19 edges
10. `_setup()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Validate Workflow (hassfest/HACS)` --semantically_similar_to--> `Pre-commit Configuration`  [INFERRED] [semantically similar]
  .github/workflows/validate.yaml → .pre-commit-config.yaml
- `test_attributes_without_data()` --calls--> `CoordinatorData`  [EXTRACTED]
  tests/test_soil_and_forecast.py → custom_components/garden_irrigation/coordinator.py
- `_coordinator()` --references--> `GardenIrrigationCoordinator`  [EXTRACTED]
  tests/test_coordinator.py → custom_components/garden_irrigation/coordinator.py
- `test_depletion_fraction_adjusted_for_etc()` --calls--> `depletion_fraction()`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/model/balance.py
- `test_depletion_fraction_without_adjustment()` --calls--> `depletion_fraction()`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/model/balance.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CI / Quality Gate Toolchain** — github_workflows_lint_lint_workflow, github_workflows_test_test_workflow, github_workflows_validate_validate_workflow, pre_commit_config_pre_commit_config, requirements_test_requirements_test [INFERRED 0.85]
- **Cross-linked Project Documentation Set** — readme_readme, docs_readme_docs_readme, docs_agronomy_agronomy_doc, docs_calibration_calibration_doc, docs_fao56_fao56_doc, claude_claude_md [EXTRACTED 1.00]
- **Milestone 9 Feature Set (modes, calibration override, declared cycle)** — claude_modes_calibration_monitoring, claude_declared_manual_cycle, docs_calibration_wh51_manual_override, changelog_milestone_9_modes_calibration [EXTRACTED 1.00]

## Communities (67 total, 21 thin omitted)

### Community 0 - "Diagnostics & Test Fixtures"
Cohesion: 0.11
Nodes (31): _import(), Any, HomeAssistant, Test data shared across garden_irrigation tests., Write a sensor state with the given unit and state class., Create a valid set of weather source sensors., set_sensor(), set_weather_states() (+23 more)

### Community 1 - "Button Platform (Cycle & Calibration)"
Cohesion: 0.12
Nodes (17): 10. Limiti → avvisi (non vincoli), 11. Futuro: valvole (fuori da v2.0), 12. Entità, 13. Storage, 14. Test, 15. Card / dashboard, 16. Fasi di lavoro, 1. Obiettivo e perimetro (+9 more)

### Community 2 - "Water Balance Engine"
Cohesion: 0.35
Nodes (17): _configure(), loaded_entry(), Any, HomeAssistant, MockConfigEntry, Tests for the zone subentry flow., The main entry, set up., _start_add() (+9 more)

### Community 3 - "Binary Sensor Platform"
Cohesion: 0.29
Nodes (7): kc_for_month(), Crop reference data: monthly Kc profiles and depletion fraction p.  Cool-season, Return the Kc of `month` (1 = January) from a 12-value profile., Sanity tests for the agronomic reference tables., test_cool_season_turf_profile(), test_kc_for_month_rejects_invalid_month(), test_kc_for_month_rejects_short_profile()

### Community 4 - "test_fao56.py"
Cohesion: 0.07
Nodes (57): actual_vapour_pressure(), clear_sky_radiation(), compute_et0(), DailyWeather, Et0Method, Et0Result, extraterrestrial_radiation(), hargreaves() (+49 more)

### Community 5 - "Zone Sensors (Deficit & Rain)"
Cohesion: 0.38
Nodes (11): Any, HomeAssistant, MockConfigEntry, Tests for entry setup, unload, reload and removal., _stored_zone(), test_options_change_reloads_entry(), test_remove_entry_deletes_store(), test_setup_and_unload() (+3 more)

### Community 6 - "Coordinator: Operational State"
Cohesion: 0.47
Nodes (5): HomeAssistant, MockConfigEntry, Tests for the options flow., test_options_defaults_and_save(), test_weekly_cap_can_be_disabled()

### Community 8 - "test_recommendation.py"
Cohesion: 0.09
Nodes (42): Advisory, Message, StrEnum, Explainable irrigation recommendation for one zone.  Pure function of the zone's, Build the recommendation for one zone., Why the decision is what it is., Advisory conditions shown next to the recommendation., A reason or warning code with the values that explain it. (+34 more)

### Community 9 - "Config Flow"
Cohesion: 0.06
Nodes (39): ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, GardenIrrigationConfigFlow, GardenIrrigationOptionsFlow, _kc_schema(), _number(), Any (+31 more)

### Community 10 - "Project Governance & Milestones"
Cohesion: 0.15
Nodes (13): Declared Manual Cycle In Progress, Rationale: Estimates vs Measurements Labeling, Modes: calibration / monitoring (select.mode), Golden Rule: v1 Never Actuates Hardware, record_irrigation Action, services.yaml (record_irrigation schema), Garden Irrigation Lovelace Dashboard, Weekly Irrigation Cap (30mm default) (+5 more)

### Community 11 - "Scheduler: Advisory Monitors"
Cohesion: 0.22
Nodes (14): DayRecord, IrrigationRecord, Daily balance outcome for one zone (values in mm)., A manually recorded irrigation., _day(), _irrigation(), Any, HomeAssistant (+6 more)

### Community 12 - "test_balance.py"
Cohesion: 0.11
Nodes (31): apply_day(), current_deficit(), DayBalance, depletion_fraction(), effective_rain(), FAO-56 root-zone soil water balance, single crop coefficient (chapter 8).  Deple, Deficit right now: last closed day minus irrigation recorded today., Water holding capacity of a zone's root zone (mm). (+23 more)

### Community 13 - "test_daily_weather.py"
Cohesion: 0.08
Nodes (49): aggregate_day(), async_read_day(), DayWeather, _max(), _min(), date, HomeAssistant, StatisticsRow (+41 more)

### Community 14 - "test_repairs.py"
Cohesion: 0.15
Nodes (22): Binary sensor: does a zone need irrigation today., Everything known about a zone right now., ZoneSnapshot, messages_as_attributes(), Any, Base entities: one device for the installation, one per zone., Round for attributes, keeping None., Reason/warning codes with their (rounded) values, for attributes. (+14 more)

### Community 15 - "test_coordinator.py"
Cohesion: 0.23
Nodes (33): import_day_statistics(), date, Import one local day of hourly statistics shaped like FAO-56 Example 18.      Ra, _coordinator(), expected_et0(), date, DeviceRegistry, FrozenDateTimeFactory (+25 more)

### Community 16 - "coordinator.py"
Cohesion: 0.11
Nodes (20): ConfigSubentry, ConfigEntry, Read the configuration once: any change reloads the entry., _optional_float(), Any, ConfigEntry, Typed views of the config entry: site, operating options and zones., One irrigated zone, with presets resolved. (+12 more)

### Community 17 - "Repair Issues"
Cohesion: 0.10
Nodes (29): attr(), clamp(), classifyZoneStatus(), deviceName(), escapeHtml(), findEntity(), findZoneDevices(), fireMoreInfo() (+21 more)

### Community 18 - "GardenIrrigationCoordinator"
Cohesion: 0.12
Nodes (14): CALLBACK_TYPE, GardenIrrigationCoordinator, _local_date(), date, datetime, HomeAssistant, Run daily and after startup; follow the soil moisture sensors., Most recent day that may be closed at `now`.          Yesterday counts as closed (+6 more)

### Community 19 - "GardenIrrigationStore"
Cohesion: 0.09
Nodes (13): GardenIrrigationStore, date, HomeAssistant, Weather of the last closed day that was processed., Return the ids of all zones with persisted state., Drop state of zones that no longer exist. Return True if changed., Drop day/irrigation records older than RETENTION_DAYS., Schedule a debounced save of the current document. (+5 more)

### Community 20 - "test_services.py"
Cohesion: 0.23
Nodes (21): _call(), Any, DeviceRegistry, FrozenDateTimeFactory, HomeAssistant, MockConfigEntry, Tests for the record_irrigation and set_deficit actions., Italian local time, 7 July 2026 at 18:00. (+13 more)

### Community 21 - "__init__.py"
Cohesion: 0.18
Nodes (16): GardenIrrigationRuntimeData, Runtime data attached to the config entry., Objects that live as long as the config entry is loaded., _async_register_devices(), _async_reload_on_update(), async_remove_entry(), async_setup_entry(), async_unload_entry() (+8 more)

### Community 22 - "Irrigation Log: Aggregates"
Cohesion: 0.50
Nodes (3): Configuration, Garden Irrigation — custom cards, Installation

### Community 23 - "services.py"
Cohesion: 0.21
Nodes (12): ConfigType, async_setup(), Register the integration's actions., _async_record_irrigation(), _async_set_deficit(), async_setup_services(), HomeAssistant, Register the integration's actions (once, not per entry). (+4 more)

### Community 24 - ".from_subentry"
Cohesion: 0.15
Nodes (11): BinarySensorEntity, async_setup_entry(), NeedsIrrigationSensor, AddConfigEntryEntitiesCallback, Any, GardenIrrigationConfigEntry, HomeAssistant, On when the zone's deficit has reached its RAW. (+3 more)

### Community 25 - ".async_schedule_daily_run"
Cohesion: 0.12
Nodes (42): async_fetch_forecast_rain(), Any, datetime, HomeAssistant, Forecast rain from a user-selected Home Assistant weather entity.  Informational, Ask the weather entity for its forecast and total the rain.      Hourly forecast, _total_rain(), datetime (+34 more)

### Community 26 - "Integration Manifest"
Cohesion: 0.13
Nodes (14): codeowners, config_flow, dependencies, documentation, domain, integration_type, iot_class, issue_tracker (+6 more)

### Community 27 - "InstallationSensor"
Cohesion: 0.17
Nodes (10): async_setup_entry(), AddConfigEntryEntitiesCallback, datetime, GardenIrrigationConfigEntry, HomeAssistant, Sensor of a zone device., Value from the zone snapshot., Explanation of the value. (+2 more)

### Community 28 - "balance.py"
Cohesion: 0.35
Nodes (17): FrozenDateTimeFactory, HomeAssistant, MockConfigEntry, Tests for the sensor and binary_sensor entities., Italian local time, 7 July 2026 at 06:00 (after the 05:30 run)., rome_time(), _set_deficit(), _setup() (+9 more)

### Community 29 - "GardenIrrigationZoneEntity"
Cohesion: 0.10
Nodes (21): GardenIrrigationEntity, GardenIrrigationZoneEntity, Entity of the installation device., Bind the entity to the installation device., Entity of a zone device., Bind the entity to its zone device., Current data of this entity's zone., InstallationSensor (+13 more)

### Community 30 - "store.py"
Cohesion: 0.28
Nodes (7): _empty_zone(), Single versioned persistence store for the integration.  Holds, per zone (keyed, Persisted state of one zone., Top-level persisted document., Return the state of `zone_id`, creating it if needed., StoredData, ZoneState

### Community 31 - "coordinator.py"
Cohesion: 0.17
Nodes (13): Constants shared across the garden_irrigation integration.  Agronomic reference, CoordinatorData, Coordinator: daily water balance, catch-up of missed days, user actions.  Once a, Data shared with the entities., _weather_record(), ForecastRain, Rain expected in the next hours, in mm., _data_quality() (+5 more)

### Community 32 - "GardenIrrigationEntity"
Cohesion: 0.20
Nodes (10): async_get_config_entry_diagnostics(), Any, GardenIrrigationConfigEntry, HomeAssistant, Diagnostics download: configuration, persisted state and current data., Return everything needed to understand a recommendation., HomeAssistant, MockConfigEntry (+2 more)

### Community 33 - "Telegram Send Logic"
Cohesion: 0.14
Nodes (14): Actions, Dashboard, Development, Disclaimer, Documentation, Entities, Garden Irrigation, HACS (+6 more)

### Community 34 - "FAO-56 reference evapotranspiration (ET0)"
Cohesion: 0.50
Nodes (4): Daily weather from Home Assistant statistics, FAO-56 reference evapotranspiration (ET0), Hargreaves (eq. 52), optional, Penman-Monteith, daily (eq. 6)

### Community 35 - "5. Configurazione"
Cohesion: 0.50
Nodes (4): 5.1 Entry principale (config flow), 5.2 Subentry "zona", 5.3 Opzioni (modificabili in ogni momento), 5. Configurazione

### Community 39 - "Agronomy: water balance, TAW/RAW, effective rain, weekly cap"
Cohesion: 0.24
Nodes (5): Daily step, Recommendation, Warnings (never change the amount), Water balance and recommendation, Documentation

### Community 40 - "GardenIrrigationStore"
Cohesion: 0.38
Nodes (3): GardenIrrigationOverviewCardEditor, LABELS, SCHEMA

### Community 41 - "test_init.py"
Cohesion: 0.38
Nodes (3): GardenIrrigationZoneCardEditor, LABELS, SCHEMA

### Community 42 - "6. Modello agronomico"
Cohesion: 0.50
Nodes (4): 6.1 Terreni (FAO-56, tab. 19 — valore centrale di θFC−θWP), 6.2 Kc mensile di default (prato microtermo), 6.3 Bilancio giornaliero (invariato nella sostanza), 6. Modello agronomico

### Community 43 - "CLAUDE.md — garden_irrigation"
Cohesion: 0.25
Nodes (7): Architecture invariants, CLAUDE.md — garden_irrigation (v2), Conventions, Golden rules (never violate), graphify — STANDBY during the v2 rewrite, Water/agronomy model (do not "simplify" away), Workflow guardrails

### Community 44 - "Root-zone water"
Cohesion: 0.67
Nodes (3): Crop coefficient (Kc), Root-zone water, Soils (FAO-56 Table 19, midpoint of θFC − θWP)

### Community 45 - "Pre-commit Configuration"
Cohesion: 0.40
Nodes (5): Lint Workflow (CI), Test Workflow (CI), Validate Workflow (hassfest/HACS), Pre-commit Configuration, README

### Community 46 - "[0.1.0] - 2026-07-13"
Cohesion: 0.18
Nodes (10): [0.1.0] - 2026-07-13, [2.0.0] - Unreleased, Added, Added, Changed, Changed, Changelog, Removed (+2 more)

## Knowledge Gaps
- **104 isolated node(s):** `domain`, `name`, `@mbonny95`, `config_flow`, `recorder` (+99 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GardenIrrigationCoordinator` connect `GardenIrrigationCoordinator` to `Scheduler: Advisory Monitors`, `test_daily_weather.py`, `test_repairs.py`, `test_coordinator.py`, `coordinator.py`, `GardenIrrigationStore`, `__init__.py`, `services.py`, `InstallationSensor`, `GardenIrrigationZoneEntity`, `coordinator.py`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `GardenIrrigationStore` connect `GardenIrrigationStore` to `Scheduler: Advisory Monitors`, `test_repairs.py`, `coordinator.py`, `GardenIrrigationCoordinator`, `__init__.py`, `store.py`, `coordinator.py`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `recommend()` connect `test_recommendation.py` to `GardenIrrigationCoordinator`, `coordinator.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `GardenIrrigationCoordinator` (e.g. with `DayWeather` and `ForecastRain`) actually correct?**
  _`GardenIrrigationCoordinator` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `ZoneSnapshot` (e.g. with `DayWeather` and `ForecastRain`) actually correct?**
  _`ZoneSnapshot` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `GardenIrrigationStore` (e.g. with `CoordinatorData` and `GardenIrrigationCoordinator`) actually correct?**
  _`GardenIrrigationStore` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `domain`, `name`, `@mbonny95` to the rest of the system?**
  _104 weakly-connected nodes found - possible documentation gaps or missing edges._