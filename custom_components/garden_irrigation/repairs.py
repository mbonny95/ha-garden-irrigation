"""Repair issues for garden_irrigation.

Milestone 8 scope only: informational (non-fixable) repair issues for
conditions this integration can detect but that the user must resolve
outside Home Assistant (Telegram misconfiguration/failure, stale WH51/
weather data). None of these are `is_fixable` - there is no interactive fix
flow here, just an explanatory, translated issue. `ir.async_create_issue` is
itself idempotent (calling it again for the same issue_id replaces rather
than duplicates), so repeated monitor ticks never spam the Repairs UI; the
corresponding `async_clear_*` helper removes the issue once the underlying
condition resolves.

Deliberately NOT included (see the Milestone 8 report): a "source not
calibrated" repair. Leaving a zone's rainwater tank uncalibrated is a valid,
often intentional configuration choice (irrigation_log.py already handles it
gracefully - see its `calibrated` flag), not a fault to nag about.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ZONES

ISSUE_TELEGRAM_NOT_CONFIGURED = "telegram_not_configured"
ISSUE_TELEGRAM_TARGET_INVALID = "telegram_target_invalid"
ISSUE_TELEGRAM_SEND_FAILED = "telegram_send_failed"
ISSUE_WEATHER_STALE = "weather_stale"

_TELEGRAM_ISSUE_IDS = (
    ISSUE_TELEGRAM_NOT_CONFIGURED,
    ISSUE_TELEGRAM_TARGET_INVALID,
    ISSUE_TELEGRAM_SEND_FAILED,
)


def _wh51_stale_issue_id(zone_id: str) -> str:
    return f"wh51_stale_{zone_id}"


def _severity(level: str) -> ir.IssueSeverity:
    return ir.IssueSeverity.ERROR if level == "error" else ir.IssueSeverity.WARNING


def async_create_telegram_not_configured_issue(hass: HomeAssistant) -> None:
    """Neither an entity_id nor a config_entry_id+chat_id target is set."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_TELEGRAM_NOT_CONFIGURED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TELEGRAM_NOT_CONFIGURED,
    )


def async_create_telegram_target_invalid_issue(hass: HomeAssistant) -> None:
    """A target is configured, but its service (notify/telegram_bot) isn't available."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_TELEGRAM_TARGET_INVALID,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TELEGRAM_TARGET_INVALID,
    )


def async_create_telegram_send_failed_issue(hass: HomeAssistant) -> None:
    """A configured, available target rejected/failed the send call."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_TELEGRAM_SEND_FAILED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_TELEGRAM_SEND_FAILED,
    )


def async_clear_telegram_issues(hass: HomeAssistant) -> None:
    """Clear all Telegram-related issues (called after a successful send)."""
    for issue_id in _TELEGRAM_ISSUE_IDS:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def async_create_wh51_stale_issue(
    hass: HomeAssistant, zone_id: str, level: str
) -> None:
    """`level` is "warning" (>=3h) or "error" (>=12h) - see const.py thresholds."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _wh51_stale_issue_id(zone_id),
        is_fixable=False,
        severity=_severity(level),
        translation_key="wh51_stale",
        translation_placeholders={"zone_id": zone_id},
    )


def async_clear_wh51_stale_issue(hass: HomeAssistant, zone_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, _wh51_stale_issue_id(zone_id))


def async_create_weather_stale_issue(hass: HomeAssistant, level: str) -> None:
    """`level` is "warning" (>=30min) or "error" (>=2h) - see const.py thresholds."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_WEATHER_STALE,
        is_fixable=False,
        severity=_severity(level),
        translation_key=ISSUE_WEATHER_STALE,
    )


def async_clear_weather_stale_issue(hass: HomeAssistant) -> None:
    ir.async_delete_issue(hass, DOMAIN, ISSUE_WEATHER_STALE)


def async_clear_all_issues(hass: HomeAssistant) -> None:
    """Remove every issue this integration may have created (called on unload)."""
    async_clear_telegram_issues(hass)
    async_clear_weather_stale_issue(hass)
    for zone_id in ZONES:
        async_clear_wh51_stale_issue(hass, zone_id)
