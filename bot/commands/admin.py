"""Owner/admin commands: /botupdate, /status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.config import SEP
from bot.db import get_config, query_guild_channel_pairs
from bot.formatting import format_body
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

    @tree.command(name="botupdate", description="Broadcast a bot update changelog to all servers with an updates channel.")
    @app_commands.describe(
        version="Version tag for this update (e.g. v2.5)",
        title="Short title for the update (e.g. Smart Health Monitor & Welcome DMs)",
        changelog="Body text — use \\n for lines, --- for dividers, ##Header for sub-headers",
    )
    @app_commands.default_permissions(administrator=True)
    async def botupdate(
        interaction: discord.Interaction,
        version: str,
        title: str,
        changelog: str,
    ):
        if interaction.user.id != (await client.application_info()).owner.id:
            await interaction.response.send_message(
                "❌ Only the bot owner can broadcast updates.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        bulleted = format_body(changelog)
        now = datetime.now(timezone.utc)

        description = f"""【｡✦｡】 # BOT UPDATE 【｡✦｡】
{SEP}

##{version} — {title}

{bulleted}

{SEP}

✦ Run `/setup botcheck #channel` to enable the health indicator channel"""

        embed = discord.Embed(description=description, color=discord.Color.purple())
        if client.user:
            embed.set_thumbnail(url=client.user.display_avatar.url)
        embed.set_footer(text=f"Update Log • {now.strftime('%Y-%m-%d %H:%M UTC')}")

        rows = query_guild_channel_pairs("updates_channel_id")
        sent = 0
        failed = 0
        for _guild_id, channel_id in rows:
            try:
                ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                await ch.send(embed=embed)
                sent += 1
            except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
                failed += 1

        await interaction.followup.send(
            f"✅ Update **{version}** broadcast to **{sent}** server(s)"
            + (f" ({failed} failed)" if failed else ""),
            ephemeral=True,
        )
        await log_command(client, interaction, extra=f"Version: {version} | Sent: {sent} | Failed: {failed}")
