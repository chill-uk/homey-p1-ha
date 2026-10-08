"""Capability discovery helpers for optional DSMR measurements."""

from __future__ import annotations

from collections.abc import Mapping

OPTIONAL_METER_KEYS: tuple[str, ...] = (
    "energy_import_total",
    "energy_export_total",
)


def new_optional_meter_keys(
    data: Mapping[str, object],
    known_keys: set[str],
) -> tuple[str, ...]:
    """Return newly available optional meter keys in stable order."""
    return tuple(
        key
        for key in OPTIONAL_METER_KEYS
        if key in data and key not in known_keys
    )
