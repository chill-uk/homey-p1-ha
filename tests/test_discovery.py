"""Tests for optional DSMR capability discovery."""

import unittest

from custom_components.homey_p1.discovery import new_optional_meter_keys


class OptionalMeterDiscoveryTests(unittest.TestCase):
    """Verify optional entities can appear after initial setup."""

    def test_discovers_totals_when_data_arrives_after_setup(self) -> None:
        """Late first telegram exposes both total counters exactly once."""
        known: set[str] = set()

        self.assertEqual(new_optional_meter_keys({}, known), ())

        data = {
            "power_consumption": 123.0,
            "energy_import_total": 10000.123,
            "energy_export_total": 500.456,
        }
        discovered = new_optional_meter_keys(data, known)

        self.assertEqual(
            discovered,
            ("energy_import_total", "energy_export_total"),
        )

        known.update(discovered)
        self.assertEqual(new_optional_meter_keys(data, known), ())

    def test_discovers_each_optional_counter_independently(self) -> None:
        """A meter can expose one optional total before the other."""
        known: set[str] = set()

        first = new_optional_meter_keys({"energy_import_total": 1.0}, known)
        self.assertEqual(first, ("energy_import_total",))

        known.update(first)
        second = new_optional_meter_keys(
            {
                "energy_import_total": 1.0,
                "energy_export_total": 2.0,
            },
            known,
        )
        self.assertEqual(second, ("energy_export_total",))


if __name__ == "__main__":
    unittest.main()
