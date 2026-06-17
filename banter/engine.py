from __future__ import annotations

import logging
import os
import random

from banter.templates import TEMPLATES

log = logging.getLogger(__name__)


def generate_banter(stats: dict, pool: str | None = None) -> str:
    """Return a formatted banter string for the given stats dict.

    Args:
        stats: Must contain keys: name (str), kda (float), hs (float),
               wr (float), acs (float).
        pool:  Force a specific template pool (e.g. "comparison_win").
               If None, the pool is selected automatically from stat thresholds.
    """
    name = stats.get("name", "you")
    kda = float(stats.get("kda", 0.0))
    hs = float(stats.get("hs", 0.0))
    wr = float(stats.get("wr", 0.0))
    acs = float(stats.get("acs", 0.0))

    if os.getenv("BANTER_MODE", "template").lower() == "ai":
        log.warning("BANTER_MODE=ai is not yet implemented — falling back to template.")

    selected_pool = pool if pool else _pick_pool(kda, hs, wr, acs)
    template = random.choice(TEMPLATES[selected_pool])

    return template.format(
        name=name,
        kda=f"{kda:.2f}",
        hs=f"{hs:.1f}",
        wr=f"{wr:.0f}",
        loss_wr=f"{100 - wr:.0f}",
        acs=f"{acs:.0f}",
    )


def _pick_pool(kda: float, hs: float, wr: float, acs: float) -> str:
    """Select the roast pool based on PRD Section 8.2 thresholds.

    Priority: worst stat first. First threshold that fails wins.
    """
    if kda < 1.0:
        return "trash_kda"
    if hs < 15.0:
        return "trash_hs"
    if wr < 40.0:
        return "trash_winrate"
    if acs < 150.0:
        return "trash_acs"

    good_count = sum([kda > 1.5, hs > 25.0, wr > 55.0, acs > 220.0])
    if good_count >= 2:
        return "good_performance"

    return "decent"
