"""Validation helpers for talking to the Homey P1 websocket."""

from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientSession, WSServerHandshakeError

from .client import (
    CannotConnectError,
    ConnectionLimitError,
    HomeyP1Client,
    LocalAPIDisabledError,
    classify_close_reason,
)
from .const import VALIDATION_TIMEOUT_SECONDS
from .parser import parse_dsmr_telegram


async def async_validate_connection(session: ClientSession, host: str) -> None:
    """Validate that the Homey websocket is reachable and carries DSMR data."""
    client = HomeyP1Client(session, host)

    try:
        async with asyncio.timeout(VALIDATION_TIMEOUT_SECONDS):
            async for telegram in client.telegrams():
                if parse_dsmr_telegram(telegram):
                    return
    except LocalAPIDisabledError:
        raise
    except ConnectionLimitError:
        raise
    except CannotConnectError:
        raise
    except (ClientError, WSServerHandshakeError, TimeoutError) as err:
        raise CannotConnectError(str(err)) from err
