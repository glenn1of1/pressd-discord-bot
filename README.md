# PRESSD

A Discord bot that links your Riot account, pulls your Valorant match history and rank from the [HenrikDev API](https://docs.henrikdev.xyz/), and turns your stats into personality-driven trash talk.

> **Heads up:** PRESSD's banter engine is built around crude, profanity-heavy humor by design (see `banter/templates.py`). It's meant for a private friend server, not a general-audience bot. Keep that in mind before inviting it to a public/mixed server — see [Content & Tone](#content--tone) below.

## Features

| Command | Description |
|---|---|
| `/register` | Link your Riot ID (`Name#TAG`) and region to your Discord account |
| `/unregister` | Remove your linked account |
| `/stats` | Last 20 games — KDA, headshot %, win rate, ACS, top agent, current rank |
| `/rank` | Current rank, RR, peak rank, and recent RR trend |
| `/recent` | Match-by-match breakdown (1–10 most recent games) |
| `/compare` | Head-to-head stat comparison between two registered players |
| `/leaderboard` | Server-wide ranking by KDA, headshot %, win rate, or rank |
| `/roast` | Instant roast based on someone's recent performance |
| `/version` | Bot version, release date, and command count |

## Tech Stack

- [`discord.py`](https://github.com/Rapptz/discord.py) — slash commands, cogs
- [`aiohttp`](https://docs.aiohttp.org/) — async HTTP client for the HenrikDev API
- [`aiosqlite`](https://github.com/omnilib/aiosqlite) — async SQLite for user registration + stats caching
- [HenrikDev API](https://docs.henrikdev.xyz/) — Valorant match, MMR, and account data
- Deployed on [Railway](https://railway.app/)

## Architecture Notes

- `api/henrik.py` — `HenrikClient` owns a single lazily-created `aiohttp.ClientSession`, reused across requests. The client lives on the bot instance (`bot.henrik`) and is closed cleanly on shutdown.
- `utils/stats.py` — turns raw HenrikDev match JSON into the aggregate stats dict consumed everywhere else (`compute_stats`).
- `banter/engine.py` + `banter/templates.py` — template-based roast generation, picked by stat thresholds (`_pick_pool`). `BANTER_MODE=ai` is scaffolded but not yet implemented.
- `database/db.py` — user registration table + a 5-minute stats cache table (currently only used by `/leaderboard`).

## Setup

```bash
git clone https://github.com/<your-username>/pressd.git
cd pressd
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your values
python main.py
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Your bot's token from the [Discord Developer Portal](https://discord.com/developers/applications) |
| `HENRIK_API_KEY` | Yes | API key from [HenrikDev](https://docs.henrikdev.xyz/) |
| `DISCORD_GUILD_ID` | No | Guild ID for instant (guild-scoped) slash command syncing during dev. Omit for global sync. |
| `DB_PATH` | No | Path to the SQLite database file. Defaults to `./valorant_bot.db`. Set this to a persistent volume path in production (e.g. Railway). |
| `BANTER_MODE` | No | `template` (default) or `ai` (not yet implemented) |

## Deployment

Configured for [Railway](https://railway.app/) via the included `Procfile` (runs as a background worker, not a web service). Set the environment variables above in your Railway project, attach a persistent volume, and point `DB_PATH` at it so registrations survive redeploys.

## Roadmap

- [ ] Extend the stats cache to `/stats` and `/compare` (currently only `/leaderboard` uses it)
- [ ] Paginate `/leaderboard` for large servers (Discord's 4096-char embed description limit)
- [ ] Filter match history by game mode so deathmatch/casual don't skew competitive stats
- [ ] Replace `print()` calls with structured `logging`
- [ ] `BANTER_MODE=ai` — AI-generated banter (pending a product decision)

## Content & Tone

The roast templates contain strong profanity and crude sexual humor. This is intentional. It's a bot built for a specific friend group's sense of humor but, it's worth knowing before you invite it somewhere new or point people at this repo. If you plan to run it in a mixed or public server, check Discord's [Developer Policy](https://discord.com/developers/docs/policies-and-agreements/developer-policy) on age-restricted content, and consider marking the app as age-restricted in the Developer Portal or maintaining a toned-down template set for that context.

## License

MIT — see [LICENSE](LICENSE).
