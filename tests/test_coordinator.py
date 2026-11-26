"""Tests for the daily balance, catch-up and recommendation data."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.garden_irrigation.const import DOMAIN
from custom_components.garden_irrigation.coordinator import (
    GardenIrrigationCoordinator,
)
from custom_components.garden_irrigation.daily_weather import DailyWeather
from custom_components.garden_irrigation.model.fao56 import Site, compute_et0
from custom_components.garden_irrigation.model.recommendation import Reason
from custom_components.garden_irrigation.services import device_links

from .common import RAIN, ZONE_ID, ZONE_INPUT, get_device, import_day_statistics

TAW = 23.25  # 150 mm × 155 mm/m (loam)
RAW = 9.3  # p = 0.40
KC_JULY = 0.95


# The weather that import_day_statistics produces, at the test site.
def expected_et0(day: date) -> float:
    """ET0 of a day imported with import_day_statistics."""
    et0 = compute_et0(
        DailyWeather(
            tmax_c=21.5,
            tmin_c=12.3,
            rh_max_pct=84,
            rh_min_pct=63,
            rh_mean_pct=72,
            solar_mj_m2=255.44 * 0.0864,
            wind_ms=2.078,
        ),
        Site(latitude_deg=45.5, elevation_m=116, anemometer_height_m=2.0),
        day,
        allow_hargreaves=False,
    ).et0_mm
    assert et0 is not None
    return et0


EXPECTED_ET0 = expected_et0(date(2026, 7, 6))
EXPECTED_ETC = EXPECTED_ET0 * KC_JULY


@pytest.fixture(autouse=True)
async def rome_time(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Italian local time, 7 July 2026 at 06:00 (after the 05:30 run)."""
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 7, 7, 6, 0, tzinfo=dt_util.get_default_time_zone()))


def _coordinator(entry: MockConfigEntry) -> GardenIrrigationCoordinator:
    return entry.runtime_data.coordinator


def _set_zone(
    entry: MockConfigEntry, deficit: float | None, last_balance: str | None
) -> None:
    state = entry.runtime_data.store.zone(ZONE_ID)
    state["deficit_mm"] = deficit
    state["last_balance_date"] = last_balance


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _statistics(hass: HomeAssistant, *days: date, rain_mm: float = 0.0) -> None:
    for day in days:
        import_day_statistics(hass, day, rain_mm=rain_mm)
    await async_wait_recording_done(hass)


async def test_zone_without_deficit_waits_for_the_user(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    snapshot = _coordinator(config_entry).data.zones[ZONE_ID]
    assert snapshot.deficit_mm is None
    assert snapshot.recommendation.needs_irrigation is None
    assert snapshot.recommendation.reasons[0].code == Reason.DEFICIT_UNKNOWN
    assert snapshot.soil.taw_mm == pytest.approx(TAW)
    assert snapshot.soil.raw_mm == pytest.approx(RAW)
    assert snapshot.kc_today == KC_JULY
    assert config_entry.runtime_data.store.zone(ZONE_ID)["days"] == []


async def test_startup_records_weather_and_raises_repairs(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    # No statistics at all for yesterday.
    await _setup(hass, config_entry)

    weather = _coordinator(config_entry).data.weather_day
    assert weather is not None
    assert weather["date"] == "2026-07-06"
    assert weather["et0_mm"] is None
    assert "rain_entity" in weather["incomplete"]
    assert len(issue_registry.issues) == 5


async def test_daily_balance_of_yesterday(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    await _statistics(hass, date(2026, 7, 6))
    await _setup(hass, config_entry)
    _set_zone(config_entry, 5.0, "2026-07-05")

    await _coordinator(config_entry).async_run_daily()

    state = config_entry.runtime_data.store.zone(ZONE_ID)
    assert state["last_balance_date"] == "2026-07-06"
    assert state["deficit_mm"] == pytest.approx(5.0 + EXPECTED_ETC)
    [day] = state["days"]
    assert day["date"] == "2026-07-06"
    assert day["et0_mm"] == pytest.approx(EXPECTED_ET0)
    assert day["etc_mm"] == pytest.approx(EXPECTED_ETC)
    assert day["incomplete"] == []
    assert day["et0_estimate"] is False
    weather = _coordinator(config_entry).data.weather_day
    assert weather is not None
    assert weather["et0_method"] == "penman_monteith"
    assert issue_registry.issues == {}

    # Running again the same day changes nothing (idempotent).
    await _coordinator(config_entry).async_run_daily()
    assert len(state["days"]) == 1


async def test_catch_up_of_missed_days(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _statistics(hass, date(2026, 7, 4), date(2026, 7, 5), date(2026, 7, 6))
    await _setup(hass, config_entry)
    _set_zone(config_entry, 0.0, "2026-07-03")
    config_entry.runtime_data.store.last_weather_day = None  # type: ignore[assignment]

    await _coordinator(config_entry).async_run_daily()

    state = config_entry.runtime_data.store.zone(ZONE_ID)
    assert [d["date"] for d in state["days"]] == [
        "2026-07-04",
        "2026-07-05",
        "2026-07-06",
    ]
    expected = sum(expected_et0(date(2026, 7, d)) for d in (4, 5, 6)) * KC_JULY
    assert state["deficit_mm"] == pytest.approx(expected)


async def test_yesterday_waits_for_the_run_time(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(datetime(2026, 7, 7, 5, 0, tzinfo=dt_util.get_default_time_zone()))
    await _statistics(hass, date(2026, 7, 5), date(2026, 7, 6))
    await _setup(hass, config_entry)
    _set_zone(config_entry, 0.0, "2026-07-04")

    await _coordinator(config_entry).async_run_daily()

    state = config_entry.runtime_data.store.zone(ZONE_ID)
    assert state["last_balance_date"] == "2026-07-05"


async def test_scheduled_run_at_run_time(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await _statistics(hass, date(2026, 7, 6), date(2026, 7, 7))
    await _setup(hass, config_entry)
    _set_zone(config_entry, 0.0, "2026-07-06")

    run_at = datetime(2026, 7, 8, 5, 30, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(run_at)
    async_fire_time_changed(hass, run_at)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    await hass.async_block_till_done()

    state = config_entry.runtime_data.store.zone(ZONE_ID)
    assert state["last_balance_date"] == "2026-07-07"


async def test_day_without_et0_applies_rain_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    import_day_statistics(hass, date(2026, 7, 6), rain_mm=5.0, sources=(RAIN,))
    await async_wait_recording_done(hass)
    await _setup(hass, config_entry)
    _set_zone(config_entry, 10.0, "2026-07-05")

    await _coordinator(config_entry).async_run_daily()

    [day] = config_entry.runtime_data.store.zone(ZONE_ID)["days"]
    assert day["et0_mm"] is None
    assert day["etc_mm"] is None
    assert day["rain_mm"] == pytest.approx(5.0)
    assert day["effective_rain_mm"] == pytest.approx(4.0)
    assert day["deficit_mm"] == pytest.approx(6.0)
    assert set(day["incomplete"]) == {
        "temperature_entity",
        "humidity_entity",
        "solar_radiation_entity",
        "wind_speed_entity",
    }
    assert len(issue_registry.issues) == 4


async def test_heavy_rain_resets_the_deficit(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _statistics(hass, date(2026, 7, 6), rain_mm=67.0)
    await _setup(hass, config_entry)
    _set_zone(config_entry, 12.0, "2026-07-05")

    await _coordinator(config_entry).async_run_daily()

    snapshot = _coordinator(config_entry).data.zones[ZONE_ID]
    assert snapshot.deficit_mm == 0.0
    assert snapshot.last_day is not None
    assert snapshot.last_day["rain_mm"] == pytest.approx(67.0)


async def test_recommendation_when_raw_is_reached(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    _set_zone(config_entry, 12.0, "2026-07-06")

    await _coordinator(config_entry).async_refresh()

    rec = _coordinator(config_entry).data.zones[ZONE_ID].recommendation
    assert rec.needs_irrigation is True
    assert rec.amount_mm == pytest.approx(12.0)
    assert rec.blocks_mm == pytest.approx((6.0, 6.0))
    assert rec.sources["mains"].total_minutes == pytest.approx(48.0)
    assert list(rec.sources) == ["mains"]


async def test_irrigation_lowers_current_deficit_until_the_day_is_closed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await _setup(hass, config_entry)
    _set_zone(config_entry, 12.0, "2026-07-06")
    coordinator = _coordinator(config_entry)

    await coordinator.async_record_irrigation(ZONE_ID, "mains", minutes=20)

    snapshot = coordinator.data.zones[ZONE_ID]
    assert snapshot.closed_deficit_mm == 12.0
    assert snapshot.pending_irrigation_mm == pytest.approx(5.0)
    assert snapshot.deficit_mm == pytest.approx(7.0)
    assert snapshot.irrigation_7d_mm == pytest.approx(5.0)
    assert snapshot.last_irrigation == dt_util.now()
    assert snapshot.recommendation.needs_irrigation is False

    # Next morning the irrigated day is closed: irrigation moves into it.
    await _statistics(hass, date(2026, 7, 7))
    freezer.move_to(datetime(2026, 7, 8, 6, 0, tzinfo=dt_util.get_default_time_zone()))
    await coordinator.async_run_daily()

    snapshot = coordinator.data.zones[ZONE_ID]
    assert snapshot.last_day is not None
    assert snapshot.last_day["irrigation_mm"] == pytest.approx(5.0)
    assert snapshot.pending_irrigation_mm == 0.0
    etc_july_7 = expected_et0(date(2026, 7, 7)) * KC_JULY
    assert snapshot.deficit_mm == pytest.approx(12.0 + etc_july_7 - 5.0)


async def test_irrigation_older_than_a_week_leaves_the_window(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await _setup(hass, config_entry)
    _set_zone(config_entry, 0.0, "2026-07-06")
    coordinator = _coordinator(config_entry)
    await coordinator.async_record_irrigation(ZONE_ID, "mains", mm=5.0)

    freezer.tick(timedelta(days=7, minutes=1))
    await coordinator.async_refresh()

    assert coordinator.data.zones[ZONE_ID].irrigation_7d_mm == 0.0


async def test_devices_for_installation_and_zones(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    await _setup(hass, config_entry)

    main = get_device(
        device_registry, (DOMAIN, config_entry.entry_id), config_entry.entry_id
    )
    zone = get_device(device_registry, (DOMAIN, ZONE_ID), config_entry.entry_id)
    assert main is not None
    assert zone is not None
    assert zone.name == ZONE_INPUT["name"]
    assert zone.via_device_id == main.id
    assert device_links(zone) == {config_entry.entry_id: {ZONE_ID}}


async def test_retention_limits_catch_up(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    _set_zone(config_entry, 0.0, "2024-01-01")

    await _coordinator(config_entry).async_run_daily()

    days = config_entry.runtime_data.store.zone(ZONE_ID)["days"]
    assert len(days) == 365
    assert days[0]["date"] == "2025-07-07"
    assert days[-1]["date"] == "2026-07-06"


async def test_unknown_zone_is_rejected(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    with pytest.raises(ServiceValidationError):
        await _coordinator(config_entry).async_set_deficit("missing", 0.0)


async def test_renamed_zone_renames_its_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    await _setup(hass, config_entry)

    hass.config_entries.async_update_subentry(
        config_entry,
        config_entry.subentries[ZONE_ID],
        title="Front lawn",
        data={**ZONE_INPUT, "name": "Front lawn"},
    )
    await hass.async_block_till_done()

    zone = get_device(device_registry, (DOMAIN, ZONE_ID), config_entry.entry_id)
    assert zone is not None
    assert zone.name == "Front lawn"
