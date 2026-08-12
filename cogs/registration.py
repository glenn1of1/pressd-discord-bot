from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from api.henrik import HenrikClient
from database.db import delete_user, get_user, register_user


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.henrik: HenrikClient = bot.henrik

    @app_commands.command(
        name="register",
        description="Link your Riot ID to your Discord account.",
    )
    @app_commands.describe(
        riot_id="Your Riot ID in Name#TAG format (e.g. TenZ#NA1)",
        region="The region your account is on (default: North America)",
    )
    @app_commands.choices(
        region=[
            app_commands.Choice(name="North America", value="na"),
            app_commands.Choice(name="Europe", value="eu"),
            app_commands.Choice(name="Asia Pacific", value="ap"),
            app_commands.Choice(name="Korea", value="kr"),
            app_commands.Choice(name="Latin America", value="latam"),
            app_commands.Choice(name="Brazil", value="br"),
        ]
    )
    async def register(
        self,
        interaction: discord.Interaction,
        riot_id: str,
        region: str = "na",
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if "#" not in riot_id:
            await interaction.followup.send(
                "Hey dumbass, `Name#TAG` format, e.g. `TenZ#NA1`.",
                ephemeral=True,
            )
            return

        name, tag = riot_id.split("#", 1)

        try:
            await self.henrik.get_account(name, tag)
        except LookupError:
            await interaction.followup.send(
                "Couldn't find that trash Riot account. Double-check the name and tag so I can see how bad you are.",
                ephemeral=True,
            )
            return
        except RuntimeError:
            await interaction.followup.send(
                "CHILL CHILL CHILL! Too many requests, slow down a little. Take a walk and ask me again.",
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.followup.send(
                "The Valorant API is having a lil temper tantrum moment. Try again in a bit.",
                ephemeral=True,
            )
            return

        await register_user(str(interaction.user.id), name, tag, region)
        await interaction.followup.send(
            f"Registered **{name}#{tag}** ({region.upper()}). You're in the system.",
            ephemeral=True,
        )

    @app_commands.command(
        name="unregister",
        description="Remove your linked Riot ID.",
    )
    async def unregister(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        user = await get_user(str(interaction.user.id))
        if user is None:
            await interaction.followup.send(
                "You're not registered. Didn't need ur trashy ass anyways.",
                ephemeral=True,
            )
            return

        await delete_user(str(interaction.user.id))
        await interaction.followup.send(
            f"Unregistered **{user['riot_name']}#{user['riot_tag']}**. I'm going to set my database on fire to forget about yo stupid ahh.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Registration(bot))
