"""Tests for transient DSMR data retention."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GRACE_PATH = REPO_ROOT / "custom_components" / "homey_p1" / "grace.py"

spec = importlib.util.spec_from_file_location("homey_p1_grace", GRACE_PATH)
grace = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(grace)


class LastKnownDataTests(unittest.TestCase):
    """Test bounded retention of fields omitted from DSMR telegrams."""

    def test_retains_value_during_one_off_omission(self) -> None:
        cache = grace.LastKnownData(15)
        cache.update({"tariff_indicator": 2, "power_consumption": 0.5}, 100)

        result = cache.update({"power_consumption": 0.6}, 105)

        self.assertEqual(result["tariff_indicator"], 2)
        self.assertEqual(result["power_consumption"], 0.6)

    def test_expires_value_after_sustained_omission(self) -> None:
        cache = grace.LastKnownData(15)
        cache.update({"tariff_indicator": 2, "power_consumption": 0.5}, 100)

        result = cache.update({"power_consumption": 0.7}, 115)

        self.assertNotIn("tariff_indicator", result)
        self.assertEqual(result["power_consumption"], 0.7)

    def test_reappearing_value_restarts_grace_period(self) -> None:
        cache = grace.LastKnownData(15)
        cache.update({"tariff_indicator": 2}, 100)
        cache.update({}, 110)
        cache.update({"tariff_indicator": 1}, 112)

        result = cache.update({}, 126)

        self.assertEqual(result["tariff_indicator"], 1)

    def test_none_does_not_replace_last_valid_value(self) -> None:
        cache = grace.LastKnownData(15)
        cache.update({"tariff_indicator": 2}, 100)

        result = cache.update({"tariff_indicator": None}, 105)

        self.assertEqual(result["tariff_indicator"], 2)


if __name__ == "__main__":
    unittest.main()
