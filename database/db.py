from __future__ import annotations

import json
import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(
    os.getenv("DB_PATH", str(Path(__file__).parent.parent / "valorant_bot.db"))
)

if not os.getenv("DB_PATH"):
    print(
        "WARNING: DB_PATH env var is not set. Using local fallback path. "
        "Registrations will be lost on redeploy if running on Railway.",
        flush=True,
    )


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                discord_id    TEXT PRIMARY KEY,
                riot_name     TEXT NOT NULL,
                riot_tag      TEXT NOT NULL,
                region        TEXT NOT NULL DEFAULT 'na',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS stats_cache (
                discord_id   TEXT PRIMARY KEY,
                cached_json  TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def register_user(
    discord_id: str,
    riot_name: str,
    riot_tag: str,
    region: str = "na",
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (discord_id, riot_name, riot_tag, region)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                riot_name     = excluded.riot_name,
                riot_tag      = excluded.riot_tag,
                region        = excluded.region,
                registered_at = CURRENT_TIMESTAMP
            """,
            (discord_id, riot_name, riot_tag, region),
        )
        # The cache row is keyed by discord_id only, so a re-register under a
        # different Riot ID would keep serving the previous account's stats
        # until the TTL expired.
        await db.execute("DELETE FROM stats_cache WHERE discord_id = ?", (discord_id,))
        await db.commit()


async def get_user(discord_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_user(discord_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM stats_cache WHERE discord_id = ?", (discord_id,))
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_cached_stats(
    discord_id: str,
    max_age_seconds: int = 300,
) -> dict | None:
    """Return cached leaderboard data for a user if it is within max_age_seconds, else None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT cached_json
            FROM stats_cache
            WHERE discord_id = ?
              AND (julianday('now') - julianday(last_updated)) * 86400 < ?
            """,
            (discord_id, max_age_seconds),
        ) as cursor:
            row = await cursor.fetchone()
            return json.loads(row["cached_json"]) if row else None


async def set_cached_stats(discord_id: str, data: dict) -> None:
    """Write or refresh leaderboard cache for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO stats_cache (discord_id, cached_json, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id) DO UPDATE SET
                cached_json  = excluded.cached_json,
                last_updated = CURRENT_TIMESTAMP
            """,
            (discord_id, json.dumps(data)),
        )
        await db.commit()
