# Calibration

Three things are yours to measure: the application rate of each water
source, the starting deficit, and (optionally) the soil moisture thresholds.

## Application rate (mm/min) per water source

Each zone has one rate per source, because pressure and flow differ between
mains water and a rainwater-tank pump.

**Catch-cup test** (recommended, one run per source):

1. Place 6–10 straight-sided cups or tins across the zone, including edges
   and the area between sprinklers.
2. Run the zone for a fixed time, e.g. 15 minutes, from one source.
3. Measure the water depth in each cup (mm), take the average.
4. Rate = average depth ÷ minutes. Example: 3.75 mm in 15 min → 0.25 mm/min.

With mains water you can cross-check with the meter: liters used ÷ area
(m²) ÷ minutes = mm/min (1 L over 1 m² = 1 mm). Mixed rotors and fixed
sprays in one zone spread water unevenly: the cup average is the honest
figure.

Leave a source empty if the zone is never watered from it: no minutes are
shown for it and recording with minutes is refused (millimeters still work).

## Starting deficit

A new zone waits until you set its deficit with
`garden_irrigation.set_deficit` (zone device, `deficit_mm`). The value is
the deficit **now**.

1. **Simplest**: the day after a soaking rain (more than TAW, e.g. > 25 mm)
   or a deep irrigation, set `0`.
2. **Estimate**: from the last soaking, add up each day's ETc minus
   effective rain and irrigation, never below 0 nor above TAW. Example with
   TAW = 23 mm: three dry days at ETc 4 mm → about 12 mm.
3. **The lawn as a hint**: footprints that stay, blue-grey colour → around
   or beyond RAW.

## Soil moisture sensor thresholds (e.g. WH51)

The percentage of these sensors is **device-relative**, not volumetric water
content: it depends on the probe, the soil and how it was inserted. It is
never converted into millimeters. The integration only compares it with two
thresholds that you choose per zone, and only to add warnings.

Read the thresholds from the sensor's history in Home Assistant:

| When | What you see | Use it as |
|---|---|---|
| Day of a heavy rain | the highest value (saturated) | upper reference |
| 24–48 h later, when the decline slows | field capacity | **wet** threshold, slightly below it |
| First lawn stress signs | the dry end | **dry** threshold |

Real example (26/11/2026, 67 mm of rain): 75 % on the small zone and 78 % on
the big one — the saturated values; the wet thresholds come from the
readings a day or two later. Each zone gets its own thresholds.

The sensor status entity shows *dry*, *between thresholds*, *wet*, *no
thresholds set*, *not updated* (no reading for 6 h) or *unavailable*. Stale
or unavailable readings are ignored.
