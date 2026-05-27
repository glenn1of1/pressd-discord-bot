# ValoPresser Bot — Build & Development Guide

**Version:** 0.1
**Last Updated:** May 26, 2026

This document covers everything needed to go from zero to a running ValoPresser Bot instance — locally and on a production VPS via Railway.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [API Keys & Credentials](#2-api-keys--credentials)
3. [Local Environment Setup](#3-local-environment-setup)
4. [Project Structure](#4-project-structure)
5. [Environment Variables](#5-environment-variables)
6. [Running Locally](#6-running-locally)
7. [Deploying to Railway](#7-deploying-to-railway)
8. [Dependency Reference](#8-dependency-reference)
9. [Development Workflow](#9-development-workflow)

---

## 1. Prerequisites

Before you begin, make sure the following are installed on your machine:

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| pip | bundled with Python 3.11 | Package management |
| Git | Any recent version | Version control |
| A code editor | VS Code recommended | Development |

### Install Python (Windows)

Download from [python.org/downloads](https://www.python.org/downloads/). During installation:
- Check **"Add Python to PATH"**
- Check **"Install pip"**

Verify installation:
```powershell
python --version
pip --version
```

---

## 2. API Keys & Credentials

You will need three credentials before the bot can run. Collect these before starting setup.

### 2.1 Discord Bot Token

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **"New Application"** — name it `ValoPresser Bot`
3. Go to the **Bot** tab → click **"Add Bot"**
4. Under **"Token"**, click **"Reset Token"** and copy the value
5. Under **"Privileged Gateway Intents"**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`, `Read Message History`
   - Copy the generated URL and use it to invite the bot to your server

> **Keep your token secret.** If it leaks, regenerate it immediately.

### 2.2 HenrikDev API Key (Valorant Stats)

1. Go to [api.henrikdev.xyz/dashboard](https://api.henrikdev.xyz/dashboard)
2. Sign in (Discord OAuth)
3. Generate a **Basic Key** — available instantly, no waiting
4. Copy the key value

> **Rate limit:** 30 requests/minute on the Basic Key. Sufficient for a private friend-group server.
> **Enhanced Key:** Apply from the same dashboard for 90 req/min if needed (1–2 week approval).

### 2.3 Discord Guild ID (Server ID)

1. In Discord, enable Developer Mode: **Settings → Advanced → Developer Mode**
2. Right-click your server name → **"Copy Server ID"**
3. Save this value — it's used to register slash commands instantly to your specific server during development

---

## 3. Local Environment Setup

### 3.1 Clone / Open the Project

If you pulled this from GitHub:
```powershell
git clone <your-repo-url> "Valorant Discord Bot"
cd "Valorant Discord Bot"
```

If you're already in the project directory, skip this step.

### 3.2 Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate it:
```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat
```

Your prompt should show `(.venv)` when active.

### 3.3 Install Dependencies

```powershell
pip install -r requirements.txt
```

To also install optional Phase 2 (AI banter) dependencies:
```powershell
pip install openai>=1.30.0
```

### 3.4 Configure Environment Variables

Copy the example file and fill in your values:
```powershell
copy .env.example .env
```

Then open `.env` in your editor and fill in all values. See [Section 5](#5-environment-variables) for the full reference.

---

## 4. Project Structure

```
Valorant Discord Bot/
│
├── PRD.md                   Product Requirements Document
├── BUILD.md                 This file
├── main.py                  Entrypoint — creates bot, starts event loop
├── bot.py                   Bot client class, cog loader, on_ready handler
├── requirements.txt         Python dependencies
├── .env                     Your local secrets (NEVER commit this)
├── .env.example             Committed template — no real values
├── .gitignore
│
├── database/
│   └── db.py                SQLite schema definitions + async CRUD helpers
│
├── cogs/
│   ├── registration.py      /register, /unregister commands
│   ├── stats.py             /stats, /rank, /recent commands
│   └── social.py            /compare, /leaderboard, /roast commands
│
├── api/
│   └── henrik.py            All HenrikDev API calls (aiohttp wrapper)
│
└── banter/
    ├── engine.py            Stat analysis, template selection, optional AI dispatch
    └── templates.py         Roast template string pools
```

### File Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | Single entry point — do not put logic here |
| `bot.py` | `discord.ext.commands.Bot` subclass; loads cogs; handles `on_ready` |
| `database/db.py` | `init_db()`, `register_user()`, `get_user()`, `delete_user()`, `get_all_users()` |
| `api/henrik.py` | `get_account()`, `get_matches()`, `get_mmr()`, `get_mmr_history()` — all return typed dicts or raise |
| `cogs/registration.py` | `/register` and `/unregister` slash commands |
| `cogs/stats.py` | `/stats`, `/rank`, `/recent` — fetch data and build embeds |
| `cogs/social.py` | `/compare`, `/leaderboard`, `/roast` |
| `banter/engine.py` | `generate_banter(stats: dict) -> str` — the single public interface |
| `banter/templates.py` | All roast template strings, organized by stat category |

---

## 5. Environment Variables

Create `.env` in the project root with these values. The `.env.example` file is a blank copy you can duplicate.

```dotenv
# ── Discord ──────────────────────────────────────────────────
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here

# ── HenrikDev Valorant API ───────────────────────────────────
HENRIK_API_KEY=your_henrikdev_key_here

# ── Bot Behaviour ────────────────────────────────────────────
DEFAULT_REGION=na
# Banter mode: "template" (default) or "ai" (requires OpenAI key)
BANTER_MODE=template

# ── Optional: AI Banter (Phase 2) ────────────────────────────
# Only needed if BANTER_MODE=ai
OPENAI_API_KEY=
```

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Your bot's secret token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | Yes | Your server's ID — used to sync slash commands during dev |
| `HENRIK_API_KEY` | Yes | HenrikDev API key for Valorant data |
| `DEFAULT_REGION` | No | Default region for Valorant lookups (`na`, `eu`, `ap`, `kr`, `latam`, `br`) |
| `BANTER_MODE` | No | `template` (default) or `ai` |
| `OPENAI_API_KEY` | No | Only required if `BANTER_MODE=ai` |

---

## 6. Running Locally

Once your virtual environment is active and `.env` is filled in:

```powershell
python main.py
```

You should see output like:
```
Logged in as ValoPresser Bot#1234
Synced 8 commands to guild 123456789012345678
Database initialized.
Ready.
```

The bot is now running and slash commands are available in your Discord server.

To stop the bot, press `Ctrl + C`.

### 6.1 Watching for Changes (Development)

There is no auto-reload built in by default. To restart after code changes:
1. `Ctrl + C` to stop
2. `python main.py` to restart

Optionally install `watchdog` or use `nodemon`-style wrappers, but this is not required.

### 6.2 Database Location

SQLite creates `valorant_bot.db` in the project root on first run. This file is gitignored. To reset the database during development, simply delete it — it will be recreated with the correct schema on next startup.

---

## 7. Deploying to Railway

[Railway](https://railway.app) is a PaaS platform that keeps the bot running 24/7, restarts it on crashes, and deploys automatically from GitHub.

### 7.1 Push Project to GitHub

```powershell
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### 7.2 Create a Railway Project

1. Go to [railway.app](https://railway.app) and log in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `ValoPresser Bot` repository
4. Railway detects Python automatically and deploys

### 7.3 Set Environment Variables on Railway

1. In your Railway project, go to the **Variables** tab
2. Add each key from your `.env` file (without the file — one key per line):
   - `DISCORD_TOKEN`
   - `DISCORD_GUILD_ID`
   - `HENRIK_API_KEY`
   - `DEFAULT_REGION`
   - `BANTER_MODE`
3. Railway injects these at runtime

### 7.4 Add a Start Command

Railway needs to know how to start the bot. Create a `Procfile` in the project root:

```
worker: python main.py
```

> The process type is `worker` (not `web`) because the bot does not listen on an HTTP port.

### 7.5 Confirm Deployment

After pushing, Railway builds the project and starts the bot. Check the **Logs** tab in Railway for the bot's startup output. If you see "Logged in as ValoPresser Bot#...", it's running.

### 7.6 Redeploys

Every `git push` to `main` triggers an automatic redeploy on Railway. No manual action needed.

---

## 8. Dependency Reference

### Core Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---|---|---|
| `discord.py` | >=2.3.0 | Discord bot framework, slash command support (`app_commands`) |
| `aiohttp` | >=3.9.0 | Async HTTP client for HenrikDev API calls |
| `aiosqlite` | >=0.20.0 | Async wrapper for SQLite — non-blocking DB queries |
| `python-dotenv` | >=1.0.0 | Load `.env` file into environment variables |

### Optional Dependencies

| Package | Version | Purpose |
|---|---|---|
| `openai` | >=1.30.0 | Phase 2 AI-generated banter via GPT-4o-mini |

### Installing / Updating

Add a new package:
```powershell
pip install <package-name>
pip freeze > requirements.txt
```

---

## 9. Development Workflow

### 9.1 Branching Convention

```
main        → production (deploys to Railway)
dev         → active development
feature/*   → individual feature branches
```

### 9.2 Adding a New Command

1. Decide which cog it belongs to (`registration.py`, `stats.py`, `social.py`)
2. Add a new `@app_commands.command()` decorated method to the cog's `Cog` class
3. If it needs data from HenrikDev, add a method to `api/henrik.py` first
4. Test locally — restart the bot to sync the new command to Discord
5. Push to `dev`, verify, then merge to `main`

### 9.3 Adding New Banter Templates

Open `banter/templates.py` and add strings to the appropriate category pool. No other changes needed — the engine picks randomly from the pool at runtime.

### 9.4 Switching to AI Banter (Phase 2)

1. Add your `OPENAI_API_KEY` to `.env`
2. Change `BANTER_MODE=ai` in `.env`
3. Install `openai`: `pip install openai>=1.30.0`
4. Restart the bot — the banter engine will route through the AI path automatically

### 9.5 Linting

```powershell
pip install ruff
ruff check .
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `discord.errors.LoginFailure` | Bad or expired token | Regenerate token in Discord Dev Portal, update `.env` |
| Slash commands not appearing | Guild ID wrong or commands not synced | Check `DISCORD_GUILD_ID`, restart bot to force sync |
| `401 Unauthorized` from HenrikDev | Invalid API key | Re-copy key from api.henrikdev.xyz/dashboard |
| `429 Too Many Requests` | Hit rate limit | Wait 60 seconds; consider Enhanced Key |
| `aiosqlite` DB locked error | Multiple bot instances running | Kill all Python processes; only run one instance |
| Bot offline on Railway | Procfile wrong or crash loop | Check Railway logs; ensure `worker: python main.py` in Procfile |
