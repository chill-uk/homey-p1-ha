"""Tests for the DSMR telegram parser."""

from __future__ import annotations

import importlib.util
import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PARSER_PATH = REPO_ROOT / "custom_components" / "homey_p1" / "parser.py"

spec = importlib.util.spec_from_file_location("homey_p1_parser", PARSER_PATH)
parser = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(parser)

SAMPLE_TELEGRAM = r"""/XYZ5\TESTMETER-0001

1-3:0.2.8(50)
0-0:1.0.0(240424101530S)
0-0:96.1.1(4531323334353637383930313233343536)
1-0:1.8.1(001234.567*kWh)
1-0:1.8.2(008765.432*kWh)
1-0:2.8.1(000123.456*kWh)
1-0:2.8.2(000234.567*kWh)
0-0:96.14.0(0002)
1-0:1.7.0(01.234*kW)
1-0:2.7.0(00.321*kW)
0-0:96.7.21(00003)
0-0:96.7.9(00001)
1-0:99.97.0(1)(0-0:96.7.19)(240101120000W)(0000000120*s)
1-0:32.32.0(00004)
1-0:32.36.0(00001)
0-0:96.13.0()
1-0:32.7.0(230.4*V)
1-0:31.7.0(006*A)
1-0:21.7.0(00.789*kW)
1-0:22.7.0(00.111*kW)
0-1:24.1.0(003)
0-1:96.1.0(4739383736353433323130393837363534)
0-1:24.2.1(240424101000S)(00123.456*m3)
0-2:24.1.0(004)
0-2:96.1.0(4831323334353637383930313233343536)
0-2:24.2.1(240424101100S)(00456.789*GJ)
!ABCD
"""


class ParseTelegramTests(unittest.TestCase):
    """Test DSMR telegram parsing."""

    def test_parses_real_homey_telegram(self) -> None:
        result = parser.parse_dsmr_telegram(SAMPLE_TELEGRAM)

        self.assertRegex(result["meter_manufacturer"], r"^[A-Z]{3}$")
        self.assertTrue(result["meter_model"])
        self.assertRegex(result["protocol_family"], r"^DSMR v\d+$")
        self.assertRegex(result["telegram_timestamp"], r"^\d{12}[SW]$")
        self.assertRegex(result["equipment_id"], r"^[0-9A-F]+$")
        self.assertTrue(result["electricity_meter_id"])
        self.assertEqual(
            result["electricity_meter_id"],
            bytes.fromhex(result["equipment_id"]).decode("ascii"),
        )
        self.assertIn(result["tariff_indicator"], (1, 2))
        self.assertGreaterEqual(result["energy_import_tariff_1"], 0.0)
        self.assertGreaterEqual(result["energy_import_tariff_2"], 0.0)
        self.assertGreaterEqual(result["energy_export_tariff_1"], 0.0)
        self.assertGreaterEqual(result["energy_export_tariff_2"], 0.0)
        self.assertGreaterEqual(
            result["energy_import_tariff_2"],
            result["energy_export_tariff_2"],
        )
        self.assertGreaterEqual(result["power_consumption"], 0.0)
        self.assertGreaterEqual(result["power_production"], 0.0)
        self.assertGreaterEqual(result["power_failures"], 0)
        self.assertGreaterEqual(result["long_power_failures"], 0)
        self.assertGreaterEqual(result["voltage_sags_l1"], 0)
        self.assertGreaterEqual(result["voltage_swells_l1"], 0)
        self.assertGreater(result["voltage_l1"], 0.0)
        self.assertGreaterEqual(result["current_l1"], 0.0)
        self.assertGreaterEqual(result["power_consumption_l1"], 0.0)
        self.assertGreaterEqual(result["power_production_l1"], 0.0)
        self.assertEqual(result["mbus_device_type"], 3)
        self.assertRegex(result["gas_equipment_id"], r"^[0-9A-F]+$")
        self.assertEqual(
            result["mbus_meter_id"],
            bytes.fromhex(result["gas_equipment_id"]).decode("ascii"),
        )
        self.assertRegex(result["gas_timestamp"], r"^\d{12}[SW]$")
        self.assertGreaterEqual(result["gas_delivered"], 0.0)
        self.assertIn("mbus_channels", result)
        self.assertEqual(sorted(result["mbus_channels"]), ["1", "2"])
        self.assertEqual(result["mbus_channels"]["1"]["device_type"], 3)
        self.assertEqual(result["mbus_channels"]["1"]["unit"], "m3")
        self.assertEqual(result["mbus_channels"]["2"]["device_type"], 4)
        self.assertEqual(result["mbus_channels"]["2"]["unit"], "GJ")
        self.assertEqual(
            result["mbus_channels"]["2"]["meter_id"],
            bytes.fromhex(result["mbus_channels"]["2"]["equipment_id"]).decode("ascii"),
        )

    def test_ignores_unknown_lines_and_empty_telegram(self) -> None:
        result = parser.parse_dsmr_telegram("/HEADER\n1-0:99.99.9(abc)\n!0000\n")
        self.assertEqual(result, {})
