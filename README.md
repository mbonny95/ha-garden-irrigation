# garden-irrigation

Custom Home Assistant integration (`garden_irrigation`) that provides
**irrigation decision support** for two *Festuca arundinacea* lawn zones,
based on a FAO-56 Penman–Monteith daily water balance computed locally from
existing Ecowitt weather-station and WH51 soil-moisture entities.

## What this integration is

- A **decision-support tool**: it reads existing Home Assistant entities,
  computes ET0/ETc and a per-zone soil water deficit, and **recommends**
  irrigation (mm, minutes, liters).
- A **manual logbook**: after you physically water a zone (manual taps, manual
  source switch), you record what you did and the integration updates the
  water balance and per-source consumption counters.
- A **Telegram notifier** (optional, degrades gracefully to persistent
  notifications if not configured).

## What this integration is NOT (v1)

- **It does not control any hardware.** There are no valves, relays, flow
  meters, or tank-level sensors in this setup. Taps and the source switch
  (rainwater tank / mains water) are operated **manually** by the user.
  Nothing in this integration ever opens/closes a valve or starts a pump.
- **It does not use cloud services or external weather forecasts.** All
  computation is local, from entities you already have in Home Assistant.

## Estimates vs. measurements

There is no flow meter and no tank level sensor. Every liter/mm figure shown
by this integration is an **estimate**, derived from a user-calibrated
`mm per minute` rate per zone and source. Only entity states from your
existing Ecowitt/WH51 sensors are real measurements; everything else
(ET0, ETc, deficit, recommended mm/minutes/liters) is a **model output**,
not a physical measurement.

## Disclaimer

This integration is a decision-support aid. It does not replace visual
inspection of the lawn, manual verification of the hydraulic system, or your
own judgment about when and how much to water.

## Status

Milestone 1 (scaffold): config flow, skeleton coordinator, diagnostics, and a
single diagnostic sensor. Weather aggregation, the FAO-56 engine, the water
balance, the recommendation engine, manual-cycle recording, and Telegram
notifications are implemented in later milestones — see `CLAUDE.md` for the
full roadmap and architecture invariants.

## Development

```bash
uv sync --extra test
uv run pytest
uv run ruff check .
uv run mypy custom_components
```

See `CLAUDE.md` for project-wide rules and invariants that must not be
violated when contributing.
