"""Minimal async client for the WiEnergy EMS Signal API (v1.x)."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import DEFAULT_BASE_URL, SIGNAL_HOURS

TIMEOUT = aiohttp.ClientTimeout(total=20)


class WiEnergyError(Exception):
    """Base error."""


class WiEnergyConnectionError(WiEnergyError):
    """Network problem or unexpected answer."""


class WiEnergyAuthError(WiEnergyError):
    """API key missing or invalid."""


class WiEnergyNotFoundError(WiEnergyError):
    """Community or participant not found."""


class WiEnergyRateLimitError(WiEnergyError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int | None) -> None:
        super().__init__(f"Rate limit exceeded, retry after {retry_after}s")
        self.retry_after = retry_after


class WiEnergyClient:
    """Read-only client.

    Without an API key only the public endpoints are used (community
    level). With an API key (Ausbaustufe 2) the participant endpoints
    deliver the individual ``recommendedMaxW``.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._session = session
        self._api_key = api_key or None
        self._base = base_url.rstrip("/")
        self._etags: dict[str, tuple[str, Any]] = {}

    @property
    def authenticated(self) -> bool:
        """Return True if an API key is configured."""
        return self._api_key is not None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{path}"
        cache_key = f"{url}?{sorted((params or {}).items())}"
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if cached := self._etags.get(cache_key):
            headers["If-None-Match"] = cached[0]
        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status == 304 and cached:
                    return cached[1]
                if resp.status == 401:
                    raise WiEnergyAuthError("API key rejected")
                if resp.status == 404:
                    raise WiEnergyNotFoundError(path)
                if resp.status == 429:
                    retry = resp.headers.get("Retry-After")
                    raise WiEnergyRateLimitError(
                        int(retry) if retry and retry.isdigit() else None
                    )
                if resp.status != 200:
                    raise WiEnergyConnectionError(f"HTTP {resp.status} for {path}")
                data = await resp.json(content_type=None)
                if etag := resp.headers.get("ETag"):
                    self._etags[cache_key] = (etag, data)
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise WiEnergyConnectionError(str(err)) from err

    # ------------------------------------------------------------ public
    async def async_get_public_communities(self) -> list[dict[str, Any]]:
        """Return the public list of communities."""
        data = await self._get("/api/v1/public/communities")
        return list(data.get("communities", []))

    async def async_get_public_signal(self, community_id: str) -> dict[str, Any]:
        """Return the public community signal (recommendedMaxW is null)."""
        return await self._get(f"/api/v1/public/communities/{community_id}/signal")

    async def async_get_public_forecast(self, community_id: str) -> dict[str, Any]:
        """Return the public 15-minute forecast (today + 2 days)."""
        return await self._get(f"/api/v1/public/communities/{community_id}/forecast")

    # ------------------------------------------------------ with API key
    async def async_get_participants(self) -> list[dict[str, Any]]:
        """Return the participants bound to the API key."""
        data = await self._get("/api/v1/participants")
        return list(data.get("participants", []))

    async def async_get_participant_signal(self, participant_id: str) -> dict[str, Any]:
        """Return the participant signal including recommendedMaxW."""
        return await self._get(
            f"/api/v1/participants/{participant_id}/signal",
            {"hours": SIGNAL_HOURS},
        )

    async def async_get_forecast(self, community_id: str) -> dict[str, Any]:
        """Return the authenticated forecast."""
        return await self._get(f"/api/v1/communities/{community_id}/forecast")
