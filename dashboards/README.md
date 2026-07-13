# Dashboards

`gardenirrigation.yaml` is an example Lovelace dashboard (Milestone 10),
built entirely from core Home Assistant cards (no custom cards). It only
displays entities that actually exist after Milestones 1–9: sensors,
binary_sensors, the `mode`/`active_cycle_zone` selects, and the
cycle/calibration buttons. There is no native manual-record form (no
`number`/`text` platform in this integration by design); the dashboard notes
how to call the `garden_irrigation.record_irrigation` action instead.

See the comment header in `gardenirrigation.yaml` for the entity_id
assumptions (default zone names) — adjust them if your instance differs.
