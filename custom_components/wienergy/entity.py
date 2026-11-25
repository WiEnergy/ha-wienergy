"""Base entity for WiEnergy."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, WEB_APP_URL
from .coordinator import WiEnergyCoordinator


class WiEnergyEntity(CoordinatorEntity[WiEnergyCoordinator]):
    """Common device info and unique ids."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WiEnergyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        name = coordinator.data.community.get("name") or coordinator.community_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title or name,
            manufacturer=MANUFACTURER,
            model="Überschussprognose"
            if not coordinator.participant_id
            else "Teilnehmer-Signal",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=WEB_APP_URL.format(community_id=coordinator.community_id),
        )
