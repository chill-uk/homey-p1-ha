"""Validation helpers for talking to the Homey P1 websocket."""

from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientSession, WSServerHandshakeError

from .client import (
    CannotConnectError,
    ConnectionLimitError,
    EncryptionKeyRequiredError,
    HomeyP1Client,
    LocalAPIDisabledError,
    classify_close_reason,
)
from .const import VALIDATION_TIMEOUT_SECONDS
from .decryption import DecryptionError, InvalidKeyError
from .parser import parse_dsmr_telegram


async def async_validate_connection(
    session: ClientSession,
    host: str,
    encryption_key: bytes | None = None,
    authentication_key: bytes | None = None,
) -> None:
    """Validate that the Homey websocket is reachable and carries DSMR data."""
    client = HomeyP1Client(session, host, encryption_key, authentication_key)

    try:
        async with asyncio.timeout(VALIDATION_TIMEOUT_SECONDS):
            async for telegram in client.telegrams():
                if parse_dsmr_telegram(telegram):
                    return
    except LocalAPIDisabledError:
        raise
    except EncryptionKeyRequiredError:
        raise
    except InvalidKeyError:
        raise
    except DecryptionError as err:
        raise CannotConnectError(str(err)) from err
    except ConnectionLimitError:
        raise
    except CannotConnectError:
        raise
    except (ClientError, WSServerHandshakeError, TimeoutError) as err:
        raise CannotConnectError(str(err)) from err
