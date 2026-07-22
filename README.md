# garden-irrigation

Custom Home Assistant integration (`garden_irrigation`) that provides
**irrigation decision support** for two *Festuca arundinacea* lawn zones,
based on a FAO-56 Penman–Monteith daily water balance computed locally from
existing Ecowitt weather-station and WH51 soil-moisture entities.

## What this integration is

- A **decision-support tool**: it reads existing Home Assistant entities,
  computes ET0/ETc and a per-zone soil water deficit, and **recommends**
  irrigation (mm, minutes per source, estimated liters), with the reasons and
  limits behind every recommendation exposed as entity attributes.
- A **manual logbook**: after you physically water a zone (manual taps,
  manual source switch), you call an action to record what you did; the
  integration updates the water balance and the 7-day recorded-irrigation
  figure.
- Home Assistant **Repairs** for conditions you need to act on outside the
  integration (stale weather/WH51 data). The integration itself sends no
  notifications anywhere - everything is read from its entities/attributes.

## What this integration is NOT (v1)

- **It does not control any hardware.** There are no valves, relays, flow
  meters, or tank-level sensors in this setup. Taps and the source switch
  (rainwater tank / mains water) are operated **manually** by the user.
  Nothing in this integration ever opens/closes a valve or starts a pump —
  not now, and no hidden "automation" mode is planned for v1.
- **It does not use cloud services or external weather forecasts.** All
  computation is local, from entities you already have in Home Assistant.

## Prerequisites

You need an existing weather station and two soil-moisture probes already
exposed as Home Assistant entities. The config flow asks for **entity_ids** —
it never hardcodes a brand — but this was built against and is described here
in terms of an **Ecowitt GW1100 console + two WH51 soil-moisture sensors**
(one per zone) as a concrete example.

**Required** (ET0 cannot be computed without these):
- Outdoor temperature, humidity, absolute pressure, solar irradiance, wind
  speed (all `sensor` domain, numeric, with a compatible unit).
- Daily rainfall and rain rate.
- One WH51 soil-moisture sensor per zone.

**Optional:**
- Wind gust (not used by ET0; kept for a possible future use).
- 24-hour rainfall and "rain event" (diagnostic-only, never summed into the
  balance).
- WH51 battery and signal per zone (not currently used by any check).

If a required entity is missing/stale, the affected computation reports
`unknown` with an explanation — it is never silently guessed (see
`docs/fao56.md`).

## Installation

### HACS

1. HACS → Integrations → ⋮ → **Custom repositories** → add this repository
   URL as an **Integration**.
2. Install **Garden Irrigation**, then restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Garden Irrigation*.

### Manual

1. Copy `custom_components/garden_irrigation` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Garden Irrigation*.

## Initial configuration

The config flow is a guided, multi-step wizard: (1) location + FAO-56 weather
entities, (2) rain entities, (3) WH51 per-zone entities, (4) zone names/areas/
`mm per minute` distribution rates. Only one config entry is allowed.
Everything above is validated (entity exists, correct domain, compatible
unit, currently numeric) before you can proceed. Operational thresholds (Kc,
caps, staleness thresholds, WH51 sensitivity, ...) are managed from the
integration's **options**, not the initial flow.

## Key concepts

### ET0 / ETc

`ET0` is the FAO-56 Penman–Monteith daily reference evapotranspiration,
computed **locally**, once per day, from your weather entities. `ETc = ET0 ×
Kc` is the crop-specific evapotranspiration for the configured grass. See
`docs/fao56.md` for the full formula, the data actually used, and the
approximations made when a refinement (e.g. RHmin/RHmax, measured pressure)
isn't available.

### Water deficit

Each zone keeps a persisted `deficit` (mm) — how much water the lawn is
"behind" — updated once per completed day: `deficit = clamp(prev_deficit +
ETc − effective_rain − recorded_irrigation, 0, TAW)`. See `docs/agronomy.md`
for `TAW`/`RAW`, effective rain, and the weekly cap.

### Recommendation: preview vs. final

- The **05:30** job finalizes the **previous** full calendar day (00:00:00 to
  23:59:59.999999) exactly once (idempotent) and produces the **final**
  recommendation you should act on.
- The **20:00** job only refreshes a **preview**: a projection of "if today
  ended right now" from today's still-in-progress ET0/rain/irrigation. It is
  clearly labeled as a preview and is **never persisted** into the deficit.

Both are exposed as attributes on `binary_sensor.needs_irrigation_<zone>`
(`recommended_mm` is currently the final value; `preview_needs_irrigation`
carries the 20:00 projection).

### WH51 is device-relative, not absolute soil moisture

The WH51 capacitive sensor's `%` reading is **not** an absolute volumetric
water content — it is relative to that specific probe's own installation.
For the first 14 days after calibration starts, its status is
diagnostic-only. Afterwards, it becomes a soft, explainable **corroborating
signal** (`wh51_status`: critical/dry/moderate/wet) — it never blocks or
overrides the deficit-based decision by itself. See `docs/calibration.md`.

### Manual irrigation, recorded

There is no native input form (no `input_number`/`input_select` workarounds,
by design). Call the `garden_irrigation.record_irrigation` action — from
Developer tools → Actions, a script, an automation, or a dashboard button —
with `zone`, `source`, `duration_minutes` (> 0, ≤ 15 per call) and optional
`notes`. It always uses the **current timestamp** (no backdating in v1). If
the chosen source has no calibrated `mm per minute` for that zone, the event
is still logged (for the record), but the deficit is **not** decremented and
a warning is raised.

### Weekly cap

The 30 mm (default) weekly cap limits **only the irrigation you record**,
over a sliding 7×24h window — not effective rain. Rain still reduces the
deficit; it just doesn't count against (or get limited by) the cap. See
`docs/agronomy.md`.

### Modes: calibration / monitoring

`select.mode` exposes exactly **`calibration`** and **`monitoring`** — there
is no `automation` mode in v1, not even as a hidden placeholder. It is purely
an operational/UX indicator: changing it never alters a past balance,
recommendation, or log entry.

### Declared cycle in progress (optional)

`select.active_cycle_zone` + `button.start_cycle`/`button.end_cycle` let you
**declare** that a manual cycle is running, and `binary_sensor.
irrigation_in_progress` reflects it (with `elapsed_minutes` as a read-only
attribute). This is entirely declarative — the integration cannot detect a
real cycle — and using it is optional. Using it never pre-fills the
`record_irrigation` action's `duration_minutes`: you always type/confirm the
actual duration yourself when you log the cycle.

## Repairs

The integration sends no notifications anywhere. Stale weather/WH51 data
(no new reading within the expected time) raises a Home Assistant Repair
issue (Settings → System → Repairs) explaining what to check, and clears
itself automatically once the sensor updates again.

## Limitations

- Two fixed zones in v1 (modeled as a list internally, but not user-extensible
  yet).
- No automatic ET0 fallback (e.g. Hargreaves–Samani) if core weather inputs
  are missing — a future, opt-in, disabled-by-default option.
- No backdating of recorded irrigation, and no retroactive recalculation of
  past balances when a previously uncalibrated source is later calibrated.
- Soil heat flux (G) is assumed 0 on a daily basis, per FAO-56.
- Solar radiation is an integral of instantaneous samples — its accuracy
  depends on your station's update frequency.

## ⚠️ Estimates vs. measurements

There is no flow meter and no tank level sensor. Every liter/mm figure shown
by this integration is an **estimate**, derived from a user-calibrated `mm
per minute` rate per zone and source. Only entity states from your existing
Ecowitt/WH51 sensors are real measurements; everything else (ET0, ETc,
deficit, recommended mm/minutes/liters) is a **model output**, not a physical
measurement. **This integration never actuates any hardware in v1** — it only
reads, computes, and recommends.

## Disclaimer

This integration is a decision-support aid. It does not replace visual
inspection of the lawn, manual verification of the hydraulic system, or your
own judgment about when and how much to water.

## Status

Milestones 1–9 are implemented: scaffold, weather aggregation, the FAO-56
engine, the water balance, the full sensor/binary_sensor platform, manual
cycle recording, the recommendation engine + scheduler, and
mode/calibration/declared-cycle controls. The notification system built in
Milestone 8 was later removed entirely (see `CHANGELOG.md`); stale
weather/WH51 detection remains, surfaced only via Repairs. See `CLAUDE.md`
for architecture invariants and `CHANGELOG.md` for what shipped in each
milestone.

## Documentation

- `docs/agronomy.md` — the water balance: deficit, TAW/RAW, effective rain,
  the weekly cap.
- `docs/calibration.md` — the WH51 calibration window and its explicit
  start/finish override.
- `docs/fao56.md` — the FAO-56 ET0 formula as implemented, inputs, and
  approximations.
- `dashboards/gardenirrigation.yaml` — an example Lovelace dashboard (core
  cards only).

## Development

```bash
uv sync --extra test
uv run pytest
uv run ruff check .
uv run mypy custom_components
```

See `CLAUDE.md` for project-wide rules and invariants that must not be
violated when contributing.
