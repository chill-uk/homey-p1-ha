"""Helpers for interpreting DSMR M-Bus measurements."""

from __future__ import annotations

from typing import Literal

MbusMeasurementKind = Literal["energy", "gas", "water"]

ENERGY_UNITS = frozenset({"J", "kJ", "MJ", "GJ", "Wh", "kWh", "MWh"})


def classify_mbus_measurement(
    device_type: object,
    unit: object,
) -> MbusMeasurementKind | None:
    """Return the Home Assistant measurement kind for an M-Bus reading."""
    normalized_type = normalize_device_type(device_type)

    # Some gas meters report energy instead of volume. The unit takes precedence
    # so Home Assistant does not receive a gas device class with an energy unit.
    if isinstance(unit, str) and unit in ENERGY_UNITS:
        return "energy"
    if normalized_type == 3:
        return "gas"
    if normalized_type in {6, 7}:
        return "water"
    return None


def normalize_device_type(device_type: object) -> int | None:
    """Convert an M-Bus device type to an integer when possible."""
    if isinstance(device_type, int):
        return device_type

    if isinstance(device_type, str):
        try:
            return int(device_type, 10)
        except ValueError:
            return None

    return None
