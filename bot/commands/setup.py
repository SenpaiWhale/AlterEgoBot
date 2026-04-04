"""Server setup commands (/setup group)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.config import SEP
from bot.db import get_config, set_config
from bot.helpers import set_bot_check_name

if TYPE_CHECKING:
    from bot.client import AlterEgoClient

setup_group = app_commands.Group(
    name="setup",
    description="Configure the bot for this server — requires Manage Server permission",
)


@setup_group.command(name="gamenight", description="Set the channel for game night announcements")
@app_commands.describe(channel="Channel to post game night hype messages and polls")
@app_commands.default_permissions(manage_guild=True)
async def setup_gamenight(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, gamenight_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Game night channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="announce", description="Set the default channel for announcements")
@app_commands.describe(channel="Channel for /announce posts")
@app_commands.default_permissions(manage_guild=True)
async def setup_announce(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, announce_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Announcement channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="ads", description="Set the channel for advertisement posts")
@app_commands.describe(channel="Channel where /postad embeds will be posted")
@app_commands.default_permissions(manage_guild=True)
async def setup_ads(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, ad_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Ad channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="status", description="Set the channel for bot status updates (optional)")
@app_commands.describe(channel="Channel for online/offline/error alerts and /status posts")
@app_commands.default_permissions(manage_guild=True)
async def setup_status(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, status_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Status channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="modlog", description="Set the channel for command usage logs (optional)")
@app_commands.describe(channel="Channel where command logs are recorded")
@app_commands.default_permissions(manage_guild=True)
async def setup_modlog(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, modlog_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Modlog channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="botcheck", description="Set a channel whose name reflects bot status (🟢 online / 🔴 offline / 🟡 error)")
@app_commands.describe(channel="Channel to rename based on bot status")
@app_commands.default_permissions(manage_guild=True)
async def setup_botcheck(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, bot_check_channel_id=channel.id)
    client: AlterEgoClient = interaction.client  # type: ignore[assignment]
    await set_bot_check_name(client, interaction.guild_id, "🟢")
    await interaction.response.send_message(
        f"✅ Bot-check channel set to {channel.mention} — renamed to 🟢 now", ephemeral=True
    )


@setup_group.command(name="updates", description="Set a channel where bot update notifications are posted (staff/owner only)")
@app_commands.describe(channel="Channel to receive bot update announcements")
@app_commands.default_permissions(manage_guild=True)
async def setup_updates(interaction: discord.Interaction, channel: discord.TextChannel):
    set_config(interaction.guild_id, updates_channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Updates channel set to {channel.mention}", ephemeral=True
    )


@setup_group.command(name="view", description="View the current bot configuration for this server")
@app_commands.default_permissions(manage_guild=True)
async def setup_view(interaction: discord.Interaction):
    config = get_config(interaction.guild_id)

    def fmt(channel_id):
        return f"<#{channel_id}>" if channel_id else "❌ Not set"

    description = f"""【｡✦｡】 # BOT CONFIGURATION 【｡✦｡】
{SEP}

✦ **Game Night Channel:** {fmt(config.get("gamenight_channel_id"))}
✦ **Announce Channel:** {fmt(config.get("announce_channel_id"))}
✦ **Ad Channel:** {fmt(config.get("ad_channel_id"))}
✦ **Status Channel:** {fmt(config.get("status_channel_id"))}
✦ **Modlog Channel:** {fmt(config.get("modlog_channel_id"))}
✦ **Bot-Check Channel:** {fmt(config.get("bot_check_channel_id"))}
✦ **Updates Channel:** {fmt(config.get("updates_channel_id"))}

{SEP}

✦ Use `/setup <setting> #channel` to change any of these"""
    embed = discord.Embed(description=description, color=discord.Color.purple())
    await interaction.response.send_message(embed=embed, ephemeral=True)


def register(client: AlterEgoClient):
    """Attach the setup command group to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    client.tree.add_command(setup_group)
