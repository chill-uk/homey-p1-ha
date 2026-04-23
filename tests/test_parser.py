"""Tests for the DSMR telegram parser."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PARSER_PATH = REPO_ROOT / "custom_components" / "homey_p1" / "parser.py"

spec = importlib.util.spec_from_file_location("homey_p1_parser", PARSER_PATH)
parser = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(parser)

SAMPLE_TELEGRAM = r"""/XYZ5\TESTMETER-0001

1-3:0.2.8(50)
0-0:1.0.0(260423134812S)
0-0:96.1.1(4531323334353637383930313233343536)
1-0:1.8.1(014339.615*kWh)
1-0:1.8.2(015748.606*kWh)
1-0:2.8.1(000001.229*kWh)
1-0:2.8.2(000002.838*kWh)
0-0:96.14.0(0002)
1-0:1.7.0(00.005*kW)
1-0:2.7.0(00.000*kW)
0-0:96.7.21(00016)
0-0:96.7.9(00007)
1-0:99.97.0(2)(0-0:96.7.19)(170112141836W)(0000001793*s)(221224033537W)(0000016055*s)
1-0:32.32.0(00014)
1-0:32.36.0(00002)
0-0:96.13.0()
1-0:32.7.0(242.1*V)
1-0:31.7.0(003*A)
1-0:21.7.0(00.000*kW)
1-0:22.7.0(00.000*kW)
0-1:24.1.0(003)
0-1:96.1.0(4739383736353433323130393837363534)
0-1:24.2.1(260423134501S)(11035.909*m3)
!DD34
"""


class ParseTelegramTests(unittest.TestCase):
    """Test DSMR telegram parsing."""

    def test_parses_real_homey_telegram(self) -> None:
        result = parser.parse_dsmr_telegram(SAMPLE_TELEGRAM)

        self.assertEqual(result["telegram_timestamp"], "260423134812S")
        self.assertEqual(
            result["equipment_id"],
            "4531323334353637383930313233343536",
        )
        self.assertEqual(result["tariff_indicator"], 2)
        self.assertEqual(result["energy_import_tariff_1"], 14339.615)
        self.assertEqual(result["energy_import_tariff_2"], 15748.606)
        self.assertEqual(result["energy_export_tariff_1"], 1.229)
        self.assertEqual(result["energy_export_tariff_2"], 2.838)
        self.assertEqual(result["power_consumption"], 0.005)
        self.assertEqual(result["power_production"], 0.0)
        self.assertEqual(result["power_failures"], 16)
        self.assertEqual(result["long_power_failures"], 7)
        self.assertEqual(result["voltage_sags_l1"], 14)
        self.assertEqual(result["voltage_swells_l1"], 2)
        self.assertEqual(result["voltage_l1"], 242.1)
        self.assertEqual(result["current_l1"], 3.0)
        self.assertEqual(result["power_consumption_l1"], 0.0)
        self.assertEqual(result["power_production_l1"], 0.0)
        self.assertEqual(result["gas_timestamp"], "260423134501S")
        self.assertEqual(result["gas_delivered"], 11035.909)

    def test_ignores_unknown_lines_and_empty_telegram(self) -> None:
        result = parser.parse_dsmr_telegram("/HEADER\n1-0:99.99.9(abc)\n!0000\n")
        self.assertEqual(result, {})
