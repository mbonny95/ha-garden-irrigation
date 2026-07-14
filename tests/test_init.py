"""Tests for garden_irrigation entry setup/unload/reload."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation import SERVICE_TEST_TELEGRAM
from custom_components.garden_irrigation.const import DOMAIN, ZONE_1
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.notify import translate

from .const import (
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


def _full_entry_data() -> dict:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        **telegram_step_input(),
    }


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """The entry loads cleanly and creates/removes its coordinator on unload."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]


async def test_reload_entry(hass: HomeAssistant) -> None:
    """Reloading the entry (e.g. after an options change) succeeds cleanly."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]


# ---------------------------------------------------------------------------
# test_telegram: diagnostic-only Telegram/notifier test service
# ---------------------------------------------------------------------------


async def test_test_telegram_service_registered_and_removed_with_entry(
    hass: HomeAssistant,
) -> None:
    """The service exists once the entry is loaded, and is torn down on unload."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, SERVICE_TEST_TELEGRAM)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, SERVICE_TEST_TELEGRAM)


async def test_test_telegram_uses_default_message_and_notifier(
    hass: HomeAssistant,
) -> None:
    """With no `message` field, the notifier is called with the default text,
    a fixed title, and a stable notification_id - via coordinator.notifier,
    never through record_irrigation."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await hass.services.async_call(DOMAIN, SERVICE_TEST_TELEGRAM, {}, blocking=True)

    mock_send.assert_awaited_once_with(
        translate(hass, "test_telegram_default"),
        title="Garden Irrigation",
        notification_id="garden_irrigation_test_telegram",
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_test_telegram_forwards_custom_message(hass: HomeAssistant) -> None:
    """A provided `message` is forwarded verbatim instead of the default."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TEST_TELEGRAM,
            {"message": "Ciao dal test"},
            blocking=True,
        )

    mock_send.assert_awaited_once_with(
        "Ciao dal test",
        title="Garden Irrigation",
        notification_id="garden_irrigation_test_telegram",
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_test_telegram_has_no_side_effects_on_irrigation_domain(
    hass: HomeAssistant,
) -> None:
    """The service never records irrigation, never touches the balance
    ledger, and never triggers a coordinator refresh - only the notifier."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    deficit_before = coordinator.balance.current_deficit_mm(ZONE_1)

    with (
        patch.object(coordinator.notifier, "async_send", new=AsyncMock()),
        patch.object(
            coordinator.irrigation_log, "async_record_irrigation", new=AsyncMock()
        ) as mock_record_irrigation,
        patch.object(
            coordinator.balance, "record_irrigation"
        ) as mock_balance_record_irrigation,
        patch.object(
            GardenIrrigationCoordinator, "async_request_refresh", new=AsyncMock()
        ) as mock_refresh,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_TEST_TELEGRAM, {}, blocking=True)

        mock_record_irrigation.assert_not_awaited()
        mock_balance_record_irrigation.assert_not_called()
        mock_refresh.assert_not_awaited()

    assert coordinator.irrigation_log.events_for_zone(ZONE_1) == []
    assert coordinator.balance.current_deficit_mm(ZONE_1) == deficit_before

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
