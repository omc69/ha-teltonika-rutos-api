"""Binary sensor platform for the Teltonika RutOS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import to_int
from .coordinator import RutosData, TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity


@dataclass(frozen=True, kw_only=True)
class RutosBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one RutOS binary sensor."""

    value_fn: Callable[[RutosData], bool | None]


def _gps_fix(data: RutosData) -> bool | None:
    """Return whether the GPS reports a valid fix.

    ``fix_status`` is 1 when the position is valid. The field arrives as a
    string, so compare numerically — a string comparison would silently be
    false forever.
    """
    status = to_int(data.gps.get("fix_status"))
    return None if status is None else status >= 1


def _mobile_connected(data: RutosData) -> bool | None:
    """Return whether the modem has a data connection."""
    modem = data.modem
    if not modem:
        return None
    state = modem.get("data_conn_state") or modem.get("state")
    return None if state is None else str(state).lower() == "connected"


def _sim_inserted(data: RutosData) -> bool | None:
    """Return whether a SIM card is present."""
    modem = data.modem
    if not modem:
        return None
    state = modem.get("simstate")
    return None if state is None else str(state).lower() == "inserted"


BINARY_SENSORS: tuple[RutosBinarySensorDescription, ...] = (
    RutosBinarySensorDescription(
        key="gps_fix",
        translation_key="gps_fix",
        icon="mdi:crosshairs-gps",
        value_fn=_gps_fix,
    ),
    RutosBinarySensorDescription(
        key="mobile_connected",
        translation_key="mobile_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_mobile_connected,
    ),
    RutosBinarySensorDescription(
        key="sim_inserted",
        translation_key="sim_inserted",
        icon="mdi:sim",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sim_inserted,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        TeltonikaBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class TeltonikaBinarySensor(TeltonikaEntity, BinarySensorEntity):
    """A binary sensor derived from one field of the snapshot."""

    entity_description: RutosBinarySensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        entry: TeltonikaConfigEntry,
        description: RutosBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Report unavailable while the underlying field is missing."""
        return super().available and self.is_on is not None
