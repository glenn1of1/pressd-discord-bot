import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


class ValoPresserBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})", flush=True)
        print("we ready muddddyyy.", flush=True)

    async def start_bot(self) -> None:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN is not set in .env dumbass")
        await self.start(token)
