"""Parse DSMR telegrams from the Homey P1 websocket."""

from __future__ import annotations

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

HEADER_RE = re.compile(r"^/(?P<manufacturer>[A-Za-z]{3})(?P<version>\d)\\(?P<model>.+)$")
LINE_RE = re.compile(r"^(?P<obis>[\d-]+:[\d.]+(?:\.\d+)?)\((?P<value>.*)\)$")
UNIT_RE = re.compile(r"^(?P<value>[-\d.]+)\*(?P<unit>[A-Za-z0-9]+)$")
GROUP_RE = re.compile(r"\(([^()]*)\)")
MBUS_DEVICE_TYPE_RE = re.compile(r"^0-(?P<channel>\d+):24\.1\.0\((?P<value>\d+)\)$")
MBUS_EQUIPMENT_ID_RE = re.compile(r"^0-(?P<channel>\d+):96\.1\.0\((?P<value>[^()]*)\)$")
MBUS_READING_RE = re.compile(
    r"^0-(?P<channel>\d+):24\.2\.1\((?P<timestamp>\d{12}[SW])\)\((?P<value>[-\d.]+)\*(?P<unit>[A-Za-z0-9]+)\)$"
)

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
    "0-1:24.1.0": ("mbus_device_type", int),
    "0-1:96.1.0": ("gas_equipment_id", str),
}


def parse_dsmr_telegram(telegram: str) -> dict[str, Any]:
    """Parse a DSMR telegram into a flat dictionary."""
    parsed: dict[str, Any] = {}

    mbus_channels: dict[str, dict[str, Any]] = {}

    for raw_line in telegram.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("/"):
            header_match = HEADER_RE.match(line)
            if header_match:
                parsed["meter_manufacturer"] = header_match.group("manufacturer")
                parsed["meter_model"] = header_match.group("model")
                parsed["protocol_family"] = (
                    f"DSMR v{header_match.group('version')}"
                )
            continue

        if line.startswith("!"):
            continue

        if _parse_mbus_line(line, mbus_channels):
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

    if equipment_id := parsed.get("equipment_id"):
        parsed["electricity_meter_id"] = _decode_hex_identifier(str(equipment_id))

    if gas_equipment_id := parsed.get("gas_equipment_id"):
        parsed["mbus_meter_id"] = _decode_hex_identifier(str(gas_equipment_id))

    if mbus_channels:
        for channel_data in mbus_channels.values():
            if equipment_id := channel_data.get("equipment_id"):
                channel_data["meter_id"] = _decode_hex_identifier(str(equipment_id))

        parsed["mbus_channels"] = mbus_channels

        # Mirror channel 1 into the legacy flat keys for backwards compatibility.
        if channel_one := mbus_channels.get("1"):
            parsed["mbus_device_type"] = channel_one.get("device_type")
            parsed["gas_equipment_id"] = channel_one.get("equipment_id")
            parsed["mbus_meter_id"] = channel_one.get("meter_id")
            parsed["gas_timestamp"] = channel_one.get("timestamp")
            parsed["gas_delivered"] = channel_one.get("delivered")

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


def _parse_mbus_line(line: str, channels: dict[str, dict[str, Any]]) -> bool:
    """Parse a dynamic M-Bus line into the channel map."""
    if match := MBUS_DEVICE_TYPE_RE.match(line):
        channel = match.group("channel")
        channels.setdefault(channel, {})["device_type"] = int(match.group("value"))
        return True

    if match := MBUS_EQUIPMENT_ID_RE.match(line):
        channel = match.group("channel")
        channels.setdefault(channel, {})["equipment_id"] = match.group("value")
        return True

    if match := MBUS_READING_RE.match(line):
        channel = match.group("channel")
        channel_data = channels.setdefault(channel, {})
        channel_data["timestamp"] = match.group("timestamp")
        channel_data["unit"] = match.group("unit")
        channel_data["delivered"] = float(match.group("value"))
        return True

    return False


def _normalize_value(payload: str, caster: callable) -> Any | None:
    """Convert a DSMR payload to the requested type."""
    unit_match = UNIT_RE.match(payload)
    raw_value = unit_match.group("value") if unit_match else payload

    try:
        return caster(raw_value)
    except (TypeError, ValueError):
        _LOGGER.debug("Unable to parse DSMR value %s with %s", payload, caster)
        return None


def _decode_hex_identifier(value: str) -> str:
    """Decode a hex-encoded meter identifier to ASCII when possible."""
    try:
        decoded = bytes.fromhex(value).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return value

    if all(32 <= ord(char) <= 126 for char in decoded):
        return decoded

    return value
