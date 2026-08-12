"""The shared stats cache behind /stats, /compare, and /leaderboard."""

from __future__ import annotations

import pytest
from conftest import make_match

from database.db import (
    delete_user,
    get_cached_stats,
    get_user,
    register_user,
    set_cached_stats,
)
from utils.cache import _belongs_to, _jittered, _TTL_JITTER_RATIO, get_player_blob

UID = "111222333"


class CountingHenrik:
    """Stub client that records how many API calls the cache actually avoided."""

    def __init__(self):
        self.matches_calls = 0
        self.mmr_calls = 0

    async def get_matches(self, region, name, tag, size=5):
        self.matches_calls += 1
        return {"data": [make_match(name, tag), make_match(name, tag, won=False)]}

    async def get_mmr(self, region, name, tag):
        self.mmr_calls += 1
        return {"data": {"current": {"tier": {"name": "Diamond 2"}, "rr": 42}}}


@pytest.fixture
async def registered(temp_db):
    await register_user(UID, "TenZ", "NA1", "na")
    return await get_user(UID)


async def test_cold_fetch_populates_the_blob(registered):
    henrik = CountingHenrik()
    blob = await get_player_blob(henrik, registered)

    assert (henrik.matches_calls, henrik.mmr_calls) == (1, 1)
    assert blob["stats"]["games"] == 2
    assert blob["tier_name"] == "Diamond 2"
    assert blob["rr"] == 42
    assert blob["riot_name"] == "TenZ"


async def test_warm_cache_makes_no_api_calls(registered):
    henrik = CountingHenrik()
    first = await get_player_blob(henrik, registered)
    second = await get_player_blob(henrik, registered)

    assert (henrik.matches_calls, henrik.mmr_calls) == (1, 1)
    assert second["stats"] == first["stats"]


async def test_expired_ttl_refetches(registered):
    henrik = CountingHenrik()
    await get_player_blob(henrik, registered)
    await get_player_blob(henrik, registered, max_age_seconds=0)
    assert henrik.matches_calls == 2


async def test_reregistering_a_different_riot_id_invalidates(registered):
    henrik = CountingHenrik()
    await get_player_blob(henrik, registered)

    await register_user(UID, "Aspas", "LEV", "na")
    updated = await get_user(UID)

    # register_user clears the row in the same transaction as the write.
    assert await get_cached_stats(UID, 300) is None

    blob = await get_player_blob(henrik, updated)
    assert blob["riot_name"] == "Aspas"
    assert henrik.matches_calls == 2


async def test_identity_guard_rejects_a_stale_row(registered):
    """Belt-and-braces: even a row that escaped deletion must not be served."""
    henrik = CountingHenrik()
    await set_cached_stats(
        UID,
        {
            "riot_name": "Ghost",
            "riot_tag": "OLD",
            "region": "na",
            "stats": {"games": 99},
            "tier_name": "Iron 1",
            "rr": 0,
        },
    )
    blob = await get_player_blob(henrik, registered)
    assert blob["riot_name"] == "TenZ"
    assert henrik.matches_calls == 1


async def test_unregistering_clears_the_cache_row(registered):
    await get_player_blob(CountingHenrik(), registered)
    await delete_user(UID)
    assert await get_cached_stats(UID, 300) is None


def test_belongs_to_compares_case_insensitively():
    record = {"riot_name": "TenZ", "riot_tag": "NA1", "region": "na"}
    assert _belongs_to({"riot_name": "tenz", "riot_tag": "na1", "region": "na"}, record)
    assert not _belongs_to(
        {"riot_name": "TenZ", "riot_tag": "NA1", "region": "eu"}, record
    )
    assert not _belongs_to({}, record)


def test_jitter_shortens_within_bounds():
    ttl = 300
    values = [_jittered(ttl) for _ in range(200)]
    assert all(ttl * (1 - _TTL_JITTER_RATIO) <= v <= ttl for v in values)
    # Rows written together must not all expire together.
    assert len(set(values)) > 1


def test_jitter_of_zero_stays_zero():
    assert _jittered(0) == 0
