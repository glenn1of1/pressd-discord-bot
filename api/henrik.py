from __future__ import annotations

import asyncio

import aiohttp

BASE_URL = "https://api.henrikdev.xyz"

# aiohttp's default is 5 minutes. A request that hangs that long would pin a
# /leaderboard semaphore slot and outlive the Discord interaction anyway.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Transient statuses worth one more attempt before surfacing an error.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_BASE_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 5.0


def _retry_delay(resp: aiohttp.ClientResponse, attempt: int) -> float:
    """Seconds to wait before retrying, honouring Retry-After when sent."""
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), _MAX_BACKOFF_SECONDS)
        except ValueError:
            pass  # Header can be an HTTP-date; fall through to backoff.
    return min(_BASE_BACKOFF_SECONDS * 2**attempt, _MAX_BACKOFF_SECONDS)


class HenrikClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {"Authorization": api_key}
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers, timeout=REQUEST_TIMEOUT
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, **params) -> dict:
        url = f"{BASE_URL}{path}"
        session = self._get_session()

        for attempt in range(_MAX_RETRIES + 1):
            async with session.get(url, params=params) as resp:
                if resp.status == 401:
                    raise ValueError(
                        "Invalid HenrikDev API key — check HENRIK_API_KEY in .env"
                    )
                if resp.status == 404:
                    raise LookupError("Riot account not found")

                if resp.status in _RETRYABLE_STATUSES and attempt < _MAX_RETRIES:
                    delay = _retry_delay(resp, attempt)
                else:
                    if resp.status == 429:
                        raise RuntimeError("Rate limit hit — slow down mud")
                    resp.raise_for_status()
                    return await resp.json()

            # Sleep outside the response context so the connection is released
            # back to the pool while we wait.
            await asyncio.sleep(delay)

        raise RuntimeError("Rate limit hit — slow down mud")  # unreachable

    async def get_account(self, name: str, tag: str) -> dict:
        return await self._get(f"/valorant/v1/account/{name}/{tag}")

    async def get_matches(
        self, region: str, name: str, tag: str, size: int = 5
    ) -> dict:
        return await self._get(
            f"/valorant/v4/matches/{region}/pc/{name}/{tag}",
            size=size,
        )

    async def get_mmr(self, region: str, name: str, tag: str) -> dict:
        return await self._get(f"/valorant/v3/mmr/{region}/pc/{name}/{tag}")

    async def get_mmr_history(self, region: str, name: str, tag: str) -> dict:
        return await self._get(f"/valorant/v2/mmr-history/{region}/pc/{name}/{tag}")
