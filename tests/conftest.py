"""Shared fixtures for garden_irrigation tests."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN, SUBENTRY_TYPE_ZONE

from .common import WEATHER_INPUT, ZONE_ID, ZONE_INPUT, set_weather_states

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_setup(recorder_mock: Any, enable_custom_integrations: None) -> None:
    """In-memory recorder (a dependency) and custom integrations, every test.

    recorder_mock must be requested before anything that sets up `hass`.
    """


@pytest.fixture
def weather_states(hass: HomeAssistant) -> None:
    """Create valid weather source sensor states."""
    set_weather_states(hass)


@pytest.fixture
def config_entry(hass: HomeAssistant, weather_states: None) -> MockConfigEntry:
    """A main config entry with one zone subentry, not yet set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden Irrigation",
        version=2,
        data=dict(WEATHER_INPUT),
        subentries_data=[
            {
                "subentry_id": ZONE_ID,
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "title": ZONE_INPUT["name"],
                "data": dict(ZONE_INPUT),
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry
