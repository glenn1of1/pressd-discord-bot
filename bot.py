import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from api.henrik import HenrikClient
from database.db import init_db

load_dotenv()

log = logging.getLogger(__name__)


class ValoPresserBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.henrik = HenrikClient(os.getenv("HENRIK_API_KEY"))
        # One handler for every cog. CommandTree calls this in a `finally` after
        # any per-command handler, so a cog-level handler would double-respond.
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = (
                f"CHILL IM BROKE. THIS COMMAND IS ON COOLDOWN. "
                f"Try again in {error.retry_after:.0f}s."
            )
        else:
            command = interaction.command.name if interaction.command else "unknown"
            log.exception("Unhandled error in /%s", command, exc_info=error)
            msg = "Something broke on my end. Try again in a bit."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            # Interaction already expired or was responded to — nothing to do.
            pass

    async def setup_hook(self) -> None:
        await init_db()
        print("Database initialized.", flush=True)

        cogs_dir = Path(__file__).parent / "cogs"
        for path in sorted(cogs_dir.glob("*.py")):
            if path.stem != "__init__":
                await self.load_extension(f"cogs.{path.stem}")
                print(f"Loaded cog: cogs.{path.stem}", flush=True)

        # DISCORD_GUILD_ID is the dev switch: a guild sync lands instantly, so
        # it's what you want while iterating. Production leaves it unset and
        # syncs globally, which reaches every server but can take up to an hour
        # to propagate. Doing both would show duplicate commands in the dev guild.
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(
                f"Synced {len(synced)} commands to guild {guild_id} (dev mode).",
                flush=True,
            )
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} commands globally.", flush=True)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})", flush=True)
        print("we ready muddddyyy.", flush=True)

    async def close(self) -> None:
        await self.henrik.close()
        await super().close()

    async def start_bot(self) -> None:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN is not set in .env dumbass")
        await self.start(token)
