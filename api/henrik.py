from __future__ import annotations

import aiohttp

BASE_URL = "https://api.henrikdev.xyz"


class HenrikClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {"Authorization": api_key}
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, **params) -> dict:
        url = f"{BASE_URL}{path}"
        session = self._get_session()
        async with session.get(url, params=params) as resp:
            if resp.status == 401:
                raise ValueError(
                    "Invalid HenrikDev API key — check HENRIK_API_KEY in .env"
                )
            if resp.status == 404:
                raise LookupError("Riot account not found")
            if resp.status == 429:
                raise RuntimeError("Rate limit hit — slow down mud")
            resp.raise_for_status()
            return await resp.json()

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
