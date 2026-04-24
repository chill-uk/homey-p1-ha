"""Sensors for the Homey P1 integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeyP1Coordinator


@dataclass(frozen=True, kw_only=True)
class HomeyP1SensorDescription(SensorEntityDescription):
    """Describe a Homey P1 sensor."""

    enabled_by_default: bool = True


SENSORS: tuple[HomeyP1SensorDescription, ...] = (
    HomeyP1SensorDescription(
        key="energy_import_tariff_1",
        translation_key="energy_import_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeyP1SensorDescription(
        key="energy_import_tariff_2",
        translation_key="energy_import_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeyP1SensorDescription(
        key="energy_export_tariff_1",
        translation_key="energy_export_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeyP1SensorDescription(
        key="energy_export_tariff_2",
        translation_key="energy_export_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeyP1SensorDescription(
        key="power_consumption",
        translation_key="power_consumption",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HomeyP1SensorDescription(
        key="power_production",
        translation_key="power_production",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HomeyP1SensorDescription(
        key="power_consumption_l1",
        translation_key="power_consumption_l1",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_consumption_l2",
        translation_key="power_consumption_l2",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_consumption_l3",
        translation_key="power_consumption_l3",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_production_l1",
        translation_key="power_production_l1",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_production_l2",
        translation_key="power_production_l2",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_production_l3",
        translation_key="power_production_l3",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HomeyP1SensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="current_l1",
        translation_key="current_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="current_l2",
        translation_key="current_l2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="current_l3",
        translation_key="current_l3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="tariff_indicator",
        translation_key="tariff_indicator",
        icon="mdi:counter",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="power_failures",
        translation_key="power_failures",
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="long_power_failures",
        translation_key="long_power_failures",
        icon="mdi:flash-alert",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_sags_l1",
        translation_key="voltage_sags_l1",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_sags_l2",
        translation_key="voltage_sags_l2",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_sags_l3",
        translation_key="voltage_sags_l3",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_swells_l1",
        translation_key="voltage_swells_l1",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_swells_l2",
        translation_key="voltage_swells_l2",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
    HomeyP1SensorDescription(
        key="voltage_swells_l3",
        translation_key="voltage_swells_l3",
        icon="mdi:sine-wave",
        enabled_by_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homey P1 sensors."""
    coordinator: HomeyP1Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        HomeyP1Sensor(coordinator, entry, description) for description in SENSORS
    ]
    for channel in sorted(coordinator.data.get("mbus_channels", {}), key=int):
        entities.append(HomeyP1MBusDeliveredSensor(coordinator, entry, channel))
    async_add_entities(entities)


class HomeyP1Sensor(CoordinatorEntity[HomeyP1Coordinator], SensorEntity):
    """Representation of a Homey P1 sensor."""

    entity_description: HomeyP1SensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomeyP1Coordinator,
        entry: ConfigEntry,
        description: HomeyP1SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_entity_registry_enabled_default = description.enabled_by_default

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.available and self.native_value is not None

    @property
    def native_value(self):
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers=self.coordinator.device_identifiers,
            manufacturer=self.coordinator.data.get("meter_manufacturer", "Homey"),
            model=_electricity_meter_model(self.coordinator.data),
            name=METER_TYPE_MAP[2],
            serial_number=self.coordinator.data.get("electricity_meter_id"),
        )


class HomeyP1MBusDeliveredSensor(CoordinatorEntity[HomeyP1Coordinator], SensorEntity):
    """Representation of a delivered-volume/energy sensor for one M-Bus channel."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: HomeyP1Coordinator,
        entry: ConfigEntry,
        channel: str,
    ) -> None:
        """Initialize the M-Bus sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self.channel = channel
        self._attr_unique_id = f"{entry.entry_id}_mbus_{channel}_delivered"
        self._attr_translation_key = "gas_delivered"

    @property
    def _channel_data(self) -> dict:
        """Return channel-specific data."""
        return self.coordinator.data.get("mbus_channels", {}).get(self.channel, {})

    @property
    def name(self) -> str:
        """Return the entity name."""
        meter_name = _mbus_device_type_name(self._channel_data.get("device_type"))
        return f"{meter_name} delivered"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.available and self.native_value is not None

    @property
    def native_value(self):
        """Return the sensor value."""
        return self._channel_data.get("delivered")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the channel unit."""
        unit = self._channel_data.get("unit")
        if unit == "m3":
            return UnitOfVolume.CUBIC_METERS
        return unit

    @property
    def device_class(self):
        """Return the best matching device class."""
        device_type = _normalize_device_type(self._channel_data.get("device_type"))
        if device_type == 3:
            return SensorDeviceClass.GAS
        if self.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
            return SensorDeviceClass.ENERGY
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        meter_id = self._channel_data.get("equipment_id", f"channel:{self.channel}")
        return DeviceInfo(
            identifiers={(DOMAIN, f"mbus:{self.channel}:{meter_id}")},
            via_device=self.coordinator.primary_device_identifier,
            model=_mbus_device_details(
                self.channel,
                self._channel_data.get("device_type"),
            ),
            name=_mbus_device_title(self._channel_data.get("device_type")),
            serial_number=self._channel_data.get("meter_id"),
        )


def _mbus_device_type_name(device_type: object) -> str:
    """Return a readable M-Bus device type name."""
    return METER_TYPE_MAP.get(_normalize_device_type(device_type), "M-Bus meter")


def _mbus_device_label(device_type: object) -> str:
    """Return the label shown for an M-Bus device."""
    name = _mbus_device_type_name(device_type)
    code = _mbus_device_type_code(device_type)
    if code:
        return f"{name} (ID:{code})"
    return name


def _mbus_device_title(device_type: object) -> str:
    """Return the device name shown in Home Assistant."""
    return _mbus_device_type_name(device_type).title()


def _mbus_device_details(channel: str, device_type: object) -> str:
    """Return the detail text shown under the M-Bus device name."""
    code = _mbus_device_type_code(device_type)
    if code:
        return f"M-Bus {channel} / ID:{code}"
    return f"M-Bus {channel}"


def _mbus_device_type_code(device_type: object) -> str | None:
    """Return the three-digit device type code for display."""
    normalized = _normalize_device_type(device_type)
    if normalized is None:
        return None
    return f"{normalized:03d}"


def _normalize_device_type(device_type: object) -> int | None:
    """Convert a device type to an integer when possible."""
    if isinstance(device_type, int):
        return device_type

    if isinstance(device_type, str):
        try:
            return int(device_type, 10)
        except ValueError:
            return None

    return None


METER_TYPE_MAP: dict[int, str] = {
    2: "Electricity meter",
    3: "Gas meter",
    4: "Heat meter",
    5: "Cooling meter",
    6: "Hot water meter",
    7: "Water meter",
}


def _electricity_meter_model(data: dict) -> str:
    """Build the electricity meter model label shown in Home Assistant."""
    meter_model = data.get("meter_model")
    protocol_family = data.get("protocol_family")

    if meter_model and protocol_family:
        return f"{meter_model} / {protocol_family}"
    if meter_model:
        return str(meter_model)
    if protocol_family:
        return str(protocol_family)
    return "Electricity meter"
