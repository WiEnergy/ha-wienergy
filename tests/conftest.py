"""Fixtures for WiEnergy tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

BASE = "https://api.eeg-wienergy.at"
CID = "RC106901"
# Fixed reference time: 2026-06-15 11:07 Vienna (09:07 UTC)
NOW = datetime(2026, 6, 15, 9, 7, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


def _q(dt: datetime) -> datetime:
    return dt.replace(minute=dt.minute - dt.minute % 15, second=0, microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def make_signal(now: datetime = NOW, participant: bool = False) -> dict[str, Any]:
    """Signal: current quarter surplus/likely, next quarter deficit, then surplus/possible."""
    start = _q(now)
    pattern = [
        ("surplus", "likely", 12000, 3500),
        ("deficit", "none", -4000, 0),
        ("surplus", "possible", 2500, 800),
        ("surplus", "certain", 20000, 4200),
    ]
    intervals = []
    for i in range(8):
        level, cert, bal, rec = pattern[i % 4]
        s = start + timedelta(minutes=15 * i)
        intervals.append(
            {
                "start": iso(s),
                "end": iso(s + timedelta(minutes=15)),
                "level": level,
                "certainty": cert,
                "communityBalanceW": bal,
                "confidence": "high",
                "recommendedMaxW": rec if participant else None,
                "windowId": None,
            }
        )
    data = {
        "apiVersion": "1.1",
        "community": {"id": CID, "name": "Bruckhaufen", "timezone": "Europe/Vienna"},
        "generatedAt": iso(start - timedelta(minutes=20)),
        "expiresAt": iso(start + timedelta(hours=2)),
        "resolution": "PT15M",
        "current": intervals[0],
        "intervals": intervals,
        "windows": [
            {
                "id": "win_past",
                "start": iso(start - timedelta(hours=3)),
                "end": iso(start - timedelta(hours=2)),
                "certainty": "certain",
                "expectedSurplusKwh": 10,
                "peakBalanceW": 9000,
                "recommendedEnergyKwh": None,
            },
            {
                "id": "win_1",
                "start": iso(start + timedelta(minutes=45)),
                "end": iso(start + timedelta(hours=3)),
                "certainty": "likely",
                "expectedSurplusKwh": 42.5,
                "peakBalanceW": 24800,
                "recommendedEnergyKwh": 8.1 if participant else None,
            },
        ],
    }
    if participant:
        data["participant"] = {
            "id": "P-7F3A2C",
            "communityId": CID,
            "registeredFlexW": 11000,
            "signalEnabled": True,
        }
    return data


def make_forecast(now: datetime = NOW) -> dict[str, Any]:
    """Forecast from the current quarter until 2 days later; 2 kWh surplus per quarter until 16:00 Vienna."""
    start = _q(now)
    values = []
    for i in range(4 * 24):
        s = start + timedelta(minutes=15 * i)
        surplus = s < datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)
        values.append(
            {
                "start": iso(s),
                "end": iso(s + timedelta(minutes=15)),
                "productionKwh": 6.0 if surplus else 0.0,
                "consumptionKwh": 4.0,
                "balanceKwh": 2.0 if surplus else -4.0,
                "productionW": 24000 if surplus else 0,
                "consumptionW": 16000,
                "balanceW": 8000 if surplus else -16000,
                "communityCoverage": 1.0 if surplus else 0.0,
                "confidence": "high",
                "quality": "forecast",
            }
        )
    return {
        "apiVersion": "1.1",
        "community": {"id": CID, "name": "Bruckhaufen", "timezone": "Europe/Vienna"},
        "generatedAt": iso(start),
        "validUntil": iso(start + timedelta(hours=2)),
        "resolution": "PT15M",
        "unitConvention": {
            "power": "W",
            "energy": "kWh_per_interval",
            "balanceSign": "positive_surplus_negative_deficit",
        },
        "values": values,
    }


COMMUNITIES = {
    "apiVersion": "1.1",
    "communities": [
        {"id": CID, "name": "Bruckhaufen", "timezone": "Europe/Vienna"},
        {"id": "RC107211", "name": "Heiligenstadt", "timezone": "Europe/Vienna"},
    ],
}
