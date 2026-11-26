# Dashboards

`gardenirrigation.yaml` is an example dashboard for the v2 integration:

- the **overview card** (yesterday's ET0 and rain, forecast, data quality
  with a link to Repairs, status of every zone);
- one **zone card** per zone (decision, recommended mm and minutes per
  source, deficit vs RAW/TAW, warnings, record-irrigation form);
- two buttons that set a zone's starting deficit to 0 (field capacity).

It needs the custom cards from `www/garden-irrigation-cards/` and the zone
device ids: replace the `REPLACE_WITH_ZONE_*_DEVICE_ID` placeholders, or
simply add the cards from the dashboard UI and pick each zone in the card
editor.
