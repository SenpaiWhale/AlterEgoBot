"""Shared helper utilities used across commands and events."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from bot.config import SEP
from bot.db import get_config


def is_staff(interaction: discord.Interaction) -> bool:
    """Return True if the member has Manage Server or Administrator.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction context.

    Returns
    -------
    bool
        Whether the user qualifies as staff.
    """
    if not isinstance(interaction.user, discord.Member):
        return False
    p = interaction.user.guild_permissions
    return p.manage_guild or p.administrator


async def log_command(
    client: discord.Client,
    interaction: discord.Interaction,
    extra: str | None = None,
):
    """Log command usage to the guild's configured modlog channel.

    Parameters
    ----------
    client : discord.Client
        The bot client instance.
    interaction : discord.Interaction
        The slash-command interaction.
    extra : str or None
        Optional additional detail string.
    """
    try:
        config = get_config(interaction.guild_id or 0)
        channel_id = config.get("modlog_channel_id")
        if not channel_id:
            return
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        cmd = f"/{interaction.command.name}" if interaction.command else "/unknown"
        lines = [
            f"**Command:** {cmd}",
            f"**Used by:** {interaction.user.mention} (`{interaction.user}`)",
            f"**User ID:** `{interaction.user.id}`",
            f"**Channel:** <#{interaction.channel_id}>",
        ]
        if extra:
            lines.append(f"**Details:** {extra}")
        embed = discord.Embed(
            description="\n".join(f"✦ {l}" for l in lines),
            color=discord.Color.purple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Command Log")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Modlog error: {e}")


async def set_bot_check_name(
    client: discord.Client,
    guild_id: int,
    circle: str,
):
    """Rename the bot-check channel indicator for *guild_id*.

    Parameters
    ----------
    client : discord.Client
        The bot client instance.
    guild_id : int
        Discord guild snowflake.
    circle : str
        Emoji circle (🟢, 🔴, 🟡).
    """
    try:
        config = get_config(guild_id)
        channel_id = config.get("bot_check_channel_id")
        if not channel_id:
            return
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        base = channel.name.split("︱", 1)[-1]
        new_name = f"{circle}︱{base}"
        if channel.name != new_name:
            await channel.edit(name=new_name)
            print(f"Bot-check channel renamed → {new_name}")
    except Exception as e:
        print(f"Bot-check rename failed: {e}")


async def post_status_to(client: discord.Client, channel_id: int):
    """Build and post the status embed to a specific channel.

    Parameters
    ----------
    client : discord.Client
        The bot client instance.
    channel_id : int
        Target channel snowflake.
    """
    from bot.client import get_uptime_str

    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    ping = round(client.latency * 1000)
    guild_count = len(client.guilds)
    command_count = len(client.tree.get_commands())
    now = datetime.now(timezone.utc)
    description = f"""【｡✦｡】 # BOT STATUS 【｡✦｡】
{SEP}

✦ **Bot:** {client.user.name}
✦ **ID:** `{client.user.id}`
✦ **Version:** {client.bot_version}
✦ **Ping:** {ping}ms
✦ **Uptime:** {get_uptime_str(client)}
✦ **Servers:** {guild_count}
✦ **Commands:** {command_count}

{SEP}

✦ All systems operational 🟢"""
    embed = discord.Embed(description=description, color=discord.Color.purple())
    embed.set_footer(text=f"Status Report • {now.strftime('%Y-%m-%d %H:%M UTC')}")
    await channel.send(embed=embed)
