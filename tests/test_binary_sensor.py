"""Tests for the garden_irrigation binary_sensor platform (Milestone 7)."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.balance import ZoneBalanceResult
from custom_components.garden_irrigation.binary_sensor import (
    NeedsIrrigationZoneSensor,
    WeeklyCapReachedZoneSensor,
)
from custom_components.garden_irrigation.const import (
    DEFAULT_AWC_MM_PER_M,
    DEFAULT_P_DEPLETION_FRACTION,
    DEFAULT_ROOT_DEPTH_MM,
    DEFAULT_WEEKLY_CAP_MM,
    DOMAIN,
    ZONE_1,
    ZONE_2,
    ZONES,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator

from .const import (
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)

TAW_MM = (DEFAULT_ROOT_DEPTH_MM / 1000.0) * DEFAULT_AWC_MM_PER_M
RAW_MM = TAW_MM * DEFAULT_P_DEPLETION_FRACTION


def _full_entry_data() -> dict[str, Any]:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        **telegram_step_input(),
    }


def _coordinator(hass: HomeAssistant) -> GardenIrrigationCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    return GardenIrrigationCoordinator(hass, entry)


def _balance_result(
    *,
    deficit_mm: float = 20.0,
    irrigation_7d_mm: float = 0.0,
    weekly_cap_mm: float = DEFAULT_WEEKLY_CAP_MM,
    weekly_cap_reached: bool = False,
    applied: bool = True,
    skipped_reason: str | None = None,
) -> ZoneBalanceResult:
    return ZoneBalanceResult(
        zone_id=ZONE_1,
        day=date(2026, 6, 1),
        applied=applied,
        skipped_reason=skipped_reason,
        etc_mm=5.0 if applied else None,
        eff_rain_mm=0.0 if applied else None,
        irrigation_mm=0.0,
        deficit_mm=deficit_mm,
        taw_mm=TAW_MM,
        raw_mm=RAW_MM,
        irrigation_7d_mm=irrigation_7d_mm,
        weekly_cap_mm=weekly_cap_mm,
        weekly_cap_reached=weekly_cap_reached,
    )


# ---------------------------------------------------------------------------
# Full platform wiring: entities exist with correct unique_id/translation_key
# ---------------------------------------------------------------------------


async def test_all_expected_binary_sensor_entities_are_created(
    hass: HomeAssistant,
) -> None:
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    expected_unique_ids = [
        f"{entry.entry_id}_{key}_{zone_id}"
        for zone_id in ZONES
        for key in ("needs_irrigation", "weekly_cap_reached")
    ]
    for unique_id in expected_unique_ids:
        entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"missing entity for unique_id {unique_id}"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"


async def test_unique_ids_and_translation_keys(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    entry = coordinator.entry

    for zone_id in ZONES:
        needs = NeedsIrrigationZoneSensor(coordinator, entry, zone_id)
        assert needs.unique_id == f"{entry.entry_id}_needs_irrigation_{zone_id}"
        assert needs.translation_key == "needs_irrigation"
        assert needs.has_entity_name is True
        assert needs.device_info is not None

        cap = WeeklyCapReachedZoneSensor(coordinator, entry, zone_id)
        assert cap.unique_id == f"{entry.entry_id}_weekly_cap_reached_{zone_id}"
        assert cap.translation_key == "weekly_cap_reached"


# ---------------------------------------------------------------------------
# needs_irrigation: dry/wet/not-ready, availability, attributes
# ---------------------------------------------------------------------------


async def test_needs_irrigation_none_before_first_refresh(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)

    assert sensor.available is True
    assert sensor.is_on is None
    assert sensor.extra_state_attributes is None


async def test_needs_irrigation_true_when_dry_and_no_limits(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(deficit_mm=20.0)  # >= RAW_MM
    # Populate coordinator.data manually the way _async_update_data would.
    coordinator.data = {
        "recommendation": {
            ZONE_1: coordinator.recommendation.build(
                ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
            )
        },
        "balance": {ZONE_1: result},
    }

    sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["ready"] is True
    assert attrs["recommended_mm"] == pytest.approx(20.0)


async def test_needs_irrigation_false_when_wet(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(deficit_mm=5.0)  # < RAW_MM
    coordinator.data = {
        "recommendation": {
            ZONE_1: coordinator.recommendation.build(
                ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
            )
        },
        "balance": {ZONE_1: result},
    }

    sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert sensor.is_on is False


async def test_needs_irrigation_unknown_when_not_ready(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(applied=False, skipped_reason=None)
    coordinator.data = {
        "recommendation": {
            ZONE_1: coordinator.recommendation.build(
                ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
            )
        },
        "balance": {ZONE_1: result},
    }

    sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert sensor.is_on is None
    assert sensor.extra_state_attributes["ready"] is False


async def test_needs_irrigation_zone_2_independent_of_zone_1(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    dry_result = _balance_result(deficit_mm=20.0)
    wet_result = ZoneBalanceResult(
        zone_id=ZONE_2,
        day=date(2026, 6, 1),
        applied=True,
        skipped_reason=None,
        etc_mm=5.0,
        eff_rain_mm=0.0,
        irrigation_mm=0.0,
        deficit_mm=5.0,
        taw_mm=TAW_MM,
        raw_mm=RAW_MM,
        irrigation_7d_mm=0.0,
        weekly_cap_mm=DEFAULT_WEEKLY_CAP_MM,
        weekly_cap_reached=False,
    )
    coordinator.data = {
        "recommendation": {
            ZONE_1: coordinator.recommendation.build(
                ZONE_1, dry_result, today_et0_mm=5.0, today_rain_mm=0.0
            ),
            ZONE_2: coordinator.recommendation.build(
                ZONE_2, wet_result, today_et0_mm=5.0, today_rain_mm=0.0
            ),
        },
        "balance": {ZONE_1: dry_result, ZONE_2: wet_result},
    }

    zone1_sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)
    zone2_sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_2)
    assert zone1_sensor.is_on is True
    assert zone2_sensor.is_on is False


# ---------------------------------------------------------------------------
# weekly_cap_reached: directly reflects balance.py, no new logic
# ---------------------------------------------------------------------------


async def test_weekly_cap_reached_none_before_first_refresh(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    sensor = WeeklyCapReachedZoneSensor(coordinator, coordinator.entry, ZONE_1)

    assert sensor.available is True
    assert sensor.is_on is None
    assert sensor.extra_state_attributes is None


async def test_weekly_cap_reached_true(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM, weekly_cap_reached=True
    )
    coordinator.data = {"balance": {ZONE_1: result}}

    sensor = WeeklyCapReachedZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["irrigation_7d_mm"] == DEFAULT_WEEKLY_CAP_MM
    assert attrs["weekly_cap_mm"] == DEFAULT_WEEKLY_CAP_MM


async def test_weekly_cap_reached_false(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(irrigation_7d_mm=5.0, weekly_cap_reached=False)
    coordinator.data = {"balance": {ZONE_1: result}}

    sensor = WeeklyCapReachedZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert sensor.is_on is False


# ---------------------------------------------------------------------------
# Availability follows the coordinator's own update success (M5 precedent),
# never an artificial override.
# ---------------------------------------------------------------------------


async def test_availability_follows_coordinator_update_success(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    await coordinator.async_refresh()
    needs_sensor = NeedsIrrigationZoneSensor(coordinator, coordinator.entry, ZONE_1)
    cap_sensor = WeeklyCapReachedZoneSensor(coordinator, coordinator.entry, ZONE_1)
    assert needs_sensor.available is True
    assert cap_sensor.available is True

    with patch.object(
        coordinator, "_async_update_data", side_effect=RuntimeError("boom")
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert needs_sensor.available is False
    assert cap_sensor.available is False
