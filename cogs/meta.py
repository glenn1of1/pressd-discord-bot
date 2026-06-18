from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from version import RELEASED, VERSION

class MetaCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="version",
        description="Show the current bot version and release date.",
    )
    async def version(self, interaction: discord.Interaction) -> None:
        command_count = len(self.bot.tree.get_commands())

        embed = discord.Embed(
            title="ValoPresser Bot",
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Version", value=f"v{VERSION}", inline=True)
        embed.add_field(name="Released", value=RELEASED, inline=True)
        embed.add_field(
            name="Commands",
            value=f"{command_count} slash commands available",
            inline=True,
        )
        embed.set_footer(text="Data via HenrikDev · Thanks brah for the API!")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MetaCog(bot))
