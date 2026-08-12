"""compute_stats aggregates raw v4 match JSON into the numbers every embed uses."""

from __future__ import annotations

from conftest import make_match

from utils.stats import _find_player, compute_stats

NAME, TAG = "TenZ", "NA1"


def test_empty_history_returns_zeroed_stats():
    result = compute_stats({"data": []}, NAME, TAG)
    assert result["games"] == 0
    assert result["kda"] == 0.0
    assert result["top_agent"] == "Unknown"
    assert result["name"] == NAME


def test_missing_data_key_is_treated_as_empty():
    assert compute_stats({}, NAME, TAG)["games"] == 0


def test_aggregates_across_matches():
    matches = {
        "data": [
            make_match(NAME, TAG, kills=20, deaths=10, assists=5, won=True),
            make_match(NAME, TAG, kills=10, deaths=10, assists=5, won=False),
        ]
    }
    result = compute_stats(matches, NAME, TAG)

    assert result["games"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["wr"] == 50.0
    # (30 kills + 10 assists) / 20 deaths
    assert result["kda"] == 2.0
    assert result["avg_kills"] == 15.0


def test_zero_deaths_does_not_divide_by_zero():
    matches = {"data": [make_match(NAME, TAG, kills=15, deaths=0, assists=3)]}
    result = compute_stats(matches, NAME, TAG)
    assert result["kda"] == 18.0  # divisor floored at 1, not a ZeroDivisionError


def test_matches_without_the_player_are_skipped():
    matches = {
        "data": [
            make_match("SomeoneElse", "EUW", kills=40),
            make_match(NAME, TAG, kills=10, deaths=10, assists=0),
        ]
    }
    result = compute_stats(matches, NAME, TAG)
    assert result["games"] == 1
    assert result["avg_kills"] == 10.0


def test_all_matches_missing_the_player_returns_empty():
    matches = {"data": [make_match("Ghost", "XXX")]}
    assert compute_stats(matches, NAME, TAG)["games"] == 0


def test_headshot_percentage_uses_total_shots():
    matches = {
        "data": [
            make_match(NAME, TAG, headshots=25, bodyshots=50, legshots=25),
        ]
    }
    assert compute_stats(matches, NAME, TAG)["hs"] == 25.0


def test_top_agent_is_the_most_played():
    matches = {
        "data": [
            make_match(NAME, TAG, agent="Reyna"),
            make_match(NAME, TAG, agent="Reyna"),
            make_match(NAME, TAG, agent="Jett"),
        ]
    }
    assert compute_stats(matches, NAME, TAG)["top_agent"] == "Reyna"


def test_find_player_is_case_insensitive():
    players = [{"name": "TenZ", "tag": "NA1"}]
    assert _find_player(players, "tenz", "na1") is not None
    assert _find_player(players, "TENZ", "NA1") is not None
    assert _find_player(players, "TenZ", "EUW") is None
