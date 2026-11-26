"""Regression tests for Homey P1 device registry migration (issue #12)."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from dataclasses import dataclass, field
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "homey_p1"
DOMAIN = "homey_p1"

package = types.ModuleType("custom_components.homey_p1")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules["custom_components.homey_p1"] = package

ha = types.ModuleType("homeassistant")
ha.__path__ = []
sys.modules["homeassistant"] = ha
config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
sys.modules["homeassistant.config_entries"] = config_entries
const = types.ModuleType("homeassistant.const")
const.CONF_HOST = "host"
sys.modules["homeassistant.const"] = const
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
sys.modules["homeassistant.core"] = core
helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
sys.modules["homeassistant.helpers"] = helpers
dr = types.ModuleType("homeassistant.helpers.device_registry")
er = types.ModuleType("homeassistant.helpers.entity_registry")
sys.modules["homeassistant.helpers.device_registry"] = dr
sys.modules["homeassistant.helpers.entity_registry"] = er
helpers.device_registry = dr
helpers.entity_registry = er


@dataclass
class Device:
    id: str
    identifiers: set[tuple[str, str]]
    config_entries: set[str] = field(default_factory=lambda: {"entry1"})
    via_device_id: str | None = None
    area_id: str | None = None


@dataclass
class Entity:
    entity_id: str
    device_id: str
    config_entry_id: str = "entry1"


class Devices:
    def __init__(self, *items: Device) -> None:
        self.devices = {d.id: d for d in items}
        self.removed = []

    def async_update_device(self, device_id, *, new_identifiers=None, via_device_id=None):
        device = self.devices[device_id]
        if new_identifiers is not None:
            for other in self.devices.values():
                if other.id != device_id and other.identifiers & new_identifiers:
                    raise ValueError("identifier collision")
            device.identifiers = new_identifiers
        if via_device_id is not None:
            device.via_device_id = via_device_id

    def async_remove_device(self, device_id):
        self.removed.append(device_id)
        del self.devices[device_id]


class Entities:
    def __init__(self, *items: Entity) -> None:
        self.entities = {e.entity_id: e for e in items}

    def async_update_entity(self, entity_id, *, device_id):
        self.entities[entity_id].device_id = device_id


dr.DeviceEntry = Device
dr.async_get = lambda hass: hass.devices
dr.async_entries_for_config_entry = (
    lambda registry, entry_id: [
        d for d in registry.devices.values() if entry_id in d.config_entries
    ]
)
er.async_get = lambda hass: hass.entities
er.async_entries_for_device = (
    lambda registry, device_id, include_disabled_entities=False: [
        e for e in registry.entities.values() if e.device_id == device_id
    ]
)

spec = importlib.util.spec_from_file_location(
    "custom_components.homey_p1.device_migration", ROOT / "device_migration.py"
)
migration = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = migration
assert spec.loader is not None
spec.loader.exec_module(migration)


def run(devices, entities=()):
    hass = SimpleNamespace(devices=Devices(*devices), entities=Entities(*entities))
    entry = SimpleNamespace(entry_id="entry1", data={"host": "192.168.8.168"})
    migration.async_migrate_devices(hass, entry)
    return hass


class DeviceMigrationTests(unittest.TestCase):
    def test_new_installation_has_nothing_to_migrate(self):
        hass = run([])
        self.assertEqual(hass.devices.devices, {})

    def test_old_host_identifier_migrated_without_changing_device_id(self):
        old = Device("original", {(DOMAIN, "host:192.168.8.168")}, area_id="kitchen")
        hass = run([old], [Entity("sensor.energy", "original")])
        self.assertEqual(old.identifiers, {(DOMAIN, "entry:entry1")})
        self.assertEqual(old.id, "original")
        self.assertEqual(old.area_id, "kitchen")
        self.assertEqual(hass.entities.entities["sensor.energy"].device_id, "original")

    def test_ip_change_merges_duplicate_and_reparents_child(self):
        old = Device("original", {(DOMAIN, "host:192.168.8.168")})
        new = Device("duplicate", {(DOMAIN, "host:192.168.8.246")})
        gas = Device("gas", {(DOMAIN, "mbus:1:gas")}, via_device_id="duplicate")
        hass = run(
            [old, new, gas],
            [Entity("sensor.energy", "duplicate"), Entity("sensor.gas", "gas")],
        )
        self.assertEqual(old.identifiers, {(DOMAIN, "entry:entry1")})
        self.assertEqual(hass.entities.entities["sensor.energy"].device_id, "original")
        self.assertEqual(gas.via_device_id, "original")
        self.assertEqual(hass.devices.removed, ["duplicate"])
        self.assertIn("gas", hass.devices.devices)

    def test_migration_is_idempotent(self):
        stable = Device("original", {(DOMAIN, "entry:entry1")})
        duplicate = Device("other", {(DOMAIN, "host:192.168.8.246")})
        hass = run([stable, duplicate], [Entity("sensor.energy", "other")])
        migration.async_migrate_devices(
            hass, SimpleNamespace(entry_id="entry1", data={"host": "192.168.8.168"})
        )
        self.assertEqual(hass.devices.removed, ["other"])
        self.assertEqual(hass.entities.entities["sensor.energy"].device_id, "original")

    def test_mbus_device_is_not_migrated_as_main_device(self):
        gas = Device("gas", {(DOMAIN, "mbus:1:gas")})
        hass = run([gas])
        self.assertEqual(gas.identifiers, {(DOMAIN, "mbus:1:gas")})
        self.assertEqual(hass.devices.removed, [])

    def test_shared_duplicate_is_not_deleted(self):
        original = Device("original", {(DOMAIN, "host:192.168.8.168")})
        shared = Device(
            "shared",
            {(DOMAIN, "host:192.168.8.246")},
            config_entries={"entry1", "another"},
        )
        hass = run([original, shared], [Entity("sensor.energy", "shared")])
        self.assertIn("shared", hass.devices.devices)
        self.assertEqual(hass.entities.entities["sensor.energy"].device_id, "shared")


if __name__ == "__main__":
    unittest.main()
