from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from api.henrik import HenrikClient
from banter.engine import generate_banter
from database.db import get_user
from utils.cache import get_player_blob
from utils.stats import _find_player

_GREEN = 0x2ECC71
_RED = 0xE74C3C


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.henrik: HenrikClient = bot.henrik

    async def _resolve_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None,
    ) -> dict | None:
        target = user or interaction.user
        record = await get_user(str(target.id))
        if record is None:
            who = "" if target == interaction.user else f"{target.display_name}"
            await interaction.followup.send(
                f"{who} is a nimrod and has not registered yet. Use `/register Name#TAG` to link an account.",
                ephemeral=True,
            )
            return None
        return record

    # ------------------------------------------------------------------ /stats

    @app_commands.command(
        name="stats",
        description="Show last 20 game stats for a player.",
    )
    @app_commands.describe(user="Discord user to look up (defaults to you)")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: (i.guild_id, i.user.id))
    async def stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer()

        record = await self._resolve_user(interaction, user)
        if record is None:
            return

        name, tag = record["riot_name"], record["riot_tag"]

        try:
            blob = await get_player_blob(self.henrik, record)
        except LookupError:
            await interaction.followup.send(
                "Must be tweaking cuz I cant find that Riot account. Double-check the name and tag.",
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

        stats = blob["stats"]

        if stats["games"] == 0:
            await interaction.followup.send(
                "This player thinks they the shit and is too cool to make their match history public. Nothing to show.",
                ephemeral=True,
            )
            return

        tier_name = blob["tier_name"]
        rr = blob["rr"]

        color = _GREEN if stats["wins"] >= stats["losses"] else _RED
        embed = discord.Embed(
            title=f"{name}#{tag} — Last {stats['games']} Games",
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(
            name="Record",
            value=f"{stats['wins']}W / {stats['losses']}L ({stats['wr']:.0f}% WR)",
            inline=False,
        )
        embed.add_field(
            name="KDA",
            value=(
                f"{stats['avg_kills']} / {stats['avg_deaths']} / {stats['avg_assists']}"
                f"  →  Ratio: **{stats['kda']}**"
            ),
            inline=False,
        )
        embed.add_field(name="Headshot %", value=f"{stats['hs']}%", inline=True)
        embed.add_field(name="Avg ACS", value=str(stats["acs"]), inline=True)
        embed.add_field(name="Most Played", value=stats["top_agent"], inline=True)
        embed.add_field(
            name="Current Rank",
            value=f"{tier_name} — {rr} RR",
            inline=False,
        )

        embed.set_footer(text=generate_banter(stats))

        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------ /rank

    @app_commands.command(
        name="rank",
        description="Show current rank, RR, and recent RR trend.",
    )
    @app_commands.describe(user="Discord user to look up (defaults to you)")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: (i.guild_id, i.user.id))
    async def rank(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer()

        record = await self._resolve_user(interaction, user)
        if record is None:
            return

        name, tag, region = record["riot_name"], record["riot_tag"], record["region"]

        try:
            mmr_raw, hist_raw = await asyncio.gather(
                self.henrik.get_mmr(region, name, tag),
                self.henrik.get_mmr_history(region, name, tag),
            )
        except LookupError:
            await interaction.followup.send(
                "Couldn't find that Riot account.", ephemeral=True
            )
            return
        except RuntimeError:
            await interaction.followup.send(
                "Too many requests — try again in a minute.", ephemeral=True
            )
            return
        except Exception:
            await interaction.followup.send(
                "The Valorant API is having a moment. Try again in a bit.",
                ephemeral=True,
            )
            return

        data = mmr_raw.get("data", {})
        current = data.get("current", {})
        peak = data.get("peak", {})

        tier_name = current.get("tier", {}).get("name", "Unranked")
        rr = current.get("rr", 0)
        last_change = current.get("last_change", 0)
        peak_tier = peak.get("tier", {}).get("name", "Unknown")
        peak_season = peak.get("season", {}).get("short", "?")

        history = hist_raw.get("data", {}).get("history", [])
        trend_parts = []
        for entry in history[:5]:
            change = entry.get("last_change", 0)
            trend_parts.append(f"+{change}" if change >= 0 else str(change))
        trend = " / ".join(trend_parts) if trend_parts else "No data"

        last_str = f"+{last_change}" if last_change >= 0 else str(last_change)

        embed = discord.Embed(
            title=f"{name}#{tag} — Rank",
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="Current Rank",
            value=f"**{tier_name}** — {rr} RR  ({last_str} last game)",
            inline=False,
        )
        embed.add_field(
            name="Peak",
            value=f"{peak_tier}  ({peak_season})",
            inline=True,
        )
        embed.add_field(name="RR Trend (last 5)", value=trend, inline=True)
        embed.set_footer(text=f"Act {peak_season}")

        await interaction.followup.send(embed=embed)

    # ----------------------------------------------------------------- /recent

    @app_commands.command(
        name="recent",
        description="Show recent match history.",
    )
    @app_commands.describe(
        user="Discord user to look up (defaults to you)",
        count="Number of matches to show (1–10, default 5)",
    )
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: (i.guild_id, i.user.id))
    async def recent(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        count: int = 5,
    ) -> None:
        await interaction.response.defer()

        count = max(1, min(count, 10))

        record = await self._resolve_user(interaction, user)
        if record is None:
            return

        name, tag, region = record["riot_name"], record["riot_tag"], record["region"]

        try:
            matches_raw = await self.henrik.get_matches(region, name, tag, size=count)
        except LookupError:
            await interaction.followup.send(
                "Must be tweaking cuz I cant find that Riot account.", ephemeral=True
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

        matches = matches_raw.get("data", [])
        if not matches:
            await interaction.followup.send(
                "This player thinks they the shit and is too cool to make their match history public. Nothing to show.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{name}#{tag} — Last {len(matches)} Games",
            timestamp=datetime.now(timezone.utc),
        )

        for match in matches:
            player = _find_player(match.get("players", []), name, tag)
            if player is None:
                continue

            meta = match.get("metadata", {})
            map_name = meta.get("map", {}).get("name", "?")
            started_at = meta.get("started_at", "")
            try:
                date_str = datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                ).strftime("%b %d")
            except (ValueError, AttributeError):
                date_str = "?"

            stats = player.get("stats", {})
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            score = stats.get("score", 0)

            player_team_id = player.get("team_id", "")
            won = False
            rounds_total = 0
            for team in match.get("teams", []):
                if team.get("team_id") == player_team_id:
                    won = bool(team.get("won"))
                    r = team.get("rounds", {})
                    rounds_total = r.get("won", 0) + r.get("lost", 0)
                    break

            acs = round(score / max(rounds_total, 1))
            outcome = "W" if won else "L"
            agent = player.get("agent", {}).get("name", "?")

            embed.add_field(
                name=f"{outcome}  {map_name}  ·  {date_str}",
                value=f"{agent}  |  {k}/{d}/{a}  |  {acs} ACS",
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))
