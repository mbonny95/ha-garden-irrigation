"""Tests for the garden_irrigation sensor platform (Milestones 1 and 5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPrecipitationDepth
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    DATA_QUALITY_INITIALIZING,
    DATA_QUALITY_NOT_CONFIGURED,
    DEFAULT_AWC_MM_PER_M,
    DEFAULT_KC,
    DEFAULT_P_DEPLETION_FRACTION,
    DEFAULT_RAIN_EFFECTIVE_FACTOR,
    DEFAULT_ROOT_DEPTH_MM,
    DEFAULT_WEEKLY_CAP_MM,
    DOMAIN,
    SOURCE_MAINS_WATER,
    ZONE_1,
    ZONE_2,
    ZONES,
)
from custom_components.garden_irrigation.coordinator import (
    GardenIrrigationCoordinator,
)
from custom_components.garden_irrigation.sensor import (
    DataQualitySensor,
    DeficitZoneSensor,
    EffectiveRainZoneSensor,
    Et0DailySensor,
    EtcZoneSensor,
    Irrigation7dZoneSensor,
    RawZoneSensor,
    TawZoneSensor,
)

from .const import (
    rain_step_input,
    setup_mock_weather_states,
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


# ---------------------------------------------------------------------------
# data_quality (Milestone 1, unchanged contract)
# ---------------------------------------------------------------------------


async def test_not_configured_before_first_refresh(hass: HomeAssistant) -> None:
    """Before any coordinator refresh, the sensor reports not_configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    sensor = DataQualitySensor(coordinator, entry)

    assert sensor.available is True
    assert sensor.native_value == DATA_QUALITY_NOT_CONFIGURED


async def test_initializing_after_first_refresh(hass: HomeAssistant) -> None:
    """After the coordinator's first (skeleton) refresh, state is initializing.

    Uses async_refresh() (a plain manual refresh) rather than
    async_config_entry_first_refresh(), which requires the config entry to be
    in SETUP_IN_PROGRESS state and is exercised end-to-end by
    test_sensor_always_available_via_full_setup below.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_refresh()
    sensor = DataQualitySensor(coordinator, entry)

    assert sensor.available is True
    assert sensor.native_value == DATA_QUALITY_INITIALIZING


async def test_sensor_always_available_via_full_setup(hass: HomeAssistant) -> None:
    """End-to-end: after entry setup the entity exists, is available, and
    reports initializing (never unavailable)."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_data_quality"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == DATA_QUALITY_INITIALIZING
    assert state.state != "unavailable"


# ---------------------------------------------------------------------------
# Milestone 5: full platform wiring (unique_id/translation_key/entity registry)
# ---------------------------------------------------------------------------

_ZONE_SENSOR_KEYS = ("etc", "deficit", "taw", "raw", "effective_rain", "irrigation_7d")


async def test_all_expected_sensor_entities_are_created(hass: HomeAssistant) -> None:
    """Every sensor described by the plan's data-backed subset exists after setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    expected_unique_ids = [
        f"{entry.entry_id}_data_quality",
        f"{entry.entry_id}_et0_daily",
    ]
    for zone_id in ZONES:
        expected_unique_ids += [
            f"{entry.entry_id}_{key}_{zone_id}" for key in _ZONE_SENSOR_KEYS
        ]

    for unique_id in expected_unique_ids:
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"missing entity for unique_id {unique_id}"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"


async def test_zone_sensor_unique_ids_and_translation_keys(hass: HomeAssistant) -> None:
    """unique_id/translation_key/translation_placeholders are stable and per-zone."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)

    sensor_classes = {
        "etc": EtcZoneSensor,
        "deficit": DeficitZoneSensor,
        "taw": TawZoneSensor,
        "raw": RawZoneSensor,
        "effective_rain": EffectiveRainZoneSensor,
        "irrigation_7d": Irrigation7dZoneSensor,
    }
    for key, cls in sensor_classes.items():
        for zone_id in ZONES:
            entity = cls(coordinator, entry, zone_id)
            assert entity.unique_id == f"{entry.entry_id}_{key}_{zone_id}"
            assert entity.translation_key == key
            assert entity._attr_translation_placeholders == {
                "zone_name": "Zona 1" if zone_id == ZONE_1 else "Zona 2"
            }
            assert entity.has_entity_name is True
            assert entity.device_info is not None


async def test_et0_daily_unique_id_and_unit(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    sensor = Et0DailySensor(coordinator, entry)

    assert sensor.unique_id == f"{entry.entry_id}_et0_daily"
    assert sensor.translation_key == "et0_daily"
    assert sensor.native_unit_of_measurement == UnitOfPrecipitationDepth.MILLIMETERS
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_et0_daily_none_before_first_refresh(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    sensor = Et0DailySensor(coordinator, entry)

    assert sensor.available is True
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None


async def test_zone_sensor_none_before_first_refresh(hass: HomeAssistant) -> None:
    """Before any coordinator.data exists, zone sensors report unknown, not
    a fabricated value (mirrors Et0DailySensor's pre-refresh contract)."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    sensor = DeficitZoneSensor(coordinator, entry, ZONE_1)

    assert sensor.available is True
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None


async def test_et0_daily_value_and_attributes_after_refresh(
    hass: HomeAssistant,
) -> None:
    """Live (in-progress-day) ET0, fed through real weather state_changed events."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    try:
        setup_mock_weather_states(hass)
        await hass.async_block_till_done()
        await coordinator.async_refresh()

        sensor = Et0DailySensor(coordinator, entry)
        assert sensor.available is True
        assert sensor.native_value is not None
        assert sensor.native_value > 0.0

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["method"] == "fao56"
        assert attrs["incomplete"] is False
        assert attrs["missing_inputs"] == []
        assert attrs["u2_ms"] is not None
    finally:
        await coordinator.async_shutdown()


# ---------------------------------------------------------------------------
# Zone sensors: pending state (no finalized day yet) vs applied state
# ---------------------------------------------------------------------------


async def test_zone_sensors_pending_state_before_any_finalized_day(
    hass: HomeAssistant,
) -> None:
    """Immediately after setup, TAW/RAW/deficit/irrigation_7d are already known
    (they don't depend on a finalized day), but ETc/effective-rain are None
    since no day has actually been applied yet."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_refresh()

    for zone_id in ZONES:
        etc = EtcZoneSensor(coordinator, entry, zone_id)
        deficit = DeficitZoneSensor(coordinator, entry, zone_id)
        taw = TawZoneSensor(coordinator, entry, zone_id)
        raw = RawZoneSensor(coordinator, entry, zone_id)
        eff_rain = EffectiveRainZoneSensor(coordinator, entry, zone_id)
        irrigation_7d = Irrigation7dZoneSensor(coordinator, entry, zone_id)

        assert etc.native_value is None
        assert eff_rain.native_value is None
        assert deficit.native_value == 0.0
        assert (
            taw.native_value == (DEFAULT_ROOT_DEPTH_MM / 1000.0) * DEFAULT_AWC_MM_PER_M
        )
        assert raw.native_value == taw.native_value * DEFAULT_P_DEPLETION_FRACTION
        assert irrigation_7d.native_value == 0.0

        for entity in (etc, deficit, taw, raw, eff_rain):
            assert entity.available is True
            attrs = entity.extra_state_attributes
            assert attrs is not None
            assert attrs["applied"] is False

        # irrigation_7d is not a _ZoneBalanceSensor (reads irrigation_log.py
        # directly, not coordinator.data["balance"]) - no applied/day here.
        assert irrigation_7d.available is True
        irrigation_attrs = irrigation_7d.extra_state_attributes
        assert irrigation_attrs["breakdown"]["mains_water"]["mm"] == 0.0
        assert irrigation_attrs["weekly_cap_reached"] is False


async def test_zone_sensors_applied_state_after_finalized_day(
    hass: HomeAssistant, freezer: Any
) -> None:
    """End-to-end: once a finalized "yesterday" weather snapshot exists, ETc
    and effective rain reflect the real applied day, with correct attrs."""
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    freezer.move_to(start)

    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    try:
        setup_mock_weather_states(hass)
        await hass.async_block_till_done()

        midnight = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
        await coordinator.weather._handle_midnight(midnight)
        freezer.move_to(midnight + timedelta(hours=6))

        await coordinator.async_refresh()

        for zone_id in ZONES:
            etc = EtcZoneSensor(coordinator, entry, zone_id)
            deficit = DeficitZoneSensor(coordinator, entry, zone_id)
            eff_rain = EffectiveRainZoneSensor(coordinator, entry, zone_id)
            irrigation_7d = Irrigation7dZoneSensor(coordinator, entry, zone_id)

            assert etc.native_value is not None
            assert etc.native_value > 0.0
            etc_attrs = etc.extra_state_attributes
            assert etc_attrs is not None
            assert etc_attrs["applied"] is True
            assert etc_attrs["kc"] == DEFAULT_KC
            assert etc_attrs["et0_mm"] == etc.native_value / DEFAULT_KC

            assert deficit.native_value == etc.native_value
            deficit_attrs = deficit.extra_state_attributes
            assert deficit_attrs is not None
            assert deficit_attrs["p"] == DEFAULT_P_DEPLETION_FRACTION

            assert eff_rain.native_value == 0.0  # no rain was recorded that day
            eff_rain_attrs = eff_rain.extra_state_attributes
            assert eff_rain_attrs is not None
            assert eff_rain_attrs["factor"] == DEFAULT_RAIN_EFFECTIVE_FACTOR
            assert eff_rain_attrs["daily_rain_raw_mm"] == 0.0

            irrigation_attrs = irrigation_7d.extra_state_attributes
            assert irrigation_attrs is not None
            assert irrigation_attrs["cap_mm"] == DEFAULT_WEEKLY_CAP_MM
            assert irrigation_attrs["remaining_mm"] == DEFAULT_WEEKLY_CAP_MM
            assert irrigation_attrs["weekly_cap_reached"] is False
    finally:
        await coordinator.async_shutdown()


# ---------------------------------------------------------------------------
# Units / device classes / state classes
# ---------------------------------------------------------------------------


async def test_zone_sensor_units_and_state_classes(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)

    for cls in (
        EtcZoneSensor,
        DeficitZoneSensor,
        TawZoneSensor,
        RawZoneSensor,
        EffectiveRainZoneSensor,
        Irrigation7dZoneSensor,
    ):
        entity = cls(coordinator, entry, ZONE_1)
        assert entity.native_unit_of_measurement == UnitOfPrecipitationDepth.MILLIMETERS
        assert entity.state_class == SensorStateClass.MEASUREMENT

    effective_rain = EffectiveRainZoneSensor(coordinator, entry, ZONE_1)
    assert effective_rain.device_class == SensorDeviceClass.PRECIPITATION
    # The other zone sensors intentionally have no device_class (plan §3.1).
    for cls in (EtcZoneSensor, DeficitZoneSensor, TawZoneSensor, RawZoneSensor):
        entity = cls(coordinator, entry, ZONE_1)
        assert entity.device_class is None


# ---------------------------------------------------------------------------
# Availability follows the coordinator's own update success, not artificially
# ---------------------------------------------------------------------------


async def test_availability_follows_coordinator_update_success(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_refresh()

    et0_sensor = Et0DailySensor(coordinator, entry)
    etc_sensor = EtcZoneSensor(coordinator, entry, ZONE_1)
    data_quality_sensor = DataQualitySensor(coordinator, entry)
    assert et0_sensor.available is True
    assert etc_sensor.available is True

    with patch.object(
        coordinator, "_async_update_data", side_effect=RuntimeError("boom")
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert et0_sensor.available is False
    assert etc_sensor.available is False
    # data_quality intentionally always reports available (Milestone 1 contract).
    assert data_quality_sensor.available is True


# ---------------------------------------------------------------------------
# irrigation_7d reflects irrigation_log.py directly, not balance.py's own
# day-anchored figure (regression: same-day recordings must show up now,
# not only after the next day's 05:30 finalization).
# ---------------------------------------------------------------------------


async def test_irrigation_7d_reflects_same_day_recording_immediately(
    hass: HomeAssistant,
) -> None:
    """A cycle recorded today must be visible today - not just after balance.py's
    next once-per-day rollover, which is anchored to the end of yesterday."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_refresh()

    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )
    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_2, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )

    zone1 = Irrigation7dZoneSensor(coordinator, entry, ZONE_1)
    zone2 = Irrigation7dZoneSensor(coordinator, entry, ZONE_2)

    # Defaults: zone1 mains 0.25 mm/min, zone2 mains 0.175 mm/min -> 10 min each.
    assert zone1.native_value == 2.5
    assert zone2.native_value == 1.75

    # balance.py's own figure is now ALSO correct here (its weekly-cap
    # anchor was fixed separately in balance.py - see BalanceEngine.
    # weekly_irrigation_mm's docstring), so the two agree. This sensor still
    # does not read it directly (see its own docstring for why), but the
    # values matching is the expected end-to-end result, not a coincidence.
    balance_result = coordinator.data["balance"][ZONE_1]
    assert balance_result.irrigation_7d_mm == 2.5

    zone1_attrs = zone1.extra_state_attributes
    assert zone1_attrs["breakdown"]["mains_water"]["mm"] == 2.5
    assert zone1_attrs["breakdown"]["mains_water"]["count"] == 1
    assert zone1_attrs["breakdown"]["rainwater_tank"]["mm"] == 0.0
    assert zone1_attrs["cap_mm"] == DEFAULT_WEEKLY_CAP_MM
    assert zone1_attrs["remaining_mm"] == DEFAULT_WEEKLY_CAP_MM - 2.5
    assert zone1_attrs["weekly_cap_reached"] is False
