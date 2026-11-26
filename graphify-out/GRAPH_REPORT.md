# Graph Report - garden-irrigation  (2026-11-26)

## Corpus Check
- 55 files · ~34,480 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 754 nodes · 1511 edges · 57 communities (35 shown, 22 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bddcf929`
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
- Telegram Send Logic
- Package Root
- Agronomy: water balance, TAW/RAW, effective rain, weekly cap
- GardenIrrigationStore
- test_init.py
- CLAUDE.md — garden_irrigation
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
1. `GardenIrrigationCoordinator` - 31 edges
2. `recommend()` - 28 edges
3. `GardenIrrigationStore` - 28 edges
4. `penman_monteith()` - 25 edges
5. `DailyWeather` - 23 edges
6. `GardenIrrigationZoneCard` - 22 edges
7. `aggregate_day()` - 19 edges
8. `_setup()` - 18 edges
9. `compute_et0()` - 17 edges
10. `escapeHtml()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Validate Workflow (hassfest/HACS)` --semantically_similar_to--> `Pre-commit Configuration`  [INFERRED] [semantically similar]
  .github/workflows/validate.yaml → .pre-commit-config.yaml
- `_coordinator()` --references--> `GardenIrrigationCoordinator`  [EXTRACTED]
  tests/test_coordinator.py → custom_components/garden_irrigation/coordinator.py
- `test_depletion_fraction_adjusted_for_etc()` --calls--> `depletion_fraction()`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/model/balance.py
- `test_depletion_fraction_without_adjustment()` --calls--> `depletion_fraction()`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/model/balance.py
- `test_effective_rain()` --calls--> `effective_rain()`  [EXTRACTED]
  tests/test_balance.py → custom_components/garden_irrigation/model/balance.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CI / Quality Gate Toolchain** — github_workflows_lint_lint_workflow, github_workflows_test_test_workflow, github_workflows_validate_validate_workflow, pre_commit_config_pre_commit_config, requirements_test_requirements_test [INFERRED 0.85]
- **Cross-linked Project Documentation Set** — readme_readme, docs_readme_docs_readme, docs_agronomy_agronomy_doc, docs_calibration_calibration_doc, docs_fao56_fao56_doc, claude_claude_md [EXTRACTED 1.00]
- **Milestone 9 Feature Set (modes, calibration override, declared cycle)** — claude_modes_calibration_monitoring, claude_declared_manual_cycle, docs_calibration_wh51_manual_override, changelog_milestone_9_modes_calibration [EXTRACTED 1.00]

## Communities (57 total, 22 thin omitted)

### Community 0 - "Diagnostics & Test Fixtures"
Cohesion: 0.11
Nodes (31): _import(), Any, HomeAssistant, Test data shared across garden_irrigation tests., Write a sensor state with the given unit and state class., Create a valid set of weather source sensors., set_sensor(), set_weather_states() (+23 more)

### Community 1 - "Button Platform (Cycle & Calibration)"
Cohesion: 0.08
Nodes (25): 10. Limiti → avvisi (non vincoli), 11. Futuro: valvole (fuori da v2.0), 12. Entità, 13. Storage, 14. Test, 15. Card / dashboard, 16. Fasi di lavoro, 1. Obiettivo e perimetro (+17 more)

### Community 2 - "Water Balance Engine"
Cohesion: 0.35
Nodes (17): _configure(), loaded_entry(), Any, HomeAssistant, MockConfigEntry, Tests for the zone subentry flow., The main entry, set up., _start_add() (+9 more)

### Community 3 - "Binary Sensor Platform"
Cohesion: 0.21
Nodes (9): kc_for_month(), Return the Kc of `month` (1 = January) from a 12-value profile., Soil reference data.  Available water capacity (AWC) is the midpoint of the θFC, Reference properties of a soil texture class., SoilType, Sanity tests for the agronomic reference tables., test_cool_season_turf_profile(), test_kc_for_month_rejects_invalid_month() (+1 more)

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
Cohesion: 0.10
Nodes (41): Advisory, Message, StrEnum, Explainable irrigation recommendation for one zone.  Pure function of the zone's, Build the recommendation for one zone., Why the decision is what it is., Advisory conditions shown next to the recommendation., A reason or warning code with the values that explain it. (+33 more)

### Community 9 - "Config Flow"
Cohesion: 0.07
Nodes (36): ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, GardenIrrigationConfigFlow, GardenIrrigationOptionsFlow, _kc_schema(), _number(), Any (+28 more)

### Community 10 - "Project Governance & Milestones"
Cohesion: 0.20
Nodes (10): Declared Manual Cycle In Progress, Rationale: Estimates vs Measurements Labeling, Modes: calibration / monitoring (select.mode), Golden Rule: v1 Never Actuates Hardware, record_irrigation Action, services.yaml (record_irrigation schema), Garden Irrigation Lovelace Dashboard, Weekly Irrigation Cap (30mm default) (+2 more)

### Community 11 - "Scheduler: Advisory Monitors"
Cohesion: 0.14
Nodes (21): DayRecord, _empty_zone(), IrrigationRecord, Single versioned persistence store for the integration.  Holds, per zone (keyed, Daily balance outcome for one zone (values in mm)., A manually recorded irrigation., Persisted state of one zone., Top-level persisted document. (+13 more)

### Community 12 - "test_balance.py"
Cohesion: 0.11
Nodes (31): apply_day(), current_deficit(), DayBalance, depletion_fraction(), effective_rain(), FAO-56 root-zone soil water balance, single crop coefficient (chapter 8).  Deple, Deficit right now: last closed day minus irrigation recorded today., Water holding capacity of a zone's root zone (mm). (+23 more)

### Community 13 - "test_daily_weather.py"
Cohesion: 0.14
Nodes (31): aggregate_day(), async_read_day(), _max(), _min(), date, HomeAssistant, StatisticsRow, Daily FAO-56 weather from the recorder's long-term hourly statistics.  One bound (+23 more)

### Community 14 - "test_repairs.py"
Cohesion: 0.18
Nodes (19): Constants shared across the garden_irrigation integration.  Agronomic reference, DayWeather, Weather of one closed local day, with its data coverage., True when every required source covers the day., async_clear_issues(), async_update_source_issues(), HomeAssistant, Repair issues: the only way the integration surfaces data problems. (+11 more)

### Community 15 - "test_coordinator.py"
Cohesion: 0.23
Nodes (33): import_day_statistics(), date, Import one local day of hourly statistics shaped like FAO-56 Example 18.      Ra, _coordinator(), expected_et0(), date, DeviceRegistry, FrozenDateTimeFactory (+25 more)

### Community 16 - "coordinator.py"
Cohesion: 0.13
Nodes (20): CoordinatorData, ConfigEntry, Coordinator: daily water balance, catch-up of missed days, user actions.  Once a, Data shared with the entities., Read the configuration once: any change reloads the entry., _weather_record(), Crop reference data: monthly Kc profiles and depletion fraction p.  Cool-season, OperatingOptions (+12 more)

### Community 17 - "Repair Issues"
Cohesion: 0.08
Nodes (28): attr(), clamp(), classifyZoneStatus(), escapeHtml(), fireMoreInfo(), formatLiters(), formatMm(), getState() (+20 more)

### Community 18 - "GardenIrrigationCoordinator"
Cohesion: 0.15
Nodes (14): GardenIrrigationCoordinator, _local_date(), date, datetime, HomeAssistant, Most recent day that may be closed at `now`.          Yesterday counts as closed, Close every day not processed yet, then refresh the data., Record an irrigation done now, given its duration or its amount. (+6 more)

### Community 19 - "GardenIrrigationStore"
Cohesion: 0.09
Nodes (13): GardenIrrigationStore, date, HomeAssistant, Weather of the last closed day that was processed., Return the ids of all zones with persisted state., Drop state of zones that no longer exist. Return True if changed., Drop day/irrigation records older than RETENTION_DAYS., Schedule a debounced save of the current document. (+5 more)

### Community 20 - "test_services.py"
Cohesion: 0.23
Nodes (21): _call(), Any, DeviceRegistry, FrozenDateTimeFactory, HomeAssistant, MockConfigEntry, Tests for the record_irrigation and set_deficit actions., Italian local time, 7 July 2026 at 18:00. (+13 more)

### Community 21 - "__init__.py"
Cohesion: 0.15
Nodes (19): ConfigType, GardenIrrigationRuntimeData, Runtime data attached to the config entry., Objects that live as long as the config entry is loaded., _async_register_devices(), _async_reload_on_update(), async_remove_entry(), async_setup() (+11 more)

### Community 22 - "Irrigation Log: Aggregates"
Cohesion: 0.18
Nodes (10): Auto-discovery limitations (`getStubConfig`), Data-quality / Repairs banner, Example configuration, File structure, Garden Irrigation — Lovelace custom cards, Installation, Known gaps against the backend (do not silently work around — flagged instead), What this is (and isn't) (+2 more)

### Community 23 - "services.py"
Cohesion: 0.29
Nodes (10): _async_record_irrigation(), _async_set_deficit(), async_setup_services(), HomeAssistant, Actions: record an irrigation, set a zone's deficit., Register the integration's actions (once, not per entry)., Map a zone device to its loaded coordinator and zone (subentry) id., _resolve_zone() (+2 more)

### Community 24 - ".from_subentry"
Cohesion: 0.40
Nodes (4): ConfigSubentry, _optional_float(), Any, Build a zone from its subentry data.

### Community 26 - "Integration Manifest"
Cohesion: 0.13
Nodes (14): codeowners, config_flow, dependencies, documentation, domain, integration_type, iot_class, issue_tracker (+6 more)

### Community 33 - "Telegram Send Logic"
Cohesion: 0.08
Nodes (24): Declared cycle in progress (optional), Development, Disclaimer, Documentation, ⚠️ Estimates vs. measurements, ET0 / ETc, garden-irrigation, HACS (+16 more)

### Community 39 - "Agronomy: water balance, TAW/RAW, effective rain, weekly cap"
Cohesion: 0.10
Nodes (17): Agronomy: water balance, TAW/RAW, effective rain, weekly cap, Deficit, Effective rain, Recorded irrigation and the weekly cap, TAW / RAW, Uncalibrated sources, The automatic 14-day window (Milestone 7), The explicit override (Milestone 9) (+9 more)

### Community 40 - "GardenIrrigationStore"
Cohesion: 0.38
Nodes (3): GardenIrrigationOverviewCardEditor, LABELS, SCHEMA

### Community 41 - "test_init.py"
Cohesion: 0.38
Nodes (3): GardenIrrigationZoneCardEditor, LABELS, SCHEMA

### Community 43 - "CLAUDE.md — garden_irrigation"
Cohesion: 0.25
Nodes (7): Architecture invariants, CLAUDE.md — garden_irrigation (v2), Conventions, Golden rules (never violate), graphify — STANDBY during the v2 rewrite, Water/agronomy model (do not "simplify" away), Workflow guardrails

### Community 45 - "Pre-commit Configuration"
Cohesion: 0.40
Nodes (5): Lint Workflow (CI), Test Workflow (CI), Validate Workflow (hassfest/HACS), Pre-commit Configuration, README

### Community 46 - "[0.1.0] - 2026-07-13"
Cohesion: 0.29
Nodes (6): [0.1.0] - 2026-07-13, Added, Changed, Changelog, Removed, [Unreleased]

## Knowledge Gaps
- **124 isolated node(s):** `domain`, `name`, `@mbonny95`, `config_flow`, `recorder` (+119 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GardenIrrigationStore` connect `GardenIrrigationStore` to `coordinator.py`, `GardenIrrigationCoordinator`, `Scheduler: Advisory Monitors`, `__init__.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `GardenIrrigationCoordinator` connect `GardenIrrigationCoordinator` to `Scheduler: Advisory Monitors`, `test_repairs.py`, `test_coordinator.py`, `coordinator.py`, `GardenIrrigationStore`, `__init__.py`, `services.py`, `.async_schedule_daily_run`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `recommend()` connect `test_recommendation.py` to `coordinator.py`, `GardenIrrigationCoordinator`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `GardenIrrigationCoordinator` (e.g. with `DayWeather` and `OperatingOptions`) actually correct?**
  _`GardenIrrigationCoordinator` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `GardenIrrigationStore` (e.g. with `CoordinatorData` and `GardenIrrigationCoordinator`) actually correct?**
  _`GardenIrrigationStore` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `domain`, `name`, `@mbonny95` to the rest of the system?**
  _124 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Diagnostics & Test Fixtures` be split into smaller, more focused modules?**
  _Cohesion score 0.10873440285204991 - nodes in this community are weakly interconnected._