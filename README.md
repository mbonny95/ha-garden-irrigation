# Garden Irrigation

Home Assistant custom integration (`garden_irrigation`) for **irrigation
decision support** based on the **FAO-56** daily soil water balance. It reads
your weather station from Home Assistant, computes the reference
evapotranspiration (ET0, Penman-Monteith) and a root-zone water deficit for
each lawn or garden zone, and tells you **when to water and how much**, in
millimeters and in minutes for each water source you use.

Everything is computed locally. Millimeters, minutes and liters are
**estimates** of the model, not measurements.

## What it does

- **Daily balance, FAO-56.** Every morning (05:30 by default) the previous day
  is closed: its weather is read from Home Assistant's long-term statistics,
  ET0 is computed and each zone's deficit is updated:
  `deficit = clamp(previous + ET0 × Kc − effective rain − irrigation, 0, TAW)`.
  Days missed while Home Assistant was off are caught up in order.
- **Recommendation per zone.** Irrigate when the deficit reaches the readily
  available water (RAW = p × TAW); the recommended amount refills the deficit,
  split into cycle-and-soak blocks sized for your soil, with minutes for each
  water source (e.g. mains and rainwater tank, each with its own measured
  application rate).
- **Explanations and warnings.** Every recommendation carries its reason and
  advisory warnings: minimum interval, optional weekly amount, soil moisture
  sensor disagreeing with the model, rain in the forecast. Warnings never
  change the amount.
- **Manual logbook.** After watering you record what you did (minutes or mm,
  source); the deficit and the recommendation update immediately.
- **Repairs** when a weather sensor did not cover a day. No notifications are
  ever sent.

## What it does NOT do

- **It never controls hardware.** No valves, pumps or relays: taps and the
  water source are operated by you.
- It does not call cloud services. An optional Home Assistant `weather`
  entity can be selected to show forecast rain, informationally.

## Requirements

- Home Assistant **2026.2** or newer, with the recorder (default).
- Weather station sensors in Home Assistant, each with a unit and a
  **state class** (the integration reads their long-term statistics):

  | Input | Unit (any convertible) | State class |
  |---|---|---|
  | Air temperature | °C, °F, K | `measurement` |
  | Relative humidity | % | `measurement` |
  | Solar radiation | W/m² | `measurement` |
  | Wind speed | m/s, km/h, mph, kn… | `measurement` |
  | Daily rain | mm, cm, in | `total` or `total_increasing` |
  | Pressure (optional) | hPa, kPa, inHg… | `measurement` |

- Optional: a soil moisture sensor per zone (e.g. Ecowitt WH51) and a
  `weather` entity for forecasts.

Developed with an Ecowitt GW1100 and two WH51 probes, but no brand is
assumed: you pick the entities.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add this repository as an
   **Integration**.
2. Install **Garden Irrigation** and restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Garden Irrigation*.

### Manual

Copy `custom_components/garden_irrigation` into `config/custom_components/`,
restart, then add the integration.

> Upgrading from v1: remove the v1 integration first. v2 does not migrate v1
> configuration or data (Home Assistant reports an old entry as a migration
> error).

## Setup

1. **Weather sources and site**: pick the sensors above, the anemometer
   height (wind is converted to 2 m) and check latitude/elevation.
2. **Add a zone** (integration page → *Add zone*), once per zone:
   - name and area (m²);
   - crop: *cool-season turf* (monthly Kc, FAO-56) or a custom 12-month Kc;
   - soil type (FAO-56 texture classes) or custom available water capacity;
   - root depth and depletion fraction p (0.40 for cool-season turf);
   - **application rate per water source** in mm/min (catch-cup test, see
     [docs/calibration.md](docs/calibration.md)); leave a source empty if
     the zone never uses it;
   - optional soil moisture sensor with your own dry/wet thresholds.
3. **Set the starting deficit** of each zone with the action
   `garden_irrigation.set_deficit` — `0` the day after a soaking rain. Until
   then the zone shows "starting deficit not set".
4. **Options** (any time): effective rain factor and threshold, daily run
   time, Hargreaves fallback, p adjustment for ETc, forecast entity, warning
   thresholds, pause between blocks.

## Entities

**Garden Irrigation device**: ET0 yesterday, rain yesterday, weather data
quality (`ok` / `incomplete` / `waiting`), forecast rain (if configured).

**Each zone device**:

| Entity | Meaning |
|---|---|
| Soil water deficit | mm missing to field capacity, now |
| Needs irrigation | on when the deficit reached RAW |
| Recommended irrigation | mm to apply (attributes: liters, blocks, pause, reasons, warnings) |
| Recommended minutes (mains / tank) | per configured source (attributes: minutes per block) |
| Irrigation last 7 days, Last irrigation | from your records |
| Diagnostics | TAW, RAW, Kc, ETc and effective rain of the last closed day, soil moisture sensor status |

Reasons and warnings are codes with values (e.g.
`{"code": "deficit_reached_raw", "deficit_mm": 12.0, "raw_mm": 9.3}`); the
custom cards turn them into sentences.

## Actions

- `garden_irrigation.record_irrigation` — `zone` (device), `source`
  (`mains`/`tank`), `minutes` **or** `mm`, optional `note`. Timestamp is now;
  returns the stored record.
- `garden_irrigation.set_deficit` — `zone` (device), `deficit_mm` (0 to TAW).

## Dashboard

`www/garden-irrigation-cards/` contains two custom cards (overview and
zone, with a record form); `dashboards/gardenirrigation.yaml` is an example
dashboard using them.

## Documentation

- [docs/fao56.md](docs/fao56.md) — ET0, inputs, daily weather from statistics.
- [docs/agronomy.md](docs/agronomy.md) — water balance, soils, Kc, recommendation, warnings.
- [docs/calibration.md](docs/calibration.md) — application rates, starting deficit, soil sensor thresholds.
- [docs/v2-spec.md](docs/v2-spec.md) — design specification (Italian).

## Disclaimer

A decision-support aid: it does not replace looking at your lawn or your own
judgment about when and how much to water.

## Development

```bash
uv sync --extra test --extra dev
uv run pytest
uv run ruff check .
uv run mypy custom_components
```

See `CLAUDE.md` for the project rules.
