# CLAUDE.md — garden_irrigation (v2)

Home Assistant custom integration for **FAO-56 irrigation decision support**.
Domain: `garden_irrigation`. Meant to be shareable via HACS.

The authoritative design is **`docs/v2-spec.md`**. Read it before changing
behavior; if code and spec disagree, stop and ask.

## Golden rules (never violate)
- **v2.0 NEVER actuates hardware.** No valve/pump/relay commands. Reading a
  valve entity is a future, separately approved step (spec §11).
- Liters/mm/minutes are **estimates**: label them so in UI and docs.
- No cloud calls by the integration. The only external-origin data allowed is
  an **optional, user-selected HA `weather` entity**, informational only: it
  never changes numbers or the recommendation.
- No notifications. Problems surface only as **Repairs**.
- No secrets in the repo.

## Architecture invariants
- Agronomy lives in `model/`: pure Python, **no Home Assistant imports**,
  fully unit-tested.
- Everything async; no blocking I/O in the event loop. Recorder access only via
  `recorder.get_instance(hass).async_add_executor_job(...)`, bounded one-shot
  queries.
- Daily weather comes from recorder **long-term hourly statistics** of the
  source sensors (mean/min/max, `change` for rain), read once per day for the
  closed day; missed days are caught up in order. A day with < 20 h of
  statistics is incomplete: ET0 `unknown`, balance not applied, no invented
  values.
- **One** versioned `Store` per config entry (`store.py`), 365-day retention.
- Zones are **config subentries** (`SUBENTRY_TYPE_ZONE`), any number. Entity
  `unique_id`s are derived from the subentry id.
- Preset Kc profiles are resolved at runtime (not copied into zone data);
  only custom profiles store `kc_monthly`.
- All entities: `has_entity_name = True`, stable `unique_id`,
  `translation_key`, correct `device_info` (one device per zone + one main).
- No modes (no calibration/monitoring/automation).

## Water/agronomy model (do not "simplify" away)
- ET0: FAO-56 Penman-Monteith daily. Hargreaves only if the user enables the
  fallback option (off by default), always flagged as estimate.
- `ETc = ET0 * Kc(month)`; `TAW = (root_depth/1000) * AWC`; `RAW = p * TAW`
  (optional FAO-56 p adjustment for ETc, off by default).
- Effective rain: `0` below the threshold, else
  `min(rain * factor, prev_deficit + ETc)`.
- `deficit = clamp(prev + ETc - eff_rain - irrigation_mm, 0, TAW)`, applied
  once per closed day, idempotent via `last_balance_date`.
- Current deficit shown = last closed-day deficit − irrigation recorded today.
- Recommendation: irrigate when current deficit ≥ RAW; amount = current
  deficit; minutes per configured source = mm / source rate; split into
  blocks of at most the soil's max block mm, with the configured pause.
- Min interval, weekly cap and block limits are **warnings, never hard
  constraints**.
- Soil moisture sensors (e.g. WH51) are device-relative, **not VWC**:
  diagnostic, plus a soft confirmation against user-set dry/wet thresholds.
  Never changes numbers, never blocks.
- `record_irrigation` uses the current timestamp only (no backdating);
  the user always types the duration/amount. `set_deficit` sets the starting
  deficit.

## Conventions
- HA minimum **2026.2.0**; Python 3.13 (CI also 3.14). Ruff + mypy strict clean.
- Tests: `pytest` + `pytest-homeassistant-custom-component`
  (`recorder_mock` is autouse in `tests/conftest.py`). FAO-56 validated
  against the manual's worked examples.
- i18n: English base (`strings.json` = `translations/en.json`) + Italian.
  All user-facing strings translated.
- Comments/docstrings describe the code as it is, never its development
  history (no "Milestone N" notes).
- Conventional Commits. Never commit/push without explicit user consent.
- Never invent HA APIs — verify against the installed HA version first.

## Workflow guardrails
- Implement **one phase of spec §16 at a time**; keep CI green before moving on.
- Stop and ask before: anything that actuates hardware, storage schema
  changes once released, deleting user data, changing the balance semantics,
  or anything outside the spec.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
