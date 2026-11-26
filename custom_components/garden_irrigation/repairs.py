"""Repair issues: the only way the integration surfaces data problems."""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .daily_weather import REQUIRED_FIELDS, DayWeather

ISSUE_SOURCE_INCOMPLETE = "source_incomplete"


def source_issue_id(field: str) -> str:
    """Issue id of one weather source field."""
    return f"{ISSUE_SOURCE_INCOMPLETE}_{field}"


@callback
def async_update_source_issues(
    hass: HomeAssistant, sources: Mapping[str, str], day_weather: DayWeather
) -> None:
    """Raise an issue for each required source that did not cover the day.

    Issues of sources that covered the day are removed, so an issue always
    reflects the most recently closed day.
    """
    for field in REQUIRED_FIELDS:
        issue_id = source_issue_id(field)
        entity_id = sources.get(field)
        if entity_id is not None and field in day_weather.incomplete:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_SOURCE_INCOMPLETE,
                translation_placeholders={
                    "entity_id": entity_id,
                    "hours": str(day_weather.hours.get(field, 0)),
                    "day": day_weather.day.isoformat(),
                },
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def async_clear_issues(hass: HomeAssistant) -> None:
    """Remove every issue raised by the integration."""
    for field in REQUIRED_FIELDS:
        ir.async_delete_issue(hass, DOMAIN, source_issue_id(field))
