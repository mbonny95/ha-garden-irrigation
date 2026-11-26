"""Tests for the record_irrigation and set_deficit actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN

from .common import ZONE_ID


@pytest.fixture(autouse=True)
async def rome_time(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Italian local time, 7 July 2026 at 18:00."""
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(datetime(2026, 7, 7, 18, 0, tzinfo=dt_util.get_default_time_zone()))


@pytest.fixture
async def zone_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> str:
    """Set up the entry and return the zone's device id."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, ZONE_ID)})
    assert device is not None
    return device.id


async def _call(
    hass: HomeAssistant, service: str, data: dict[str, Any], *, response: bool = False
) -> Any:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=response
    )


async def test_record_irrigation_with_minutes(
    hass: HomeAssistant, config_entry: MockConfigEntry, zone_device: str
) -> None:
    result = await _call(
        hass,
        "record_irrigation",
        {"zone": zone_device, "source": "mains", "minutes": 15, "note": "test"},
        response=True,
    )

    assert result["mm"] == pytest.approx(3.75)
    assert result["minutes"] == 15
    assert result["source"] == "mains"
    assert result["note"] == "test"
    [record] = config_entry.runtime_data.store.zone(ZONE_ID)["irrigations"]
    assert record["timestamp"] == dt_util.now().isoformat()


async def test_record_irrigation_with_mm(
    hass: HomeAssistant, config_entry: MockConfigEntry, zone_device: str
) -> None:
    await _call(
        hass, "record_irrigation", {"zone": zone_device, "source": "mains", "mm": 5}
    )
    # The tank has no rate in this zone: mm are accepted, minutes unknown.
    await _call(
        hass, "record_irrigation", {"zone": zone_device, "source": "tank", "mm": 2}
    )

    records = config_entry.runtime_data.store.zone(ZONE_ID)["irrigations"]
    assert [(r["mm"], r["minutes"]) for r in records] == [(5.0, 20.0), (2.0, None)]


@pytest.mark.parametrize(
    ("data", "error"),
    [
        ({"source": "mains"}, "minutes_or_mm"),
        ({"source": "mains", "minutes": 5, "mm": 2}, "minutes_or_mm"),
        ({"source": "tank", "minutes": 5}, "source_rate_missing"),
    ],
)
async def test_record_irrigation_errors(
    hass: HomeAssistant, zone_device: str, data: dict[str, Any], error: str
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "record_irrigation", {"zone": zone_device, **data})

    assert err.value.translation_key == error


async def test_unknown_device(hass: HomeAssistant, zone_device: str) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_deficit", {"zone": "nope", "deficit_mm": 0})

    assert err.value.translation_key == "invalid_zone"


async def test_main_device_is_not_a_zone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zone_device: str,
    device_registry: dr.DeviceRegistry,
) -> None:
    main = device_registry.async_get_device({(DOMAIN, config_entry.entry_id)})
    assert main is not None

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_deficit", {"zone": main.id, "deficit_mm": 0})

    assert err.value.translation_key == "invalid_zone"


async def test_device_of_another_integration(
    hass: HomeAssistant, zone_device: str, device_registry: dr.DeviceRegistry
) -> None:
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "x")}
    )

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_deficit", {"zone": other.id, "deficit_mm": 0})

    assert err.value.translation_key == "invalid_zone"


async def test_entry_not_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry, zone_device: str
) -> None:
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_deficit", {"zone": zone_device, "deficit_mm": 0})

    assert err.value.translation_key == "not_loaded"


async def test_set_deficit(
    hass: HomeAssistant, config_entry: MockConfigEntry, zone_device: str
) -> None:
    await _call(hass, "set_deficit", {"zone": zone_device, "deficit_mm": 0})

    state = config_entry.runtime_data.store.zone(ZONE_ID)
    assert state["deficit_mm"] == 0.0
    assert state["last_balance_date"] == "2026-07-06"
    snapshot = config_entry.runtime_data.coordinator.data.zones[ZONE_ID]
    assert snapshot.deficit_mm == 0.0


async def test_set_deficit_counts_todays_irrigation(
    hass: HomeAssistant, config_entry: MockConfigEntry, zone_device: str
) -> None:
    await _call(
        hass, "record_irrigation", {"zone": zone_device, "source": "mains", "mm": 4}
    )
    await _call(hass, "set_deficit", {"zone": zone_device, "deficit_mm": 3})

    snapshot = config_entry.runtime_data.coordinator.data.zones[ZONE_ID]
    # What the user typed is the deficit now, after today's irrigation.
    assert snapshot.deficit_mm == pytest.approx(3.0)
    assert snapshot.closed_deficit_mm == pytest.approx(7.0)


async def test_set_deficit_above_taw(hass: HomeAssistant, zone_device: str) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_deficit", {"zone": zone_device, "deficit_mm": 30})

    assert err.value.translation_key == "deficit_above_taw"
    assert err.value.translation_placeholders == {"taw": "23.2"}
