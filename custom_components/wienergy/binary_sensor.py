"""Binary sensors for WiEnergy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_MIN_CERTAINTY, DEFAULT_MIN_CERTAINTY
from .coordinator import WiEnergyConfigEntry, WiEnergyCoordinator
from .entity import WiEnergyEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WiEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiEnergy binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities([WiEnergySurplusSensor(coordinator)])


class WiEnergySurplusSensor(WiEnergyEntity, BinarySensorEntity):
    """On while the community reports a usable surplus (switching signal).

    On = level ``surplus``, certainty at least the configured minimum,
    confidence not ``unavailable`` and the signal not expired. When the
    data is outdated the sensor turns off, so automations fall back to
    local logic (Spielregeln 2 and 3).
    """

    _attr_translation_key = "surplus"

    def __init__(self, coordinator: WiEnergyCoordinator) -> None:
        super().__init__(coordinator, "surplus")
        self._min_certainty = coordinator.config_entry.options.get(
            CONF_MIN_CERTAINTY, DEFAULT_MIN_CERTAINTY
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.go(dt_util.utcnow(), self._min_certainty)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"min_certainty": self._min_certainty}
