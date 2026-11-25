"""Config flow for WiEnergy."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import WiEnergyAuthError, WiEnergyClient, WiEnergyError
from .const import (
    CONF_COMMUNITY_ID,
    CONF_MIN_CERTAINTY,
    CONF_PARTICIPANT_ID,
    DEFAULT_MIN_CERTAINTY,
    DOMAIN,
    KNOWN_COMMUNITIES,
)
from .coordinator import WiEnergyConfigEntry

_LOGGER = logging.getLogger(__name__)

API_KEY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class WiEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiEnergy."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._communities: dict[str, str] = {}
        self._participants: dict[str, dict[str, Any]] = {}

    def _client(self, api_key: str | None = None) -> WiEnergyClient:
        return WiEnergyClient(async_get_clientsession(self.hass), api_key=api_key)

    # ---------------------------------------------------------------- user
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: optional API key (participant signal)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            if not api_key:
                return await self.async_step_community()
            try:
                participants = await self._client(api_key).async_get_participants()
            except WiEnergyAuthError:
                errors["base"] = "invalid_auth"
            except WiEnergyError:
                errors["base"] = "cannot_connect"
            else:
                if not participants:
                    errors["base"] = "no_participants"
                else:
                    self._api_key = api_key
                    self._participants = {p["id"]: p for p in participants}
                    return await self.async_step_participant()
        return self.async_show_form(
            step_id="user", data_schema=API_KEY_SCHEMA, errors=errors
        )

    # ----------------------------------------------------------- community
    async def async_step_community(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a community (public signal, no API key)."""
        if user_input is not None:
            community_id = user_input[CONF_COMMUNITY_ID]
            await self.async_set_unique_id(community_id)
            self._abort_if_unique_id_configured()
            name = self._communities.get(community_id, community_id)
            return self.async_create_entry(
                title=name, data={CONF_COMMUNITY_ID: community_id}
            )

        if not self._communities:
            try:
                items = await self._client().async_get_public_communities()
                self._communities = {c["id"]: c.get("name") or c["id"] for c in items}
            except WiEnergyError as err:
                _LOGGER.debug("Community list not available, using fallback: %s", err)
            if not self._communities:
                self._communities = dict(KNOWN_COMMUNITIES)

        options = [
            SelectOptionDict(value=cid, label=f"{name} ({cid})")
            for cid, name in sorted(self._communities.items(), key=lambda i: i[1])
        ]
        return self.async_show_form(
            step_id="community",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMMUNITY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    # --------------------------------------------------------- participant
    async def async_step_participant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a participant bound to the API key."""
        if user_input is not None or len(self._participants) == 1:
            pid = (
                user_input[CONF_PARTICIPANT_ID]
                if user_input is not None
                else next(iter(self._participants))
            )
            participant = self._participants[pid]
            await self.async_set_unique_id(pid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=participant.get("label") or pid,
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_PARTICIPANT_ID: pid,
                    CONF_COMMUNITY_ID: participant["communityId"],
                },
            )

        options = [
            SelectOptionDict(value=pid, label=f"{p.get('label') or pid} ({pid})")
            for pid, p in self._participants.items()
        ]
        return self.async_show_form(
            step_id="participant",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PARTICIPANT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    # -------------------------------------------------------------- reauth
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """API key was rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                participants = await self._client(api_key).async_get_participants()
            except WiEnergyAuthError:
                errors["base"] = "invalid_auth"
            except WiEnergyError:
                errors["base"] = "cannot_connect"
            else:
                if entry.data.get(CONF_PARTICIPANT_ID) not in {
                    p["id"] for p in participants
                }:
                    errors["base"] = "wrong_participant"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_API_KEY: api_key}
                    )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: WiEnergyConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return WiEnergyOptionsFlow()


class WiEnergyOptionsFlow(OptionsFlow):
    """Options: minimum certainty for the surplus switching signal."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_MIN_CERTAINTY, DEFAULT_MIN_CERTAINTY
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MIN_CERTAINTY, default=current): SelectSelector(
                        SelectSelectorConfig(
                            options=["possible", "likely", "certain"],
                            translation_key=CONF_MIN_CERTAINTY,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )
