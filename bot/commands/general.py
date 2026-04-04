"""General commands: /help."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.config import SEP
from bot.helpers import log_command

if TYPE_CHECKING:
    from bot.client import AlterEgoClient


def _build_help_pages() -> list[discord.Embed]:
    """Build the paginated help embed list."""
    pages = []

    p0 = discord.Embed(
        description=f"""【｡✦｡】 # HELP — SETUP 【｡✦｡】
{SEP}

⚙️ **/setup gamenight**
✦ Set the channel for game night announcements and polls
✦ `Usage:` /setup gamenight channel:

⚙️ **/setup announce**
✦ Set the default channel for /announce posts
✦ `Usage:` /setup announce channel:

⚙️ **/setup ads**
✦ Set the channel where /postad embeds are posted
✦ `Usage:` /setup ads channel:

⚙️ **/setup status**
✦ Set the channel for bot online/offline/error alerts (optional)
✦ `Usage:` /setup status channel:

⚙️ **/setup modlog**
✦ Set the channel for command usage logs (optional)
✦ `Usage:` /setup modlog channel:

⚙️ **/setup view**
✦ Show the current bot configuration for this server
✦ `Usage:` /setup view

{SEP}

✦ All commands require **Manage Server** permission
✦ Page 1 of 4 — use the buttons below to navigate ✦""",
        color=discord.Color.purple(),
    )
    pages.append(p0)

    p1 = discord.Embed(
        description=f"""【｡✦｡】 # HELP — GAME NIGHT 【｡✦｡】
{SEP}

🎮 **/gamenight**
✦ Fires a random hype announcement in the game night channel
✦ Pings **@everyone** automatically
✦ `Usage:` /gamenight

{SEP}

🗳️ **/gameplan**
✦ Starts a game vote so the squad can pick what to play
✦ Requires 2 options minimum — 3rd and 4th are optional
✦ Pings **@everyone** automatically
✦ `Usage:` /gameplan game1: game2: game3: game4:
✦ `Example:` /gameplan game1:Valorant game2:Fortnite game3:Minecraft

{SEP}

📋 **/gamecheck**
✦ Posts a Yes/No availability poll + a day of the week vote
✦ Pings **@everyone** automatically
✦ `Usage:` /gamecheck

{SEP}

✦ Page 2 of 4 — use the buttons below to navigate ✦""",
        color=discord.Color.purple(),
    )
    pages.append(p1)

    p2 = discord.Embed(
        description=f"""【｡✦｡】 # HELP — CONTENT 【｡✦｡】
{SEP}

📢 **/postad**
✦ Posts a styled ad embed to the configured ad channel
✦ Title + description required — image and link are optional
✦ NSFW content is automatically blocked
✦ `\\n` = new bullet line — `\\n\\n` = blank gap — `---` = section divider
✦ `##Title` = styled sub-header — `[label](url)` = inline hyperlink
✦ `Usage:` /postad title: description: image_url: link:
✦ `Example:` /postad title:Commissions description:##Prices\\n$5 sketches---##Contact\\nDM me!

{SEP}

📣 **/announce**
✦ Posts a styled announcement embed to any channel you pick
✦ Same formatting options as /postad (\\n, ---, ##, [label](url))
✦ `Usage:` /announce channel: title: message:
✦ `Example:` /announce channel:#general title:Update message:Server event tonight!\\nBe there

{SEP}

✦ Page 3 of 4 — use the buttons below to navigate ✦""",
        color=discord.Color.purple(),
    )
    pages.append(p2)

    p3 = discord.Embed(
        description=f"""【｡✦｡】 # HELP — EVENTS & UTILITIES 【｡✦｡】
{SEP}

🗓️ **/event**
✦ Creates a native Discord scheduled event in the server
✦ Date: `MM/DD` or `MM/DD/YYYY` — Time: `11:00PM` or `23:00` (UTC)
✦ End time defaults to 1 hour after start if not provided
✦ Location defaults to `This Server` if not provided
✦ `Usage:` /event name: description: date: start_time: end_time: location:
✦ `Example:` /event name:Giveaway description:Win a gift card! date:04/10 start_time:8:00PM

{SEP}

🚫 **/cancel**
✦ Cancels an active scheduled event by name
✦ Partial name match — no need for the exact full title
✦ `Usage:` /cancel name:
✦ `Example:` /cancel name:Giveaway

{SEP}

📊 **/status**
✦ Posts live bot stats to the configured status channel
✦ Shows version, ping, uptime, servers, and total commands
✦ Also auto-posts every **Sunday at 12:00 PM UTC**
✦ `Usage:` /status

{SEP}

❓ **/help**
✦ Sends this menu to your DMs (or shows it here if DMs are off)
✦ `Usage:` /help

{SEP}

✦ Page 4 of 4 — use the buttons below to navigate ✦""",
        color=discord.Color.purple(),
    )
    pages.append(p3)

    return pages


class _HelpView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current == len(self.pages) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def register(client: AlterEgoClient):
    """Attach the /help command to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    tree = client.tree

    @tree.command(name="help", description="Show all available bot commands and how to use them.")
    async def help_command(interaction: discord.Interaction):
        await log_command(client, interaction)
        pages = _build_help_pages()
        view = _HelpView(pages)
        try:
            await interaction.user.send(embed=pages[0], view=view)
            await interaction.response.send_message("📬 Check your DMs!", ephemeral=True)
        except discord.errors.Forbidden:
            await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
