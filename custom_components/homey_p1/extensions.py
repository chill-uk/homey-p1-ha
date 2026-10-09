"""Local DSMR compatibility extensions.

Keep generic additions here only until they are available in the dsmr-parser
version shipped by Home Assistant. Vendor-specific OBIS support can remain here.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

from dsmr_parser import obis_references as obis
from dsmr_parser.parsers import CosemParser, ValueParser


def extended_spec(base_spec: dict[str, Any]) -> dict[str, Any]:
    """Return a parser specification with required compatibility extensions."""
    spec = deepcopy(base_spec)
    extensions = (
        ("ELECTRICITY_IMPORTED_TOTAL", getattr(obis, "ELECTRICITY_IMPORTED_TOTAL", None)),
        ("ELECTRICITY_EXPORTED_TOTAL", getattr(obis, "ELECTRICITY_EXPORTED_TOTAL", None)),
    )
    existing = {item["value_name"] for item in spec["objects"]}

    for value_name, reference in extensions:
        if reference is None or value_name in existing:
            continue
        spec["objects"].append(
            {
                "obis_reference": reference,
                "value_parser": CosemParser(ValueParser(Decimal)),
                "value_name": value_name,
            }
        )

    return spec
