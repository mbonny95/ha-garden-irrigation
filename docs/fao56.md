# FAO-56 Penman–Monteith ET0, as implemented

Reference: Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop
evapotranspiration — Guidelines for computing crop water requirements.* FAO
Irrigation and Drainage Paper 56, chapter 3. Equation numbers below match
that document, and match the comments in `et0.py`.

## The equation

```
        0.408·Δ·Rn + γ·(900/(T+273))·u2·(es − ea)
ET0 = ─────────────────────────────────────────────
              Δ + γ·(1 + 0.34·u2)
```

`G` (soil heat flux) is taken as 0 — an accepted simplification on a daily
timestep (FAO-56 §3.2.2), not something the integration tries to estimate.

## Required daily inputs

Computed from one day's aggregated weather (`weather.py`'s
`DailyWeatherSnapshot` — either the just-finalized previous day, or today's
still-in-progress snapshot for the 20:00 preview):

| Symbol | From | Fallback if the ideal input is missing |
|---|---|---|
| `T_max`, `T_min` | daily temperature min/max | **none** — fundamental, ET0 is `unknown` without it |
| `RH_max`, `RH_min` (preferred) or `RH_mean` | daily humidity extremes/mean | if only mean RH is available, `ea` uses Eq. 19 instead of Eq. 17 (see below) |
| wind speed | daily time-weighted mean | **none** — fundamental |
| solar irradiance | integral of instantaneous W/m² over the day → MJ/m²/day | **none** — fundamental |
| pressure | daily mean absolute pressure | if not configured/available, estimated from configured altitude (Eq. 7) |
| latitude | `hass.config.latitude` | — |
| altitude | configured (default 116 m) | — |
| anemometer height | configured (default 2.0 m ⇒ no correction) | — |

If temperature, wind, solar irradiance, or **both** humidity forms are
missing, `et0.py` returns `incomplete=True` with the exact list of
`missing_inputs` and `et0_mm=None` — **no automatic fallback** (e.g.
Hargreaves–Samani) is applied in v1; a future opt-in method would be
disabled by default even once added.

## Step by step (matching `et0.py`)

1. `T_mean = (T_max + T_min) / 2`.
2. `es = (e°(T_max) + e°(T_min)) / 2`, with `e°(T) = 0.6108 · exp(17.27·T /
   (T+237.3))` (Eq. 11).
3. `ea`:
   - preferred (Eq. 17), when both `RH_min`/`RH_max` are available:
     `ea = (e°(T_min)·RH_max/100 + e°(T_max)·RH_min/100) / 2`;
   - fallback (Eq. 19), from mean RH only: `ea = (RH_mean/100) · es`.
4. `Δ = 4098 · e°(T_mean) / (T_mean + 237.3)²` (Eq. 13).
5. `γ = 0.000665 · P` (Eq. 8), with `P` in kPa either measured (absolute
   pressure ÷ 10, hPa → kPa) or, if not available, estimated from altitude
   (Eq. 7): `P = 101.3 · ((293 − 0.0065·z)/293)^5.26`.
6. `u2`: wind speed converted km/h → m/s, then corrected to 2 m height (Eq.
   47) only if the configured anemometer height isn't already 2 m:
   `u2 = u_z · 4.87 / ln(67.8·z − 5.42)`.
7. Radiation:
   - `Rs`: the configured solar-irradiance entity, **integrated** over the
     day (W/m² × elapsed seconds, summed, ÷ 1e6 → MJ/m²/day) — not a single
     instantaneous sample.
   - `Ra` (extraterrestrial radiation, Eq. 21): computed **astronomically**
     from `hass.config.latitude` and day-of-year (solar declination,
     inverse relative Earth–Sun distance, sunset hour angle) — no measured
     input needed.
   - `Rso = (0.75 + 2×10⁻⁵·z) · Ra` (clear-sky radiation).
   - `Rns = (1 − α) · Rs`, with `α = 0.23` (FAO-56 reference grass albedo,
     Eq. 38 — fixed, not configurable).
   - `Rnl = σ · ((T_max,K⁴ + T_min,K⁴)/2) · (0.34 − 0.14·√ea) · (1.35·min(Rs/Rso,
     1) − 0.35)` (Eq. 39), `σ = 4.903×10⁻⁹`.
   - `Rn = Rns − Rnl`.
8. `ET0` from the equation above.

Every intermediate term (`t_mean_c`, `es_kpa`, `ea_kpa`, `delta_kpa_per_c`,
`gamma_kpa_per_c`, `pressure_kpa` + its source, `u2_ms`, `rs_mj`, `ra_mj`,
`rso_mj`, `rns_mj`, `rnl_mj`, `rn_mj`) is kept on the result and surfaced as
`sensor.et0_daily`'s attributes, specifically so the computation is
auditable, not a black box.

## Practical approximations and limits, stated plainly

- **G = 0** daily — standard FAO-56 simplification, not zone-specific soil
  heat modeling.
- **Rs from instantaneous samples**: accuracy depends on how often your
  weather station reports solar irradiance; sparse updates make the
  time-weighted integral a rougher approximation of the true daily total.
- **α = 0.23 fixed**: the FAO-56 *reference grass* albedo is used, not a
  measured or lawn-specific value.
- **Ra is purely astronomical**: it does not account for real atmospheric
  turbidity/aerosols — this is exactly what FAO-56 itself specifies for
  reference ET0, not a shortcut specific to this integration.
- **Anemometer height is a configured assumption**: if the real installation
  height is wrong, `u2` will be systematically off. The default (2.0 m)
  applies no correction at all.
- **No sub-daily/hourly ET0**: this is a once-per-day computation on daily
  aggregates, consistent with FAO-56's daily method (not the hourly variant).
