"""Privacy-preserving diagnostics for Homey P1."""

from __future__ import annotations

from typing import Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Export device-independent metadata and ciphertext-only telegram captures."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    integration = await async_get_integration(hass, DOMAIN)
    capture = coordinator.encrypted_capture.diagnostics()
    encrypted_records = capture.pop("encrypted_records")
    return {
        "schema_version": 1,
        "integration_version": integration.version,
        "home_assistant_version": HA_VERSION,
        "connected": coordinator.available,
        "capture": capture,
        "encrypted_records": encrypted_records,
    }
