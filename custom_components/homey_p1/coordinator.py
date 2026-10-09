"""Coordinator for the Homey P1 integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiohttp import ClientError, ClientSession, WSMessageTypeError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import (
    CannotConnectError,
    ConnectionLimitError,
    HomeyP1Client,
    LocalAPIDisabledError,
)
from .const import (
    MAX_RECONNECT_DELAY_SECONDS,
    RECONNECT_DELAY_SECONDS,
    TRANSIENT_FAILURE_GRACE_SECONDS,
)
from .grace import LastKnownData
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
        self.session: ClientSession = async_get_clientsession(hass)
        self.client = HomeyP1Client(self.session, self.host)
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._first_update = asyncio.Event()
        self._available = False
        self._unavailable_task: asyncio.Task[None] | None = None
        self._reconnect_delay = RECONNECT_DELAY_SECONDS
        self._unique_id_updated = False
        self._last_known_data = LastKnownData(TRANSIENT_FAILURE_GRACE_SECONDS)
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
        if self._unavailable_task:
            self._unavailable_task.cancel()
            await self._unavailable_task
            self._unavailable_task = None
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def async_wait_for_initial_data(self, timeout: float = 10.0) -> bool:
        """Wait briefly for the first parsed telegram."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._first_update.wait(), timeout)
            return True
        return False

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
            except ConnectionLimitError as err:
                _LOGGER.warning(
                    "Homey P1 websocket rejected the connection: %s. "
                    "This can happen after an unclean shutdown if the dongle "
                    "still thinks the old client is connected.",
                    err,
                )
            except LocalAPIDisabledError as err:
                _LOGGER.warning("Homey P1 Local API is disabled: %s", err)
            except CannotConnectError as err:
                _LOGGER.warning("Homey P1 websocket closed: %s", err)
            except (ClientError, TimeoutError, ValueError, WSMessageTypeError) as err:
                _LOGGER.warning("Homey P1 connection error: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected Homey P1 error")

            self._set_available(False)
            if self._stopped.is_set():
                break
            delay = self._reconnect_delay
            _LOGGER.info("Retrying Homey P1 connection in %s seconds", delay)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopped.wait(), delay)
            self._reconnect_delay = min(
                delay * 2,
                MAX_RECONNECT_DELAY_SECONDS,
            )

    async def _listen(self) -> None:
        """Listen for raw telegrams from the Homey transport client."""
        _LOGGER.info("Connecting to Homey P1 websocket at %s", self.client.url)
        loop = asyncio.get_running_loop()

        async for telegram in self.client.telegrams():
            if self._stopped.is_set():
                break

            parsed = parse_dsmr_telegram(telegram)
            if not parsed:
                continue

            await self._async_update_unique_id(parsed)
            merged = self._last_known_data.update(parsed, loop.time())
            self.async_set_updated_data(merged)
            self._first_update.set()
            self._reconnect_delay = RECONNECT_DELAY_SECONDS
            self._set_available(True)

    def _set_available(self, available: bool) -> None:
        """Update availability and notify listeners."""
        if available:
            if self._unavailable_task:
                self._unavailable_task.cancel()
                self._unavailable_task = None
            if self._available:
                return
            self._available = True
            self.async_update_listeners()
            return

        if not self._available or self._unavailable_task:
            return

        self._unavailable_task = self.hass.async_create_task(
            self._async_mark_unavailable_after_grace()
        )

    async def _async_mark_unavailable_after_grace(self) -> None:
        """Mark the coordinator unavailable after a transient-failure grace period."""
        try:
            await asyncio.sleep(TRANSIENT_FAILURE_GRACE_SECONDS)
        except asyncio.CancelledError:
            return

        self._unavailable_task = None
        if not self._available:
            return
        self._available = False
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
