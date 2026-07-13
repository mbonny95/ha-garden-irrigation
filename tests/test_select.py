"""Tests for the garden_irrigation select platform (Milestone 9)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    DOMAIN,
    MODE_CALIBRATION,
    MODE_MONITORING,
    MODES,
    ZONE_1,
    ZONE_2,
    ZONES,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.select import ActiveCycleZoneSelect, ModeSelect

from .const import (
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
# Mode select: only calibration/monitoring, never automation
# ---------------------------------------------------------------------------


async def test_mode_options_are_only_calibration_and_monitoring(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    entity = ModeSelect(coordinator, coordinator.entry)

    assert entity.options == [MODE_CALIBRATION, MODE_MONITORING]
    assert set(entity.options) == {"calibration", "monitoring"}


async def test_no_automation_option_anywhere_in_modes() -> None:
    """MODES (const.py) itself must never grow an automation entry."""
    assert "automation" not in MODES
    assert all("automation" not in mode for mode in MODES)


async def test_mode_select_unique_id_and_translation_key(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    entity = ModeSelect(coordinator, coordinator.entry)

    assert entity.unique_id == f"{coordinator.entry.entry_id}_mode"
    assert entity.translation_key == "mode"
    assert entity.has_entity_name is True
    assert entity.device_info is not None


async def test_mode_select_default_is_calibration(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    entity = ModeSelect(coordinator, coordinator.entry)

    assert entity.current_option == MODE_CALIBRATION
    assert entity.available is True


async def test_mode_select_change_updates_coordinator(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    entity = ModeSelect(coordinator, coordinator.entry)

    await entity.async_select_option(MODE_MONITORING)

    assert coordinator.mode == MODE_MONITORING
    assert entity.current_option == MODE_MONITORING


async def test_mode_survives_setup_shutdown_roundtrip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    await coordinator1.async_set_mode(MODE_MONITORING)
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    await coordinator2.async_setup()
    try:
        assert coordinator2.mode == MODE_MONITORING
    finally:
        await coordinator2.async_shutdown()


async def test_mode_change_does_not_alter_balance_or_recommendation(
    hass: HomeAssistant,
) -> None:
    """Changing mode is purely UX/status - it must never touch the deficit."""
    coordinator = _coordinator(hass)
    coordinator.balance._deficit[ZONE_1] = 12.5
    entity = ModeSelect(coordinator, coordinator.entry)

    await entity.async_select_option(MODE_MONITORING)
    await entity.async_select_option(MODE_CALIBRATION)

    assert coordinator.balance.current_deficit_mm(ZONE_1) == 12.5


# ---------------------------------------------------------------------------
# Active cycle zone select
# ---------------------------------------------------------------------------


async def test_active_cycle_zone_options_are_the_two_zones(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    entity = ActiveCycleZoneSelect(coordinator, coordinator.entry)

    assert entity.options == ZONES
    assert set(entity.options) == {ZONE_1, ZONE_2}


async def test_active_cycle_zone_unique_id_and_translation_key(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    entity = ActiveCycleZoneSelect(coordinator, coordinator.entry)

    assert entity.unique_id == f"{coordinator.entry.entry_id}_active_cycle_zone"
    assert entity.translation_key == "active_cycle_zone"


async def test_active_cycle_zone_default_is_zone_1(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    entity = ActiveCycleZoneSelect(coordinator, coordinator.entry)

    assert entity.current_option == ZONE_1


async def test_active_cycle_zone_change_updates_coordinator(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    entity = ActiveCycleZoneSelect(coordinator, coordinator.entry)

    await entity.async_select_option(ZONE_2)

    assert coordinator.selected_cycle_zone == ZONE_2
    assert entity.current_option == ZONE_2


async def test_active_cycle_zone_survives_setup_shutdown_roundtrip(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    await coordinator1.async_set_selected_cycle_zone(ZONE_2)
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    await coordinator2.async_setup()
    try:
        assert coordinator2.selected_cycle_zone == ZONE_2
    finally:
        await coordinator2.async_shutdown()
