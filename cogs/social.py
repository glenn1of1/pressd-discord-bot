from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from api.henrik import HenrikClient
from banter.engine import generate_banter
from database.db import get_all_users, get_cached_stats, get_user, set_cached_stats
from utils.stats import compute_stats

# Maps Valorant tier names to sortable integers for /leaderboard rank sorting.
# RR (0–99) is added as a fractional component so Diamond 1 at 99 RR (16.99)
# never exceeds Diamond 2 at 0 RR (17.0).
_TIER_ORDER: dict[str, int] = {
    "Unranked": 0,
    "Iron 1": 1,
    "Iron 2": 2,
    "Iron 3": 3,
    "Bronze 1": 4,
    "Bronze 2": 5,
    "Bronze 3": 6,
    "Silver 1": 7,
    "Silver 2": 8,
    "Silver 3": 9,
    "Gold 1": 10,
    "Gold 2": 11,
    "Gold 3": 12,
    "Platinum 1": 13,
    "Platinum 2": 14,
    "Platinum 3": 15,
    "Diamond 1": 16,
    "Diamond 2": 17,
    "Diamond 3": 18,
    "Ascendant 1": 19,
    "Ascendant 2": 20,
    "Ascendant 3": 21,
    "Immortal 1": 22,
    "Immortal 2": 23,
    "Immortal 3": 24,
    "Radiant": 25,
}


class SocialCog(commands.Cog):
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

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = (
                f"CHILL IM BROKE. THIS COMMAND IS ON COOLDOWN. "
                f"Try again in {error.retry_after:.0f}s."
            )
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        else:
            raise error

    # --------------------------------------------------------------- /compare

    @app_commands.command(
        name="compare",
        description="Head-to-head stat comparison between two registered players.",
    )
    @app_commands.describe(user1="First player", user2="Second player")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def compare(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member,
    ) -> None:
        await interaction.response.defer()

        if user1.id == user2.id:
            await interaction.followup.send(
                "TWO. DIFFERENT. PEOPLE. PICK TWO DIFFERENT PEOPLE. DAMN.",
                ephemeral=True,
            )
            return

        record1 = await self._resolve_user(interaction, user1)
        if record1 is None:
            return
        record2 = await self._resolve_user(interaction, user2)
        if record2 is None:
            return

        try:
            matches1_raw, matches2_raw, mmr1_raw, mmr2_raw = await asyncio.gather(
                self.henrik.get_matches(
                    record1["region"],
                    record1["riot_name"],
                    record1["riot_tag"],
                    size=20,
                ),
                self.henrik.get_matches(
                    record2["region"],
                    record2["riot_name"],
                    record2["riot_tag"],
                    size=20,
                ),
                self.henrik.get_mmr(
                    record1["region"], record1["riot_name"], record1["riot_tag"]
                ),
                self.henrik.get_mmr(
                    record2["region"], record2["riot_name"], record2["riot_tag"]
                ),
            )
        except LookupError:
            await interaction.followup.send(
                "Couldn't find one of those Riot accounts. Double-check the names. Must be buggin lol.",
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

        stats1 = compute_stats(matches1_raw, record1["riot_name"], record1["riot_tag"])
        stats2 = compute_stats(matches2_raw, record2["riot_name"], record2["riot_tag"])

        name1 = f"{record1['riot_name']}#{record1['riot_tag']}"
        name2 = f"{record2['riot_name']}#{record2['riot_tag']}"
        short1 = record1["riot_name"]
        short2 = record2["riot_name"]

        if stats1["games"] == 0 and stats2["games"] == 0:
            await interaction.followup.send(
                "Both players wanna be mystery men and think they're hollywood. Nothing to compare.",
                ephemeral=True,
            )
            return
        if stats1["games"] == 0:
            await interaction.followup.send(
                f"{name1} thinks they the shit and is too cool to make their match history public.",
                ephemeral=True,
            )
            return
        if stats2["games"] == 0:
            await interaction.followup.send(
                f"{name2} thinks they the shit and is too cool to make their match history public.",
                ephemeral=True,
            )
            return

        # (label, raw_val1, raw_val2, display_str1, display_str2)
        categories: list[tuple[str, float, float, str, str]] = [
            (
                "KDA",
                stats1["kda"],
                stats2["kda"],
                str(stats1["kda"]),
                str(stats2["kda"]),
            ),
            (
                "Headshot %",
                stats1["hs"],
                stats2["hs"],
                f"{stats1['hs']}%",
                f"{stats2['hs']}%",
            ),
            (
                "Win Rate",
                stats1["wr"],
                stats2["wr"],
                f"{stats1['wr']}%",
                f"{stats2['wr']}%",
            ),
            (
                "Avg ACS",
                stats1["acs"],
                stats2["acs"],
                str(stats1["acs"]),
                str(stats2["acs"]),
            ),
        ]

        p1_wins = sum(1 for _, v1, v2, _, _ in categories if v1 > v2)
        p2_wins = sum(1 for _, v1, v2, _, _ in categories if v2 > v1)

        embed = discord.Embed(
            title=f"⚔️  {name1}  vs  {name2}",
            timestamp=datetime.now(timezone.utc),
        )

        for label, v1, v2, s1, s2 in categories:
            if v1 > v2:
                line = f"✅ **{short1}**: {s1}  |  **{short2}**: {s2}"
            elif v2 > v1:
                line = f"**{short1}**: {s1}  |  **{short2}**: {s2} ✅"
            else:
                line = f"**{short1}**: {s1}  |  **{short2}**: {s2}  (tied)"
            embed.add_field(name=label, value=line, inline=False)

        current1 = mmr1_raw.get("data", {}).get("current", {})
        current2 = mmr2_raw.get("data", {}).get("current", {})
        tier1 = current1.get("tier", {}).get("name", "Unranked")
        rr1 = current1.get("rr", 0)
        tier2 = current2.get("tier", {}).get("name", "Unranked")
        rr2 = current2.get("rr", 0)
        embed.add_field(
            name="Current Rank",
            value=f"**{short1}**: {tier1} — {rr1} RR  |  **{short2}**: {tier2} — {rr2} RR",
            inline=False,
        )

        if p1_wins > p2_wins:
            verdict = f"**{short1}** wins {p1_wins} of {len(categories)} stats — {short2} this isn't a glitch, you are shit."
            footer = generate_banter(stats2, pool="comparison_loss")
        elif p2_wins > p1_wins:
            verdict = f"**{short2}** wins {p2_wins} of {len(categories)} stats — {short1} step it up pussy ass bitch."
            footer = generate_banter(stats1, pool="comparison_loss")
        else:
            verdict = f"{short1} and {short2} are both dogshit LMFAOO."
            footer = generate_banter(stats1)

        embed.add_field(name="Verdict", value=verdict, inline=False)
        embed.set_footer(text=footer)

        await interaction.followup.send(embed=embed)

    # ----------------------------------------------------------- /leaderboard

    @app_commands.command(
        name="leaderboard",
        description="Server-wide stat leaderboard for all registered players.",
    )
    @app_commands.describe(
        stat="Stat to rank by (default: KDA) (range : last 20 games)"
    )
    @app_commands.choices(
        stat=[
            app_commands.Choice(name="KDA", value="kda"),
            app_commands.Choice(name="Headshot %", value="hs"),
            app_commands.Choice(name="Win Rate", value="winrate"),
            app_commands.Choice(name="Rank", value="rank"),
        ]
    )
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()

        stat_key = stat.value if stat else "kda"

        users = await get_all_users()
        if not users:
            await interaction.followup.send(
                "No one has registered yet. Use `/register Name#TAG` to get on the board.",
                ephemeral=True,
            )
            return

        sem = asyncio.Semaphore(3)

        async def _fetch(record: dict) -> tuple[dict, dict | None]:
            async with sem:
                cached = await get_cached_stats(record["discord_id"])
                if cached is not None:
                    return record, cached

                try:
                    matches_raw, mmr_raw = await asyncio.gather(
                        self.henrik.get_matches(
                            record["region"],
                            record["riot_name"],
                            record["riot_tag"],
                            size=20,
                        ),
                        self.henrik.get_mmr(
                            record["region"], record["riot_name"], record["riot_tag"]
                        ),
                    )
                except Exception:
                    return record, None

                stats = compute_stats(
                    matches_raw, record["riot_name"], record["riot_tag"]
                )
                current = mmr_raw.get("data", {}).get("current", {})
                blob = {
                    "stats": stats,
                    "tier_name": current.get("tier", {}).get("name", "Unranked"),
                    "rr": current.get("rr", 0),
                }
                await set_cached_stats(record["discord_id"], blob)
                return record, blob

        results: list[tuple[dict, dict | None]] = list(
            await asyncio.gather(*(_fetch(u) for u in users))
        )

        stat_labels = {
            "kda": "KDA",
            "hs": "Headshot %",
            "winrate": "Win Rate",
            "rank": "Rank",
        }

        rows: list[tuple[str, str, float]] = []  # (display_name, display_val, sort_val)
        for record, blob in results:
            display = f"{record['riot_name']}#{record['riot_tag']}"

            if blob is None:
                rows.append((display, "N/A", -999.0))
                continue

            if stat_key == "rank":
                tier_name = blob["tier_name"]
                rr = blob["rr"]
                sort_val = float(_TIER_ORDER.get(tier_name, 0)) + rr / 100
                rows.append((display, f"{tier_name} — {rr} RR", sort_val))
            else:
                stats = blob["stats"]
                if stats["games"] == 0:
                    rows.append((display, "N/A", -999.0))
                    continue
                if stat_key == "kda":
                    rows.append((display, str(stats["kda"]), stats["kda"]))
                elif stat_key == "hs":
                    rows.append((display, f"{stats['hs']}%", float(stats["hs"])))
                elif stat_key == "winrate":
                    rows.append((display, f"{stats['wr']}%", float(stats["wr"])))

        rows.sort(key=lambda x: x[2], reverse=True)

        lines: list[str] = []
        for i, (name, val, _) in enumerate(rows, 1):
            if val == "N/A":
                lines.append(f"{i}. {name} — N/A")
            else:
                lines.append(f"{i}. **{name}** — {val}")

        embed = discord.Embed(
            title=f"🏆  Server Leaderboard — {stat_labels[stat_key]}",
            description="\n".join(lines),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(
            text=(
                f"Showing {len(rows)} registered player"
                f"{'s' if len(rows) != 1 else ''} · Last 20 games · cached up to 5 min"
            )
        )

        await interaction.followup.send(embed=embed)

    # ----------------------------------------------------------------- /roast

    @app_commands.command(
        name="roast",
        description="Talk yo shit to someone.",
    )
    @app_commands.describe(user="The unfortunate soul to roast")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def roast(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        await interaction.response.defer()

        record = await self._resolve_user(interaction, user)
        if record is None:
            return

        name, tag, region = record["riot_name"], record["riot_tag"], record["region"]

        try:
            matches_raw = await self.henrik.get_matches(region, name, tag, size=20)
        except LookupError:
            await interaction.followup.send(
                "Couldn't find that Riot account. Double-check the name and tag.",
                ephemeral=True,
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

        stats = compute_stats(matches_raw, name, tag)

        if stats["games"] == 0:
            await interaction.followup.send(
                f"{user.display_name}'s match history is private. Can't roast what you can't see.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(f"🔥  {generate_banter(stats)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SocialCog(bot))
