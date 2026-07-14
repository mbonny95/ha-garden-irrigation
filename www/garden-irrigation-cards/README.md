# Garden Irrigation — Lovelace custom cards

Two read-only, decision-support Lovelace cards for the `garden_irrigation` integration:
`garden-irrigation-zone-card` (one per zone) and `garden-irrigation-overview-card` (one for
the whole garden). Implemented from the design handoff in
`design_handoff_garden_irrigation_cards/README.md` — see that document for the full,
authoritative spec (anatomy, state matrix, tokens, accessibility, responsive behavior).

This is a **separate, additive deliverable** from `dashboards/gardenirrigation.yaml` (the
Milestone 10 example dashboard, which is deliberately core-cards-only). These custom cards are
not required to use the integration; they're a richer alternative view.

## What this is (and isn't)

- Frontend only. No Python file under `custom_components/garden_irrigation/` was touched.
- No new entities, services, or backend behavior. Every number shown is read from an existing
  entity's state/attributes — see "Known gaps against the backend" below for what a couple of
  handoff-requested fields need before they can be shown at all.
- Read-only: the only taps are `more-info`, Lovelace `navigate`, and the local
  final/preview toggle and disclosure (no entity is ever written to).
- Framework-less: plain Web Components (`customElements.define`), no Lit/React, no build step,
  no npm dependency. This repository has no existing JS/frontend tooling, so a zero-dependency
  card is the least-friction fit — see "Why no Lit/build step" below if you want to change that
  later.

## Installation

1. Copy this whole `www/garden-irrigation-cards/` folder into your Home Assistant
   `config/www/` directory (so the files end up at
   `config/www/garden-irrigation-cards/garden-irrigation-zone-card.js` etc.).
2. Settings → Dashboards → ⋮ → Resources → **Add resource**:
   - URL: `/local/garden-irrigation-cards/garden-irrigation-zone-card.js`, type **JavaScript module**.
   - URL: `/local/garden-irrigation-cards/garden-irrigation-overview-card.js`, type **JavaScript module**.
   - (The editor and shared-helpers files are imported automatically by the two card files above —
     they don't need their own resource entries, but must stay in the same folder.)
3. Add the cards from the dashboard UI's card picker (they register `getStubConfig`, so a
   reasonable starting config is pre-filled from your existing entities — see "Auto-discovery
   limitations" below), or hand-write YAML — see examples below.

## Example configuration

```yaml
type: custom:garden-irrigation-zone-card
zone: zone_1
name: Zone 1
needs_irrigation_entity: binary_sensor.garden_irrigation_needs_irrigation_zona_1
deficit_entity: sensor.garden_irrigation_deficit_zona_1
raw_entity: sensor.garden_irrigation_raw_zona_1
taw_entity: sensor.garden_irrigation_taw_zona_1
irrigation_7d_entity: sensor.garden_irrigation_irrigation_7d_zona_1
weekly_cap_entity: binary_sensor.garden_irrigation_weekly_cap_reached_zona_1
# in_progress_entity is optional and NOT in the original handoff's config
# table - see "Zone card in-progress banner wiring" below for why it's here.
in_progress_entity: binary_sensor.garden_irrigation_irrigation_in_progress
default_variant: final
```

```yaml
type: custom:garden-irrigation-overview-card
mode_entity: select.garden_irrigation_mode
data_quality_entity: sensor.garden_irrigation_data_quality
et0_entity: sensor.garden_irrigation_et0_daily
in_progress_entity: binary_sensor.garden_irrigation_irrigation_in_progress
zones:
  - zone: zone_1
    name: Zone 1
    needs_irrigation_entity: binary_sensor.garden_irrigation_needs_irrigation_zona_1
    navigate_to: /garden-irrigation/zone-1
  - zone: zone_2
    name: Zone 2
    needs_irrigation_entity: binary_sensor.garden_irrigation_needs_irrigation_zona_2
    navigate_to: /garden-irrigation/zone-2
```

Your actual entity_ids depend on the zone display names you chose during setup — check
Settings → Devices & services → Garden Irrigation, or the entity picker in each card's GUI editor.

## File structure

```
www/garden-irrigation-cards/
  garden-irrigation-cards-shared.js       tokens, icons, status classification, formatting,
                                           defensive state readers - imported by both cards
  garden-irrigation-zone-card.js          <garden-irrigation-zone-card>
  garden-irrigation-overview-card.js      <garden-irrigation-overview-card>
  garden-irrigation-zone-card-editor.js   GUI config editor (ha-form based)
  garden-irrigation-overview-card-editor.js
  README.md                               this file
```

No child custom elements beyond the two cards + two editors, matching the handoff's component
list — the status badge, deficit bar, and zone roll-up row are render helpers/functions, not
separate `customElements.define` targets.

## Known gaps against the backend (do not silently work around — flagged instead)

The handoff's own README (§6) already flags that `binary_sensor.needs_irrigation_<zone>` doesn't
yet expose `estimated_liters`, per-source `sources.*.minutes/calibrated/blocks`, or
`wh51_percent`. Per its own explicit instruction ("do not fabricate these values client-side"),
this implementation renders those as "—" / omitted rather than computing them from mm × a
guessed area or rate. This requires a small, separate backend PR to
`recommendation.py`/`binary_sensor.py` if the full headline-liters / per-source-minutes /
soil-percent UI is wanted.

**A second gap beyond what the handoff's §6 lists, found during implementation:** the Zone
card's final/preview segmented control implies both variants render a full body (headline mm,
deficit bar, technical-row deficit, reasons/limits/warnings chips). In the real backend, only
`bundle.final` is fully serialized onto `needs_irrigation_entity`'s attributes —
`bundle.preview` is exposed as a **single boolean**, `preview_needs_irrigation`, and nothing
else (see `coordinator.py`'s `binary_sensor.py` wiring and `recommendation.py`'s
`ZoneRecommendationResult`). Concretely, selecting "Preview":

- **can** show whether preview agrees or disagrees with the final decision (state-matrix row 12,
  implemented as the differs-note);
- **cannot** show a preview-specific recommended mm, deficit bar, technical-row deficit, or
  reasons/limits/warnings chips — none of that is exposed for the preview variant today.

This implementation renders "—" / an explanatory note for everything preview-specific that
isn't exposed, rather than falling back to final's numbers unlabeled (which would misrepresent
them as the preview). If the full preview experience the anatomy implies is wanted, a follow-up
backend change would need to serialize `bundle.preview.deficit_mm` / `.recommended_mm` /
`.reasons` / `.limits_applied` / `.warnings` onto the entity too (or a second, preview-specific
entity) — same shape as the existing `estimated_liters`/`sources`/`wh51_percent` gap, just not
called out in the original handoff.

**A third, smaller gap:** state-matrix row 8 ("WH51 diagnostic") wants "Calibrating (day
N/14)". The calibration start timestamp (`_Wh51CalibrationState.first_seen` in
`recommendation.py`) is never serialized onto any entity attribute, so the day count can't be
computed — the soil row shows "Calibrating soil sensor (baseline in progress)" without a day
count instead of guessing one.

## Zone card in-progress banner wiring

The Zone card's anatomy (§3, item 1) requires reading `binary_sensor.irrigation_in_progress`
(a single, zone-agnostic entity) and comparing its `zone` attribute to the card's own zone — but
the Zone card's config contract (§6) doesn't list an entity field for it (only the Overview
card's contract does). This is treated as a minimal, necessary adaptation: an optional
`in_progress_entity` field was added to the Zone card's config. If you don't set it, the card
falls back to auto-discovering it by scanning `hass.states` for a `binary_sensor.*` entity whose
`device_class` is `running` and which has a `zone` attribute (true of exactly one entity in this
integration today) — if that heuristic ever matches the wrong thing in a future backend change,
set `in_progress_entity` explicitly.

## Data-quality / Repairs banner

The Overview card's banner (state-matrix row 15) is specified as triggering on
`sensor.data_quality !== 'good'` OR an open Repair issue. Today's backend's `data_quality`
sensor only ever emits `initializing`/`not_configured` (see `const.py`'s
`DATA_QUALITY_STATES`) — real stale/degraded data-quality logic was never wired to this sensor
in a later milestone, and there is no entity-based way to check for an open Repair issue from a
card (Repairs are a separate `repairs/list_issues` WebSocket API, not a state). This
implementation only triggers the banner when the `data_quality` entity is genuinely
`unavailable`/`unknown` (i.e. the integration itself isn't running) — which is honest given
current backend behavior, but means the banner is effectively dormant for the "real" degraded
case the design anticipates. Tapping it still navigates to `/config/repairs`, which remains
useful regardless.

## Auto-discovery limitations (`getStubConfig`)

Entity-id auto-discovery for the card picker's stub config relies on this integration's current
naming convention (`{domain}.garden_irrigation_{key}_{zone_name_slug}` — every sibling entity
for one zone shares everything except the `key` segment). This is a convenience heuristic, not a
documented backend contract; if you renamed things unusually or a future backend version changes
entity-id generation, the stub config may come back empty/wrong — hand-edit the YAML using the
entity_ids from Settings → Devices & services in that case.

## Why no Lit/build step

The handoff's own implementation notes recommend LitElement "unless the target codebase already
standardizes on something else." This repository is a pure-Python Home Assistant integration
with zero existing frontend code — there's nothing to match, and no `package.json`/bundler to
build on top of. Introducing one (Lit + esbuild/rollup + a `dist/` output) was judged a bigger
infrastructure decision than "implement two cards," so these ship as dependency-free Web
Components instead: drop-in `.js` files, no compile step, works immediately as Lovelace
resources. If this repo later grows more frontend surface, revisiting Lit + a real build
pipeline is reasonable — nothing here blocks that.
