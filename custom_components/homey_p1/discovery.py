"""Capability discovery helpers for optional DSMR measurements."""

from __future__ import annotations

from collections.abc import Mapping

from p1_dsmr_common.capabilities import new_capabilities

OPTIONAL_METER_KEYS: tuple[str, ...] = (
    "energy_import_total",
    "energy_export_total",
)


def new_optional_meter_keys(
    data: Mapping[str, object],
    known_keys: set[str],
) -> tuple[str, ...]:
    """Return newly available optional meter keys in stable order."""
    return new_capabilities(data, known_keys, OPTIONAL_METER_KEYS)
