"""Diagnostics and time zone tests."""

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from custom_components.wienergy.const import (
    CONF_COMMUNITY_ID,
    CONF_PARTICIPANT_ID,
    DOMAIN,
)
from custom_components.wienergy.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import BASE, CID, NOW, make_forecast, make_signal

PID = "P-7F3A2C"


async def test_diagnostics_redacted(
    hass: HomeAssistant, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    aioclient_mock.get(
        f"{BASE}/api/v1/participants/{PID}/signal", json=make_signal(participant=True)
    )
    aioclient_mock.get(
        f"{BASE}/api/v1/communities/{CID}/forecast", json=make_forecast()
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=PID,
        data={CONF_API_KEY: "secret", CONF_COMMUNITY_ID: CID, CONF_PARTICIPANT_ID: PID},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"][CONF_API_KEY] == REDACTED
    assert diag["entry"][CONF_PARTICIPANT_ID] == REDACTED
    assert diag["entry"][CONF_COMMUNITY_ID] == CID
    assert diag["signal"]["participant"] == REDACTED
    assert PID not in str(diag)
    assert "secret" not in str(diag)


async def test_unknown_timezone_falls_back(
    hass: HomeAssistant, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    signal = make_signal()
    signal["community"]["timezone"] = "Mars/Olympus"
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", json=signal)
    aioclient_mock.get(
        f"{BASE}/api/v1/public/communities/{CID}/forecast", json=make_forecast()
    )
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CID, data={CONF_COMMUNITY_ID: CID})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.bruckhaufen_surplus_remaining_today") or next(
        s for s in hass.states.async_all("sensor") if "remaining" in s.entity_id
    )
    assert state.state == "40.0"
