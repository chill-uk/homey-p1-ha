"""Framing helpers for the Homey websocket transport."""

from __future__ import annotations


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
                self._buffer = ""
                break

            if start:
                self._buffer = self._buffer[start:]

            end = self._buffer.find("!", 1)
            if end < 0:
                break

            end += 1
            checksum_end = end
            while checksum_end < len(self._buffer) and checksum_end < end + 4:
                if self._buffer[checksum_end] not in "0123456789abcdefABCDEF":
                    break
                checksum_end += 1

            telegrams.append(self._buffer[:checksum_end])
            self._buffer = self._buffer[checksum_end:]

        return telegrams
