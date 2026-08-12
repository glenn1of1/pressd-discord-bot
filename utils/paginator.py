from __future__ import annotations

import discord

PAGINATOR_TIMEOUT = 180.0


class EmbedPaginator(discord.ui.View):
    """Button-driven pager over a pre-built list of embeds.

    The embeds are rendered up front by the caller, so paging never re-queries
    the database or the HenrikDev API — the buttons only swap which embed is
    displayed. Paging is restricted to the user who invoked the command so two
    people running /leaderboard at once don't fight over one message.
    """

    def __init__(
        self,
        embeds: list[discord.Embed],
        author_id: int,
        timeout: float = PAGINATOR_TIMEOUT,
    ) -> None:
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.index = 0
        self.message: discord.Message | None = None
        self._refresh()

    def _refresh(self) -> None:
        self.prev_page.disabled = self.index == 0
        self.next_page.disabled = self.index >= len(self.embeds) - 1
        self.page_label.label = f"Page {self.index + 1}/{len(self.embeds)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "That's not your leaderboard. Run your own `/leaderboard`.",
                ephemeral=True,
            )
            return False
        return True

    async def _show(self, interaction: discord.Interaction) -> None:
        self._refresh()
        await interaction.response.edit_message(
            embed=self.embeds[self.index], view=self
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.index = max(0, self.index - 1)
        await self._show(interaction)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Permanently disabled — it exists only to display the page counter.
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.index = min(len(self.embeds) - 1, self.index + 1)
        await self._show(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                # Message deleted or the token expired — nothing to clean up.
                pass
