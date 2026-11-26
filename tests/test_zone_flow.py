"""Tests for the zone subentry flow."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import SUBENTRY_TYPE_ZONE

from .common import SOIL, ZONE_ID, ZONE_INPUT, set_sensor

NEW_ZONE: dict[str, Any] = {
    "name": "Big lawn",
    "area_m2": 72.0,
    "crop_profile": "cool_season_turf",
    "soil_type": "clay",
    "root_depth_mm": 150.0,
    "depletion_fraction": 0.4,
    "rate_mains_mm_per_min": 0.175,
    "rate_tank_mm_per_min": 0.15,
}


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """The main entry, set up."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def _start_add(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def _configure(
    hass: HomeAssistant, flow_id: str, user_input: dict[str, Any]
) -> Any:
    result = await hass.config_entries.subentries.async_configure(flow_id, user_input)
    await hass.async_block_till_done()
    return result


def _zone_by_title(entry: MockConfigEntry, title: str) -> Any:
    return next(s for s in entry.subentries.values() if s.title == title)


async def test_add_zone_with_preset_profile(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    flow_id = await _start_add(hass, loaded_entry)
    result = await _configure(hass, flow_id, {**NEW_ZONE, "name": "  Big lawn "})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = _zone_by_title(loaded_entry, "Big lawn")
    assert zone.subentry_type == SUBENTRY_TYPE_ZONE
    assert zone.data["name"] == "Big lawn"
    # Preset profiles are resolved at runtime, never copied into the zone.
    assert "kc_monthly" not in zone.data


async def test_add_zone_with_custom_kc(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    flow_id = await _start_add(hass, loaded_entry)
    result = await _configure(hass, flow_id, {**NEW_ZONE, "crop_profile": "custom"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "kc"

    kc_input = {f"kc_{month:02d}": 0.5 + month / 100 for month in range(1, 13)}
    result = await _configure(hass, result["flow_id"], kc_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = _zone_by_title(loaded_entry, "Big lawn")
    assert zone.data["kc_monthly"] == [0.5 + m / 100 for m in range(1, 13)]


async def test_add_zone_with_soil_sensor_and_thresholds(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    flow_id = await _start_add(hass, loaded_entry)
    result = await _configure(
        hass,
        flow_id,
        {
            **NEW_ZONE,
            "soil_moisture_entity": SOIL,
            "soil_moisture_dry": 40,
            "soil_moisture_wet": 68,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        (
            {"rate_mains_mm_per_min": None, "rate_tank_mm_per_min": None},
            {"base": "no_rate"},
        ),
        (
            {"soil_type": "custom"},
            {
                "awc_mm_per_m": "required_for_custom_soil",
                "max_block_mm": "required_for_custom_soil",
            },
        ),
        ({"name": "SMALL LAWN"}, {"name": "name_exists"}),
        ({"name": "   "}, {"name": "name_required"}),
        (
            {"soil_moisture_dry": 40},
            {"soil_moisture_entity": "thresholds_without_sensor"},
        ),
        (
            {
                "soil_moisture_entity": SOIL,
                "soil_moisture_dry": 70,
                "soil_moisture_wet": 60,
            },
            {"soil_moisture_dry": "dry_not_below_wet"},
        ),
        (
            {"soil_moisture_entity": "sensor.temperature_like"},
            {"soil_moisture_entity": "wrong_unit"},
        ),
    ],
)
async def test_zone_validation(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    changes: dict[str, Any],
    errors: dict[str, str],
) -> None:
    set_sensor(hass, "sensor.temperature_like", "20", "°C")
    user_input = {k: v for k, v in {**NEW_ZONE, **changes}.items() if v is not None}
    flow_id = await _start_add(hass, loaded_entry)
    result = await _configure(hass, flow_id, user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_custom_soil_with_overrides(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    flow_id = await _start_add(hass, loaded_entry)
    result = await _configure(
        hass,
        flow_id,
        {**NEW_ZONE, "soil_type": "custom", "awc_mm_per_m": 140, "max_block_mm": 7},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_zone(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    result = await loaded_entry.start_subentry_reconfigure_flow(hass, ZONE_ID)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Keeping its own name is not a duplicate.
    result = await _configure(
        hass, result["flow_id"], {**ZONE_INPUT, "rate_tank_mm_per_min": 0.2}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert loaded_entry.subentries[ZONE_ID].data["rate_tank_mm_per_min"] == 0.2


async def test_reconfigure_zone_rename_and_custom_kc_defaults(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    result = await loaded_entry.start_subentry_reconfigure_flow(hass, ZONE_ID)
    result = await _configure(
        hass,
        result["flow_id"],
        {**ZONE_INPUT, "name": "Front lawn", "crop_profile": "custom"},
    )
    assert result["step_id"] == "kc"
    # Without a previous custom profile, the form starts from the preset.
    schema = result["data_schema"].schema
    defaults = {str(key): key.default() for key in schema}
    assert defaults["kc_01"] == 0.70
    assert defaults["kc_07"] == 0.95

    kc_input = {f"kc_{month:02d}": 0.9 for month in range(1, 13)}
    result = await _configure(hass, result["flow_id"], kc_input)

    assert result["reason"] == "reconfigure_successful"
    zone = loaded_entry.subentries[ZONE_ID]
    assert zone.title == "Front lawn"
    assert zone.data["kc_monthly"] == [0.9] * 12


async def test_switching_back_to_preset_drops_custom_kc(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    hass.config_entries.async_update_subentry(
        loaded_entry,
        loaded_entry.subentries[ZONE_ID],
        data={**ZONE_INPUT, "crop_profile": "custom", "kc_monthly": [0.8] * 12},
    )
    await hass.async_block_till_done()

    result = await loaded_entry.start_subentry_reconfigure_flow(hass, ZONE_ID)
    result = await _configure(hass, result["flow_id"], ZONE_INPUT)

    assert result["reason"] == "reconfigure_successful"
    assert "kc_monthly" not in loaded_entry.subentries[ZONE_ID].data
