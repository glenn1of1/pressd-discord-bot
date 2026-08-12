# ValoPresser

A Discord bot that links Discord accounts to Riot IDs, pulls Valorant match and rank data from the
[HenrikDev API](https://api.henrikdev.xyz), computes rolling performance stats, and generates
trash talk based on how badly you're playing.

Built with `discord.py` slash commands, `aiohttp`, and SQLite.

> The banter is deliberately crude — that's the point of the bot. If you're forking this for
> something more polite, `banter/templates.py` is the only file you need to rewrite.

## Commands

| Command | What it does |
|---|---|
| `/register <Name#TAG> [region]` | Link your Riot ID to your Discord account |
| `/unregister` | Remove your linked Riot ID |
| `/stats [user]` | KDA, headshot %, win rate, ACS and rank over the last 20 games |
| `/rank [user]` | Current rank, RR, peak, and RR trend over the last 5 games |
| `/recent [user] [count]` | Recent match history, 1–10 games |
| `/compare <user1> <user2>` | Head-to-head stat comparison with a verdict |
| `/leaderboard [stat]` | Server leaderboard by KDA, headshot %, win rate, or rank |
| `/roast <user>` | Talk your shit |
| `/version` | Bot version and command count |

Registration is global — register once and your account works in every server the bot is in.
Leaderboards are scoped per server, so you only ever see people you actually share a server with.

## How it works

```
Discord slash command
  └─ cogs/            command handlers, embed building, error messages
      └─ utils/cache  shared TTL cache — checks SQLite before hitting the network
          └─ api/     HenrikClient: rate limiting, retries, one pooled session
              └─ HenrikDev API
      └─ utils/stats  aggregates raw match JSON into KDA / HS% / WR / ACS
      └─ banter/      picks a roast pool from those stats and fills a template
```

A few decisions worth calling out:

**One HTTP session for the whole process.** `HenrikClient` is constructed once by the bot and shared
across every cog, lazily creating a single pooled `aiohttp.ClientSession` and closing it on shutdown.

**One cache row serves three commands.** `/stats`, `/compare`, and `/leaderboard` all need the same
thing — computed stats plus current rank — so they share a single row per player keyed by Discord ID.
A warm `/leaderboard` makes zero API calls. Rows carry the Riot ID they were built from, so
re-registering under a different account can't serve you stale numbers, and registration changes
clear the row in the same transaction as the write.

**The rate limiter matters more than the retries.** The free HenrikDev key allows 30 requests/minute
and a cold leaderboard can want 30 at once. A token bucket in `HenrikClient` makes over-budget
requests *wait* rather than fail, so heavy use renders slowly instead of erroring. Retry with
backoff sits behind it as a backstop.

**Cache TTLs are jittered.** `/leaderboard` writes every player's row in the same instant, so
without jitter they'd all expire in the same instant and the next leaderboard would be fully cold
every time. A small random spread staggers the refresh.

## Setup

Requires Python 3.14 (see `.python-version`), a Discord bot token, and a HenrikDev API key.

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill it in — every variable is documented in that file.

In the Discord Developer Portal, the bot needs the **Server Members Intent** enabled
(Bot → Privileged Gateway Intents). Without it, `/leaderboard` can't tell who's in the server and
renders empty. Invite it with both the `bot` and `applications.commands` scopes.

```bash
.venv/Scripts/python.exe main.py
```

Set `DISCORD_GUILD_ID` locally so commands sync to your test server instantly. Leave it unset in
production to sync globally — that reaches every server, but takes up to an hour to propagate.

## Tests

```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

```bash
.venv/Scripts/python.exe -m pytest
```

No network or database access — the API client is stubbed at the session boundary and database
tests run against a throwaway SQLite file.

## Deployment

Runs on [Railway](https://railway.app) as a worker process (`Procfile`), which redeploys on every
push to the deploy branch.

Two things matter in production:

- **`DB_PATH` must point inside a mounted persistent volume** (e.g. `/data/valorant_bot.db`).
  Unset, it falls back to a file in the project directory that is wiped on every redeploy, taking
  every registration with it. The bot logs a warning at startup if it isn't set.
- **`DISCORD_GUILD_ID` must not be set**, or the bot syncs commands to that one guild only.

SQLite runs in WAL mode so reads don't block behind writes; the bot warns at startup if the
filesystem refuses it.

## Project structure

```
main.py              entrypoint
bot.py               ValoPresserBot — cog loading, command sync, global error handler
api/henrik.py        HenrikDev client: session, rate limiter, retries
database/db.py       aiosqlite persistence (users, stats_cache)
utils/cache.py       shared stats cache
utils/stats.py       match JSON → computed stats
utils/paginator.py   button pager for multi-page leaderboards
banter/              roast pool selection and templates
cogs/                slash commands
tests/               pytest suite
```

## License

MIT — see [LICENSE](LICENSE).

Valorant data via [HenrikDev](https://api.henrikdev.xyz). Not affiliated with or endorsed by
Riot Games.
