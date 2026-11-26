# FAO-56 reference evapotranspiration (ET0)

Implemented in `custom_components/garden_irrigation/model/fao56.py`, a pure
Python module with no Home Assistant dependency. Equation numbers refer to
*FAO Irrigation and Drainage Paper No. 56* (Allen et al., 1998).

## Penman-Monteith, daily (eq. 6)

```
ET0 = [0.408 Δ (Rn − G) + γ 900/(T + 273) u2 (es − ea)] / [Δ + γ (1 + 0.34 u2)]
```

| Term | How it is obtained |
|---|---|
| T | (Tmax + Tmin) / 2 |
| es | mean of e°(Tmax), e°(Tmin) (eqs. 11–12) |
| ea | from RHmax and RHmin (eq. 17); RHmax only (eq. 18); RHmean (eq. 19) |
| Δ | slope of the vapour pressure curve at T (eq. 13) |
| P, γ | measured pressure, or from elevation (eq. 7); γ = 0.665·10⁻³ P (eq. 8) |
| u2 | wind at the anemometer height converted to 2 m (eq. 47), at least 0.5 m/s |
| Ra | extraterrestrial radiation from latitude and day of year (eqs. 21–25) |
| Rso | (0.75 + 2·10⁻⁵ z) Ra (eq. 37) |
| Rns | (1 − 0.23) Rs (eq. 38) |
| Rnl | eq. 39, with Rs/Rso limited to 1 |
| G | 0 for a daily step (eq. 42) |

ET0 is never negative. If an input is missing, ET0 is `unknown` and the
missing inputs are reported (`missing_inputs` attribute of *ET0 yesterday*).

Validated against the manual's worked examples: Example 18 (Brussels,
6 July: every intermediate term and ET0 = 3.9 mm/day), Example 8 (Ra at
20°S), Example 2 (pressure at 1800 m).

## Hargreaves (eq. 52), optional

`ET0 = 0.0023 (T + 17.8) (Tmax − Tmin)^0.5 · 0.408 Ra`

Used only when the *Hargreaves fallback* option is on (off by default) and
Penman-Monteith inputs are missing. The result is flagged as an estimate.

## Daily weather from Home Assistant statistics

`daily_weather.py` reads, once per closed local day, the recorder's
**hourly long-term statistics** of the source sensors, converted by the
recorder to °C, m/s, kPa and mm:

| FAO-56 input | From the hourly statistics |
|---|---|
| Tmax / Tmin | max of hourly max / min of hourly min |
| RHmax / RHmin / RHmean | max of max / min of min / mean of means |
| Rs (MJ m⁻² day⁻¹) | mean of hourly mean W/m² × 0.0864 |
| u (m/s), P (kPa) | mean of hourly means |
| Rain (mm) | sum of hourly changes of the rain counter |

A source with fewer than 20 hourly rows does not cover the day: the day is
marked **incomplete**, a Repair is raised and that input is treated as
missing (no value is invented). Rain uses whatever hours exist. Pressure is
optional and never makes a day incomplete.
