from __future__ import annotations

import asyncio
import logging
import os
import time

import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://api.henrikdev.xyz"

# Requests per minute allowed out of this process. The HenrikDev Basic key
# permits 30/min, so the default sits under it to leave room for the retries
# below. Raise via HENRIK_RATE_LIMIT if the key is upgraded — no redeploy needed.
DEFAULT_RATE_LIMIT = 25

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


def _env_int(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back on junk values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        log.warning("%s=%r is not an integer — using %d", name, raw, default)
        return default
    if value < 1:
        log.warning("%s=%d must be at least 1 — using %d", name, value, default)
        return default
    return value


class _RateLimiter:
    """Token bucket capping outbound requests to a per-minute budget.

    Requests beyond the budget wait for a token rather than failing, which is
    what makes a 30/min API key survivable across a dozen guilds: a burst of
    /leaderboard traffic renders slowly instead of erroring out.

    The lock is deliberately held across the sleep so waiters are served in
    arrival order and the refill maths can't race.
    """

    def __init__(self, per_minute: int) -> None:
        self.capacity = float(per_minute)
        self._tokens = self.capacity
        self._refill_per_second = self.capacity / 60.0
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Consume one token, waiting if necessary. Returns seconds waited."""
        async with self._lock:
            waited = 0.0
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity,
                    self._tokens + (now - self._updated) * self._refill_per_second,
                )
                self._updated = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return waited

                delay = (1.0 - self._tokens) / self._refill_per_second
                waited += delay
                await asyncio.sleep(delay)


class HenrikClient:
    def __init__(self, api_key: str, rate_limit: int | None = None) -> None:
        self._api_key = api_key
        self._headers = {"Authorization": api_key}
        self._session: aiohttp.ClientSession | None = None
        if rate_limit is None:
            rate_limit = _env_int("HENRIK_RATE_LIMIT", DEFAULT_RATE_LIMIT)
        self._limiter = _RateLimiter(rate_limit)

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
            # Every attempt spends a token, retries included — a retry is still
            # a real request against the quota.
            waited = await self._limiter.acquire()
            if waited > 0.1:
                # The signal for whether the paid key tier is worth buying.
                log.info(
                    "Rate limiter delayed a request by %.1fs (budget %.0f/min)",
                    waited,
                    self._limiter.capacity,
                )

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
