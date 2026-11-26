"""Forecast rain from a user-selected Home Assistant weather entity.

Informational only: it adds a warning next to a recommendation and never
changes the balance or the recommended amount.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.components.weather import (
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TIME,
)
from homeassistant.components.weather.const import (
    ATTR_WEATHER_PRECIPITATION_UNIT,
    WeatherEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, UnitOfPrecipitationDepth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter

_LOGGER = logging.getLogger(__name__)

HORIZON = timedelta(hours=24)
KIND_HOURLY = "hourly"
KIND_DAILY = "daily"


@dataclass(frozen=True, slots=True)
class ForecastRain:
    """Rain expected in the next hours, in mm."""

    entity_id: str
    rain_mm: float | None
    kind: str | None  # hourly: next 24 h; daily: today's forecast
    fetched_at: datetime


async def async_fetch_forecast_rain(
    hass: HomeAssistant, entity_id: str, now: datetime
) -> ForecastRain:
    """Ask the weather entity for its forecast and total the rain.

    Hourly forecasts are summed over the next 24 hours; otherwise the first
    daily forecast is used. Any problem gives an unknown value.
    """
    state = hass.states.get(entity_id)
    if state is None:
        return ForecastRain(entity_id, None, None, now)
    features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
    kind = (
        KIND_HOURLY if features & WeatherEntityFeature.FORECAST_HOURLY else KIND_DAILY
    )
    unit = state.attributes.get(
        ATTR_WEATHER_PRECIPITATION_UNIT, UnitOfPrecipitationDepth.MILLIMETERS
    )

    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"type": kind},
            target={"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        _LOGGER.debug("Forecast from %s unavailable: %s", entity_id, err)
        return ForecastRain(entity_id, None, None, now)

    by_entity = cast(dict[str, Any], response or {})
    forecast = cast(
        list[dict[str, Any]], by_entity.get(entity_id, {}).get("forecast", [])
    )
    rain = _total_rain(forecast, kind, now)
    if rain is not None and unit != UnitOfPrecipitationDepth.MILLIMETERS:
        rain = DistanceConverter.convert(
            rain, unit, UnitOfPrecipitationDepth.MILLIMETERS
        )
    return ForecastRain(entity_id, rain, kind, now)


def _total_rain(
    forecast: list[dict[str, Any]], kind: str, now: datetime
) -> float | None:
    if not forecast:
        return None
    if kind == KIND_DAILY:
        value = forecast[0].get(ATTR_FORECAST_PRECIPITATION)
        return float(value) if value is not None else 0.0
    until = now + HORIZON
    total = 0.0
    for entry in forecast:
        when = dt_util.parse_datetime(str(entry.get(ATTR_FORECAST_TIME, "")))
        if when is None or when >= until:
            continue
        total += float(entry.get(ATTR_FORECAST_PRECIPITATION) or 0.0)
    return total
