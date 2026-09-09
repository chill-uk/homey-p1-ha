"""Helpers for talking to the Homey P1 websocket."""

from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientSession, WSMsgType, WSServerHandshakeError

from .const import DEFAULT_PORT, VALIDATION_TIMEOUT_SECONDS, WS_PATH
from .parser import DSMRTelegramBuffer, parse_dsmr_telegram


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


async def async_validate_connection(session: ClientSession, host: str) -> None:
    """Validate that the Homey websocket is reachable."""
    url = f"ws://{host}:{DEFAULT_PORT}{WS_PATH}"

    try:
        async with asyncio.timeout(VALIDATION_TIMEOUT_SECONDS):
            async with session.ws_connect(
                url,
                heartbeat=30,
                autoping=True,
            ) as websocket:
                telegram_buffer = DSMRTelegramBuffer()
                while True:
                    message = await websocket.receive()

                    if message.type == WSMsgType.TEXT:
                        chunk = message.data
                    elif message.type == WSMsgType.BINARY:
                        chunk = message.data.decode(errors="ignore")
                    elif message.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSED,
                        WSMsgType.ERROR,
                    ):
                        raise classify_close_reason(str(message.extra or ""))
                    else:
                        continue

                    if any(
                        parse_dsmr_telegram(telegram)
                        for telegram in telegram_buffer.feed(chunk)
                    ):
                        return
    except LocalAPIDisabledError:
        raise
    except ConnectionLimitError:
        raise
    except (ClientError, WSServerHandshakeError, TimeoutError) as err:
        raise CannotConnectError(str(err)) from err
