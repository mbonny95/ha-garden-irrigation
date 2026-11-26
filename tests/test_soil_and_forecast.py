"""Tests for the soil moisture confirmation and the forecast rain."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN, SUBENTRY_TYPE_ZONE
from custom_components.garden_irrigation.coordinator import CoordinatorData
from custom_components.garden_irrigation.forecast import async_fetch_forecast_rain
from custom_components.garden_irrigation.sensor import (
    _forecast_attributes,
    _soil_attributes,
    _soil_status,
)
from custom_components.garden_irrigation.settings import ZoneConfig
from custom_components.garden_irrigation.soil_sensor import (
    SoilStatus,
    read_soil_sensor,
)

from .common import SOIL, WEATHER_INPUT, ZONE_ID, ZONE_INPUT, set_sensor

WEATHER = "weather.home"
NOW = datetime(2026, 7, 7, 18, 0, tzinfo=dt_util.UTC)


@pytest.fixture(autouse=True)
def frozen(freezer: FrozenDateTimeFactory) -> None:
    """A fixed 'now' for every test."""
    freezer.move_to(NOW)


def _zone(**overrides: Any) -> ZoneConfig:
    base = ZoneConfig(
        zone_id=ZONE_ID,
        name="Small lawn",
        area_m2=38,
        kc_monthly=(0.95,) * 12,
        awc_mm_per_m=155,
        max_block_mm=6,
        root_depth_mm=150,
        depletion_fraction=0.4,
        source_rates={"mains": 0.25},
        soil_moisture_entity=SOIL,
        soil_moisture_dry=40,
        soil_moisture_wet=68,
    )
    return replace(base, **overrides)


# --- Soil moisture sensor -------------------------------------------------------------


async def test_zone_without_sensor(hass: HomeAssistant) -> None:
    assert read_soil_sensor(hass, _zone(soil_moisture_entity=None), NOW) is None


@pytest.mark.parametrize("state", ["unavailable", "unknown", "n/a"])
async def test_unusable_states(hass: HomeAssistant, state: str) -> None:
    set_sensor(hass, SOIL, state, "%", None)

    result = read_soil_sensor(hass, _zone(), NOW)

    assert result is not None
    assert result.status is SoilStatus.UNAVAILABLE
    assert result.reading is None


async def test_missing_entity(hass: HomeAssistant) -> None:
    result = read_soil_sensor(hass, _zone(), NOW)

    assert result is not None
    assert result.status is SoilStatus.UNAVAILABLE


@pytest.mark.parametrize(
    ("value", "dry", "wet", "status"),
    [
        ("35", 40, 68, SoilStatus.DRY),
        ("40", 40, 68, SoilStatus.DRY),
        ("55", 40, 68, SoilStatus.OK),
        ("68", 40, 68, SoilStatus.WET),
        ("75", 40, 68, SoilStatus.WET),
        ("30", None, 68, SoilStatus.OK),
        ("75", 40, None, SoilStatus.OK),
        ("75", None, None, SoilStatus.NO_THRESHOLDS),
    ],
)
async def test_status_against_thresholds(
    hass: HomeAssistant,
    value: str,
    dry: float | None,
    wet: float | None,
    status: SoilStatus,
) -> None:
    set_sensor(hass, SOIL, value, "%", None)

    result = read_soil_sensor(
        hass, _zone(soil_moisture_dry=dry, soil_moisture_wet=wet), NOW
    )

    assert result is not None
    assert result.status is status
    assert result.reading is not None
    assert result.reading.value_pct == float(value)


async def test_stale_reading_is_not_used(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    set_sensor(hass, SOIL, "75", "%", None)
    freezer.tick(timedelta(hours=7))

    result = read_soil_sensor(hass, _zone(), dt_util.utcnow())

    assert result is not None
    assert result.status is SoilStatus.STALE
    assert result.value_pct == 75.0
    assert result.reading is None


# --- Forecast rain --------------------------------------------------------------------


def _weather_service(
    hass: HomeAssistant, forecast: list[dict[str, Any]], calls: list[str]
) -> None:
    async def handler(call: ServiceCall) -> dict[str, Any]:
        calls.append(call.data["type"])
        return {
            entity_id: {"forecast": forecast}
            for entity_id in cv.ensure_list(call.data["entity_id"])
        }

    hass.services.async_register(
        "weather", "get_forecasts", handler, supports_response=SupportsResponse.ONLY
    )


def _weather_state(hass: HomeAssistant, features: int, unit: str = "mm") -> None:
    hass.states.async_set(
        WEATHER,
        "rainy",
        {"supported_features": features, "precipitation_unit": unit},
    )


def _hourly(hours: int, mm: float | None) -> list[dict[str, Any]]:
    return [
        {"datetime": (NOW + timedelta(hours=h)).isoformat(), "precipitation": mm}
        for h in range(hours)
    ]


async def test_hourly_forecast_sums_next_24_hours(hass: HomeAssistant) -> None:
    calls: list[str] = []
    _weather_state(hass, features=3)
    _weather_service(hass, [*_hourly(30, 0.5), {"datetime": "bad"}], calls)

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert calls == ["hourly"]
    assert result.kind == "hourly"
    assert result.rain_mm == pytest.approx(12.0)
    assert result.fetched_at == NOW


async def test_hourly_forecast_without_values(hass: HomeAssistant) -> None:
    _weather_state(hass, features=2)
    _weather_service(hass, _hourly(5, None), [])

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm == 0.0


async def test_daily_forecast_uses_today(hass: HomeAssistant) -> None:
    calls: list[str] = []
    _weather_state(hass, features=1)
    _weather_service(
        hass,
        [{"datetime": NOW.isoformat(), "precipitation": 6.5}, {"precipitation": 9}],
        calls,
    )

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert calls == ["daily"]
    assert result.kind == "daily"
    assert result.rain_mm == 6.5


async def test_daily_forecast_without_precipitation(hass: HomeAssistant) -> None:
    _weather_state(hass, features=1)
    _weather_service(hass, [{"datetime": NOW.isoformat()}], [])

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm == 0.0


async def test_inches_are_converted(hass: HomeAssistant) -> None:
    _weather_state(hass, features=1, unit="in")
    _weather_service(hass, [{"datetime": NOW.isoformat(), "precipitation": 1.0}], [])

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm == pytest.approx(25.4)


async def test_empty_forecast_is_unknown(hass: HomeAssistant) -> None:
    _weather_state(hass, features=1)
    _weather_service(hass, [], [])

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm is None


async def test_missing_weather_entity(hass: HomeAssistant) -> None:
    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm is None
    assert result.kind is None


async def test_service_failure_is_unknown(hass: HomeAssistant) -> None:
    _weather_state(hass, features=1)  # no weather service registered

    result = await async_fetch_forecast_rain(hass, WEATHER, NOW)

    assert result.rain_mm is None


# --- Through the integration -----------------------------------------------------------


@pytest.fixture
def entry_with_extras(hass: HomeAssistant, weather_states: None) -> MockConfigEntry:
    """A zone with a soil sensor and thresholds, and a forecast entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden Irrigation",
        version=2,
        data=dict(WEATHER_INPUT),
        options={"forecast_entity": WEATHER},
        subentries_data=[
            {
                "subentry_id": ZONE_ID,
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "title": ZONE_INPUT["name"],
                "data": {
                    **ZONE_INPUT,
                    "soil_moisture_entity": SOIL,
                    "soil_moisture_dry": 40,
                    "soil_moisture_wet": 68,
                },
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


def _state(hass: HomeAssistant, unique_id: str) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None, unique_id
    return hass.states.get(entity_id)


def _warning_codes(hass: HomeAssistant) -> list[str]:
    state = _state(hass, f"{ZONE_ID}_recommended_irrigation")
    return [w["code"] for w in state.attributes["warnings"]]


async def test_soil_sensor_and_forecast_in_the_recommendation(
    hass: HomeAssistant, entry_with_extras: MockConfigEntry
) -> None:
    calls: list[str] = []
    _weather_state(hass, features=1)
    _weather_service(hass, [{"datetime": NOW.isoformat(), "precipitation": 8.0}], calls)
    set_sensor(hass, SOIL, "75", "%", None)
    assert await hass.config_entries.async_setup(entry_with_extras.entry_id)
    await hass.async_block_till_done()
    coordinator = entry_with_extras.runtime_data.coordinator

    await coordinator.async_set_deficit(ZONE_ID, 12.0)
    await hass.async_block_till_done()

    soil = _state(hass, f"{ZONE_ID}_soil_moisture_status")
    assert soil.state == "wet"
    assert soil.attributes["value_pct"] == 75.0
    assert soil.attributes["device_relative"] is True
    forecast = _state(hass, f"{entry_with_extras.entry_id}_forecast_rain")
    assert float(forecast.state) == 8.0
    assert forecast.attributes["informational_only"] is True
    assert forecast.attributes["entity_id"] == WEATHER
    assert _warning_codes(hass) == ["soil_sensor_wet", "rain_forecast"]
    # Warnings never change the amount.
    rec = _state(hass, f"{ZONE_ID}_recommended_irrigation")
    assert float(rec.state) == 12.0
    # The forecast is fetched at most once an hour.
    assert calls == ["daily"]


async def test_soil_sensor_change_refreshes_the_recommendation(
    hass: HomeAssistant, entry_with_extras: MockConfigEntry
) -> None:
    set_sensor(hass, SOIL, "75", "%", None)
    assert await hass.config_entries.async_setup(entry_with_extras.entry_id)
    await hass.async_block_till_done()
    await entry_with_extras.runtime_data.coordinator.async_set_deficit(ZONE_ID, 12.0)
    await hass.async_block_till_done()
    assert "soil_sensor_wet" in _warning_codes(hass)

    set_sensor(hass, SOIL, "50", "%", None)
    await hass.async_block_till_done()

    assert _state(hass, f"{ZONE_ID}_soil_moisture_status").state == "ok"
    assert "soil_sensor_wet" not in _warning_codes(hass)


async def test_optional_entities_absent_without_sensor_or_forecast(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ZONE_ID}_soil_moisture_status"
    )
    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{config_entry.entry_id}_forecast_rain"
    )


def test_attributes_without_data() -> None:
    data = CoordinatorData(zones={}, weather_day=None, forecast=None)
    assert _forecast_attributes(data) == {}
    assert _soil_status(SimpleNamespace(soil_sensor=None)) is None  # type: ignore[arg-type]
    assert _soil_attributes(SimpleNamespace(soil_sensor=None)) == {}  # type: ignore[arg-type]
