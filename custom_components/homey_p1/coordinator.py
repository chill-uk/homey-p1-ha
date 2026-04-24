"""Coordinator for the Homey P1 integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiohttp import ClientError, ClientSession, WSMessageTypeError, WSMsgType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import Event
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PORT, RECONNECT_DELAY_SECONDS, WS_PATH
from .parser import parse_dsmr_telegram

_LOGGER = logging.getLogger(__name__)


class HomeyP1Coordinator(DataUpdateCoordinator[dict[str, object]]):
    """Coordinate Homey P1 websocket updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data[CONF_NAME],
        )
        self.entry = entry
        self.host: str = entry.options.get(CONF_HOST, entry.data[CONF_HOST])
        self.url = f"ws://{self.host}:{DEFAULT_PORT}{WS_PATH}"
        self.session: ClientSession = async_get_clientsession(hass)
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._first_update = asyncio.Event()
        self._available = False
        self._unique_id_updated = False
        self.data = {}

    @property
    def available(self) -> bool:
        """Return whether the websocket is connected."""
        return self._available

    async def async_start(self) -> None:
        """Start the websocket listener."""
        self._task = self.hass.async_create_task(self._run())

    async def async_shutdown(self) -> None:
        """Stop the websocket listener."""
        self._stopped.set()
        self._first_update.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def async_wait_for_initial_data(self, timeout: float = 10.0) -> None:
        """Wait briefly for the first parsed telegram."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._first_update.wait(), timeout)

    async def async_handle_hass_stop(self, event: Event) -> None:
        """Stop the websocket listener during Home Assistant shutdown."""
        await self.async_shutdown()

    async def _run(self) -> None:
        """Maintain a websocket connection and parse telegrams."""
        while not self._stopped.is_set():
            try:
                await self._listen()
            except asyncio.CancelledError:
                raise
            except (ClientError, TimeoutError, ValueError, WSMessageTypeError) as err:
                _LOGGER.warning("Homey P1 connection error: %s", err)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected Homey P1 error")

            self._set_available(False)
            if self._stopped.is_set():
                break
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _listen(self) -> None:
        """Listen for telegrams on the Homey websocket."""
        buffer = ""
        telegram = ""
        collecting = False

        _LOGGER.info("Connecting to Homey P1 websocket at %s", self.url)
        async with self.session.ws_connect(
            self.url,
            heartbeat=30,
            autoping=True,
        ) as websocket:
            self._set_available(True)
            _LOGGER.info("Connected to Homey P1 websocket")

            async for message in websocket:
                if message.type == WSMsgType.TEXT:
                    buffer += message.data
                elif message.type == WSMsgType.BINARY:
                    buffer += message.data.decode(errors="ignore")
                elif message.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSED):
                    break
                else:
                    continue

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.rstrip("\r")

                    if line.startswith("/"):
                        telegram = f"{line}\n"
                        collecting = True
                        continue

                    if not collecting:
                        continue

                    telegram += f"{line}\n"
                    if line.startswith("!"):
                        parsed = parse_dsmr_telegram(telegram)
                        if parsed:
                            merged = {**self.data, **parsed}
                            await self._async_update_unique_id(merged)
                            self.async_set_updated_data(merged)
                            self._first_update.set()
                        telegram = ""
                        collecting = False

    def _set_available(self, available: bool) -> None:
        """Update availability and notify listeners."""
        if self._available == available:
            return

        self._available = available
        self.async_update_listeners()

    async def _async_update_unique_id(self, data: dict[str, object]) -> None:
        """Promote the config entry unique ID to the actual meter ID."""
        if self._unique_id_updated:
            return

        equipment_id = data.get("equipment_id")
        if not isinstance(equipment_id, str) or not equipment_id:
            return

        if self.entry.unique_id == equipment_id:
            self._unique_id_updated = True
            return

        self.hass.config_entries.async_update_entry(
            self.entry,
            unique_id=equipment_id,
        )
        self._unique_id_updated = True

    @property
    def device_identifiers(self) -> set[tuple[str, str]]:
        """Return identifiers for the main device."""
        identifiers = {(self.entry.domain, f"host:{self.host.lower()}")}
        if equipment_id := self.data.get("equipment_id"):
            identifiers.add((self.entry.domain, f"meter:{equipment_id}"))
        return identifiers

    @property
    def primary_device_identifier(self) -> tuple[str, str]:
        """Return the stable parent device identifier."""
        return (self.entry.domain, f"host:{self.host.lower()}")
