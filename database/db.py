from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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

# How long a query waits on a locked database before giving up.
_BUSY_TIMEOUT_SECONDS = 10.0


@asynccontextmanager
async def _connect() -> AsyncIterator[aiosqlite.Connection]:
    """Open a connection to the bot database with per-connection settings.

    journal_mode is a persistent property of the database file, so WAL is set
    once in init_db(). The busy timeout and synchronous level are per-connection
    and reset every time — which matters here because every function in this
    module opens its own short-lived connection.
    """
    async with aiosqlite.connect(DB_PATH, timeout=_BUSY_TIMEOUT_SECONDS) as db:
        # Safe to relax under WAL: durable across process crashes, only at risk
        # from an OS-level crash or power loss mid-write. Saves an fsync per
        # commit, which /leaderboard pays once per cached row.
        await db.execute("PRAGMA synchronous=NORMAL")
        yield db


async def init_db() -> None:
    async with _connect() as db:
        # WAL lets readers proceed while a write is in flight. Without it, the
        # concurrent reads /leaderboard fans out across guilds serialise against
        # any /register happening at the same time.
        async with db.execute("PRAGMA journal_mode=WAL") as cursor:
            row = await cursor.fetchone()
        mode = (row[0] if row else "unknown").lower()
        if mode != "wal":
            # Some network filesystems silently refuse WAL. Worth knowing about
            # on a mounted volume rather than discovering it under load.
            print(
                f"WARNING: could not enable WAL (journal_mode={mode}). "
                "Writes will block concurrent reads.",
                flush=True,
            )

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
    async with _connect() as db:
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
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_user(discord_id: str) -> None:
    async with _connect() as db:
        await db.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM stats_cache WHERE discord_id = ?", (discord_id,))
        await db.commit()


async def get_all_users() -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_cached_stats(
    discord_id: str,
    max_age_seconds: int = 300,
) -> dict | None:
    """Return cached leaderboard data for a user if it is within max_age_seconds, else None."""
    async with _connect() as db:
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
    async with _connect() as db:
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
