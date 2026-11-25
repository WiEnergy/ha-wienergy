"""Diagnostics for WiEnergy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import WiEnergyConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WiEnergyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_API_KEY}),
        "options": dict(entry.options),
        "signal": data.signal,
        "forecast_values": len((data.forecast or {}).get("values") or []),
        "errors": data.errors,
    }
