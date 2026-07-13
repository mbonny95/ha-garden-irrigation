# CLAUDE.md — garden_irrigation

Home Assistant custom integration for **irrigation decision support** of two
*Festuca arundinacea* lawn zones. Domain: `garden_irrigation`.

## Golden rules (never violate)
- **v1 NEVER actuates hardware.** No valve/pump/relay control. The integration
  only reads existing HA entities, computes, recommends, and notifies. Any code
  that would command real hardware is OUT OF SCOPE for v1 — stop and ask.
- Estimates vs measurements: liters/mm are **estimates** (no flow meter, no tank
  level). Always label them as estimates in UI, README, and messages.
- No cloud services, no external weather providers. All computation is local.
- No secrets in the repo (no Telegram token/chat id). Telegram target is set via
  options flow only.

## Architecture invariants
- Everything **async**; no blocking I/O in the event loop. DB/recorder access
  only via `recorder.get_instance(hass).async_add_executor_job(...)`, **bounded
  one-shot** queries only — never continuous polling of history.
- Daily weather aggregation = **local persistent accumulators first**
  (`async_track_state_change_event`), recorder used only for backfill/recovery.
- Single source of truth = `GardenIrrigationCoordinator` (event-driven).
- Persistence via `helpers.storage.Store` (versioned, debounced). Two stores:
  `state` and `events` (365-day retention).
- All entities: `has_entity_name = True`, stable `unique_id`, `translation_key`,
  correct `device_info` and `availability`.
- Zones modeled as a **list** even though v1 has 2 fixed zones (phase-2 ready).
- Modes: only `calibration` and `monitoring` in v1. **No `automation` mode** — do
  not add or simulate it.
- Rain accumulator: strictly increasing timestamps, configurable reset tolerance
  (default 0.1 mm), `delta=0` on small decrements, no inference from the first
  post-restart value without backfill/next update, forced flush on midnight roll /
  unload / consolidation.
- Notifier is an **abstract adapter** (Telegram for MVP, degradable to
  persistent_notification). Never hard-depend on telegram_bot.

## Water/agronomy model (do not "simplify" away)
- ET0: FAO-56 Penman-Monteith daily. **No automatic fallback** in v1: if core
  inputs are missing/stale, ET0 and the recommendation are `unknown` + warning.
  (Hargreaves is a future opt-in, disabled by default.)
- `ETc = ET0 * Kc`; `TAW=(root_depth/1000)*AWC`; `RAW=TAW*p`.
- `eff_rain = min(daily_rain*factor, deficit+ETc)`.
- `deficit = clamp(prev + ETc - eff_rain - irrigation_mm, 0, TAW)`.
- Balance applied once/day at **05:30** finalizing **D-1 00:00:00–23:59:59.999999**
  (idempotent via `last_balance_date`); the 20:00 job is a labeled **preview** only.
- Rain: reset-aware accumulator anchored to HA local day. `24h_rainfall` and
  `rain_event` are diagnostic only — never summed into the balance.
- WH51 % is **device-relative, not VWC**. Diagnostic-only for first 14 days;
  afterwards a soft corroborating signal with configurable thresholds and always
  a textual explanation. Never a hard block, never presented as universal VWC.
- Manual cycles: max 15 min per record; block plan (≤15 min blocks + pause) when
  more is needed; min 48h between irrigations per zone. `record_irrigation` uses
  **current timestamp only** (no backdating in MVP; a future correction action
  with audit trail). Weekly cap 30 mm limits **only user-recorded
  `irrigation_7d_mm` over a sliding 7×24h window**; effective rain is shown
  separately (affects deficit, does NOT consume the cap).
- Declared manual cycle ("start/end cycle"): elapsed time is exposed **only**
  as the read-only diagnostic sensor `elapsed_manual_cycle_minutes`. **Never**
  prefill the manual-record form's minutes field from it — the user always
  types/confirms the duration manually.

## Config
- Config flow: guided source entity_ids with validation (exists, domain, unit,
  numeric). No hardcoded Ecowitt entity names. Global params (lat/elev/anemometer
  height), zone names/areas/mm_per_minute matrix (zone×source, tank nullable).
- Everything operational lives in **options flow**.

## Conventions
- Python target **3.13** (test 3.13). Ruff + mypy clean. Type-hint everything.
- Tests: `pytest` + `pytest-homeassistant-custom-component`. Every engine
  (et0/balance/weather/rain-reset/limits/stale/persistence/manual-record) has
  unit tests. FAO-56 validated against reference vectors.
- i18n: Italian default + English. All user-facing strings translated.
- Conventional Commits. Never commit/push without explicit user consent.
- Never invent HA APIs — verify against installed HA version before using.

## Workflow guardrails
- Implement **one milestone at a time**; keep CI green before moving on.
- Stop and ask before: anything that actuates hardware, schema/storage
  migrations, deleting data, changing the balance semantics, or anything outside
  this spec.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
