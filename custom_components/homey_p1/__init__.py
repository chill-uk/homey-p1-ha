"""Homey P1 custom integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HomeyP1Coordinator
from .device_migration import async_migrate_devices

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homey P1 from a config entry."""
    async_migrate_devices(hass, entry)
    coordinator = HomeyP1Coordinator(hass, entry)
    await coordinator.async_start()
    if not await coordinator.async_wait_for_initial_data():
        _LOGGER.warning(
            "Homey P1 did not receive its first telegram from %s within the startup "
            "timeout. Home Assistant will continue starting, but entities may stay "
            "unavailable until the websocket begins delivering data. This can happen "
            "when the Homey Local API is disabled, a stale websocket session is still "
            "held by the dongle, or the dongle is reachable but not sending telegrams.",
            coordinator.host,
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            coordinator.async_handle_hass_stop,
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HomeyP1Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok

 
async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: object
) -> bool:
    """Allow removal of orphaned devices belonging to this config entry."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    if entry.entry_id not in device_entry.config_entries:
        return False
    if er.async_entries_for_device(
        entities, device_entry.id, include_disabled_entities=True
    ):
        return False
    return not any(
        child.via_device_id == device_entry.id
        for child in devices.devices.values()
    )
