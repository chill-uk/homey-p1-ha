"""Parse DSMR telegrams from the Homey P1 websocket."""

from __future__ import annotations

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

LINE_RE = re.compile(r"^(?P<obis>[\d-]+:[\d.]+(?:\.\d+)?)\((?P<value>.*)\)$")
UNIT_RE = re.compile(r"^(?P<value>[-\d.]+)\*(?P<unit>[A-Za-z0-9]+)$")
GROUP_RE = re.compile(r"\(([^()]*)\)")

OBIS_MAP: dict[str, tuple[str, callable]] = {
    "1-3:0.2.8": ("dsmr_version", str),
    "0-0:96.1.0": ("equipment_id", str),
    "0-0:96.1.1": ("equipment_id", str),
    "0-0:96.14.0": ("tariff_indicator", int),
    "0-0:1.0.0": ("telegram_timestamp", str),
    "1-0:1.8.1": ("energy_import_tariff_1", float),
    "1-0:1.8.2": ("energy_import_tariff_2", float),
    "1-0:2.8.1": ("energy_export_tariff_1", float),
    "1-0:2.8.2": ("energy_export_tariff_2", float),
    "1-0:1.7.0": ("power_consumption", float),
    "1-0:2.7.0": ("power_production", float),
    "1-0:21.7.0": ("power_consumption_l1", float),
    "1-0:41.7.0": ("power_consumption_l2", float),
    "1-0:61.7.0": ("power_consumption_l3", float),
    "1-0:22.7.0": ("power_production_l1", float),
    "1-0:42.7.0": ("power_production_l2", float),
    "1-0:62.7.0": ("power_production_l3", float),
    "1-0:31.7.0": ("current_l1", float),
    "1-0:51.7.0": ("current_l2", float),
    "1-0:71.7.0": ("current_l3", float),
    "1-0:32.7.0": ("voltage_l1", float),
    "1-0:52.7.0": ("voltage_l2", float),
    "1-0:72.7.0": ("voltage_l3", float),
    "1-0:32.32.0": ("voltage_sags_l1", int),
    "1-0:52.32.0": ("voltage_sags_l2", int),
    "1-0:72.32.0": ("voltage_sags_l3", int),
    "1-0:32.36.0": ("voltage_swells_l1", int),
    "1-0:52.36.0": ("voltage_swells_l2", int),
    "1-0:72.36.0": ("voltage_swells_l3", int),
    "0-0:96.7.21": ("power_failures", int),
    "0-0:96.7.9": ("long_power_failures", int),
    "0-1:96.1.0": ("gas_equipment_id", str),
}


def parse_dsmr_telegram(telegram: str) -> dict[str, Any]:
    """Parse a DSMR telegram into a flat dictionary."""
    parsed: dict[str, Any] = {}

    for raw_line in telegram.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("/") or line.startswith("!"):
            continue

        if line.startswith("0-1:24.2.1"):
            gas_values = _extract_groups(line)
            if len(gas_values) >= 2:
                parsed["gas_timestamp"] = gas_values[0]
                value = _normalize_value(gas_values[1], float)
                if value is not None:
                    parsed["gas_delivered"] = value
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        obis = match.group("obis")
        payload = _extract_payload(line)
        definition = OBIS_MAP.get(obis)
        if definition is None:
            continue

        key, caster = definition
        value = _normalize_value(payload, caster)
        if value is not None:
            parsed[key] = value

    if not parsed:
        _LOGGER.debug("Received DSMR telegram without known fields")

    return parsed


def _extract_payload(line: str) -> str:
    """Return the content after the first opening parenthesis."""
    _, payload = line.split("(", 1)
    return payload[:-1]


def _extract_groups(line: str) -> list[str]:
    """Return all parenthesized groups from a telegram line."""
    return GROUP_RE.findall(line)


def _normalize_value(payload: str, caster: callable) -> Any | None:
    """Convert a DSMR payload to the requested type."""
    unit_match = UNIT_RE.match(payload)
    raw_value = unit_match.group("value") if unit_match else payload

    try:
        return caster(raw_value)
    except (TypeError, ValueError):
        _LOGGER.debug("Unable to parse DSMR value %s with %s", payload, caster)
        return None
