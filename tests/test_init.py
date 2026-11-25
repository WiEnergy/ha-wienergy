"""Setup and entity tests."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.wienergy.const import CONF_COMMUNITY_ID, DOMAIN

from .conftest import BASE, CID, NOW, make_forecast, make_signal


def _ent(hass, key: str, platform: str = "sensor") -> str:
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(platform, DOMAIN, f"{CID}_{key}")
    assert entity_id, key
    return entity_id


async def test_setup_and_states(
    hass: HomeAssistant, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", json=make_signal())
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/forecast", json=make_forecast())
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CID, title="Bruckhaufen",
                            data={CONF_COMMUNITY_ID: CID})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get(_ent(hass, "level")).state == "surplus"
    assert hass.states.get(_ent(hass, "certainty")).state == "likely"
    assert hass.states.get(_ent(hass, "balance")).state == "12000"
    assert hass.states.get(_ent(hass, "production")).state == "24000"
    assert hass.states.get(_ent(hass, "coverage")).state == "100.0"
    assert hass.states.get(_ent(hass, "surplus_remaining_today")).state == "40.0"
    assert hass.states.get(_ent(hass, "next_window_energy")).state == "42.5"
    assert hass.states.get(_ent(hass, "surplus", "binary_sensor")).state == "on"
    # participant-only sensor not created in public mode
    assert er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{CID}_recommended_max"
    ) is None

    # 15 minutes later without new data: deficit quarter is chosen by time
    calls = aioclient_mock.call_count
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(_ent(hass, "level")).state == "deficit"
    assert hass.states.get(_ent(hass, "surplus", "binary_sensor")).state == "off"
    assert aioclient_mock.call_count >= calls  # polling may happen, state stays time-based

    # after expiresAt and API down: outdated, switching signal off
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", status=503)
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/forecast", status=503)
    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(_ent(hass, "surplus", "binary_sensor")).state in ("off", "unavailable")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_api_down(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", status=503)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CID, data={CONF_COMMUNITY_ID: CID})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_forecast_failure_keeps_signal(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    freezer.move_to(NOW)
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/signal", json=make_signal())
    aioclient_mock.get(f"{BASE}/api/v1/public/communities/{CID}/forecast", status=404)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=CID, data={CONF_COMMUNITY_ID: CID})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(_ent(hass, "level")).state == "surplus"
    assert hass.states.get(_ent(hass, "production")).state == "unknown"
