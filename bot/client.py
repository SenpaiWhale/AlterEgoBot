"""Bot client factory and lifecycle events."""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone

import discord
from discord import app_commands

from bot.config import BOT_VERSION, CHANGELOG_BODY, CHANGELOG_TITLE, OWNER_GUILD, SEP
from bot.db import get_config, get_meta, init_db, query_channel_ids, query_guild_ids, set_meta
from bot.formatting import format_body
from bot.helpers import post_status_to, set_bot_check_name


class AlterEgoClient(discord.Client):
    """Custom client that stores start_time and health status."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tree = app_commands.CommandTree(self)
        self.start_time: datetime | None = None
        self.current_bot_status: str = "🟢"
        self.bot_version: str = BOT_VERSION


def get_uptime_str(client: AlterEgoClient) -> str:
    """Return a human-readable uptime string.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client with a ``start_time`` attribute.

    Returns
    -------
    str
        Formatted uptime or ``"Unknown"``.
    """
    if not client.start_time:
        return "Unknown"
    delta = datetime.now(timezone.utc) - client.start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def create_client() -> AlterEgoClient:
    """Build and return the bot client with all events registered.

    Returns
    -------
    AlterEgoClient
        Ready-to-run client instance.
    """
    intents = discord.Intents.default()
    client = AlterEgoClient(intents=intents)

    @client.event
    async def on_ready():
        client.start_time = datetime.now(timezone.utc)
        init_db()
        print(f"Logged in as {client.user} (ID: {client.user.id})")

        await client.tree.sync()
        client.tree.copy_global_to(guild=OWNER_GUILD)
        synced = await client.tree.sync(guild=OWNER_GUILD)
        print(f"Global sync done. Instant sync to owner guild: {[c.name for c in synced]}")

        from bot.tasks import start_tasks
        start_tasks(client)

        await client.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"/help | {BOT_VERSION}",
            )
        )

        for gid in query_guild_ids("bot_check_channel_id"):
            await set_bot_check_name(client, gid, "🟢")

        now = datetime.now(timezone.utc)
        description = f"""【｡✦｡】 # BOT ONLINE 【｡✦｡】
{SEP}

✦ **{client.user.name}** is back online
✦ **Version:** {BOT_VERSION}
✦ **Ping:** {round(client.latency * 1000)}ms
✦ **Servers:** {len(client.guilds)}
✦ All systems operational

{SEP}

✦ 🟢 {now.strftime('%Y-%m-%d %H:%M UTC')}"""
        embed = discord.Embed(description=description, color=discord.Color.green())
        for channel_id in query_channel_ids("status_channel_id"):
            try:
                channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                await channel.send(embed=embed)
            except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
                pass

        await _broadcast_changelog_if_new(client)

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_graceful_shutdown(client)))
        print("Signal handlers registered.")

    @client.event
    async def on_guild_join(guild: discord.Guild):
        inviter = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == client.user.id:
                    inviter = entry.user
                    break
        except (discord.errors.Forbidden, discord.errors.HTTPException):
            pass
        if not inviter:
            try:
                inviter = guild.owner or await guild.fetch_member(guild.owner_id)
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass

        if inviter:
            intro = f"""【｡✦｡】 # WELCOME TO ALTEREGO 【｡✦｡】
{SEP}

✦ Hey **{inviter.display_name}**! Thanks for inviting me to **{guild.name}** 🎉
✦ I'm **{client.user.name}** — a styled bot for game nights, announcements, ads, events, and more
✦ All staff commands require the **Manage Server** permission

{SEP}

##Step 1 — Required Setup

✦ `/setup gamenight #channel` — where game night posts go
✦ `/setup announce #channel` — where announcements go
✦ `/setup ads #channel` — where ads get posted

{SEP}

##Step 2 — Optional Setup

✦ `/setup status #channel` — bot goes online/offline alerts here
✦ `/setup modlog #channel` — logs every command used
✦ `/setup botcheck #channel` — channel name changes to 🟢 online / 🔴 offline / 🟡 error
✦ `/setup updates #channel` — receives bot update notifications
✦ `/setup view` — shows your full current config

{SEP}

##Step 3 — Webhooks (Optional)

✦ `/webhook add <name> <url>` — register a Discord webhook
✦ `/webhook list` — view all registered webhooks
✦ `/webhook remove <name>` — delete a webhook
✦ Once registered, use the webhook name in `/postad` or `/announce`

{SEP}

##Commands at a Glance

✦ `/gamenight` — post a hype message with @everyone
✦ `/gameplan` — create a game vote poll (up to 4 options)
✦ `/gamecheck` — availability poll with days of the week
✦ `/postad` — post a styled ad embed with @here + NSFW filter
✦ `/announce` — post a styled announcement to any channel
✦ `/event` — create a Discord scheduled event
✦ `/cancel` — cancel a scheduled event by name
✦ `/status` — post live bot stats
✦ `/help` — full command guide sent to your DMs

{SEP}

##Formatting (for /postad and /announce)

✦ `\\n` — new bullet line
✦ `\\n\\n` — blank gap between sections
✦ `---` — styled section divider
✦ `##Title` — styled sub-header
✦ `[label](url)` — inline clickable hyperlink
✦ Lines starting with an emoji are kept as-is (e.g. 🏆 Top 10)
✦ `/postad` supports **body2** and **body3** for longer ads

{SEP}

✦ Run `/setup view` anytime to check your config
✦ Need help? Use `/help` for the full guide"""

            dm_embed = discord.Embed(description=intro, color=discord.Color.purple())
            dm_embed.set_thumbnail(url=client.user.display_avatar.url)
            try:
                await inviter.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        channel = guild.system_channel
        if channel:
            short = f"""【｡✦｡】 # THANKS FOR INVITING ME! 【｡✦｡】
{SEP}

✦ I'm **{client.user.name}** — a styled bot for game nights, announcements, and ads
✦ The person who invited me has been sent a full setup guide in their DMs
✦ Run `/setup view` to see the current config, or `/help` for all commands

{SEP}

✦ All commands require **Manage Server** permission"""
            short_embed = discord.Embed(description=short, color=discord.Color.purple())
            try:
                await channel.send(embed=short_embed)
            except (discord.errors.Forbidden, discord.errors.HTTPException):
                pass

    @client.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        cmd_name = f"/{interaction.command.name}" if interaction.command else "/unknown"
        print(f"Command error in {cmd_name} by {interaction.user}: {error}")

        try:
            await set_bot_check_name(client, interaction.guild_id or 0, "🟡")
            config = get_config(interaction.guild_id or 0)
            channel_id = config.get("status_channel_id")
            if channel_id:
                description = f"""【｡✦｡】 # BOT ERROR 【｡✦｡】
{SEP}

✦ **Command:** {cmd_name}
✦ **Triggered by:** {interaction.user.mention}
✦ **Error:** {type(error).__name__}
✦ **Uptime:** {get_uptime_str(client)}

{SEP}

✦ 🟡 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"""
                embed = discord.Embed(description=description, color=discord.Color.yellow())
                ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                await ch.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
            pass

        msg = f"⚠️ Something went wrong with `{cmd_name}`. The issue has been logged."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except (discord.errors.HTTPException, discord.errors.InteractionResponded):
            pass

    return client


async def _broadcast_changelog_if_new(client: AlterEgoClient):
    """Post the changelog to updates channels if this is a new version."""
    last_version = get_meta("last_changelog_version")
    if last_version == BOT_VERSION:
        return

    if not CHANGELOG_BODY:
        set_meta("last_changelog_version", BOT_VERSION)
        return

    bulleted = format_body(CHANGELOG_BODY)
    now = datetime.now(timezone.utc)

    description = f"""{SEP}

🚀 **{BOT_VERSION}** — **{CHANGELOG_TITLE}**

{bulleted}

{SEP}

💡 Run `/setup botcheck #channel` to enable the health indicator
💡 Run `/help` for the full command guide"""

    embed = discord.Embed(description=description, color=0x9B59B6)
    embed.set_author(name="【｡✦｡】 # NEW UPDATE DROPPED 【｡✦｡】")
    if client.user:
        embed.set_thumbnail(url=client.user.display_avatar.url)
    embed.set_footer(
        text=f"AlterEgo {BOT_VERSION} • {now.strftime('%Y-%m-%d %H:%M UTC')}",
        icon_url=client.user.display_avatar.url if client.user else None,
    )

    sent = 0
    for channel_id in query_channel_ids("updates_channel_id"):
        try:
            ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await ch.send(embed=embed)
            sent += 1
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
            pass

    set_meta("last_changelog_version", BOT_VERSION)
    print(f"Changelog {BOT_VERSION} broadcast to {sent} server(s)")


async def _graceful_shutdown(client: AlterEgoClient):
    """Rename bot-check channels to red, post shutdown alert, then close."""
    print("Shutting down gracefully...")
    for gid in query_guild_ids("bot_check_channel_id"):
        await set_bot_check_name(client, gid, "🔴")

    now = datetime.now(timezone.utc)
    description = f"""【｡✦｡】 # BOT OFFLINE 【｡✦｡】
{SEP}

✦ **{client.user.name if client.user else 'Bot'}** is going offline
✦ **Uptime at shutdown:** {get_uptime_str(client)}
✦ Bot was restarted or stopped — back soon

{SEP}

✦ 🔴 {now.strftime('%Y-%m-%d %H:%M UTC')}"""
    embed = discord.Embed(description=description, color=discord.Color.red())
    for channel_id in query_channel_ids("status_channel_id"):
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
            pass
    await client.close()
