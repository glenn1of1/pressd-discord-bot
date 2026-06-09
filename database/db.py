from __future__ import annotations

from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent.parent / "valorant_bot.db"


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
        await db.execute(
            "DELETE FROM users WHERE discord_id = ?", (discord_id,)
        )
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
