"""Tests for the garden_irrigation notifier abstraction (Milestone 8)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation import repairs
from custom_components.garden_irrigation.const import (
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_CONFIG_ENTRY_ID,
    CONF_TELEGRAM_ENTITY_ID,
    DOMAIN,
    SOURCE_MAINS_WATER,
    ZONE_2,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.notify import (
    PersistentNotificationNotifier,
    TelegramNotifier,
    translate,
)

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


def _register_spy(
    hass: HomeAssistant, domain: str, service: str, *, raises: bool = False
) -> list[Mapping[str, Any]]:
    """Register a fake service that records call.data (or raises)."""
    calls: list[Mapping[str, Any]] = []

    async def _handler(call: ServiceCall) -> None:
        if raises:
            raise RuntimeError("boom")
        calls.append(call.data)

    hass.services.async_register(domain, service, _handler)
    return calls


def _issue(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


# ---------------------------------------------------------------------------
# TelegramNotifier: payload construction for both target styles
# ---------------------------------------------------------------------------


async def test_entity_id_target_calls_notify_send_message(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_TELEGRAM_ENTITY_ID: "notify.my_bot"}
    )
    calls = _register_spy(hass, "notify", "send_message")
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello", title="Title")

    assert len(calls) == 1
    assert calls[0]["entity_id"] == "notify.my_bot"
    assert calls[0]["message"] == "hello"
    assert calls[0]["title"] == "Title"


async def test_config_entry_chat_id_target_calls_telegram_bot_send_message(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TELEGRAM_CONFIG_ENTRY_ID: "abc123", CONF_TELEGRAM_CHAT_ID: "999"},
    )
    calls = _register_spy(hass, "telegram_bot", "send_message")
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello")

    assert len(calls) == 1
    assert calls[0]["config_entry_id"] == "abc123"
    assert calls[0]["target"] == ["999"]
    assert calls[0]["message"] == "hello"
    assert "title" not in calls[0]


async def test_entity_id_takes_precedence_over_chat_id_target(
    hass: HomeAssistant,
) -> None:
    """If both target styles are (inconsistently) present, entity_id wins."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TELEGRAM_ENTITY_ID: "notify.my_bot",
            CONF_TELEGRAM_CONFIG_ENTRY_ID: "abc123",
            CONF_TELEGRAM_CHAT_ID: "999",
        },
    )
    notify_calls = _register_spy(hass, "notify", "send_message")
    telegram_calls = _register_spy(hass, "telegram_bot", "send_message")
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello")

    assert len(notify_calls) == 1
    assert len(telegram_calls) == 0


# ---------------------------------------------------------------------------
# Degradation: never crashes, always falls back, raises the right repair
# ---------------------------------------------------------------------------


async def test_not_configured_falls_back_and_creates_issue(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    pn_calls = _register_spy(hass, "persistent_notification", "create")
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello")

    assert len(pn_calls) == 1
    assert pn_calls[0]["message"] == "hello"
    assert _issue(hass, "telegram_not_configured") is not None


async def test_target_configured_but_service_missing_falls_back(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_TELEGRAM_ENTITY_ID: "notify.missing"}
    )
    pn_calls = _register_spy(hass, "persistent_notification", "create")
    # Deliberately not registering notify.send_message.
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello")

    assert len(pn_calls) == 1
    assert _issue(hass, "telegram_target_invalid") is not None


async def test_send_failure_falls_back_and_creates_issue(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_TELEGRAM_ENTITY_ID: "notify.my_bot"}
    )
    _register_spy(hass, "notify", "send_message", raises=True)
    pn_calls = _register_spy(hass, "persistent_notification", "create")
    notifier = TelegramNotifier(hass, entry)

    await notifier.async_send("hello")

    assert len(pn_calls) == 1
    assert _issue(hass, "telegram_send_failed") is not None


async def test_successful_send_clears_telegram_issues(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_TELEGRAM_ENTITY_ID: "notify.my_bot"}
    )
    _register_spy(hass, "notify", "send_message")
    notifier = TelegramNotifier(hass, entry)
    repairs.async_create_telegram_send_failed_issue(hass)
    assert _issue(hass, "telegram_send_failed") is not None

    await notifier.async_send("hello")

    assert _issue(hass, "telegram_send_failed") is None


# ---------------------------------------------------------------------------
# PersistentNotificationNotifier: payload + never raises
# ---------------------------------------------------------------------------


async def test_persistent_notification_notifier_builds_payload_with_id(
    hass: HomeAssistant,
) -> None:
    calls = _register_spy(hass, "persistent_notification", "create")
    notifier = PersistentNotificationNotifier(hass)

    await notifier.async_send("hello", title="T", notification_id="abc")

    assert len(calls) == 1
    assert calls[0]["message"] == "hello"
    assert calls[0]["title"] == "T"
    assert calls[0]["notification_id"] == f"{DOMAIN}_abc"


async def test_persistent_notification_notifier_default_title(
    hass: HomeAssistant,
) -> None:
    calls = _register_spy(hass, "persistent_notification", "create")
    notifier = PersistentNotificationNotifier(hass)

    await notifier.async_send("hello")

    assert calls[0]["title"] == "Garden Irrigation"
    assert "notification_id" not in calls[0]


async def test_persistent_notification_notifier_never_raises(
    hass: HomeAssistant,
) -> None:
    _register_spy(hass, "persistent_notification", "create", raises=True)
    notifier = PersistentNotificationNotifier(hass)

    await notifier.async_send("hello")  # must not raise


# ---------------------------------------------------------------------------
# Message localization
# ---------------------------------------------------------------------------


async def test_translate_picks_italian(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    message = translate(hass, "morning_report_needs", zone_id="zone_1", mm=5.0)
    assert "irrigazione" in message.lower()


async def test_translate_defaults_to_english(hass: HomeAssistant) -> None:
    hass.config.language = "en"
    message = translate(hass, "morning_report_needs", zone_id="zone_1", mm=5.0)
    assert "irrigation" in message.lower()


async def test_translate_falls_back_to_english_for_unknown_language(
    hass: HomeAssistant,
) -> None:
    hass.config.language = "fr"
    message = translate(hass, "morning_report_ok", zone_id="zone_1")
    assert "no irrigation needed" in message.lower()


# ---------------------------------------------------------------------------
# Coordinator integration: "cycle recorded" confirmation (Milestone 8)
# ---------------------------------------------------------------------------


async def test_cycle_recorded_confirmation_sent_for_zone_2(hass: HomeAssistant) -> None:
    """irrigation_log.py is untouched: the coordinator detects the new event
    by diffing event ids and sends the confirmation itself (see coordinator.py)."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    try:
        with patch.object(
            coordinator.notifier, "async_send", new=AsyncMock()
        ) as mock_send:
            await coordinator.irrigation_log.async_record_irrigation(
                zone_id=ZONE_2, source=SOURCE_MAINS_WATER, duration_minutes=5.0
            )

        mock_send.assert_awaited_once()
        message = mock_send.await_args.args[0]
        assert "Zona 2" in message
        assert SOURCE_MAINS_WATER in message
    finally:
        await coordinator.async_shutdown()


async def test_preexisting_events_are_not_renotified_on_restart(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    await coordinator1.irrigation_log.async_record_irrigation(
        zone_id=ZONE_2, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    with patch.object(
        coordinator2, "notifier", new=AsyncMock(wraps=coordinator2.notifier)
    ) as mock_notifier:
        await coordinator2.async_setup()
        await coordinator2.async_refresh()
        mock_notifier.async_send.assert_not_awaited()
    await coordinator2.async_shutdown()
