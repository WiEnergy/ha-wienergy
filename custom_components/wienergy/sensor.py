"""Sensors for WiEnergy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CERTAINTY_ORDER, LEVELS
from .coordinator import WiEnergyConfigEntry, WiEnergyCoordinator
from .entity import WiEnergyEntity
from .model import WiEnergyData, parse_ts

PARALLEL_UPDATES = 0

ValueFn = Callable[[WiEnergyData, datetime, tzinfo], Any]


def _interval_value(key: str) -> ValueFn:
    def fn(data: WiEnergyData, now: datetime, _tz: tzinfo) -> Any:
        item = data.interval(now)
        return item.get(key) if item else None

    return fn


def _forecast_value(key: str, factor: float = 1) -> ValueFn:
    def fn(data: WiEnergyData, now: datetime, _tz: tzinfo) -> Any:
        item = data.forecast_value(now)
        if item is None or item.get(key) is None:
            return None
        return round(item[key] * factor, 1)

    return fn


def _window_value(key: str) -> ValueFn:
    def fn(data: WiEnergyData, now: datetime, _tz: tzinfo) -> Any:
        win = data.next_window(now)
        if win is None:
            return None
        if key in ("start", "end"):
            return parse_ts(win.get(key))
        return win.get(key)

    return fn


def _certainty(data: WiEnergyData, now: datetime, _tz: tzinfo) -> str | None:
    item = data.interval(now)
    value = item.get("certainty") if item else None
    return value if value in CERTAINTY_ORDER else None


def _windows_attrs(data: WiEnergyData, now: datetime) -> dict[str, Any]:
    win = data.next_window(now)
    return {
        "certainty": win.get("certainty") if win else None,
        "expected_surplus_kwh": win.get("expectedSurplusKwh") if win else None,
        "peak_balance_w": win.get("peakBalanceW") if win else None,
        "recommended_energy_kwh": win.get("recommendedEnergyKwh") if win else None,
        "windows": [
            {
                "start": w.get("start"),
                "end": w.get("end"),
                "certainty": w.get("certainty"),
                "expected_surplus_kwh": w.get("expectedSurplusKwh"),
            }
            for w in data.windows(now)
        ],
    }


@dataclass(frozen=True, kw_only=True)
class WiEnergySensorDescription(SensorEntityDescription):
    """Describes a WiEnergy sensor."""

    value_fn: ValueFn
    attrs_fn: Callable[[WiEnergyData, datetime], dict[str, Any]] | None = None
    participant_only: bool = False


SENSORS: tuple[WiEnergySensorDescription, ...] = (
    WiEnergySensorDescription(
        key="level",
        translation_key="level",
        device_class=SensorDeviceClass.ENUM,
        options=LEVELS,
        value_fn=lambda d, now, _tz: d.level(now),
    ),
    WiEnergySensorDescription(
        key="certainty",
        translation_key="certainty",
        device_class=SensorDeviceClass.ENUM,
        options=CERTAINTY_ORDER,
        value_fn=_certainty,
    ),
    WiEnergySensorDescription(
        key="balance",
        translation_key="balance",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=_interval_value("communityBalanceW"),
        attrs_fn=lambda d, now: {"forecast": d.upcoming(now)},
    ),
    WiEnergySensorDescription(
        key="recommended_max",
        translation_key="recommended_max",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=_interval_value("recommendedMaxW"),
        participant_only=True,
    ),
    WiEnergySensorDescription(
        key="production",
        translation_key="production",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=_forecast_value("productionW"),
    ),
    WiEnergySensorDescription(
        key="consumption",
        translation_key="consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=_forecast_value("consumptionW"),
    ),
    WiEnergySensorDescription(
        key="coverage",
        translation_key="coverage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_forecast_value("communityCoverage", 100),
    ),
    WiEnergySensorDescription(
        key="surplus_remaining_today",
        translation_key="surplus_remaining_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d, now, tz: d.surplus_remaining_today(now, tz),
    ),
    WiEnergySensorDescription(
        key="next_window_start",
        translation_key="next_window_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_window_value("start"),
        attrs_fn=_windows_attrs,
    ),
    WiEnergySensorDescription(
        key="next_window_end",
        translation_key="next_window_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_window_value("end"),
    ),
    WiEnergySensorDescription(
        key="next_window_energy",
        translation_key="next_window_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_window_value("expectedSurplusKwh"),
    ),
    WiEnergySensorDescription(
        key="generated_at",
        translation_key="generated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, _now, _tz: d.generated_at,
    ),
    WiEnergySensorDescription(
        key="expires_at",
        translation_key="expires_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d, _now, _tz: d.expires_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WiEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WiEnergy sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        WiEnergySensor(coordinator, description)
        for description in SENSORS
        if not description.participant_only or coordinator.participant_id
    )


class WiEnergySensor(WiEnergyEntity, SensorEntity):
    """A WiEnergy sensor."""

    entity_description: WiEnergySensorDescription
    # Forecast lists are large and only useful live (charts), not in history.
    _unrecorded_attributes = frozenset({"forecast", "windows"})

    def __init__(
        self, coordinator: WiEnergyCoordinator, description: WiEnergySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        tz_name = coordinator.data.community.get("timezone") or "Europe/Vienna"
        try:
            self._tz: tzinfo = ZoneInfo(tz_name)
        except (KeyError, ValueError):
            self._tz = dt_util.get_default_time_zone()

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(
            self.coordinator.data, dt_util.utcnow(), self._tz
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data, dt_util.utcnow())
