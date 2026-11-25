"""Data update coordinator for WiEnergy."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    WiEnergyAuthError,
    WiEnergyClient,
    WiEnergyError,
    WiEnergyRateLimitError,
)
from .const import (
    CONF_COMMUNITY_ID,
    CONF_PARTICIPANT_ID,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .model import WiEnergyData

_LOGGER = logging.getLogger(__name__)

type WiEnergyConfigEntry = ConfigEntry[WiEnergyCoordinator]


class WiEnergyCoordinator(DataUpdateCoordinator[WiEnergyData]):
    """Fetch signal and forecast every 5 minutes.

    Between fetches, entities are re-evaluated every minute so that the
    state switches exactly at the quarter-hour, even though the API files
    are only regenerated about every 30 minutes.
    """

    config_entry: WiEnergyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WiEnergyConfigEntry,
        client: WiEnergyClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.community_id: str = entry.data[CONF_COMMUNITY_ID]
        self.participant_id: str | None = entry.data.get(CONF_PARTICIPANT_ID)
        self._unsub_tick = None

    async def _async_update_data(self) -> WiEnergyData:
        try:
            if self.participant_id:
                signal = await self.client.async_get_participant_signal(
                    self.participant_id
                )
            else:
                signal = await self.client.async_get_public_signal(self.community_id)
        except WiEnergyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except WiEnergyRateLimitError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
            ) from err
        except WiEnergyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        data = WiEnergyData(signal=signal)

        # The forecast is optional: production/consumption sensors become
        # unavailable if it fails, the switching signal keeps working.
        previous = self.data.forecast if self.data else None
        try:
            if self.participant_id:
                data.forecast = await self.client.async_get_forecast(
                    self.community_id
                )
            else:
                data.forecast = await self.client.async_get_public_forecast(
                    self.community_id
                )
        except WiEnergyError as err:
            _LOGGER.debug("Forecast not available: %s", err)
            data.forecast = previous
            data.errors.append(f"forecast: {err}")
        return data

    @callback
    def async_start_tick(self) -> None:
        """Re-evaluate entity states every minute without fetching."""

        @callback
        def _tick(_now) -> None:
            if self.data is not None:
                self.async_update_listeners()

        self._unsub_tick = async_track_time_interval(
            self.hass, _tick, timedelta(minutes=1)
        )
        self.config_entry.async_on_unload(self._unsub_tick)
