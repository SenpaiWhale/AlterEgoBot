"""Periodic background tasks: health monitoring and weekly status."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks

from bot.config import SEP
from bot.db import get_config, query_channel_ids, query_guild_channel_pairs
from bot.helpers import post_status_to, set_bot_check_name

if TYPE_CHECKING:
    from bot.client import AlterEgoClient

_health_check: tasks.Loop | None = None
_weekly_status: tasks.Loop | None = None


def start_tasks(client: AlterEgoClient):
    """Register and start background tasks if not already running.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    global _health_check, _weekly_status

    if _health_check is None:
        @tasks.loop(minutes=5)
        async def health_check():
            try:
                latency_ms = client.latency * 1000
                if latency_ms < 500:
                    new_status = "🟢"
                elif latency_ms < 1000:
                    new_status = "🟡"
                else:
                    new_status = "🔴"
            except (AttributeError, OverflowError):
                new_status = "🔴"

            if new_status == client.current_bot_status:
                return

            old_status = client.current_bot_status
            client.current_bot_status = new_status

            rows = query_guild_channel_pairs("bot_check_channel_id", "status_channel_id")
            status_labels = {"🟢": "ONLINE", "🟡": "DEGRADED", "🔴": "OFFLINE"}
            status_colors = {
                "🟢": discord.Color.green(),
                "🟡": discord.Color.yellow(),
                "🔴": discord.Color.red(),
            }
            now = datetime.now(timezone.utc)

            for guild_id, bot_check_id, status_id in rows:
                if bot_check_id:
                    await set_bot_check_name(client, guild_id, new_status)

                if status_id:
                    try:
                        from bot.client import get_uptime_str

                        latency_ms = round(client.latency * 1000)
                        description = f"""【｡✦｡】 # STATUS CHANGE 【｡✦｡】
{SEP}

✦ **Previous:** {old_status} {status_labels.get(old_status, old_status)}
✦ **Current:** {new_status} {status_labels.get(new_status, new_status)}
✦ **Latency:** {latency_ms}ms
✦ **Uptime:** {get_uptime_str(client)}

{SEP}

✦ {"All systems operational" if new_status == "🟢" else "Performance degraded — monitoring" if new_status == "🟡" else "Bot is experiencing issues"} {new_status}"""
                        embed = discord.Embed(
                            description=description,
                            color=status_colors[new_status],
                        )
                        embed.set_footer(
                            text=f"Health Monitor • {now.strftime('%Y-%m-%d %H:%M UTC')}"
                        )
                        ch = client.get_channel(status_id) or await client.fetch_channel(status_id)
                        await ch.send(embed=embed)
                    except Exception as e:
                        print(f"Health alert error for guild {guild_id}: {e}")

        @health_check.before_loop
        async def before_health_check():
            await client.wait_until_ready()

        _health_check = health_check

    if _weekly_status is None:
        @tasks.loop(time=time(hour=12, minute=0, tzinfo=timezone.utc))
        async def weekly_status():
            if datetime.now(timezone.utc).weekday() != 6:
                return
            for channel_id in query_channel_ids("status_channel_id"):
                try:
                    await post_status_to(client, channel_id)
                except (
                    discord.errors.Forbidden,
                    discord.errors.NotFound,
                    discord.errors.HTTPException,
                ) as e:
                    print(f"Weekly status error for channel {channel_id}: {e}")

        _weekly_status = weekly_status

    if not _health_check.is_running():
        _health_check.start()
    if not _weekly_status.is_running():
        _weekly_status.start()
