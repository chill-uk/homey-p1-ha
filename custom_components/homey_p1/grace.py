"""Bounded retention for values omitted from transient DSMR telegrams."""

from __future__ import annotations

from collections.abc import Mapping


class LastKnownData:
    """Keep recently seen values while expiring genuinely stale fields."""

    def __init__(self, grace_seconds: float) -> None:
        """Initialize the value cache."""
        self._grace_seconds = grace_seconds
        self._data: dict[str, object] = {}
        self._last_seen: dict[str, float] = {}

    def update(
        self,
        incoming: Mapping[str, object],
        now: float,
    ) -> dict[str, object]:
        """Merge a telegram and remove fields absent beyond the grace period."""
        seen_keys: set[str] = set()
        for key, value in incoming.items():
            if value is None:
                continue
            self._data[key] = value
            self._last_seen[key] = now
            seen_keys.add(key)

        for key in tuple(self._data):
            if key in seen_keys:
                continue
            if now - self._last_seen[key] >= self._grace_seconds:
                self._data.pop(key)
                self._last_seen.pop(key)

        return self._data.copy()
