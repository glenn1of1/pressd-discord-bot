"""EmbedPaginator: the button view behind a multi-page /leaderboard."""

from __future__ import annotations

import discord
import pytest

from cogs.social import _ROWS_PER_PAGE
from utils.paginator import EmbedPaginator

AUTHOR, INTRUDER = 111, 222


class StubResponse:
    def __init__(self, fail=False):
        self.fail = fail
        self.edited = None
        self.sent = None

    async def edit_message(self, embed=None, view=None):
        self.edited = embed

    async def send_message(self, content, ephemeral=False):
        if self.fail:
            raise discord.HTTPException(
                type("R", (), {"status": 404, "reason": "Not Found"})(), "gone"
            )
        self.sent = content


class StubInteraction:
    def __init__(self, user_id=AUTHOR, fail=False):
        self.user = type("U", (), {"id": user_id})()
        self.response = StubResponse(fail)


class StubMessage:
    def __init__(self, raises=False):
        self.raises = raises
        self.view = None

    async def edit(self, view=None):
        if self.raises:
            raise discord.HTTPException(
                type("R", (), {"status": 404, "reason": "Not Found"})(), "gone"
            )
        self.view = view


def embeds(count):
    return [discord.Embed(title=f"page {i}") for i in range(count)]


def chunk(lines):
    """Mirrors the chunking in cogs/social.py's leaderboard."""
    return [
        lines[i : i + _ROWS_PER_PAGE] for i in range(0, len(lines), _ROWS_PER_PAGE)
    ]


# --------------------------------------------------------------- chunking
def test_chunking_preserves_every_row():
    lines = [f"{i}. player" for i in range(1, 38)]
    pages = chunk(lines)
    assert [len(p) for p in pages] == [15, 15, 7]
    assert sum(len(p) for p in pages) == len(lines)
    assert pages[0][0].startswith("1.")
    assert pages[-1][-1].startswith("37.")


def test_a_short_roster_is_one_page():
    assert len(chunk([f"{i}. p" for i in range(5)])) == 1


def test_exactly_one_full_page_does_not_spill():
    assert len(chunk([f"{i}. p" for i in range(_ROWS_PER_PAGE)])) == 1


def test_a_full_page_stays_under_the_embed_description_cap():
    # Worst case: max-length Riot IDs plus the longest rank string.
    row = f"99. **{'X' * 16}#{'Y' * 5}** — Ascendant 3 — 99 RR"
    page = "\n".join([row] * _ROWS_PER_PAGE)
    assert len(page) < 4096


# --------------------------------------------------------------- buttons
def test_first_page_disables_previous():
    view = EmbedPaginator(embeds(3), AUTHOR)
    assert view.prev_page.disabled
    assert not view.next_page.disabled
    assert view.page_label.label == "Page 1/3"


def test_single_page_disables_both():
    view = EmbedPaginator(embeds(1), AUTHOR)
    assert view.prev_page.disabled and view.next_page.disabled


async def test_paging_forward_swaps_the_embed():
    view = EmbedPaginator(embeds(3), AUTHOR)
    interaction = StubInteraction()
    await view.next_page.callback(interaction)

    assert view.index == 1
    assert view.page_label.label == "Page 2/3"
    assert interaction.response.edited is view.embeds[1]
    assert not view.prev_page.disabled and not view.next_page.disabled


async def test_last_page_disables_next():
    view = EmbedPaginator(embeds(3), AUTHOR)
    await view.next_page.callback(StubInteraction())
    await view.next_page.callback(StubInteraction())
    assert view.index == 2
    assert view.next_page.disabled


@pytest.mark.parametrize("presses,expected", [(5, 2), (1, 1)])
async def test_index_never_runs_past_the_end(presses, expected):
    view = EmbedPaginator(embeds(3), AUTHOR)
    for _ in range(presses):
        await view.next_page.callback(StubInteraction())
    assert view.index == expected


async def test_index_never_runs_below_zero():
    view = EmbedPaginator(embeds(3), AUTHOR)
    for _ in range(3):
        await view.prev_page.callback(StubInteraction())
    assert view.index == 0


# --------------------------------------------------------------- ownership
async def test_only_the_invoker_can_page():
    view = EmbedPaginator(embeds(2), AUTHOR)
    intruder = StubInteraction(user_id=INTRUDER)

    assert await view.interaction_check(intruder) is False
    assert "not your leaderboard" in intruder.response.sent
    assert await view.interaction_check(StubInteraction(AUTHOR)) is True


# --------------------------------------------------------------- timeout
async def test_timeout_disables_every_button():
    view = EmbedPaginator(embeds(2), AUTHOR)
    view.message = StubMessage()
    await view.on_timeout()

    assert all(child.disabled for child in view.children)
    assert view.message.view is view


async def test_timeout_survives_a_deleted_message():
    view = EmbedPaginator(embeds(2), AUTHOR)
    view.message = StubMessage(raises=True)
    await view.on_timeout()  # must not propagate out of a background task


async def test_timeout_without_a_message_is_safe():
    view = EmbedPaginator(embeds(2), AUTHOR)
    await view.on_timeout()
