import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import init_db

load_dotenv()


class ValoPresserBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await init_db()
        print("Database initialized.", flush=True)

        cogs_dir = Path(__file__).parent / "cogs"
        for path in sorted(cogs_dir.glob("*.py")):
            if path.stem != "__init__":
                await self.load_extension(f"cogs.{path.stem}")
                print(f"Loaded cog: cogs.{path.stem}", flush=True)

        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {guild_id}.", flush=True)
        else:
            print("DISCORD_GUILD_ID not set — skipping guild sync.", flush=True)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})", flush=True)
        print("we ready muddddyyy.", flush=True)

    async def start_bot(self) -> None:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN is not set in .env dumbass")
        await self.start(token)
