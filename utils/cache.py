from __future__ import annotations

import asyncio

from api.henrik import HenrikClient
from database.db import get_cached_stats, set_cached_stats
from utils.stats import compute_stats

# Every consumer of the shared blob aggregates over the same window, so the
# cache row is interchangeable between /stats, /compare, and /leaderboard.
# Changing this invalidates nothing automatically — bump the TTL or clear the
# table if you change it.
MATCH_SAMPLE_SIZE = 20

DEFAULT_TTL_SECONDS = 300


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

    cached = await get_cached_stats(record["discord_id"], max_age_seconds)
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
