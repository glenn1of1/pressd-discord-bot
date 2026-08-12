"""HenrikClient: session reuse, error mapping, retry/backoff, and rate limiting."""

from __future__ import annotations

import asyncio

import pytest
from conftest import FakeResponse, make_client

import api.henrik as henrik_mod
from api.henrik import _RateLimiter, _env_int, _retry_delay


@pytest.fixture
def no_sleep(monkeypatch):
    """Record backoff durations without actually waiting them out."""
    slept = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay):
        slept.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(henrik_mod.asyncio, "sleep", fake_sleep)
    return slept


# --------------------------------------------------------------- session
async def test_session_is_created_once_and_reused():
    client = henrik_mod.HenrikClient("key")
    first = client._get_session()
    assert client._get_session() is first
    await client.close()
    assert first.closed


async def test_close_is_idempotent_and_session_recreates():
    client = henrik_mod.HenrikClient("key")
    first = client._get_session()
    await client.close()
    await client.close()
    second = client._get_session()
    assert second is not first
    await client.close()


# --------------------------------------------------------------- errors
async def test_success_makes_one_call(no_sleep):
    client = make_client([200])
    assert await client._get("/x") == {"data": "ok"}
    assert client._session.calls == 1


@pytest.mark.parametrize("status,expected", [(404, LookupError), (401, ValueError)])
async def test_client_errors_raise_and_never_retry(no_sleep, status, expected):
    client = make_client([status])
    with pytest.raises(expected):
        await client._get("/x")
    assert client._session.calls == 1


# --------------------------------------------------------------- retry
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_transient_status_is_retried_then_succeeds(no_sleep, status):
    client = make_client([status, 200])
    assert await client._get("/x") == {"data": "ok"}
    assert client._session.calls == 2


async def test_persistent_429_gives_up_with_runtime_error(no_sleep):
    client = make_client([429])
    with pytest.raises(RuntimeError, match="Rate limit"):
        await client._get("/x")
    assert client._session.calls == 3  # initial attempt plus two retries
    assert len(no_sleep) == 2


async def test_retry_after_header_is_honoured(no_sleep):
    client = make_client([429, 200], headers=[{"Retry-After": "2"}, {}])
    await client._get("/x")
    assert no_sleep == [2.0]


def test_retry_after_is_clamped():
    assert _retry_delay(FakeResponse(429, {"Retry-After": "99"}), 0) == 5.0


def test_retry_after_http_date_falls_back_to_backoff():
    assert _retry_delay(FakeResponse(429, {"Retry-After": "Wed, 21 Oct 2026"}), 0) == 1.0


def test_backoff_grows_then_caps():
    assert _retry_delay(FakeResponse(500), 0) == 1.0
    assert _retry_delay(FakeResponse(500), 1) == 2.0
    assert _retry_delay(FakeResponse(500), 9) == 5.0


# --------------------------------------------------------------- rate limiter
async def test_full_bucket_does_not_wait():
    limiter = _RateLimiter(600)  # 10 tokens/sec, bucket starts full
    for _ in range(600):
        assert await limiter.acquire() == 0.0


async def test_exhausted_bucket_waits_instead_of_failing():
    limiter = _RateLimiter(6000)  # 100 tokens/sec — refills fast enough to test
    for _ in range(6000):
        await limiter.acquire()
    waited = await limiter.acquire()
    assert waited > 0, "acquire should have blocked once the bucket drained"


async def test_tokens_refill_over_time():
    limiter = _RateLimiter(6000)
    for _ in range(6000):
        await limiter.acquire()
    await asyncio.sleep(0.05)  # ~5 tokens back at 100/sec
    assert await limiter.acquire() == 0.0


async def test_limiter_spends_a_token_per_attempt_including_retries(no_sleep):
    client = make_client([429], rate_limit=6000)
    before = client._limiter._tokens
    with pytest.raises(RuntimeError):
        await client._get("/x")
    # Three HTTP attempts were made, so three tokens are gone.
    assert before - client._limiter._tokens == pytest.approx(3.0, abs=0.5)


# --------------------------------------------------------------- config
def test_env_int_reads_valid_values(monkeypatch):
    monkeypatch.setenv("HENRIK_RATE_LIMIT", "90")
    assert _env_int("HENRIK_RATE_LIMIT", 25) == 90


@pytest.mark.parametrize("raw", ["not-a-number", "0", "-5", ""])
def test_env_int_falls_back_on_junk(monkeypatch, raw):
    monkeypatch.setenv("HENRIK_RATE_LIMIT", raw)
    assert _env_int("HENRIK_RATE_LIMIT", 25) == 25


def test_env_int_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("HENRIK_RATE_LIMIT", raising=False)
    assert _env_int("HENRIK_RATE_LIMIT", 25) == 25


def test_client_reads_the_rate_limit_from_env(monkeypatch):
    monkeypatch.setenv("HENRIK_RATE_LIMIT", "90")
    assert henrik_mod.HenrikClient("key")._limiter.capacity == 90.0
