from __future__ import annotations

import json
import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(
    os.getenv("DB_PATH", str(Path(__file__).parent.parent / "valorant_bot.db"))
)


async def init_db() -> None:
    # #region agent log
    import time as _t
    _env_val = os.getenv("DB_PATH", "__NOT_SET__")
    _db_exists = Path(DB_PATH).exists()
    _payload = {"sessionId":"f30042","hypothesisId":"H1-H2-H3-H4","location":"database/db.py:init_db","message":"DB init","data":{"DB_PATH_env":_env_val,"resolved_path":str(DB_PATH),"file_exists_before_init":_db_exists},"timestamp":int(_t.time()*1000)}
    print(f"[DEBUG f30042] {json.dumps(_payload)}", flush=True)
    with open("debug-f30042.log","a") as _lf: _lf.write(json.dumps(_payload)+"\n")
    # #endregion
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
        # #region agent log
        async with db.execute("SELECT COUNT(*) FROM users") as _cur:
            _user_count = (await _cur.fetchone())[0]
        _payload2 = {"sessionId":"f30042","hypothesisId":"H3","location":"database/db.py:init_db:post","message":"DB init complete","data":{"user_rows_after_init":_user_count},"timestamp":int(_t.time()*1000)}
        print(f"[DEBUG f30042] {json.dumps(_payload2)}", flush=True)
        with open("debug-f30042.log","a") as _lf: _lf.write(json.dumps(_payload2)+"\n")
        # #endregion


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
