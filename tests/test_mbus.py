"""Tests for M-Bus measurement interpretation."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MBUS_PATH = REPO_ROOT / "custom_components" / "homey_p1" / "mbus.py"

spec = importlib.util.spec_from_file_location("homey_p1_mbus", MBUS_PATH)
mbus = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mbus)


class MBusMeasurementTests(unittest.TestCase):
    """Test M-Bus device type and unit interpretation."""

    def test_classifies_gas_volume(self) -> None:
        self.assertEqual(mbus.classify_mbus_measurement(3, "m3"), "gas")

    def test_classifies_gas_reported_as_energy(self) -> None:
        self.assertEqual(mbus.classify_mbus_measurement(3, "kWh"), "energy")

    def test_classifies_heat_energy(self) -> None:
        self.assertEqual(mbus.classify_mbus_measurement(4, "GJ"), "energy")

    def test_classifies_water_volume(self) -> None:
        self.assertEqual(mbus.classify_mbus_measurement(7, "m3"), "water")

    def test_normalizes_string_device_type(self) -> None:
        self.assertEqual(mbus.normalize_device_type("007"), 7)

    def test_leaves_unknown_measurement_unclassified(self) -> None:
        self.assertIsNone(mbus.classify_mbus_measurement(99, "m3"))
