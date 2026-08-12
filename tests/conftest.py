"""Shared fixtures and stubs.

Nothing here touches the network or the real database — the HenrikDev client is
stubbed at the aiohttp session boundary, and database tests run against a
throwaway SQLite file under pytest's tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import aiohttp
import pytest

# Tests import the bot's packages by name (api.henrik, utils.cache, ...), so the
# project root has to be importable regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database.db as db_module  # noqa: E402
from api.henrik import HenrikClient  # noqa: E402

# Large enough that the rate limiter never sleeps during a test.
UNTHROTTLED = 100_000


@pytest.fixture
async def temp_db(tmp_path, monkeypatch):
    """Point database.db at a fresh SQLite file and initialise the schema."""
    path = tmp_path / "test_bot.db"
    monkeypatch.setattr(db_module, "DB_PATH", path)
    monkeypatch.setenv("DB_PATH", str(path))
    await db_module.init_db()
    return path


class FakeResponse:
    def __init__(self, status: int, headers: dict | None = None, payload=None):
        self.status = status
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"data": "ok"}

    async def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)


class _FakeRequest:
    def __init__(self, response: FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Stands in for aiohttp.ClientSession, replaying a fixed status sequence.

    The last entry repeats once the sequence is exhausted, so a single-element
    sequence models an endpoint that always returns that status.
    """

    closed = False

    def __init__(self, statuses, headers=None, payload=None):
        self.statuses = list(statuses)
        self.headers = headers or [{}] * len(self.statuses)
        self.payload = payload
        self.calls = 0
        self.requested_params = []

    def get(self, url, params=None):
        index = min(self.calls, len(self.statuses) - 1)
        self.calls += 1
        self.requested_params.append(params)
        return _FakeRequest(
            FakeResponse(self.statuses[index], self.headers[index], self.payload)
        )


def make_client(statuses=(200,), headers=None, payload=None, rate_limit=UNTHROTTLED):
    """A HenrikClient wired to a FakeSession instead of the real network."""
    client = HenrikClient("test-key", rate_limit=rate_limit)
    client._session = FakeSession(statuses, headers, payload)
    return client


def make_match(name: str, tag: str, *, kills=20, deaths=10, assists=5, won=True,
               headshots=25, bodyshots=60, legshots=15, score=5000, agent="Jett"):
    """One entry shaped like a HenrikDev v4 match, containing a single player."""
    return {
        "metadata": {"map": {"name": "Ascent"}, "started_at": "2026-01-01T00:00:00Z"},
        "players": [
            {
                "name": name,
                "tag": tag,
                "team_id": "Red",
                "agent": {"name": agent},
                "stats": {
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "headshots": headshots,
                    "bodyshots": bodyshots,
                    "legshots": legshots,
                    "score": score,
                },
            }
        ],
        "teams": [
            {"team_id": "Red", "won": won, "rounds": {"won": 13, "lost": 7}}
        ],
    }
