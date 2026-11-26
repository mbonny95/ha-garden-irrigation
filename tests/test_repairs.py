"""Tests for repair issues."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.garden_irrigation.const import DOMAIN
from custom_components.garden_irrigation.daily_weather import DayWeather
from custom_components.garden_irrigation.model.fao56 import DailyWeather
from custom_components.garden_irrigation.repairs import (
    async_clear_issues,
    async_update_source_issues,
    source_issue_id,
)

from .common import RAIN, SOLAR, WEATHER_INPUT

SOURCES = {k: v for k, v in WEATHER_INPUT.items() if k.endswith("_entity")}


def _day(incomplete: tuple[str, ...], hours: dict[str, int]) -> DayWeather:
    return DayWeather(
        day=date(2026, 11, 25),
        weather=DailyWeather(tmax_c=None, tmin_c=None),
        rain_mm=0.0,
        hours=hours,
        incomplete=incomplete,
    )


async def test_issue_created_and_removed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    async_update_source_issues(
        hass, SOURCES, _day(("solar_radiation_entity",), {"solar_radiation_entity": 7})
    )

    issue = issue_registry.async_get_issue(
        DOMAIN, source_issue_id("solar_radiation_entity")
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "source_incomplete"
    assert issue.translation_placeholders == {
        "entity_id": SOLAR,
        "hours": "7",
        "day": "2026-11-25",
    }
    assert len(issue_registry.issues) == 1

    async_update_source_issues(hass, SOURCES, _day((), {}))

    assert issue_registry.issues == {}


async def test_missing_hours_default_to_zero(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    async_update_source_issues(hass, SOURCES, _day(("rain_entity",), {}))

    issue = issue_registry.async_get_issue(DOMAIN, source_issue_id("rain_entity"))
    assert issue is not None
    assert issue.translation_placeholders == {
        "entity_id": RAIN,
        "hours": "0",
        "day": "2026-11-25",
    }


async def test_clear_issues(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    async_update_source_issues(
        hass, SOURCES, _day(("rain_entity", "wind_speed_entity"), {})
    )
    assert len(issue_registry.issues) == 2

    async_clear_issues(hass)

    assert issue_registry.issues == {}
