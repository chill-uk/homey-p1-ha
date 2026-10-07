"""Homey P1 websocket transport.

This module owns device-specific framing and connection behavior. It deliberately
returns raw DSMR telegrams and contains no OBIS interpretation.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from aiohttp import ClientSession, WSMessageTypeError, WSMsgType

from .const import CONNECT_TIMEOUT_SECONDS, DEFAULT_PORT, TELEGRAM_TIMEOUT_SECONDS, WS_PATH


class CannotConnectError(Exception):
    """Raised when the websocket cannot be reached."""


class ConnectionLimitError(Exception):
    """Raised when the Homey websocket has no free client slots."""


class LocalAPIDisabledError(Exception):
    """Raised when the Local API is disabled on the dongle."""


def classify_close_reason(reason: str) -> Exception:
    """Map a websocket close reason to a typed exception."""
    reason_text = str(reason or "")
    reason_lower = reason_text.lower()

    if "connection limit reached" in reason_lower:
        return ConnectionLimitError(reason_text)
    if "local api disabled" in reason_lower:
        return LocalAPIDisabledError(reason_text)
    return CannotConnectError(reason_text or "websocket closed")


class DSMRTelegramBuffer:
    """Collect DSMR telegrams that may be split across websocket messages."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, chunk: str) -> list[str]:
        """Add a websocket chunk and return any complete telegrams."""
        self._buffer += chunk
        telegrams: list[str] = []

        while True:
            start = self._buffer.find("/")
            if start < 0:
                # Retain no arbitrary websocket noise.
                self._buffer = ""
                break

            if start:
                self._buffer = self._buffer[start:]

            end = self._buffer.find("!", 1)
            if end < 0:
                break

            # A DSMR checksum, when present, is four hexadecimal characters
            # after "!". Keep it if it is already in this websocket data.
            end += 1
            checksum_end = end
            while checksum_end < len(self._buffer) and checksum_end < end + 4:
                if self._buffer[checksum_end] not in "0123456789abcdefABCDEF":
                    break
                checksum_end += 1

            telegrams.append(self._buffer[:checksum_end])
            self._buffer = self._buffer[checksum_end:]

        return telegrams


class HomeyP1Client:
    """Yield raw DSMR telegrams from a Homey Energy Dongle."""

    def __init__(self, session: ClientSession, host: str) -> None:
        self._session = session
        self.host = host
        self.url = f"ws://{host}:{DEFAULT_PORT}{WS_PATH}"

    async def telegrams(self) -> AsyncIterator[str]:
        """Connect once and yield complete raw DSMR telegrams."""
        websocket = await asyncio.wait_for(
            self._session.ws_connect(
                self.url,
                heartbeat=30,
                autoping=True,
            ),
            CONNECT_TIMEOUT_SECONDS,
        )

        async with websocket:
            telegram_buffer = DSMRTelegramBuffer()
            loop = asyncio.get_running_loop()
            telegram_deadline = loop.time() + TELEGRAM_TIMEOUT_SECONDS

            while True:
                remaining = telegram_deadline - loop.time()
                if remaining <= 0:
                    raise CannotConnectError(
                        f"no complete DSMR telegram received for "
                        f"{TELEGRAM_TIMEOUT_SECONDS} seconds"
                    )

                try:
                    message = await websocket.receive(timeout=remaining)
                except (TimeoutError, asyncio.TimeoutError) as err:
                    raise CannotConnectError(
                        f"no complete DSMR telegram received for "
                        f"{TELEGRAM_TIMEOUT_SECONDS} seconds"
                    ) from err

                if message.type == WSMsgType.TEXT:
                    chunk = message.data
                elif message.type == WSMsgType.BINARY:
                    chunk = message.data.decode(errors="ignore")
                elif message.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSED):
                    raise classify_close_reason(str(message.extra or ""))
                else:
                    continue

                telegrams = telegram_buffer.feed(chunk)
                if telegrams:
                    telegram_deadline = loop.time() + TELEGRAM_TIMEOUT_SECONDS

                for telegram in telegrams:
                    yield telegram
