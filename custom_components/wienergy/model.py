"""Pure helpers that turn API payloads into the current state.

The API files are regenerated about every 30 minutes, so ``current`` in a
response may be outdated. All helpers therefore pick the interval that
contains *now* (Spielregel 7) and respect ``expiresAt`` (Spielregel 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, tzinfo
from typing import Any

from .const import CERTAINTY_ORDER


def parse_ts(value: str | None) -> datetime | None:
    """Parse an RFC 3339 timestamp."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _in_interval(item: dict[str, Any], now: datetime) -> bool:
    start = parse_ts(item.get("start"))
    end = parse_ts(item.get("end"))
    return start is not None and end is not None and start <= now < end


def certainty_at_least(value: str | None, minimum: str) -> bool:
    """Return True if ``value`` is at least as certain as ``minimum``."""
    if value not in CERTAINTY_ORDER:
        return False
    return CERTAINTY_ORDER.index(value) >= CERTAINTY_ORDER.index(minimum)


@dataclass
class WiEnergyData:
    """Raw payloads as returned by the API."""

    signal: dict[str, Any]
    forecast: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ signal
    @property
    def community(self) -> dict[str, Any]:
        return self.signal.get("community") or {}

    @property
    def participant(self) -> dict[str, Any] | None:
        return self.signal.get("participant")

    @property
    def generated_at(self) -> datetime | None:
        return parse_ts(self.signal.get("generatedAt"))

    @property
    def expires_at(self) -> datetime | None:
        return parse_ts(self.signal.get("expiresAt"))

    def is_expired(self, now: datetime) -> bool:
        expires = self.expires_at
        return expires is None or now >= expires

    def interval(self, now: datetime) -> dict[str, Any] | None:
        """Return the signal interval that contains ``now`` (None if expired)."""
        if self.is_expired(now):
            return None
        for item in self.signal.get("intervals") or []:
            if _in_interval(item, now):
                return item
        current = self.signal.get("current")
        if current and _in_interval(current, now):
            return current
        return None

    def level(self, now: datetime) -> str:
        if self.is_expired(now):
            return "expired"
        item = self.interval(now)
        if item is None:
            return "unavailable"
        level = item.get("level")
        return level if level in ("surplus", "balanced", "deficit") else "unavailable"

    def go(self, now: datetime, min_certainty: str) -> bool:
        """Switching signal: surplus, sufficiently certain, usable confidence."""
        item = self.interval(now)
        if item is None:
            return False
        return (
            item.get("level") == "surplus"
            and item.get("confidence") not in (None, "unavailable")
            and certainty_at_least(item.get("certainty"), min_certainty)
        )

    def upcoming(self, now: datetime) -> list[dict[str, Any]]:
        """Intervals from the current quarter-hour on (for charts)."""
        if self.is_expired(now):
            return []
        result = []
        for item in self.signal.get("intervals") or []:
            end = parse_ts(item.get("end"))
            if end is not None and end > now:
                result.append(
                    {
                        "start": item.get("start"),
                        "level": item.get("level"),
                        "certainty": item.get("certainty"),
                        "balance_w": item.get("communityBalanceW"),
                        "recommended_max_w": item.get("recommendedMaxW"),
                    }
                )
        return result

    # ----------------------------------------------------------- windows
    def windows(self, now: datetime) -> list[dict[str, Any]]:
        """Surplus windows that have not ended yet, chronologically."""
        items = []
        for win in self.signal.get("windows") or []:
            end = parse_ts(win.get("end"))
            if end is not None and end > now:
                items.append(win)
        return sorted(items, key=lambda w: w.get("start") or "")

    def next_window(self, now: datetime) -> dict[str, Any] | None:
        """The running window, or else the next one."""
        wins = self.windows(now)
        return wins[0] if wins else None

    # ---------------------------------------------------------- forecast
    def forecast_value(self, now: datetime) -> dict[str, Any] | None:
        if not self.forecast:
            return None
        for item in self.forecast.get("values") or []:
            if _in_interval(item, now):
                if item.get("confidence") == "unavailable" or item.get(
                    "quality"
                ) == "unavailable":
                    return None
                return item
        return None

    def surplus_remaining_today(self, now: datetime, tz: tzinfo) -> float | None:
        """Sum of positive balance (kWh) from now until midnight local time."""
        if not self.forecast:
            return None
        today = now.astimezone(tz).date()
        total = 0.0
        found = False
        for item in self.forecast.get("values") or []:
            start = parse_ts(item.get("start"))
            end = parse_ts(item.get("end"))
            if start is None or end is None or end <= now:
                continue
            if start.astimezone(tz).date() != today:
                continue
            if item.get("confidence") == "unavailable":
                continue
            found = True
            balance = item.get("balanceKwh") or 0
            if balance > 0:
                total += balance
        return round(total, 2) if found else None
