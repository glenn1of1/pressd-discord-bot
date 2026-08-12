from __future__ import annotations

import asyncio
import logging
import os
import random

from api.henrik import HenrikClient
from database.db import get_cached_stats, set_cached_stats
from utils.stats import compute_stats

log = logging.getLogger(__name__)

# Every consumer of the shared blob aggregates over the same window, so the
# cache row is interchangeable between /stats, /compare, and /leaderboard.
# Changing this invalidates nothing automatically — bump the TTL or clear the
# table if you change it.
MATCH_SAMPLE_SIZE = 20

_FALLBACK_TTL_SECONDS = 300

# Fraction of the TTL used to spread expiries out. /leaderboard writes every
# player's row in the same instant, so without jitter they all expire in the
# same instant too and the next leaderboard is fully cold — the most expensive
# case, every time. This staggers them so rows refresh a few at a time.
_TTL_JITTER_RATIO = 0.2


def _read_ttl() -> int:
    """Effective cache TTL in seconds, from STATS_CACHE_TTL."""
    raw = os.getenv("STATS_CACHE_TTL")
    if raw is None:
        return _FALLBACK_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        log.warning(
            "STATS_CACHE_TTL=%r is not an integer — using %d",
            raw,
            _FALLBACK_TTL_SECONDS,
        )
        return _FALLBACK_TTL_SECONDS
    if value < 1:
        log.warning(
            "STATS_CACHE_TTL=%d must be at least 1 — using %d",
            value,
            _FALLBACK_TTL_SECONDS,
        )
        return _FALLBACK_TTL_SECONDS
    return value


# Read once at import so every caller agrees on the window. Changing it means a
# restart, which on Railway is what setting the variable does anyway.
DEFAULT_TTL_SECONDS = _read_ttl()


def _jittered(ttl: int) -> float:
    """Shorten a TTL by a random slice so batch-written rows expire staggered."""
    return ttl * (1.0 - random.uniform(0.0, _TTL_JITTER_RATIO))


def _belongs_to(blob: dict, record: dict) -> bool:
    """True if a cached blob describes the Riot account currently registered.

    A cache row is keyed by discord_id alone, so a user who re-registers under
    a different Riot ID would otherwise be served the previous account's stats
    until the TTL expired.
    """
    return (
        blob.get("riot_name", "").lower() == record["riot_name"].lower()
        and blob.get("riot_tag", "").lower() == record["riot_tag"].lower()
        and blob.get("region", "") == record["region"]
    )


async def get_player_blob(
    henrik: HenrikClient,
    record: dict,
    max_age_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """Return computed stats + current rank for a registered user, via cache.

    Serves a cached blob when one exists, is within max_age_seconds, and still
    matches the user's registered Riot ID. Otherwise fetches from the HenrikDev
    API, writes the result to stats_cache, and returns it.

    API errors (LookupError, RuntimeError, and transport failures) propagate to
    the caller so each command can render its own message — /leaderboard wants
    to degrade a single row to "N/A", while /stats and /compare want to abort
    with an explanation.
    """
    name = record["riot_name"]
    tag = record["riot_tag"]
    region = record["region"]

    # Jitter is applied per read, so the N rows /leaderboard checks in one pass
    # each get a slightly different freshness window and refresh in waves.
    cached = await get_cached_stats(record["discord_id"], _jittered(max_age_seconds))
    if cached is not None and _belongs_to(cached, record):
        return cached

    matches_raw, mmr_raw = await asyncio.gather(
        henrik.get_matches(region, name, tag, size=MATCH_SAMPLE_SIZE),
        henrik.get_mmr(region, name, tag),
    )

    current = mmr_raw.get("data", {}).get("current", {})
    blob = {
        "riot_name": name,
        "riot_tag": tag,
        "region": region,
        "stats": compute_stats(matches_raw, name, tag),
        "tier_name": current.get("tier", {}).get("name", "Unranked"),
        "rr": current.get("rr", 0),
    }

    await set_cached_stats(record["discord_id"], blob)
    return blob
