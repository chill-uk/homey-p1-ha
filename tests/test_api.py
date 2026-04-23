"""Tests for websocket validation helpers."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from enum import Enum
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


class _WSMsgType(Enum):
    TEXT = "text"
    BINARY = "binary"
    CLOSE = "close"
    CLOSED = "closed"
    ERROR = "error"


fake_aiohttp = types.ModuleType("aiohttp")
fake_aiohttp.ClientError = Exception
fake_aiohttp.ClientSession = object
fake_aiohttp.WSServerHandshakeError = Exception
fake_aiohttp.WSMsgType = _WSMsgType
sys.modules["aiohttp"] = fake_aiohttp

_load_module("custom_components.homey_p1.const", "const.py")
api = _load_module("custom_components.homey_p1.api", "api.py")


class FakeWebSocket:
    """Minimal async websocket context manager for tests."""

    def __init__(self, message=None, raise_on_receive=None) -> None:
        self.message = message
        self.raise_on_receive = raise_on_receive

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def receive(self, timeout=None):
        if self.raise_on_receive is not None:
            raise self.raise_on_receive
        return self.message


class FakeSession:
    """Minimal aiohttp-like session for tests."""

    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    def ws_connect(self, url, heartbeat=None, autoping=None):
        return self.websocket


class ValidateConnectionTests(unittest.IsolatedAsyncioTestCase):
    """Test Homey websocket validation."""

    async def test_accepts_text_message(self) -> None:
        session = FakeSession(
            FakeWebSocket(SimpleNamespace(type=_WSMsgType.TEXT, extra="", data="ok"))
        )
        await api.async_validate_connection(session, "192.168.1.10")

    async def test_accepts_idle_open_connection(self) -> None:
        session = FakeSession(FakeWebSocket(raise_on_receive=TimeoutError()))
        await api.async_validate_connection(session, "192.168.1.10")

    async def test_detects_local_api_disabled(self) -> None:
        session = FakeSession(
            FakeWebSocket(
                SimpleNamespace(
                    type=_WSMsgType.CLOSE,
                    extra="Local API disabled",
                    data=None,
                )
            )
        )

        with self.assertRaises(api.LocalAPIDisabledError):
            await api.async_validate_connection(session, "192.168.1.10")

    async def test_detects_connection_limit(self) -> None:
        session = FakeSession(
            FakeWebSocket(
                SimpleNamespace(
                    type=_WSMsgType.CLOSE,
                    extra="Connection limit reached",
                    data=None,
                )
            )
        )

        with self.assertRaises(api.ConnectionLimitError):
            await api.async_validate_connection(session, "192.168.1.10")

    async def test_maps_unknown_close_to_cannot_connect(self) -> None:
        session = FakeSession(
            FakeWebSocket(
                SimpleNamespace(type=_WSMsgType.CLOSE, extra="closed", data=None)
            )
        )

        with self.assertRaises(api.CannotConnectError):
            await api.async_validate_connection(session, "192.168.1.10")
