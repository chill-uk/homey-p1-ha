"""Homey P1 websocket transport.

This module owns device-specific framing and connection behavior. It deliberately
returns raw DSMR telegrams and contains no OBIS interpretation.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from aiohttp import ClientSession, WSMsgType

from .const import CONNECT_TIMEOUT_SECONDS, DEFAULT_PORT, TELEGRAM_TIMEOUT_SECONDS, WS_PATH
from .decryption import DLMSFrameBuffer, decrypt_frame, looks_encrypted
from .framing import DSMRTelegramBuffer


class CannotConnectError(Exception):
    """Raised when the websocket cannot be reached."""


class ConnectionLimitError(Exception):
    """Raised when the Homey websocket has no free client slots."""


class LocalAPIDisabledError(Exception):
    """Raised when the Local API is disabled on the dongle."""


class EncryptionKeyRequiredError(Exception):
    """Raised when the meter sends encrypted frames but no key is configured."""


def classify_close_reason(reason: str) -> Exception:
    """Map a websocket close reason to a typed exception."""
    reason_text = str(reason or "")
    reason_lower = reason_text.lower()

    if "connection limit reached" in reason_lower:
        return ConnectionLimitError(reason_text)
    if "local api disabled" in reason_lower:
        return LocalAPIDisabledError(reason_text)
    return CannotConnectError(reason_text or "websocket closed")


class HomeyP1Client:
    """Yield raw DSMR telegrams from a Homey Energy Dongle."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        encryption_key: bytes | None = None,
        authentication_key: bytes | None = None,
    ) -> None:
        self._session = session
        self.host = host
        self.url = f"ws://{host}:{DEFAULT_PORT}{WS_PATH}"
        self._encryption_key = encryption_key
        self._authentication_key = authentication_key

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
            frame_buffer = DLMSFrameBuffer()
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
                    telegrams = telegram_buffer.feed(message.data)
                elif message.type == WSMsgType.BINARY:
                    telegrams = self._handle_binary(
                        message.data, telegram_buffer, frame_buffer
                    )
                elif message.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSED):
                    raise classify_close_reason(str(message.extra or ""))
                else:
                    continue

                if telegrams:
                    telegram_deadline = loop.time() + TELEGRAM_TIMEOUT_SECONDS

                for telegram in telegrams:
                    yield telegram

    def _handle_binary(
        self,
        data: bytes,
        telegram_buffer: DSMRTelegramBuffer,
        frame_buffer: DLMSFrameBuffer,
    ) -> list[str]:
        """Return telegrams from a binary message, decrypting DLMS frames."""
        if self._encryption_key is None:
            if looks_encrypted(data):
                raise EncryptionKeyRequiredError(
                    "meter sends encrypted DLMS frames; configure the encryption key"
                )
            return telegram_buffer.feed(data.decode(errors="ignore"))

        return [
            decrypt_frame(frame, self._encryption_key, self._authentication_key)
            for frame in frame_buffer.feed(data)
        ]
