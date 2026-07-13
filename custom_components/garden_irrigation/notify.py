"""Notifier abstraction for garden_irrigation.

Milestone 8 scope only: an abstract, degradable notifier used by the
scheduler's morning report, cycle-recorded confirmation, and monitor
advisories (see scheduler.py). `TelegramNotifier` sends via whichever target
the config flow already captured (Milestone 1 - `CONF_TELEGRAM_ENTITY_ID`, or
`CONF_TELEGRAM_CONFIG_ENTRY_ID` + `CONF_TELEGRAM_CHAT_ID`); if Telegram isn't
configured, its target service isn't available, or a send fails, it degrades
to `PersistentNotificationNotifier` and raises the matching repair issue
(repairs.py) - it never lets a notification failure crash the integration or
propagate (CLAUDE.md: "Never hard-depend on telegram_bot").
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import repairs
from .const import (
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_CONFIG_ENTRY_ID,
    CONF_TELEGRAM_ENTITY_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Centralized IT/EN templates for every outbound message this integration
# sends (scheduler.py's morning report/monitors, coordinator.py's cycle
# confirmation) - kept here since this module already owns "how a message
# gets sent"; this is "what it says". Not entity/config-flow strings (those
# stay in strings.json/translations, rendered by HA itself), just the
# free-text bodies handed to the notifier.
_MESSAGES: dict[str, dict[str, str]] = {
    "morning_report_title": {
        "en": "Garden Irrigation - Morning report",
        "it": "Garden Irrigation - Report mattutino",
    },
    "cycle_recorded_title": {
        "en": "Garden Irrigation - Cycle recorded",
        "it": "Garden Irrigation - Ciclo registrato",
    },
    "morning_report_needs": {
        "en": "{zone_id}: irrigation recommended, {mm:.1f} mm",
        "it": "{zone_id}: irrigazione consigliata, {mm:.1f} mm",
    },
    "morning_report_ok": {
        "en": "{zone_id}: no irrigation needed",
        "it": "{zone_id}: nessuna irrigazione necessaria",
    },
    "morning_report_not_ready": {
        "en": "{zone_id}: data not ready yet",
        "it": "{zone_id}: dati non ancora disponibili",
    },
    "cycle_recorded": {
        "en": "Cycle recorded: {zone_id}, {source}, {minutes:.1f} min, {mm:.2f} mm",
        "it": "Ciclo registrato: {zone_id}, {source}, {minutes:.1f} min, {mm:.2f} mm",
    },
    "cycle_recorded_uncalibrated": {
        "en": (
            "Cycle recorded: {zone_id}, {source}, {minutes:.1f} min "
            "(source not calibrated, deficit not updated)"
        ),
        "it": (
            "Ciclo registrato: {zone_id}, {source}, {minutes:.1f} min "
            "(sorgente non calibrata, deficit non aggiornato)"
        ),
    },
    "wh51_stale": {
        "en": "{zone_id}: soil moisture sensor not updating ({level})",
        "it": "{zone_id}: sensore umidità del suolo non aggiornato ({level})",
    },
    "weather_stale": {
        "en": "Weather data not updating ({level})",
        "it": "Dati meteo non aggiornati ({level})",
    },
    "wh51_battery_low": {
        "en": "{zone_id}: WH51 battery low ({percent:.0f}%)",
        "it": "{zone_id}: batteria WH51 scarica ({percent:.0f}%)",
    },
    "wh51_signal_low": {
        "en": "{zone_id}: WH51 signal weak",
        "it": "{zone_id}: segnale WH51 debole",
    },
    "wind_strong": {
        "en": "Strong wind: avg {avg:.1f} km/h, gust {gust:.1f} km/h",
        "it": "Vento forte: media {avg:.1f} km/h, raffica {gust:.1f} km/h",
    },
}


def _language(hass: HomeAssistant) -> str:
    return "it" if hass.config.language == "it" else "en"


def translate(hass: HomeAssistant, key: str, **kwargs: Any) -> str:
    """Render the IT/EN template `key` (see `_MESSAGES`) with `kwargs`."""
    template = _MESSAGES[key][_language(hass)]
    return template.format(**kwargs)


class Notifier(ABC):
    """Abstract notifier: send a message, degrading cleanly on any failure."""

    @abstractmethod
    async def async_send(
        self,
        message: str,
        *,
        title: str | None = None,
        level: str = "info",
        notification_id: str | None = None,
    ) -> None:
        """Send `message`. Must never raise - failures degrade internally."""


class PersistentNotificationNotifier(Notifier):
    """Fallback notifier: a dismissible `persistent_notification` card.

    `notification_id` (when given) makes repeated calls for the same logical
    message update the existing card instead of stacking up duplicates.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Bind to `hass`; nothing else to set up (stateless)."""
        self.hass = hass

    async def async_send(
        self,
        message: str,
        *,
        title: str | None = None,
        level: str = "info",
        notification_id: str | None = None,
    ) -> None:
        """Create (or replace) a persistent_notification; never raises."""
        service_data: dict[str, Any] = {
            "message": message,
            "title": title or "Garden Irrigation",
        }
        if notification_id:
            service_data["notification_id"] = f"{DOMAIN}_{notification_id}"
        try:
            await self.hass.services.async_call(
                "persistent_notification", "create", service_data, blocking=True
            )
        except Exception:
            _LOGGER.exception("Failed to create the persistent_notification fallback")


class TelegramNotifier(Notifier):
    """Sends via the configured Telegram target; degrades on failure/misconfiguration.

    Two target styles, matching the plan/config flow (Milestone 1):
      - `CONF_TELEGRAM_ENTITY_ID` set: calls `notify.send_message` targeting
        that notify entity (the modern per-entity notify service).
      - `CONF_TELEGRAM_CONFIG_ENTRY_ID` + `CONF_TELEGRAM_CHAT_ID` set: calls
        `telegram_bot.send_message` directly with that bot config entry and
        chat id as `target`.
    Neither configured -> `telegram_not_configured`. Configured but the
    target service isn't registered (integration not set up) ->
    `telegram_target_invalid`. Configured and available but the call itself
    fails -> `telegram_send_failed`. Any of these degrades to
    `PersistentNotificationNotifier`; a successful send clears all three.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Bind to `hass`/`entry` and build the persistent_notification fallback."""
        self.hass = hass
        self._entry = entry
        self._fallback = PersistentNotificationNotifier(hass)

    def _target_service(self) -> tuple[str, str, dict[str, Any]] | None:
        """Return (domain, service, base_service_data) for the configured
        target, or None if neither target style is configured."""
        data = self._entry.data
        entity_id = data.get(CONF_TELEGRAM_ENTITY_ID)
        if entity_id:
            return "notify", "send_message", {"entity_id": entity_id}

        config_entry_id = data.get(CONF_TELEGRAM_CONFIG_ENTRY_ID)
        chat_id = data.get(CONF_TELEGRAM_CHAT_ID)
        if config_entry_id and chat_id:
            return (
                "telegram_bot",
                "send_message",
                {"config_entry_id": config_entry_id, "target": [chat_id]},
            )

        return None

    async def async_send(
        self,
        message: str,
        *,
        title: str | None = None,
        level: str = "info",
        notification_id: str | None = None,
    ) -> None:
        """Send via Telegram; on any failure, degrade to persistent_notification."""
        target = self._target_service()
        if target is None:
            _LOGGER.debug(
                "Telegram not configured; falling back to persistent_notification"
            )
            repairs.async_create_telegram_not_configured_issue(self.hass)
            await self._fallback.async_send(
                message, title=title, level=level, notification_id=notification_id
            )
            return

        domain, service, service_data = target
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning(
                "Telegram target configured but %s.%s is not available; "
                "falling back to persistent_notification",
                domain,
                service,
            )
            repairs.async_create_telegram_target_invalid_issue(self.hass)
            await self._fallback.async_send(
                message, title=title, level=level, notification_id=notification_id
            )
            return

        service_data = {**service_data, "message": message}
        if title:
            service_data["title"] = title

        try:
            await self.hass.services.async_call(
                domain, service, service_data, blocking=True
            )
        except Exception:
            _LOGGER.warning(
                "Telegram send failed; falling back to persistent_notification",
                exc_info=True,
            )
            repairs.async_create_telegram_send_failed_issue(self.hass)
            await self._fallback.async_send(
                message, title=title, level=level, notification_id=notification_id
            )
            return

        repairs.async_clear_telegram_issues(self.hass)
