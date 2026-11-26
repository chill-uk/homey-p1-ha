"""Preserve Home Assistant device IDs when the dongle host changes."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_legacy_main_device(device: dr.DeviceEntry) -> bool:
    """Distinguish the electricity meter from its M-Bus child devices."""
    return any(
        domain == DOMAIN and (value.startswith("host:") or value.startswith("meter:"))
        for domain, value in device.identifiers
    )


def _sort_key(device: dr.DeviceEntry, original_host: str) -> tuple[int, str]:
    """Prefer the original device, retaining its areas and automation references."""
    initial_identifier = (DOMAIN, f"host:{original_host.strip().lower()}")
    return (0 if initial_identifier in device.identifiers else 1, device.id)


def async_migrate_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old IP-based devices in place before entities are created.

    An earlier IP change may already have produced several electricity-meter
    device records. Prefer the device associated with the initial host so its
    ID (and therefore device automations, labels and area) survives.
    """
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    identifier = (DOMAIN, f"entry:{entry.entry_id}")
    candidates = [
        device
        for device in dr.async_entries_for_config_entry(devices, entry.entry_id)
        if _is_legacy_main_device(device) or identifier in device.identifiers
    ]
    if not candidates:
        return

    # An already migrated device always wins on subsequent restarts.
    canonical = next(
        (device for device in candidates if identifier in device.identifiers),
        None,
    )
    if canonical is None:
        canonical = min(
            candidates,
            key=lambda device: _sort_key(device, entry.data[CONF_HOST]),
        )

    # Remove old identifiers from the chosen device. Meter identifiers must
    # not accidentally merge two integrations reading the same DSMR meter.
    devices.async_update_device(canonical.id, new_identifiers={identifier})

    for duplicate in candidates:
        if duplicate.id == canonical.id:
            continue
        if duplicate.config_entries != {entry.entry_id}:
            _LOGGER.warning(
                "Cannot merge Homey P1 device %s: shared with another config entry",
                duplicate.id,
            )
            continue

        for entity in er.async_entries_for_device(
            entities, duplicate.id, include_disabled_entities=True
        ):
            if entity.config_entry_id == entry.entry_id:
                entities.async_update_entity(entity.entity_id, device_id=canonical.id)

        # Keep child M-Bus device identities and their linked automations.
        for child in dr.async_entries_for_parent_device(devices, duplicate.id):
            devices.async_update_device(child.id, via_device_id=canonical.id)

        if not er.async_entries_for_device(
            entities, duplicate.id, include_disabled_entities=True
        ) and not dr.async_entries_for_parent_device(devices, duplicate.id):
            devices.async_remove_device(duplicate.id)
            _LOGGER.info(
                "Merged orphaned Homey P1 device %s into %s",
                duplicate.id,
                canonical.id,
            )
