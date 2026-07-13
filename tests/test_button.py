"""Tests for the garden_irrigation button platform (Milestone 9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.balance import ZoneBalanceResult
from custom_components.garden_irrigation.button import (
    EndCycleButton,
    FinishCalibrationButton,
    StartCalibrationButton,
    StartCycleButton,
)
from custom_components.garden_irrigation.const import (
    DEFAULT_CALIBRATION_DAYS,
    DOMAIN,
    ZONE_1,
    ZONE_2,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.recommendation import _Wh51CalibrationState

from .const import (
    MOCK_ZONE1_SOIL_ENTITY,
    rain_step_input,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


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


# ---------------------------------------------------------------------------
# Start/end cycle: declarative state only, no side effects on the log/balance
# ---------------------------------------------------------------------------


async def test_start_cycle_sets_zone_and_timestamp(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)
    coordinator.selected_cycle_zone = ZONE_2
    button = StartCycleButton(coordinator, coordinator.entry)

    await button.async_press()

    assert coordinator.cycle_zone == ZONE_2
    assert coordinator.cycle_started_at == now


async def test_end_cycle_clears_state(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    start_button = StartCycleButton(coordinator, coordinator.entry)
    end_button = EndCycleButton(coordinator, coordinator.entry)
    await start_button.async_press()
    assert coordinator.cycle_zone is not None

    await end_button.async_press()

    assert coordinator.cycle_zone is None
    assert coordinator.cycle_started_at is None


async def test_start_cycle_uses_currently_selected_zone(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    button = StartCycleButton(coordinator, coordinator.entry)

    coordinator.selected_cycle_zone = ZONE_1
    await button.async_press()
    assert coordinator.cycle_zone == ZONE_1

    await EndCycleButton(coordinator, coordinator.entry).async_press()
    coordinator.selected_cycle_zone = ZONE_2
    await button.async_press()
    assert coordinator.cycle_zone == ZONE_2


async def test_declared_cycle_never_touches_irrigation_log_or_balance(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    deficit_before = coordinator.balance.current_deficit_mm(ZONE_1)

    await StartCycleButton(coordinator, coordinator.entry).async_press()
    await EndCycleButton(coordinator, coordinator.entry).async_press()

    assert coordinator.irrigation_log.events_for_zone(ZONE_1) == []
    assert coordinator.irrigation_log.events_for_zone(ZONE_2) == []
    assert coordinator.balance.current_deficit_mm(ZONE_1) == deficit_before


async def test_cycle_state_survives_setup_shutdown_roundtrip(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    await StartCycleButton(coordinator1, entry).async_press()
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    await coordinator2.async_setup()
    try:
        assert coordinator2.cycle_zone == ZONE_1
        assert coordinator2.cycle_started_at == now
    finally:
        await coordinator2.async_shutdown()


async def test_start_end_cycle_unique_ids_and_translation_keys(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    start = StartCycleButton(coordinator, coordinator.entry)
    end = EndCycleButton(coordinator, coordinator.entry)

    assert start.unique_id == f"{coordinator.entry.entry_id}_start_cycle"
    assert start.translation_key == "start_cycle"
    assert end.unique_id == f"{coordinator.entry.entry_id}_end_cycle"
    assert end.translation_key == "end_cycle"
    assert start.has_entity_name is True
    assert start.device_info is not None


# ---------------------------------------------------------------------------
# Calibration override: compatible with M7's automatic marker, no migration
# ---------------------------------------------------------------------------


async def test_start_calibration_resets_marker_and_clears_baseline(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)

    # Seed the state directly (as M7's automatic calibration would have left
    # it) rather than via build(), which schedules its own debounced store
    # save that could otherwise race with this button's immediate write.
    coordinator.recommendation._calibration[ZONE_1] = _Wh51CalibrationState(
        first_seen=now, baseline_min=40.0, baseline_max=40.0
    )

    later = now + timedelta(hours=1)
    freezer.move_to(later)
    button = StartCalibrationButton(coordinator, coordinator.entry, ZONE_1)
    await button.async_press()

    calibration = coordinator.recommendation._calibration[ZONE_1]
    assert calibration.first_seen == later
    assert calibration.baseline_min is None
    assert calibration.baseline_max is None


async def test_finish_calibration_forces_complete_keeping_observed_baseline(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)

    # Only 1 day into the automatic window (would not be complete for 13
    # more days), with a range already observed.
    coordinator.recommendation._calibration[ZONE_1] = _Wh51CalibrationState(
        first_seen=now, baseline_min=20.0, baseline_max=60.0
    )

    button = FinishCalibrationButton(coordinator, coordinator.entry, ZONE_1)
    await button.async_press()

    calibration = coordinator.recommendation._calibration[ZONE_1]
    assert calibration.baseline_min == 20.0
    assert calibration.baseline_max == 60.0
    assert calibration.first_seen is not None
    assert now >= calibration.first_seen + timedelta(days=DEFAULT_CALIBRATION_DAYS)

    # The next build() call reports it as calibrated using the kept baseline.
    result = ZoneBalanceResult(
        zone_id=ZONE_1,
        day=now.date(),
        applied=True,
        skipped_reason=None,
        etc_mm=5.0,
        eff_rain_mm=0.0,
        irrigation_mm=0.0,
        deficit_mm=5.0,
        taw_mm=30.0,
        raw_mm=15.0,
        irrigation_7d_mm=0.0,
        weekly_cap_mm=30.0,
        weekly_cap_reached=False,
    )
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "58", {"unit_of_measurement": "%"})
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )
    assert bundle.final.wh51_calibrated is True


async def test_finish_calibration_without_any_observed_baseline_is_a_no_op(
    hass: HomeAssistant,
) -> None:
    """No reading ever observed: forcing "finished" invents nothing."""
    coordinator = _coordinator(hass)
    button = FinishCalibrationButton(coordinator, coordinator.entry, ZONE_1)

    await button.async_press()

    calibration = coordinator.recommendation._calibration[ZONE_1]
    assert calibration.baseline_min is None
    assert calibration.baseline_max is None


async def test_calibration_override_only_affects_the_targeted_zone(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)

    await StartCalibrationButton(coordinator, coordinator.entry, ZONE_1).async_press()

    assert coordinator.recommendation._calibration[ZONE_2].first_seen is None


async def test_calibration_buttons_unique_ids_and_translation_keys(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    start = StartCalibrationButton(coordinator, coordinator.entry, ZONE_1)
    finish = FinishCalibrationButton(coordinator, coordinator.entry, ZONE_2)

    assert start.unique_id == f"{coordinator.entry.entry_id}_start_calibration_{ZONE_1}"
    assert start.translation_key == "start_calibration"
    assert finish.unique_id == (
        f"{coordinator.entry.entry_id}_finish_calibration_{ZONE_2}"
    )
    assert finish.translation_key == "finish_calibration"
