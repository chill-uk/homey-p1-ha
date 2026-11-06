"""DLMS/COSEM general-global-ciphering support for encrypted P1 meters.

Some meters (e.g. Austrian smart meters such as the Sagemcom T210-D-r used by
Energienetze Steiermark, Luxembourg Smarty) do not emit plaintext DSMR on the
customer interface. Instead every telegram is wrapped in a DLMS
``general-glo-ciphering`` APDU (tag ``0xDB``) and encrypted with AES-128-GCM.
The Homey Energy Dongle Local API forwards these frames unchanged, so the
integration has to decrypt them itself.

Frame layout::

    DB                      general-glo-ciphering tag
    08 <8 bytes>            system title (length + value)
    <A-XDR length>          length of the remaining payload
    <1 byte>                security control byte
    <4 bytes>               invocation (frame) counter
    <ciphertext>            encrypted DSMR telegram
    <12 bytes>              GCM authentication tag (if authenticated)

The GCM IV is ``system_title || frame_counter``; the additional authenticated
data is ``security_control || authentication_key``.
"""

from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

GENERAL_GLO_CIPHERING_TAG = 0xDB
SYSTEM_TITLE_LENGTH = 8
GCM_TAG_LENGTH = 12
MAX_FRAME_PAYLOAD = 4096

SECURITY_AUTHENTICATED = 0x10
SECURITY_ENCRYPTED = 0x20


class DecryptionError(Exception):
    """Raised when an encrypted frame cannot be decrypted."""


class InvalidKeyError(DecryptionError):
    """Raised when the key does not match the frame (tag or plaintext invalid)."""


def normalize_key(value: str | None) -> bytes | None:
    """Return a 16-byte key from a hex string, or ``None`` when empty.

    Whitespace, colons and dashes are ignored so keys can be pasted as shown
    by network operator portals.
    """
    if value is None:
        return None
    cleaned = "".join(ch for ch in str(value) if ch not in " \t\r\n:-")
    if not cleaned:
        return None
    try:
        key = bytes.fromhex(cleaned)
    except ValueError as err:
        raise ValueError("key must be hexadecimal") from err
    if len(key) != 16:
        raise ValueError("key must be 32 hexadecimal characters (16 bytes)")
    return key


def looks_encrypted(data: bytes) -> bool:
    """Return whether ``data`` starts like a general-glo-ciphering APDU."""
    return (
        len(data) >= 2
        and data[0] == GENERAL_GLO_CIPHERING_TAG
        and data[1] == SYSTEM_TITLE_LENGTH
    )


def _read_length(buffer: bytes | bytearray, pos: int) -> tuple[int, int] | None:
    """Read an A-XDR length at ``pos``; return ``(length, next_pos)`` or ``None``."""
    if pos >= len(buffer):
        return None
    first = buffer[pos]
    if first < 0x80:
        return first, pos + 1
    count = first & 0x7F
    if count == 0 or count > 2:
        raise DecryptionError("unsupported A-XDR length encoding")
    if pos + 1 + count > len(buffer):
        return None
    return int.from_bytes(buffer[pos + 1 : pos + 1 + count], "big"), pos + 1 + count


class DLMSFrameBuffer:
    """Collect general-glo-ciphering frames that may be split across messages."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Add a websocket chunk and return any complete frames."""
        self._buffer += chunk
        frames: list[bytes] = []

        while True:
            start = self._buffer.find(bytes([GENERAL_GLO_CIPHERING_TAG]))
            if start < 0:
                self._buffer.clear()
                break
            if start:
                del self._buffer[:start]

            if len(self._buffer) < 2:
                break
            if self._buffer[1] != SYSTEM_TITLE_LENGTH:
                del self._buffer[:1]
                continue

            header_end = 2 + SYSTEM_TITLE_LENGTH
            try:
                length_info = _read_length(self._buffer, header_end)
            except DecryptionError:
                del self._buffer[:1]
                continue
            if length_info is None:
                break

            length, payload_start = length_info
            if length < 5 or length > MAX_FRAME_PAYLOAD:
                del self._buffer[:1]
                continue

            frame_end = payload_start + length
            if len(self._buffer) < frame_end:
                break

            frames.append(bytes(self._buffer[:frame_end]))
            del self._buffer[:frame_end]

        return frames


def decrypt_frame(
    frame: bytes,
    encryption_key: bytes,
    authentication_key: bytes | None = None,
) -> str:
    """Decrypt a general-glo-ciphering frame and return the DSMR telegram text.

    When the frame is authenticated and ``authentication_key`` is given, the
    GCM tag is verified. Without an authentication key the payload is
    decrypted without tag verification (as ESPHome and dsmr-parser do for
    meters whose AK is not published); the plaintext is then sanity-checked.
    """
    if not looks_encrypted(frame):
        raise DecryptionError("not a general-glo-ciphering frame")

    system_title = frame[2 : 2 + SYSTEM_TITLE_LENGTH]
    length_info = _read_length(frame, 2 + SYSTEM_TITLE_LENGTH)
    if length_info is None:
        raise DecryptionError("truncated frame")
    length, pos = length_info
    payload = frame[pos : pos + length]
    if len(payload) != length or length < 5:
        raise DecryptionError("truncated frame")

    security_control = payload[0]
    if not security_control & SECURITY_ENCRYPTED:
        raise DecryptionError("frame is not encrypted")
    frame_counter = payload[1:5]
    authenticated = bool(security_control & SECURITY_AUTHENTICATED)

    iv = system_title + frame_counter
    if authenticated:
        if len(payload) < 5 + GCM_TAG_LENGTH:
            raise DecryptionError("truncated frame")
        ciphertext = payload[5:-GCM_TAG_LENGTH]
        tag = payload[-GCM_TAG_LENGTH:]
    else:
        ciphertext = payload[5:]
        tag = b""

    if authenticated and authentication_key is not None:
        decryptor = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(iv, tag, min_tag_length=GCM_TAG_LENGTH),
        ).decryptor()
        decryptor.authenticate_additional_data(
            bytes([security_control]) + authentication_key
        )
        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        except InvalidTag as err:
            raise InvalidKeyError(
                "authentication failed; check the encryption and authentication keys"
            ) from err
    else:
        # GCM without tag verification is AES-CTR starting at counter block 2.
        decryptor = Cipher(
            algorithms.AES(encryption_key),
            modes.CTR(iv + b"\x00\x00\x00\x02"),
        ).decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    try:
        telegram = plaintext.decode("ascii")
    except UnicodeDecodeError as err:
        raise InvalidKeyError("decrypted payload is not a DSMR telegram") from err
    if not telegram.startswith("/"):
        raise InvalidKeyError("decrypted payload is not a DSMR telegram")
    return telegram
