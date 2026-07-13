# WH51 calibration: device-relative, not absolute soil moisture

## Why calibration exists

The WH51 is a **capacitive** soil-moisture probe. Its reported `%` depends on
the specific soil, probe depth/contact, and installation — it is **not** an
absolute volumetric water content (VWC) comparable across probes or gardens.
What *is* meaningful is where a current reading sits **relative to the range
this specific probe has actually observed** for this specific zone.

## The automatic 14-day window (Milestone 7)

For each zone, the integration keeps a persisted baseline:
`first_seen` (timestamp), `baseline_min`, `baseline_max` (the widest range of
`%` values observed so far). This baseline widens every time a recommendation
is built and a valid reading is available — it is **sampled at refresh time**
(event-driven), not a continuous accumulator, which is an accepted
approximation consistent with the rest of this integration's architecture.

- `first_seen` is set automatically to the timestamp of the **first ever
  valid reading** observed for that zone — no user action required.
- For 14 days (`DEFAULT_CALIBRATION_DAYS`) from `first_seen`, the zone's WH51
  status is `diagnostic` only: informative, but never used to corroborate or
  contradict the deficit-based recommendation.
- Once 14 days have elapsed **and** a non-degenerate range has been observed
  (`baseline_max > baseline_min`), the zone is **calibrated**. The current
  reading's position within `[baseline_min, baseline_max]` (0 = driest ever
  seen, 1 = wettest ever seen) is classified as:

  | position          | status     |
  |-------------------|------------|
  | ≤ 0.1 (default)    | `critical` |
  | ≤ 0.3 (default)    | `dry`      |
  | 0.3 – 0.7 (default)| `moderate` |
  | ≥ 0.7 (default)    | `wet`      |

  (Thresholds are configurable defaults, not hardcoded constants.)

## The explicit override (Milestone 9)

Waiting out an automatic 14-day window is not always what you want — e.g.
after re-installing a probe, or when you already trust an observed range and
want to shorten the wait. Two per-zone buttons let you override the marker
directly, with no migration and no change to the classification logic above:

- **`button.start_calibration_<zone>`** — restarts the window from *now* and
  **clears** the previously observed baseline (`baseline_min`/`baseline_max`
  reset to unset). Use this when you want a clean slate, e.g. after
  reinstalling a probe: readings observed before the old baseline are not
  representative of the new installation.
- **`button.finish_calibration_<zone>`** — forces the zone to be considered
  calibrated **now**, keeping whatever `baseline_min`/`baseline_max` has
  already been observed. If nothing has been observed yet, this is a no-op
  with respect to calibrated status — there is no range to classify a
  position against, so no baseline is invented.

Both act on the **same** persisted marker the automatic window in Milestone 7
uses — there are two ways to set it (automatic-on-first-reading, or this
explicit override), not two separate mechanisms.

## What calibration is NOT

- It is **never a hard block**. Even a fully calibrated, "critical" WH51
  reading only ever **corroborates or contradicts** (with an explicit
  `warnings`/`reasons` entry) the deficit/RAW-based decision — it cannot flip
  `needs_irrigation` on its own.
- It does **not** produce an absolute VWC percentage anywhere in the UI. Every
  place WH51 status is shown, it is explicitly labeled relative
  (`wh51_status`, `wh51_percent`, `wh51_calibrated` — see
  `binary_sensor.needs_irrigation_<zone>`'s attributes).
