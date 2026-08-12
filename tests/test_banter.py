"""_pick_pool decides which roast pool a set of stats earns.

Order matters: the worst stat wins, so the checks are ordered and the first
failing threshold short-circuits.
"""

from __future__ import annotations

from banter.engine import _pick_pool, generate_banter
from banter.templates import TEMPLATES


def test_worst_stat_wins_kda_first():
    # Bad KDA and bad headshots — KDA is checked first, so it claims the roast.
    assert _pick_pool(kda=0.5, hs=5.0, wr=10.0, acs=50.0) == "trash_kda"


def test_each_threshold_in_priority_order():
    assert _pick_pool(kda=0.9, hs=50.0, wr=90.0, acs=300.0) == "trash_kda"
    assert _pick_pool(kda=2.0, hs=14.9, wr=90.0, acs=300.0) == "trash_hs"
    assert _pick_pool(kda=2.0, hs=30.0, wr=39.9, acs=300.0) == "trash_winrate"
    assert _pick_pool(kda=2.0, hs=30.0, wr=60.0, acs=149.0) == "trash_acs"


def test_boundaries_are_exclusive():
    # Exactly on a threshold is not "trash" — the checks use strict <.
    assert _pick_pool(kda=1.0, hs=15.0, wr=40.0, acs=150.0) != "trash_kda"
    assert _pick_pool(kda=1.0, hs=15.0, wr=40.0, acs=150.0) != "trash_hs"


def test_good_performance_needs_two_strong_stats():
    assert _pick_pool(kda=1.6, hs=26.0, wr=50.0, acs=200.0) == "good_performance"
    # Only one stat clears its bar, so this is merely decent.
    assert _pick_pool(kda=1.6, hs=20.0, wr=50.0, acs=200.0) == "decent"


def test_middling_stats_are_decent():
    assert _pick_pool(kda=1.2, hs=20.0, wr=50.0, acs=180.0) == "decent"


def test_every_pool_name_exists_in_templates():
    # A pool name with no templates would raise KeyError at roast time.
    pools = {
        "trash_kda", "trash_hs", "trash_winrate", "trash_acs",
        "good_performance", "decent",
    }
    assert pools <= set(TEMPLATES)
    assert all(TEMPLATES[pool] for pool in pools)


def test_generate_banter_fills_every_placeholder():
    """Every template in every pool must render with the kwargs the engine passes.

    The head-to-head pools use {name2}, which nothing supplied until it was
    given a default — picking one of those templates raised KeyError.
    """
    stats = {"name": "TenZ", "kda": 0.4, "hs": 9.0, "wr": 20.0, "acs": 90.0}
    for pool in TEMPLATES:
        for _ in range(20):  # templates are picked at random
            result = generate_banter(stats, pool=pool)
            assert "{" not in result and "}" not in result, (pool, result)


def test_opponent_name_reaches_head_to_head_templates():
    stats = {"name": "TenZ", "kda": 3.0, "hs": 30.0, "wr": 70.0, "acs": 300.0}
    rendered = {
        generate_banter(stats, pool="comparison_win", opponent="Aspas")
        for _ in range(50)
    }
    assert any("Aspas" in line for line in rendered)


def test_generate_banter_tolerates_missing_keys():
    assert generate_banter({}) != ""
