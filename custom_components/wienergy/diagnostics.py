"""Diagnostics for WiEnergy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_PARTICIPANT_ID
from .coordinator import WiEnergyConfigEntry

TO_REDACT_ENTRY = {CONF_API_KEY, CONF_PARTICIPANT_ID}
TO_REDACT_SIGNAL = {"participant", "participantId", "participant_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WiEnergyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT_ENTRY),
        "options": dict(entry.options),
        "signal": async_redact_data(data.signal or {}, TO_REDACT_SIGNAL),
        "forecast_values": len((data.forecast or {}).get("values") or []),
        "errors": data.errors,
    }
