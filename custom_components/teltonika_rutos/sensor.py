"""Sensor platform for the Teltonika RutOS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    EntityCategory,
    UnitOfInformation,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import to_float, to_int
from .coordinator import RutosData, TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity


@dataclass(frozen=True, kw_only=True)
class RutosSensorDescription(SensorEntityDescription):
    """Describes one RutOS sensor."""

    value_fn: Callable[[RutosData], StateType]


def _modem(data: RutosData, key: str) -> Any:
    """Read a field from the first modem, or None if there is none."""
    modem = data.modem
    return modem.get(key) if modem else None


SENSORS: tuple[RutosSensorDescription, ...] = (
    # --- GPS ---------------------------------------------------------------
    # One endpoint delivers all of these from the same sample, so the values
    # are always consistent with each other.
    RutosSensorDescription(
        key="gps_latitude",
        translation_key="gps_latitude",
        icon="mdi:latitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_float(d.gps.get("latitude")),
    ),
    RutosSensorDescription(
        key="gps_longitude",
        translation_key="gps_longitude",
        icon="mdi:longitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_float(d.gps.get("longitude")),
    ),
    RutosSensorDescription(
        key="gps_altitude",
        translation_key="gps_altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: to_float(d.gps.get("altitude")),
    ),
    RutosSensorDescription(
        key="gps_speed",
        translation_key="gps_speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: to_float(d.gps.get("speed")),
    ),
    RutosSensorDescription(
        key="gps_accuracy",
        translation_key="gps_accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_float(d.gps.get("accuracy")),
    ),
    RutosSensorDescription(
        key="gps_satellites",
        translation_key="gps_satellites",
        icon="mdi:satellite-variant",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: to_int(d.gps.get("satellites")),
    ),
    RutosSensorDescription(
        key="gps_heading",
        translation_key="gps_heading",
        icon="mdi:compass",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_float(d.gps.get("angle")),
    ),
    # --- Mobile signal -----------------------------------------------------
    RutosSensorDescription(
        key="signal",
        translation_key="signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: to_int(_modem(d, "signal")),
    ),
    RutosSensorDescription(
        key="signal_quality",
        translation_key="signal_quality",
        icon="mdi:signal-cellular-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: to_int(_modem(d, "signal_quality")),
    ),
    # RSRP/RSRQ/SINR are not exposed over Modbus at all — they are one of the
    # concrete reasons to use the REST API.
    RutosSensorDescription(
        key="rsrp",
        translation_key="rsrp",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_int(_modem(d, "rsrp")),
    ),
    RutosSensorDescription(
        key="rsrq",
        translation_key="rsrq",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_int(_modem(d, "rsrq")),
    ),
    RutosSensorDescription(
        key="sinr",
        translation_key="sinr",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_int(_modem(d, "sinr")),
    ),
    # --- Mobile network ----------------------------------------------------
    RutosSensorDescription(
        key="operator",
        translation_key="operator",
        icon="mdi:cellphone-wireless",
        value_fn=lambda d: _modem(d, "operator"),
    ),
    RutosSensorDescription(
        key="connection_type",
        translation_key="connection_type",
        icon="mdi:signal-5g",
        value_fn=lambda d: _modem(d, "conntype"),
    ),
    RutosSensorDescription(
        key="connection_state",
        translation_key="connection_state",
        icon="mdi:connection",
        value_fn=lambda d: _modem(d, "state"),
    ),
    RutosSensorDescription(
        key="operator_state",
        translation_key="operator_state",
        icon="mdi:sitemap-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _modem(d, "operator_state"),
    ),
    RutosSensorDescription(
        key="band",
        translation_key="band",
        icon="mdi:radio-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _modem(d, "band"),
    ),
    RutosSensorDescription(
        key="cell_id",
        translation_key="cell_id",
        icon="mdi:tower-fire",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _modem(d, "cellid"),
    ),
    RutosSensorDescription(
        key="active_sim",
        translation_key="active_sim",
        icon="mdi:sim",
        value_fn=lambda d: to_int(_modem(d, "active_sim")),
    ),
    RutosSensorDescription(
        key="sim_state",
        translation_key="sim_state",
        icon="mdi:sim-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _modem(d, "simstate"),
    ),
    # --- Modem hardware ----------------------------------------------------
    RutosSensorDescription(
        key="modem_temperature",
        translation_key="modem_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: to_int(_modem(d, "temperature")),
    ),
    RutosSensorDescription(
        key="modem_rx",
        translation_key="modem_rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_int(_modem(d, "rxbytes")),
    ),
    RutosSensorDescription(
        key="modem_tx",
        translation_key="modem_tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: to_int(_modem(d, "txbytes")),
    ),
)

# Personal identifiers. Created but disabled, so nobody exports them by
# accident — a user who needs them can switch them on deliberately.
IDENTITY_SENSORS: tuple[RutosSensorDescription, ...] = (
    RutosSensorDescription(
        key="imei",
        translation_key="imei",
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _modem(d, "imei"),
    ),
    RutosSensorDescription(
        key="imsi",
        translation_key="imsi",
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _modem(d, "imsi"),
    ),
    RutosSensorDescription(
        key="iccid",
        translation_key="iccid",
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _modem(d, "iccid"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        TeltonikaSensor(coordinator, entry, description)
        for description in (*SENSORS, *IDENTITY_SENSORS)
    ]

    # Traffic counters are created per interface found at setup time.
    for interface_id, interface in coordinator.data.interfaces.items():
        name = interface.get("name") or interface_id
        for direction in ("rx", "tx"):
            entities.append(
                TeltonikaInterfaceSensor(
                    coordinator, entry, interface_id, name, direction
                )
            )

    async_add_entities(entities)


class TeltonikaSensor(TeltonikaEntity, SensorEntity):
    """A sensor whose value comes from one field of the snapshot."""

    entity_description: RutosSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        entry: TeltonikaConfigEntry,
        description: RutosSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Report unavailable when the field is missing entirely.

        A value of 0 is meaningful (speed, SINR), so only None counts as
        missing — never falsiness.
        """
        return super().available and self.native_value is not None


class TeltonikaInterfaceSensor(TeltonikaEntity, SensorEntity):
    """Traffic counter for one network interface."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_suggested_unit_of_measurement = UnitOfInformation.GIGABYTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        entry: TeltonikaConfigEntry,
        interface_id: str,
        interface_name: str,
        direction: str,
    ) -> None:
        """Initialise the counter."""
        super().__init__(coordinator, entry, f"iface_{interface_id}_{direction}")
        self._interface_id = interface_id
        self._field = f"{direction}_bytes"
        arrow = "Down" if direction == "rx" else "Up"
        self._attr_name = f"{interface_name} {arrow}"
        self._attr_icon = "mdi:download" if direction == "rx" else "mdi:upload"

    @property
    def native_value(self) -> StateType:
        """Return the byte counter of this interface."""
        interface = self.coordinator.data.interfaces.get(self._interface_id)
        return to_int(interface.get(self._field)) if interface else None

    @property
    def available(self) -> bool:
        """Report unavailable while the interface is absent from the snapshot."""
        return super().available and self.native_value is not None
