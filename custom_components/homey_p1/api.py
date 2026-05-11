"""Helpers for talking to the Homey P1 websocket."""

from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientSession, WSServerHandshakeError, WSMsgType

from .const import DEFAULT_PORT, WS_PATH


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
        async with session.ws_connect(url, heartbeat=30, autoping=True) as websocket:
            try:
                message = await websocket.receive(timeout=1)
            except TimeoutError:
                return
            except asyncio.TimeoutError:
                return

            if message.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                return

            if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                raise classify_close_reason(str(message.extra or ""))
    except LocalAPIDisabledError:
        raise
    except ConnectionLimitError:
        raise
    except (ClientError, WSServerHandshakeError) as err:
        raise CannotConnectError(str(err)) from err
