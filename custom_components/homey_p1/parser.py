"""Parse DSMR telegrams into the integration's stable data contract."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import logging
import re
from typing import Any

from dsmr_parser import telegram_specifications
from dsmr_parser.exceptions import ParseError
from dsmr_parser.parsers import TelegramParser

from .extensions import extended_spec

_LOGGER = logging.getLogger(__name__)

# Keep the existing integration output keys stable even though dsmr-parser uses
# its own canonical property names internally.
HEADER_RE = re.compile(r"^/(?P<manufacturer>[A-Za-z]{3})\d(?P<model>.*)$", re.MULTILINE)
VERSION_RE = re.compile(r"^1-3:0\.2\.8\((?P<value>[^)]+)\)$", re.MULTILINE)
TIMESTAMP_RE = re.compile(r"^0-0:1\.0\.0\((?P<value>[^)]+)\)$", re.MULTILINE)
MBUS_TIMESTAMP_RE = re.compile(
    r"^0-(?P<channel>\d+):24\.2\.[13]\((?P<timestamp>\d{12}[SW])\)",
    re.MULTILINE,
)

DSMR_TO_HOMEY: dict[str, tuple[str, float]] = {
    "ELECTRICITY_IMPORTED_TOTAL": ("energy_import_total", 1.0),
    "ELECTRICITY_EXPORTED_TOTAL": ("energy_export_total", 1.0),
    "ELECTRICITY_USED_TARIFF_1": ("energy_import_tariff_1", 1.0),
    "ELECTRICITY_USED_TARIFF_2": ("energy_import_tariff_2", 1.0),
    "ELECTRICITY_DELIVERED_TARIFF_1": ("energy_export_tariff_1", 1.0),
    "ELECTRICITY_DELIVERED_TARIFF_2": ("energy_export_tariff_2", 1.0),
    "CURRENT_ELECTRICITY_USAGE": ("power_consumption", 1.0),
    "CURRENT_ELECTRICITY_DELIVERY": ("power_production", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE": ("power_consumption_l1", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE": ("power_consumption_l2", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE": ("power_consumption_l3", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE": ("power_production_l1", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE": ("power_production_l2", 1.0),
    "INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE": ("power_production_l3", 1.0),
    "INSTANTANEOUS_CURRENT_L1": ("current_l1", 1.0),
    "INSTANTANEOUS_CURRENT_L2": ("current_l2", 1.0),
    "INSTANTANEOUS_CURRENT_L3": ("current_l3", 1.0),
    "INSTANTANEOUS_VOLTAGE_L1": ("voltage_l1", 1.0),
    "INSTANTANEOUS_VOLTAGE_L2": ("voltage_l2", 1.0),
    "INSTANTANEOUS_VOLTAGE_L3": ("voltage_l3", 1.0),
    "VOLTAGE_SAG_L1_COUNT": ("voltage_sags_l1", 1.0),
    "VOLTAGE_SAG_L2_COUNT": ("voltage_sags_l2", 1.0),
    "VOLTAGE_SAG_L3_COUNT": ("voltage_sags_l3", 1.0),
    "VOLTAGE_SWELL_L1_COUNT": ("voltage_swells_l1", 1.0),
    "VOLTAGE_SWELL_L2_COUNT": ("voltage_swells_l2", 1.0),
    "VOLTAGE_SWELL_L3_COUNT": ("voltage_swells_l3", 1.0),
    "SHORT_POWER_FAILURE_COUNT": ("power_failures", 1.0),
    "LONG_POWER_FAILURE_COUNT": ("long_power_failures", 1.0),
}


# Checksum validation is intentionally disabled here. The Homey websocket
# transport currently exposes text and the parser normalizes line endings before
# handing telegrams to dsmr-parser. CRC validation is byte-sensitive, so enabling
# it here could reject valid telegrams after line-ending normalization. Revisit
# this once the transport preserves the exact raw telegram bytes end-to-end.
_PARSERS = {
    "3": TelegramParser(extended_spec(telegram_specifications.V3), apply_checksum_validation=False),
    "4": TelegramParser(extended_spec(telegram_specifications.V4), apply_checksum_validation=False),
    "5": TelegramParser(extended_spec(telegram_specifications.V5), apply_checksum_validation=False),
}


def parse_dsmr_telegram(telegram: str) -> dict[str, Any]:
    """Parse a DSMR telegram into the integration's backwards-compatible schema."""
    prepared = _normalize_line_endings(telegram)
    version_code = _raw_match(VERSION_RE, telegram)
    parser = _PARSERS.get((version_code or "5")[:1], _PARSERS["5"])

    try:
        parsed_telegram = parser.parse(prepared)
    except ParseError as err:
        _LOGGER.debug("Unable to parse DSMR telegram: %s", err)
        return {}

    parsed: dict[str, Any] = {}

    header_match = HEADER_RE.search(telegram)
    if header_match:
        parsed["meter_manufacturer"] = header_match.group("manufacturer")
        model = header_match.group("model").removeprefix("\\").strip()
        if model:
            parsed["meter_model"] = model

    if version_code:
        version = _format_dsmr_version(version_code)
        parsed["dsmr_version"] = version
        parsed["protocol_family"] = f"DSMR v{version}"

    if timestamp := _raw_match(TIMESTAMP_RE, telegram):
        parsed["telegram_timestamp"] = timestamp

    equipment = getattr(parsed_telegram, "EQUIPMENT_IDENTIFIER", None)
    if equipment is not None:
        equipment_id = str(equipment.value)
        parsed["equipment_id"] = equipment_id
        parsed["electricity_meter_id"] = _decode_hex_identifier(equipment_id)

    tariff = getattr(parsed_telegram, "ELECTRICITY_ACTIVE_TARIFF", None)
    if tariff is not None:
        try:
            parsed["tariff_indicator"] = int(tariff.value)
        except (TypeError, ValueError):
            parsed["tariff_indicator"] = tariff.value

    for source_name, (destination, scale) in DSMR_TO_HOMEY.items():
        source = getattr(parsed_telegram, source_name, None)
        if source is None:
            continue
        value = _plain_value(source.value)
        if isinstance(value, (int, float)):
            value *= scale
        parsed[destination] = value

    _normalize_mbus(parsed_telegram, telegram, parsed)

    if not parsed:
        _LOGGER.debug("Received DSMR telegram without known fields")

    return parsed


def _normalize_mbus(parsed_telegram: Any, raw_telegram: str, parsed: dict[str, Any]) -> None:
    """Normalize dsmr-parser M-Bus devices into the existing channel schema."""
    devices = getattr(parsed_telegram, "MBUS_DEVICES", None)
    if not devices:
        return

    timestamps = {
        match.group("channel"): match.group("timestamp")
        for match in MBUS_TIMESTAMP_RE.finditer(raw_telegram)
    }
    channels: dict[str, dict[str, Any]] = {}

    for device in devices:
        channel = str(device.channel_id)
        channel_data: dict[str, Any] = {}

        device_type = getattr(device, "MBUS_DEVICE_TYPE", None)
        if device_type is not None:
            channel_data["device_type"] = _plain_value(device_type.value)

        equipment = getattr(device, "MBUS_EQUIPMENT_IDENTIFIER", None)
        if equipment is not None:
            equipment_id = str(equipment.value)
            channel_data["equipment_id"] = equipment_id
            channel_data["meter_id"] = _decode_hex_identifier(equipment_id)

        reading = getattr(device, "MBUS_METER_READING", None)
        if reading is not None:
            channel_data["delivered"] = _plain_value(reading.value)
            channel_data["unit"] = reading.unit
            channel_data["timestamp"] = timestamps.get(channel, _timestamp_string(reading.datetime))

        if channel_data:
            channels[channel] = channel_data

    if not channels:
        return

    parsed["mbus_channels"] = channels

    # Preserve the legacy flat channel-1 keys used by existing entities/users.
    if channel_one := channels.get("1"):
        parsed["mbus_device_type"] = channel_one.get("device_type")
        parsed["gas_equipment_id"] = channel_one.get("equipment_id")
        parsed["mbus_meter_id"] = channel_one.get("meter_id")
        parsed["gas_timestamp"] = channel_one.get("timestamp")
        parsed["gas_delivered"] = channel_one.get("delivered")


def _normalize_line_endings(telegram: str) -> str:
    """Normalize websocket line endings to the CRLF form expected by dsmr-parser."""
    normalized = telegram.replace("\r\n", "\n").replace("\r", "\n")
    return "\r\n".join(normalized.split("\n"))


def _raw_match(pattern: re.Pattern[str], telegram: str) -> str | None:
    """Return a named value from a raw telegram regex."""
    normalized = telegram.replace("\r\n", "\n").replace("\r", "\n")
    match = pattern.search(normalized)
    return match.group("value") if match and "value" in match.groupdict() else None


def _plain_value(value: Any) -> Any:
    """Convert dsmr-parser value types to the integration's existing primitives."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def _timestamp_string(value: Any) -> str | None:
    """Return a stable timestamp string when a raw DSMR timestamp is unavailable."""
    if isinstance(value, datetime):
        return value.strftime("%y%m%d%H%M%S")
    if value is None:
        return None
    return str(value)


def _format_dsmr_version(version: str) -> str:
    """Format the DSMR version from OBIS 1-3:0.2.8 for display."""
    if len(version) == 2 and version.isdigit():
        return f"{version[0]}.{version[1]}"
    return version


def _decode_hex_identifier(value: str) -> str:
    """Decode a hex-encoded meter identifier to ASCII when possible."""
    try:
        decoded = bytes.fromhex(value).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return value

    if all(32 <= ord(char) <= 126 for char in decoded):
        return decoded

    return value
