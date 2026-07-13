# Agronomy: water balance, TAW/RAW, effective rain, weekly cap

This describes exactly what `balance.py`/`recommendation.py` compute — not a
generic irrigation-theory primer.

## Deficit

Each zone (`zone_1`, `zone_2`) keeps a single persisted number: `deficit_mm`
— how far the root zone is below field capacity. It starts at 0 and is
updated **at most once per completed local calendar day**, at 05:30, for the
day that just ended (D-1, 00:00:00–23:59:59.999999):

```
ETc         = ET0 * Kc                                   # Kc = 0.95 (default)
eff_rain    = min(daily_rain * rain_factor, prev_deficit + ETc)
new_deficit = clamp(prev_deficit + ETc - eff_rain - recorded_irrigation_mm,
                     0, TAW)
```

- `ET0` comes from `et0.py` (see `fao56.md`); if it's unavailable for that
  day, the balance is **left untouched** and the day is **not** marked
  processed — it can still be applied later once the data is available. No
  guessed `ETc` is ever substituted.
- `recorded_irrigation_mm` is the sum of `garden_irrigation.record_irrigation`
  calls for that zone on that day, **only counting calibrated sources** (see
  below).
- The result is clamped to `[0, TAW]`: it can never go negative (over-full)
  or exceed the total available water.
- Idempotency: a second attempt to process an already-finalized day is a
  no-op that just reports the stored result (tracked via a per-zone
  `last_balance_date` marker) — the 20:00 job re-triggering a refresh, a
  Home Assistant restart, or a manual `recalculate` never double-applies a
  day.

## TAW / RAW

```
TAW = (root_depth_mm / 1000) * AWC_mm_per_m     # defaults: 150 mm, 200 mm/m
RAW = TAW * p                                   # p = 0.5 (default)
```

- **TAW** (Total Available Water): the maximum water the root zone can hold
  above wilting point, in mm.
- **RAW** (Readily Available Water): the fraction of TAW the plant can
  extract without stress. Irrigation is recommended once `deficit >= RAW`,
  not only once the soil is fully depleted at `TAW`.

`root_depth_mm`/`AWC_mm_per_m`/`p` are currently shared defaults (not yet a
per-zone options-flow override).

## Effective rain

`eff_rain = min(daily_rain * rain_factor, prev_deficit + ETc)` — two things
worth noting:

- **`rain_factor` (default 0.8)**: not all measured rainfall reaches and
  stays in the root zone (runoff, interception); this factor is a simple,
  documented approximation of that loss.
- **The cap at `prev_deficit + ETc`**: effective rain can never make the
  *new* deficit go negative — a very large rain event doesn't create
  "negative debt" that offsets future days: it's capped at whatever the zone
  actually needed that day, no more.

`24h_rainfall` and `rain_event` (if configured) are **diagnostic-only** and
are never summed into `eff_rain` — they would double-count against the
`daily_rainfall` accumulator that already covers the same period (see
`weather.py`'s reset-aware accumulator).

## Recorded irrigation and the weekly cap

`irrigation_7d_mm` is the sum of **user-recorded** irrigation for a zone over
a **sliding 7×24h window** (not the calendar week) — this is what the 30 mm
(default) weekly cap governs:

```
cap_remaining_mm = max(weekly_cap_mm - irrigation_7d_mm, 0)
recommended_mm   = min(deficit_mm, cap_remaining_mm)   # once deficit >= RAW
```

**Effective rain is deliberately excluded from the cap.** Rain is not
something the user controls, so limiting it would be meaningless; the cap's
actual purpose is to prevent the *operator* from over-watering. Effective
rain still reduces the deficit (see above) — it just isn't counted against,
or limited by, this cap. Both figures are shown side by side
(`sensor.irrigation_7d_<zone>` and `sensor.effective_rain_<zone>`) precisely
so this distinction is visible, not implied.

A **48-hour minimum interval** between recorded irrigations on the same zone
is also enforced as a limit on the recommendation (`min_interval_not_elapsed`
in `limits_applied`) — it does not block `record_irrigation` itself (you can
always log what you actually did), only the *recommendation* that would
suggest watering again too soon.

## Uncalibrated sources

If `mm_per_minute` is not set for a given zone+source (the rainwater tank is
the common case — no flow meter to calibrate it against), a recorded cycle
on that source is still logged (minutes, source, timestamp, notes preserved)
but:

- mm/liters are reported as **not calibrated** rather than a guessed number;
- the deficit is **not** decremented for that event.

Calibrating the source later does not retroactively recompute past events —
history is not rewritten.
