"""Tests for config-flow helper logic."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from types import SimpleNamespace


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "custom_components" / "homey_p1"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("custom_components.homey_p1")
package.__path__ = [str(MODULE_DIR)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules["custom_components.homey_p1"] = package

fake_config_entries = types.ModuleType("homeassistant.config_entries")


class AbortFlow(Exception):
    """Stub AbortFlow exception."""


class ConfigFlow:
    """Stub ConfigFlow."""

    def __init_subclass__(cls, **kwargs):
        return None


class OptionsFlow:
    """Stub OptionsFlow."""


fake_config_entries.AbortFlow = AbortFlow
fake_config_entries.ConfigFlow = ConfigFlow
fake_config_entries.OptionsFlow = OptionsFlow
fake_config_entries.ConfigEntry = object

fake_homeassistant = types.ModuleType("homeassistant")
fake_homeassistant.config_entries = fake_config_entries
sys.modules["homeassistant"] = fake_homeassistant
sys.modules["homeassistant.config_entries"] = fake_config_entries

fake_const = types.ModuleType("homeassistant.const")
fake_const.CONF_HOST = "host"
fake_const.CONF_NAME = "name"
sys.modules["homeassistant.const"] = fake_const

fake_core = types.ModuleType("homeassistant.core")
fake_core.HomeAssistant = object
sys.modules["homeassistant.core"] = fake_core

fake_flow = types.ModuleType("homeassistant.data_entry_flow")
fake_flow.FlowResult = dict
sys.modules["homeassistant.data_entry_flow"] = fake_flow

fake_vol = types.ModuleType("voluptuous")
fake_vol.Required = lambda key, default=None: key
fake_vol.Optional = lambda key, default=None: key
fake_vol.Schema = lambda schema: schema
sys.modules["voluptuous"] = fake_vol

fake_aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
fake_aiohttp_client.async_get_clientsession = lambda hass: None
sys.modules["homeassistant.helpers"] = types.ModuleType("homeassistant.helpers")
sys.modules["homeassistant.helpers.aiohttp_client"] = fake_aiohttp_client

fake_api = types.ModuleType("custom_components.homey_p1.api")
fake_api.CannotConnectError = Exception
fake_api.ConnectionLimitError = Exception
fake_api.LocalAPIDisabledError = Exception


async def _noop_validate_connection(session, host):
    return None


fake_api.async_validate_connection = _noop_validate_connection
sys.modules["custom_components.homey_p1.api"] = fake_api

_load_module("custom_components.homey_p1.const", "const.py")
config_flow = _load_module("custom_components.homey_p1.config_flow", "config_flow.py")


class HostDuplicateGuardTests(unittest.TestCase):
    """Test duplicate host guard behavior."""

    def test_allows_same_entry_to_keep_its_host(self) -> None:
        current = SimpleNamespace(entry_id="one", data={"host": "192.168.1.10"}, options={})

        config_flow._abort_if_host_already_configured(
            current,
            [current],
            "192.168.1.10",
        )

    def test_rejects_duplicate_host_from_other_entry(self) -> None:
        current = SimpleNamespace(entry_id="one", data={"host": "192.168.1.10"}, options={})
        other = SimpleNamespace(entry_id="two", data={"host": "192.168.1.20"}, options={})

        with self.assertRaises(AbortFlow):
            config_flow._abort_if_host_already_configured(
                current,
                [current, other],
                "192.168.1.20",
            )

    def test_uses_options_host_when_present(self) -> None:
        current = SimpleNamespace(entry_id="one", data={"host": "192.168.1.10"}, options={})
        other = SimpleNamespace(
            entry_id="two",
            data={"host": "192.168.1.20"},
            options={"host": "192.168.1.30"},
        )

        with self.assertRaises(AbortFlow):
            config_flow._abort_if_host_already_configured(
                current,
                [current, other],
                "192.168.1.30",
            )
