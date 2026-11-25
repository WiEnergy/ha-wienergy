"""Tests for the pure model helpers."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from custom_components.wienergy.model import WiEnergyData

from .conftest import NOW, make_forecast, make_signal

TZ = ZoneInfo("Europe/Vienna")


def test_interval_selected_by_time_not_current() -> None:
    data = WiEnergyData(signal=make_signal())
    assert data.level(NOW) == "surplus"
    # 15 minutes later: 'current' in the file is still the old one,
    # but the deficit interval must be chosen.
    assert data.level(NOW + timedelta(minutes=15)) == "deficit"


def test_go_respects_certainty() -> None:
    data = WiEnergyData(signal=make_signal())
    assert data.go(NOW, "likely")
    assert not data.go(NOW, "certain")
    later = NOW + timedelta(minutes=30)  # surplus / possible
    assert not data.go(later, "likely")
    assert data.go(later, "possible")
    assert not data.go(NOW + timedelta(minutes=15), "possible")  # deficit


def test_expired() -> None:
    data = WiEnergyData(signal=make_signal())
    late = NOW + timedelta(hours=3)
    assert data.level(late) == "expired"
    assert not data.go(late, "possible")
    assert data.upcoming(late) == []


def test_unavailable_confidence_never_go() -> None:
    sig = make_signal()
    sig["intervals"][0]["confidence"] = "unavailable"
    assert not WiEnergyData(signal=sig).go(NOW, "possible")


def test_windows_skip_past() -> None:
    data = WiEnergyData(signal=make_signal())
    assert data.next_window(NOW)["id"] == "win_1"


def test_surplus_remaining_today() -> None:
    data = WiEnergyData(signal=make_signal(), forecast=make_forecast())
    # from 09:00 UTC quarter (ends 09:15 > now) to 14:00 UTC: 20 quarters x 2 kWh
    assert data.surplus_remaining_today(NOW, TZ) == 40.0
    assert data.forecast_value(NOW)["productionW"] == 24000
