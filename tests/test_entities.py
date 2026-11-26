"""Tests for the sensor and binary_sensor entities."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.garden_irrigation.const import DOMAIN

from .common import ZONE_ID, import_day_statistics


@pytest.fixture(autouse=True)
async def rome_time(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Italian local time, 7 July 2026 at 06:00 (after the 05:30 run)."""
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 7, 7, 6, 0, tzinfo=dt_util.get_default_time_zone()))


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, domain: str, unique_id: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None, unique_id
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def _zone(hass: HomeAssistant, key: str, domain: str = "sensor") -> State:
    return _state(hass, domain, f"{ZONE_ID}_{key}")


async def _set_deficit(
    hass: HomeAssistant, entry: MockConfigEntry, deficit: float
) -> None:
    await entry.runtime_data.coordinator.async_set_deficit(ZONE_ID, deficit)
    await hass.async_block_till_done()


async def test_entities_before_the_deficit_is_set(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    assert _zone(hass, "deficit").state == STATE_UNKNOWN
    assert _zone(hass, "recommended_irrigation").state == STATE_UNKNOWN
    assert _zone(hass, "needs_irrigation", "binary_sensor").state == STATE_UNKNOWN
    reasons = _zone(hass, "needs_irrigation", "binary_sensor").attributes["reasons"]
    assert reasons == [{"code": "deficit_unknown"}]
    assert float(_zone(hass, "taw").state) == pytest.approx(23.25)
    assert float(_zone(hass, "raw").state) == pytest.approx(9.3)
    assert float(_zone(hass, "kc").state) == 0.95
    assert _zone(hass, "etc_yesterday").state == STATE_UNKNOWN
    assert _zone(hass, "last_irrigation").state == STATE_UNKNOWN


async def test_only_configured_sources_get_minutes(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    registry = er.async_get(hass)

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ZONE_ID}_recommended_minutes_mains"
    )
    assert not registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ZONE_ID}_recommended_minutes_tank"
    )


async def test_zone_entities_belong_to_the_zone(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    registry = er.async_get(hass)

    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{ZONE_ID}_deficit")
    assert entity_id is not None
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert entry.config_subentry_id == ZONE_ID
    assert entity_id == "sensor.small_lawn_soil_water_deficit"


async def test_recommendation_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    await _set_deficit(hass, config_entry, 12.0)

    deficit = _zone(hass, "deficit")
    assert float(deficit.state) == 12.0
    assert deficit.attributes["closed_deficit_mm"] == 12.0
    assert deficit.attributes["last_balance_date"] == "2026-07-06"
    assert deficit.attributes["raw_mm"] == 9.3

    assert _zone(hass, "needs_irrigation", "binary_sensor").state == STATE_ON

    recommended = _zone(hass, "recommended_irrigation")
    assert float(recommended.state) == 12.0
    assert recommended.attributes["estimate"] is True
    assert recommended.attributes["liters"] == 456
    assert recommended.attributes["blocks_mm"] == [6.0, 6.0]
    assert recommended.attributes["block_pause_min"] == 30
    assert recommended.attributes["reasons"] == [
        {"code": "deficit_reached_raw", "deficit_mm": 12.0, "raw_mm": 9.3}
    ]
    assert recommended.attributes["warnings"] == []

    minutes = _zone(hass, "recommended_minutes_mains")
    assert float(minutes.state) == 48.0
    assert minutes.attributes["block_minutes"] == [24.0, 24.0]
    assert minutes.attributes["rate_mm_per_min"] == 0.25


async def test_recording_irrigation_updates_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    await _set_deficit(hass, config_entry, 12.0)

    await config_entry.runtime_data.coordinator.async_record_irrigation(
        ZONE_ID, "mains", minutes=20
    )
    await hass.async_block_till_done()

    assert float(_zone(hass, "deficit").state) == pytest.approx(7.0)
    assert _zone(hass, "needs_irrigation", "binary_sensor").state == STATE_OFF
    assert float(_zone(hass, "recommended_irrigation").state) == 0.0
    assert float(_zone(hass, "irrigation_7d").state) == pytest.approx(5.0)
    assert dt_util.parse_datetime(_zone(hass, "last_irrigation").state) == (
        dt_util.now()
    )
    warnings = _zone(hass, "needs_irrigation", "binary_sensor").attributes["warnings"]
    assert warnings == []


async def test_weather_and_daily_values(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    import_day_statistics(hass, date(2026, 7, 6), rain_mm=3.0)
    await async_wait_recording_done(hass)
    await _setup(hass, config_entry)
    await _set_deficit(hass, config_entry, 5.0)
    config_entry.runtime_data.store.zone(ZONE_ID)["last_balance_date"] = "2026-07-05"
    await config_entry.runtime_data.coordinator.async_run_daily()
    await hass.async_block_till_done()

    entry_id = config_entry.entry_id
    et0 = _state(hass, "sensor", f"{entry_id}_et0_yesterday")
    assert float(et0.state) > 0
    assert et0.attributes["date"] == "2026-07-06"
    assert et0.attributes["method"] == "penman_monteith"
    assert et0.attributes["estimate"] is False
    assert float(_state(hass, "sensor", f"{entry_id}_rain_yesterday").state) == 3.0
    assert _state(hass, "sensor", f"{entry_id}_data_quality").state == "ok"

    etc = _zone(hass, "etc_yesterday")
    assert float(etc.state) == pytest.approx(float(et0.state) * 0.95)
    assert etc.attributes["date"] == "2026-07-06"
    assert float(_zone(hass, "effective_rain_yesterday").state) == pytest.approx(2.4)


async def test_data_quality_states(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    entry_id = config_entry.entry_id

    # Startup closed yesterday without any statistics.
    quality = _state(hass, "sensor", f"{entry_id}_data_quality")
    assert quality.state == "incomplete"
    assert "temperature_entity" in quality.attributes["incomplete_sources"]
    assert _state(hass, "sensor", f"{entry_id}_et0_yesterday").state == STATE_UNKNOWN

    config_entry.runtime_data.store.last_weather_day = None  # type: ignore[assignment]
    await config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    quality = _state(hass, "sensor", f"{entry_id}_data_quality")
    assert quality.state == "waiting"
    assert quality.attributes == {
        "device_class": "enum",
        "friendly_name": quality.attributes["friendly_name"],
        "options": ["ok", "incomplete", "waiting"],
    }
    rain = _state(hass, "sensor", f"{entry_id}_rain_yesterday")
    assert rain.state == STATE_UNKNOWN
    assert "date" not in rain.attributes
