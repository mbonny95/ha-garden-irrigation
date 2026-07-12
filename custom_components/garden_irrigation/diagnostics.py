"""Diagnostics support for garden_irrigation."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_TELEGRAM_CHAT_ID, CONF_TELEGRAM_CONFIG_ENTRY_ID, DOMAIN
from .coordinator import GardenIrrigationCoordinator

TO_REDACT = {CONF_TELEGRAM_CHAT_ID, CONF_TELEGRAM_CONFIG_ENTRY_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with Telegram target redacted."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": coordinator.data,
    }
