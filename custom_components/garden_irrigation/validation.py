"""Entity validation helpers for the config/options flow.

Checks existence, domain, unit compatibility and numeric state, per the plan's
requirement to validate every configured source entity_id before accepting it.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

EXPECTED_DOMAIN = "sensor"


class EntityValidationError(Exception):
    """Raised when a configured entity fails validation."""

    def __init__(self, entity_id: str, reason: str) -> None:
        """Store the entity_id and a machine-readable reason code."""
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"{entity_id}: {reason}")


def validate_sensor_entity(
    hass: HomeAssistant,
    entity_id: str,
    *,
    expected_units: set[str] | None = None,
) -> None:
    """Validate that entity_id exists, is a sensor, has a compatible unit.

    Raises EntityValidationError with one of these reasons:
    - "entity_not_found": no such entity in the state machine.
    - "entity_wrong_domain": entity_id is not in the `sensor.` domain.
    - "entity_wrong_unit": unit_of_measurement is set but not in expected_units.
    - "entity_not_numeric": state is a concrete value but not parseable as float.

    A state of `unknown`/`unavailable` is accepted (the source entity may not
    have produced data yet); only domain/unit/existence are enforced in that
    case.
    """
    if not entity_id.startswith(f"{EXPECTED_DOMAIN}."):
        raise EntityValidationError(entity_id, "entity_wrong_domain")

    state = hass.states.get(entity_id)
    if state is None:
        raise EntityValidationError(entity_id, "entity_not_found")

    if expected_units is not None:
        unit = state.attributes.get("unit_of_measurement")
        if unit is not None and unit not in expected_units:
            raise EntityValidationError(entity_id, "entity_wrong_unit")

    if state.state not in ("unknown", "unavailable"):
        try:
            float(state.state)
        except (TypeError, ValueError):
            raise EntityValidationError(entity_id, "entity_not_numeric") from None
