# Water balance and recommendation

Implemented in `model/balance.py`, `model/recommendation.py`,
`model/soils.py` and `model/crops.py` (pure Python), orchestrated by
`coordinator.py`.

## Root-zone water

- **TAW** (total available water) = root depth (m) × AWC (mm/m).
- **RAW** (readily available water) = p × TAW. Below RAW the lawn is not
  stressed; at RAW it is time to water.
- **p** defaults to 0.40 (FAO-56 Table 22, cool-season turf). Optionally
  adjusted for the evaporative demand: p = p + 0.04 (5 − ETc), limited to
  0.1–0.8.

### Soils (FAO-56 Table 19, midpoint of θFC − θWP)

| Soil | AWC (mm/m) | Max block (mm) |
|---|---|---|
| Sand | 80 | 12 |
| Loamy sand | 90 | 10 |
| Sandy loam | 130 | 8 |
| Loam | 155 | 6 |
| Silt loam | 160 | 6 |
| Silt | 180 | 5 |
| Silty clay loam | 155 | 5 |
| Silty clay | 160 | 4 |
| Clay | 160 | 4 |

The *max block* (water per block before a soak pause) is a practical
starting point, not a FAO-56 value. Both values can be overridden per zone.

### Crop coefficient (Kc)

Cool-season turf (e.g. *Festuca arundinacea*), monthly:

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.70 | 0.70 | 0.80 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.80 | 0.70 | 0.70 |

0.95 in active growth is FAO-56 Table 12; the cold-season reductions are a
starting assumption to validate in the field. A custom 12-month profile can
be entered per zone.

## Daily step

For each closed day:

```
ETc            = ET0 × Kc(month)
effective rain = 0                                   if rain < threshold (2 mm)
               = min(rain × factor (0.8), deficit + ETc)   otherwise
deficit        = clamp(deficit + ETc − effective rain − irrigation, 0, TAW)
```

- Applied once per day (idempotent), at the daily run time, for the previous
  day; missed days are processed in order (up to 365).
- **Day without ET0** (weather incomplete): the day is still applied with
  ETc = 0, so its rain and irrigation are not lost, and it is flagged
  incomplete.
- **Current deficit** = deficit of the last closed day − irrigation recorded
  after it, so recording an irrigation updates the recommendation at once.

## Recommendation

- **Needs irrigation** when current deficit ≥ RAW.
- **Amount** = current deficit (refill to field capacity).
- **Blocks**: the fewest equal blocks not larger than the zone's max block,
  separated by the configured pause (30 min by default).
- **Minutes per source** = mm ÷ that source's application rate; **liters** =
  mm × area. All are estimates.

### Warnings (never change the amount)

| Code | When |
|---|---|
| `min_interval` | last irrigation more recent than the minimum interval (48 h) |
| `weekly_cap` | last 7 days + this amount above your optional weekly limit |
| `soil_sensor_wet` | model says water, soil sensor above your wet threshold |
| `soil_sensor_dry` | model says no, soil sensor at or below your dry threshold |
| `rain_forecast` | forecast rain in the next 24 h ≥ the effective-rain threshold |
| `no_source_rate` | no water source has an application rate |

The weekly limit is off by default: in summer a cool-season lawn can use
about 40 mm a week, so a fixed 30 mm cap would under-irrigate.
