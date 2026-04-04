"""Admin commands: /status."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from bot.db import get_config
from bot.helpers import is_staff, log_command, post_status_to

if TYPE_CHECKING:
    from bot.client import AlterEgoClient


def register(client: AlterEgoClient):
    """Attach admin commands to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    tree = client.tree

    @tree.command(name="status", description="Post live bot stats to the status channel.")
    async def status(interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )
            return
        await log_command(client, interaction)
        await interaction.response.defer(ephemeral=True)

        config = get_config(interaction.guild_id)
        channel_id = config.get("status_channel_id")
        if not channel_id:
            await interaction.followup.send(
                "❌ No status channel configured. Run `/setup status #channel` first.", ephemeral=True
            )
            return
        try:
            await post_status_to(client, channel_id)
            await interaction.followup.send("✅ Status posted!", ephemeral=True)
        except (discord.errors.Forbidden, discord.errors.NotFound):
            await interaction.followup.send(
                "❌ Couldn't post — check I have **Send Messages** and **Embed Links** in the status channel.",
                ephemeral=True,
            )
