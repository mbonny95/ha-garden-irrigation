# Garden Irrigation — custom cards

Two Lovelace cards for the `garden_irrigation` integration (v2):

- **`garden-irrigation-overview-card`** — ET0 and rain of yesterday, forecast
  rain (if configured), weather data quality with a link to Repairs, and one
  row per zone (status, recommended mm or deficit). Zones are discovered
  automatically.
- **`garden-irrigation-zone-card`** — one zone: decision, recommended mm and
  estimated liters, minutes per water source with the block plan, deficit bar
  against RAW/TAW, warnings as sentences, soil sensor status, the reason, the
  last closed day, irrigation of the last 7 days, and a form to **record an
  irrigation** (source + minutes, or mm for a source without a rate).

The cards find their entities on the zone device through the entity
registry, so entity ids can be renamed freely. Texts are in Italian or
English, following the Home Assistant language. Plain Web Components: no
build step, no dependency.

The only write is the `garden_irrigation.record_irrigation` action, with
the duration typed by you. Nothing operates hardware.

## Installation

1. Copy this folder into `config/www/` (files end up in
   `config/www/garden-irrigation-cards/`).
2. Settings → Dashboards → ⋮ → Resources → **Add resource**, type
   **JavaScript module**:
   - `/local/garden-irrigation-cards/garden-irrigation-zone-card.js?v=2.0.1`
   - `/local/garden-irrigation-cards/garden-irrigation-overview-card.js?v=2.0.1`

   The shared module and the editors are imported by these two files and
   must stay in the same folder.

   Home Assistant lets browsers cache `/local` files for 31 days: after
   copying a new version, change `?v=` in both resources to the new version
   (the cards' internal imports already carry it). If a card still says
   "Custom element doesn't exist", force-reload the page (Cmd/Ctrl+Shift+R)
   or, in the companion app, reset the frontend cache.
3. Add the cards from the dashboard card picker and choose the zone in the
   editor, or write YAML.

## Configuration

```yaml
type: custom:garden-irrigation-overview-card
title: Giardino            # optional
```

```yaml
type: custom:garden-irrigation-zone-card
device_id: 0123456789abcdef0123456789abcdef   # the zone device
name: Prato davanti         # optional, defaults to the device name
show_record_form: true      # optional, default true
```

The device id is the last part of the URL of the zone's device page
(Settings → Devices & services → Garden Irrigation → zone).

See `dashboards/gardenirrigation.yaml` for a complete example.
