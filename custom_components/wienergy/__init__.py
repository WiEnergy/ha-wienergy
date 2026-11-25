"""The WiEnergy integration: community surplus signal for Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WiEnergyClient
from .coordinator import WiEnergyConfigEntry, WiEnergyCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WiEnergyConfigEntry) -> bool:
    """Set up WiEnergy from a config entry."""
    client = WiEnergyClient(
        async_get_clientsession(hass), api_key=entry.data.get(CONF_API_KEY)
    )
    coordinator = WiEnergyCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_start_tick()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: WiEnergyConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WiEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
