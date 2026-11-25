"""Config flow tests."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wienergy.const import (
    CONF_COMMUNITY_ID,
    CONF_MIN_CERTAINTY,
    CONF_PARTICIPANT_ID,
    DOMAIN,
)

from .conftest import BASE, CID, COMMUNITIES, make_forecast, make_signal


async def test_public_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/api/v1/public/communities", json=COMMUNITIES)
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", json=make_signal())
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/forecast", json=make_forecast())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "community"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COMMUNITY_ID: CID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bruckhaufen"
    assert result["data"] == {CONF_COMMUNITY_ID: CID}
    await hass.async_block_till_done()

    # second time: already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COMMUNITY_ID: CID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_public_flow_fallback_list(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/api/v1/public/communities", status=500)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "community"
    options = result["data_schema"].schema[CONF_COMMUNITY_ID].config["options"]
    assert any(o["value"] == "RC107211" for o in options)


async def test_api_key_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        f"{BASE}/api/v1/participants",
        json={
            "apiVersion": "1.1",
            "participants": [
                {"id": "P-7F3A2C", "communityId": CID, "label": "Haus Müller",
                 "registeredFlexW": 11000, "signalEnabled": True}
            ],
        },
    )
    aioclient_mock.get(
        f"{BASE}/api/v1/participants/P-7F3A2C/signal",
        json=make_signal(participant=True),
    )
    aioclient_mock.get(f"{BASE}/api/v1/communities/{CID}/forecast", json=make_forecast())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Haus Müller"
    assert result["data"][CONF_PARTICIPANT_ID] == "P-7F3A2C"
    assert result["data"][CONF_COMMUNITY_ID] == CID
    await hass.async_block_till_done()
    # API key is sent as header
    assert any(
        call[3] and call[3].get("X-API-Key") == "secret"
        for call in aioclient_mock.mock_calls
    )


async def test_api_key_invalid(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/api/v1/participants", status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass: HomeAssistant, aioclient_mock) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", json=make_signal())
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/forecast", json=make_forecast())
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CID, title="Bruckhaufen",
                            data={CONF_COMMUNITY_ID: CID})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MIN_CERTAINTY: "certain"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_MIN_CERTAINTY] == "certain"
