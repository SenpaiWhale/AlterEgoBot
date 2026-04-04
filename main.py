import discord
from discord import app_commands
from discord.ext import tasks
import aiohttp
import random
import os
import signal
import asyncio
import sqlite3
import re
from datetime import datetime, timezone, time, timedelta
from better_profanity import profanity

profanity.load_censor_words()

# ── NSFW Filter ───────────────────────────────────────────────────────────────

NSFW_BLOCKLIST = {
    "pornhub", "xvideos", "xhamster", "xnxx", "redtube", "youporn", "tube8",
    "spankbang", "porntrex", "beeg", "tnaflix", "drtuber", "slutload",
    "motherless", "hentaihaven", "nhentai", "rule34", "gelbooru", "danbooru",
    "onlyfans", "fansly", "manyvids", "clips4sale", "chaturbate", "cam4",
    "bongacams", "stripchat", "myfreecams", "livejasmin", "camsoda",
    "porn", "porno", "pornography", "hentai", "xxx", "nsfw", "nude", "nudes",
    "naked", "nudity", "explicit", "adult content", "18+",
    "sex tape", "sextape", "sex video", "sexvideo", "lewd", "r34",
    "rule 34", "rule34", "cum", "cumshot", "creampie", "gangbang",
    "blowjob", "handjob", "rimjob", "footjob", "titjob", "anal",
    "vagina", "penis", "dick pic", "dickpic", "cock", "pussy", "boobs",
    "tits", "butthole", "anus", "dildo", "vibrator", "masturbat",
    "orgasm", "erotic", "erotica", "fetish", "bdsm", "kink", "kinky",
    "horny", "aroused", "seductive", "stripclub", "strip club",
    "escort", "prostitut", "hooker", "whore", "slut", "thot",
}


def is_nsfw(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    clean = re.sub(r'[-\d]', ' ', lower)
    if profanity.contains_profanity(clean):
        return True
    for term in NSFW_BLOCKLIST:
        if term in lower:
            return True
    return False


# ── Configuration ─────────────────────────────────────────────────────────────

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
BOT_VERSION = "v2.5"  # bump this with every update post
CURRENT_BOT_STATUS = "🟢"  # tracks last known status to avoid spam renames
SEP = "· · ───────────── ꒰ঌ·✦·໒꒱ ───────────── · ·"
DB_PATH = os.path.join(os.path.dirname(__file__), "config.db")

# Guild used for instant command sync during development (ALTER EGO)
OWNER_GUILD = discord.Object(id=1471048262285918210)


# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    """Create tables and run migrations for the guild configuration database."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id             INTEGER PRIMARY KEY,
                gamenight_channel_id INTEGER,
                announce_channel_id  INTEGER,
                ad_channel_id        INTEGER,
                status_channel_id    INTEGER,
                modlog_channel_id    INTEGER,
                bot_check_channel_id INTEGER
            )
        """)
        # Migrate existing DBs that don't have the new column yet
        try:
            c.execute("ALTER TABLE guild_config ADD COLUMN bot_check_channel_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE guild_config ADD COLUMN updates_channel_id INTEGER")
        except sqlite3.OperationalError:
            pass
        c.execute("""
            CREATE TABLE IF NOT EXISTS guild_webhooks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name     TEXT    NOT NULL,
                url      TEXT    NOT NULL,
                UNIQUE(guild_id, name)
            )
        """)
        conn.commit()


def get_config(guild_id: int) -> dict:
    """Retrieve the guild configuration row as a dict.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.

    Returns
    -------
    dict
        Mapping of config column names to values, or empty dict if not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
    if not row:
        return {}
    keys = ["guild_id", "gamenight_channel_id", "announce_channel_id",
            "ad_channel_id", "status_channel_id", "modlog_channel_id",
            "bot_check_channel_id", "updates_channel_id"]
    return dict(zip(keys, row))


_ALLOWED_CONFIG_COLUMNS = frozenset({
    "gamenight_channel_id",
    "announce_channel_id",
    "ad_channel_id",
    "status_channel_id",
    "modlog_channel_id",
    "bot_check_channel_id",
    "updates_channel_id",
})


def set_config(guild_id: int, **kwargs):
    """Upsert guild configuration values.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    **kwargs
        Column-value pairs. Column names are validated against an allowlist.

    Raises
    ------
    ValueError
        If an unknown column name is supplied.
    """
    bad_keys = set(kwargs) - _ALLOWED_CONFIG_COLUMNS
    if bad_keys:
        raise ValueError(f"Invalid config keys: {bad_keys}")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        for key, value in kwargs.items():
            c.execute(f"UPDATE guild_config SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        conn.commit()


# ── Webhook DB Helpers ────────────────────────────────────────────────────────

def webhook_add(guild_id: int, name: str, url: str) -> bool:
    """Register a new webhook. Returns False if the name already exists.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Short label for the webhook.
    url : str
        Discord webhook URL.

    Returns
    -------
    bool
        True if inserted, False if name already exists.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO guild_webhooks (guild_id, name, url) VALUES (?, ?, ?)",
                      (guild_id, name.lower(), url))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def webhook_update(guild_id: int, name: str, url: str) -> bool:
    """Update an existing webhook URL by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to update.
    url : str
        New Discord webhook URL.

    Returns
    -------
    bool
        True if a row was updated, False if the name was not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE guild_webhooks SET url = ? WHERE guild_id = ? AND name = ?",
                  (url, guild_id, name.lower()))
        updated = c.rowcount > 0
        conn.commit()
    return updated


def webhook_remove(guild_id: int, name: str) -> bool:
    """Delete a webhook registration by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to remove.

    Returns
    -------
    bool
        True if a row was deleted, False if the name was not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM guild_webhooks WHERE guild_id = ? AND name = ?",
                  (guild_id, name.lower()))
        removed = c.rowcount > 0
        conn.commit()
    return removed


def webhook_list(guild_id: int) -> list[dict]:
    """List all registered webhooks for a guild.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.

    Returns
    -------
    list[dict]
        Each entry has ``name`` and ``url`` keys, sorted alphabetically.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT name, url FROM guild_webhooks WHERE guild_id = ? ORDER BY name",
                  (guild_id,))
        rows = c.fetchall()
    return [{"name": r[0], "url": r[1]} for r in rows]


def webhook_get(guild_id: int, name: str) -> str | None:
    """Fetch a single webhook URL by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to look up.

    Returns
    -------
    str or None
        The webhook URL, or None if not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT url FROM guild_webhooks WHERE guild_id = ? AND name = ?",
                  (guild_id, name.lower()))
        row = c.fetchone()
    return row[0] if row else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_staff(interaction: discord.Interaction) -> bool:
    """True if the user has Manage Server or Administrator in this guild."""
    if not isinstance(interaction.user, discord.Member):
        return False
    p = interaction.user.guild_permissions
    return p.manage_guild or p.administrator


def format_body(text: str) -> str:
    """Format message body.
    - \\n        → new line / new bullet point
    - \\n\\n     → blank line gap
    - ---       → styled section breaker (SEP divider)
    - ##Title   → styled sub-header: 【｡✦｡】 # TITLE 【｡✦｡】
    - [label](url) → inline clickable hyperlink (Discord markdown)
    - all other non-empty lines get auto-bulleted with ✦
    """
    text = text.replace("\\n", "\n")
    sections = text.split("---")
    formatted_sections = []
    for section in sections:
        lines = []
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("##"):
                header_text = stripped[2:].strip().upper()
                lines.append(f"【｡✦｡】 # {header_text} 【｡✦｡】")
            elif stripped and not stripped.startswith("✦"):
                lines.append(f"✦ {stripped}")
            elif stripped:
                lines.append(stripped)
            else:
                if lines and lines[-1] != "":
                    lines.append("")
        if lines:
            formatted_sections.append("\n".join(lines))
    return f"\n\n{SEP}\n\n".join(formatted_sections)


def get_uptime_str() -> str:
    if not start_time:
        return "Unknown"
    delta = datetime.now(timezone.utc) - start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


async def set_bot_check_name(guild_id: int, circle: str):
    """Rename the bot-check channel to 🟢/🔴/🟡 for the given guild."""
    try:
        config = get_config(guild_id)
        channel_id = config.get("bot_check_channel_id")
        if not channel_id:
            return
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        base = channel.name.split("︱", 1)[-1]  # strip existing circle prefix
        new_name = f"{circle}︱{base}"
        if channel.name != new_name:
            await channel.edit(name=new_name)
            print(f"Bot-check channel renamed → {new_name}")
    except Exception as e:
        print(f"Bot-check rename failed: {e}")


async def log_command(interaction: discord.Interaction, extra: str = None):
    """Log command usage to the guild's configured modlog channel (if set)."""
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


async def post_status_to(channel_id: int):
    """Build and post the status embed to a specific channel."""
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    ping = round(client.latency * 1000)
    guild_count = len(client.guilds)
    command_count = len(tree.get_commands())
    now = datetime.now(timezone.utc)
    description = f"""【｡✦｡】 # BOT STATUS 【｡✦｡】
{SEP}

✦ **Bot:** {client.user.name}
✦ **ID:** `{client.user.id}`
✦ **Version:** {BOT_VERSION}
✦ **Ping:** {ping}ms
✦ **Uptime:** {get_uptime_str()}
✦ **Servers:** {guild_count}
✦ **Commands:** {command_count}

{SEP}

✦ All systems operational 🟢"""
    embed = discord.Embed(description=description, color=discord.Color.purple())
    embed.set_footer(text=f"Status Report • {now.strftime('%Y-%m-%d %H:%M UTC')}")
    await channel.send(embed=embed)


async def graceful_shutdown():
    """Rename bot-check channels to red, post shutdown alert, then close."""
    print("Shutting down gracefully...")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT guild_id FROM guild_config WHERE bot_check_channel_id IS NOT NULL")
        check_rows = c.fetchall()
    for (gid,) in check_rows:
        await set_bot_check_name(gid, "🔴")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT status_channel_id FROM guild_config WHERE status_channel_id IS NOT NULL")
        rows = c.fetchall()
    now = datetime.now(timezone.utc)
    description = f"""【｡✦｡】 # BOT OFFLINE 【｡✦｡】
{SEP}

✦ **{client.user.name if client.user else 'Bot'}** is going offline
✦ **Uptime at shutdown:** {get_uptime_str()}
✦ Bot was restarted or stopped — back soon

{SEP}

✦ 🔴 {now.strftime('%Y-%m-%d %H:%M UTC')}"""
    embed = discord.Embed(description=description, color=discord.Color.red())
    for (channel_id,) in rows:
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
            pass
    await client.close()


# ── Bot Setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
start_time: datetime = None


# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    global start_time
    start_time = datetime.now(timezone.utc)
    init_db()
    print(f"Logged in as {client.user} (ID: {client.user.id})")

    # Sync globally (takes up to 1 hour to propagate to all servers)
    await tree.sync()

    # Also copy to the owner guild for instant availability there
    tree.copy_global_to(guild=OWNER_GUILD)
    synced = await tree.sync(guild=OWNER_GUILD)
    print(f"Global sync done. Instant sync to owner guild: {[c.name for c in synced]}")

    if not weekly_status.is_running():
        weekly_status.start()
    if not health_check.is_running():
        health_check.start()

    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"/help | {BOT_VERSION}",
        )
    )

    # Rename bot-check channels to green for all configured guilds
    with sqlite3.connect(DB_PATH) as conn2:
        c2 = conn2.cursor()
        c2.execute("SELECT guild_id FROM guild_config WHERE bot_check_channel_id IS NOT NULL")
        check_rows = c2.fetchall()
    for (gid,) in check_rows:
        await set_bot_check_name(gid, "🟢")

    # Post online alert to all configured status channels
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
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT status_channel_id FROM guild_config WHERE status_channel_id IS NOT NULL")
        rows = c.fetchall()
    for (channel_id,) in rows:
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
            pass

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown()))
    print("Signal handlers registered.")


@client.event
async def on_guild_join(guild: discord.Guild):
    """DM the person who invited the bot with a welcome + full setup tutorial."""

    # Try to find who added the bot via audit log, fall back to guild owner
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

{SEP}

✦ Run `/setup view` anytime to check your config
✦ Need help? Use `/help` for the full guide"""

        dm_embed = discord.Embed(description=intro, color=discord.Color.purple())
        dm_embed.set_thumbnail(url=client.user.display_avatar.url)
        try:
            await inviter.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs closed — silently skip

    # Also post a short welcome in the system channel if available
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


# ── /setup Command Group ──────────────────────────────────────────────────────

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
    await set_bot_check_name(interaction.guild_id, "🟢")
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


tree.add_command(setup_group)


# ── Webhook Commands ──────────────────────────────────────────────────────────

webhook_group = app_commands.Group(
    name="webhook",
    description="Manage and post to Discord webhooks"
)
tree.add_command(webhook_group)


@webhook_group.command(name="add", description="Register a new webhook with a name")
@app_commands.describe(name="Short name to identify this webhook", url="The Discord webhook URL")
@app_commands.default_permissions(manage_guild=True)
async def webhook_cmd_add(interaction: discord.Interaction, name: str, url: str):
    if not is_staff(interaction):
        await interaction.response.send_message("❌ You need **Manage Server** permission.", ephemeral=True)
        return
    if not url.startswith("https://discord.com/api/webhooks/") and not url.startswith("https://discordapp.com/api/webhooks/"):
        await interaction.response.send_message("❌ That doesn't look like a valid Discord webhook URL.", ephemeral=True)
        return
    added = webhook_add(interaction.guild_id, name, url)
    if added:
        await interaction.response.send_message(f"✅ Webhook **{name.lower()}** registered.", ephemeral=True)
    else:
        # Name already exists — offer to update
        webhook_update(interaction.guild_id, name, url)
        await interaction.response.send_message(f"🔄 Webhook **{name.lower()}** already existed — URL updated.", ephemeral=True)
    await log_command(interaction)


@webhook_group.command(name="remove", description="Remove a registered webhook by name")
@app_commands.describe(name="Name of the webhook to remove")
@app_commands.default_permissions(manage_guild=True)
async def webhook_cmd_remove(interaction: discord.Interaction, name: str):
    if not is_staff(interaction):
        await interaction.response.send_message("❌ You need **Manage Server** permission.", ephemeral=True)
        return
    removed = webhook_remove(interaction.guild_id, name)
    if removed:
        await interaction.response.send_message(f"✅ Webhook **{name.lower()}** removed.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No webhook named **{name.lower()}** found.", ephemeral=True)
    await log_command(interaction)


@webhook_group.command(name="list", description="List all registered webhooks for this server")
@app_commands.default_permissions(manage_guild=True)
async def webhook_cmd_list(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message("❌ You need **Manage Server** permission.", ephemeral=True)
        return
    hooks = webhook_list(interaction.guild_id)
    if not hooks:
        await interaction.response.send_message("❌ No webhooks registered yet. Use `/webhook add` to add one.", ephemeral=True)
        return
    lines = "\n".join(f"✦ **{h['name']}** — `•••••/{h['url'].rsplit('/', 1)[-1][:6]}…`" for h in hooks)
    description = f"""【｡✦｡】 # REGISTERED WEBHOOKS 【｡✦｡】
{SEP}

{lines}

{SEP}

✦ Total: **{len(hooks)}** webhook(s)
✦ URLs are masked for security"""
    embed = discord.Embed(description=description, color=discord.Color.purple())
    await interaction.response.send_message(embed=embed, ephemeral=True)



# ── /botupdate ────────────────────────────────────────────────────────────────

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
    """Push a styled update post to every guild that has configured an updates channel."""
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

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT guild_id, updates_channel_id FROM guild_config WHERE updates_channel_id IS NOT NULL")
        rows = c.fetchall()

    sent = 0
    failed = 0
    for guild_id, channel_id in rows:
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
    await log_command(interaction, extra=f"Version: {version} | Sent: {sent} | Failed: {failed}")


# ── Game Night ────────────────────────────────────────────────────────────────

HYPE_MESSAGES = [
    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ Drop whatever boring sh*t you're doing — we're gaming NOW 🎮
✦ The squad is logging on and we're not waiting around for you
✦ Show up or stay crying about it. Simple as that 🔥

{SEP}

✦ Get in the voice chat and let's run it 🕹️""",

    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ Snacks? Check. Headset? Check. Excuses? Leave those at the door 😏
✦ We're running lobbies tonight and the vibes are immaculate
✦ Lose or win, at least you're not sitting there being bored 🕹️

{SEP}

✦ Come through already 🎮""",

    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ It's giving chaotic energy and we are so here for it 🎯
✦ Controllers charged, patience nonexistent — let's f*cking go
✦ The only bad decision is not showing up tonight 😎

{SEP}

✦ Hop in and let's get it 🔥""",

    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ GG crew assemble — it's that time again 🔥
✦ No skill required. Just vibes, chaos, and a will to destroy your friends
✦ We go hard, we have fun, and we do NOT gatekeep the good times 🎮

{SEP}

✦ Link up — let's go 🎯""",

    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ Logging on? Good. Not logging on? Rethink your life choices 😏
✦ Tonight we game, we laugh, and someone inevitably rage quits
✦ It's giving legendary session energy and you need to be there 🕹️

{SEP}

✦ Roll up 🎮""",

    f"""【｡✦｡】 # GAME NIGHT 【｡✦｡】
{SEP}

✦ The wait is over — game night is HERE and we're not playing around 🎯
✦ Well actually we are. We're literally playing games. You know what I mean 😂
✦ Get in, get loud, and for the love of god stop being in your feelings 🔥

{SEP}

✦ Let's get it started 🕹️""",
]

VOTE_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
DAY_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def get_gamenight_channel(interaction: discord.Interaction):
    """Fetch the configured game night channel or error if not set."""
    config = get_config(interaction.guild_id)
    channel_id = config.get("gamenight_channel_id")
    if not channel_id:
        await interaction.response.send_message(
            "❌ Game night channel not configured. Ask an admin to run `/setup gamenight #channel` first.",
            ephemeral=True,
        )
        return None
    try:
        return client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    except discord.errors.NotFound:
        await interaction.response.send_message(
            "❌ The configured game night channel no longer exists. Run `/setup gamenight` again.",
            ephemeral=True,
        )
        return None
    except discord.errors.Forbidden:
        await interaction.response.send_message(
            "❌ I can't access the configured game night channel — check my permissions.",
            ephemeral=True,
        )
        return None


@tree.command(name="gamenight", description="Announce Game Night with a hype message!")
async def gamenight(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    channel = await get_gamenight_channel(interaction)
    if not channel:
        return

    await log_command(interaction)
    embed = discord.Embed(description=random.choice(HYPE_MESSAGES), color=discord.Color.purple())

    try:
        await channel.send(
            content="@everyone", embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await interaction.response.send_message("✅ Hype message sent!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.response.send_message(
            "❌ Couldn't send — check I have **Send Messages** and **Embed Links** in that channel.",
            ephemeral=True,
        )


@tree.command(name="gameplan", description="Start a poll to vote on what game to play tonight!")
@app_commands.describe(
    game1="First game option",
    game2="Second game option",
    game3="Third game option (optional)",
    game4="Fourth game option (optional)",
)
async def gameplan(
    interaction: discord.Interaction,
    game1: str,
    game2: str,
    game3: str = None,
    game4: str = None,
):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    channel = await get_gamenight_channel(interaction)
    if not channel:
        return

    options = [g for g in [game1, game2, game3, game4] if g]
    await log_command(interaction, extra=f"Games: {', '.join(options)}")

    lines = "\n".join(f"{VOTE_EMOJIS[i]} **{game}**" for i, game in enumerate(options))
    description = f"""【｡✦｡】 # GAME PLAN 【｡✦｡】
{SEP}

✦ The people have gathered. Now it's time to PICK A GAME 🎮
✦ Vote below and may the best game win — no crying about the results 🔥

{SEP}

{lines}

{SEP}

✦ Drop your vote and let's get it locked in 🎯"""

    embed = discord.Embed(description=description, color=discord.Color.purple())
    await interaction.response.defer(ephemeral=True)

    try:
        msg = await channel.send(
            content="@everyone", embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        for i in range(len(options)):
            await msg.add_reaction(VOTE_EMOJIS[i])
        await interaction.followup.send("✅ Poll posted!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ Couldn't post — check I have **Send Messages**, **Embed Links**, and **Add Reactions** in that channel.",
            ephemeral=True,
        )


@tree.command(name="gamecheck", description="Ask the community if they want a game night and what day!")
async def gamecheck(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    channel = await get_gamenight_channel(interaction)
    if not channel:
        return

    await log_command(interaction)

    yn_description = f"""【｡✦｡】 # GAME NIGHT CHECK 【｡✦｡】
{SEP}

✦ Real talk — are we actually doing this? 🎮
✦ Vote below and let's see if the squad is even down

{SEP}

✅ **Yes, I'm in**
❌ **Nah, not tonight**

{SEP}

✦ Results decide our fate 🎮"""

    day_lines = "\n".join(f"{DAY_EMOJIS[i]} **{day}**" for i, day in enumerate(DAYS))
    day_description = f"""【｡✦｡】 # PICK A DAY 【｡✦｡】
{SEP}

✦ If we're doing this, WHEN are we doing this? 🗓️
✦ Vote for the day that works for you — majority rules, no excuses 🔥

{SEP}

{day_lines}

{SEP}

✦ Lock in your day — majority rules 🗓️"""

    yn_embed = discord.Embed(description=yn_description, color=discord.Color.purple())
    day_embed = discord.Embed(description=day_description, color=discord.Color.purple())

    await interaction.response.defer(ephemeral=True)

    try:
        yn_msg = await channel.send(
            content="@everyone", embed=yn_embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await yn_msg.add_reaction("✅")
        await yn_msg.add_reaction("❌")
        day_msg = await channel.send(embed=day_embed)
        for emoji in DAY_EMOJIS:
            await day_msg.add_reaction(emoji)
        await interaction.followup.send("✅ Polls posted!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ Couldn't post — check I have **Send Messages**, **Embed Links**, and **Add Reactions** in that channel.",
            ephemeral=True,
        )


# ── /status ───────────────────────────────────────────────────────────────────

@tree.command(name="status", description="Post live bot stats to the status channel.")
async def status(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    await log_command(interaction)
    await interaction.response.defer(ephemeral=True)

    config = get_config(interaction.guild_id)
    channel_id = config.get("status_channel_id")

    if not channel_id:
        await interaction.followup.send(
            "❌ No status channel configured. Run `/setup status #channel` first.", ephemeral=True
        )
        return

    try:
        await post_status_to(channel_id)
        await interaction.followup.send("✅ Status posted!", ephemeral=True)
    except (discord.errors.Forbidden, discord.errors.NotFound):
        await interaction.followup.send(
            "❌ Couldn't post — check I have **Send Messages** and **Embed Links** in the status channel.",
            ephemeral=True,
        )


# ── /postad ───────────────────────────────────────────────────────────────────

@tree.command(name="postad", description="Post a styled advertisement to the ad channel or via a webhook.")
@app_commands.describe(
    title="Title of the advertisement",
    description="Body text — use \\n for lines, --- for dividers, ##Header for sub-headers, [label](url) for links",
    image_url="Optional image URL to display in the embed",
    link="Optional standalone link shown at the bottom (e.g. invite, website)",
    webhook="Optional: name of a registered webhook to post through instead of the ad channel",
)
async def postad(
    interaction: discord.Interaction,
    title: str,
    description: str,
    image_url: str = None,
    link: str = None,
    webhook: str = None,
):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    # Resolve destination — webhook takes priority over ad channel
    webhook_url = None
    if webhook:
        webhook_url = webhook_get(interaction.guild_id, webhook)
        if not webhook_url:
            await interaction.response.send_message(
                f"❌ No webhook named **{webhook.lower()}** found. Use `/webhook list` to see registered webhooks.",
                ephemeral=True,
            )
            return
    else:
        config = get_config(interaction.guild_id)
        channel_id = config.get("ad_channel_id")
        if not channel_id:
            await interaction.response.send_message(
                "❌ Ad channel not configured. Run `/setup ads #channel` first.", ephemeral=True
            )
            return

    flagged_fields = []
    if is_nsfw(title):
        flagged_fields.append("title")
    if is_nsfw(description):
        flagged_fields.append("description")
    if link and is_nsfw(link):
        flagged_fields.append("link")

    if flagged_fields:
        await log_command(
            interaction,
            extra=f"⚠️ BLOCKED — NSFW content in: {', '.join(flagged_fields)}",
        )
        await interaction.response.send_message(
            f"❌ Your ad was blocked — NSFW content detected in the **{', '.join(flagged_fields)}**. Keep it SFW.",
            ephemeral=True,
        )
        return

    if image_url and not re.match(r'https://.+\..+', image_url):
        await interaction.response.send_message(
            "❌ `image_url` must be a valid HTTPS URL (e.g. `https://example.com/image.png`).",
            ephemeral=True,
        )
        return

    await log_command(interaction, extra=f"Title: {title} | Link: {link or 'None'} | Webhook: {webhook or 'None'}")
    await interaction.response.defer(ephemeral=True)

    bulleted = format_body(description)

    link_line = ""
    if link:
        url_match = re.search(r'https?://\S+', link)
        if url_match:
            wh_url = url_match.group()
            label = link[:url_match.start()].strip().rstrip(":").strip()
            link_line = f"\n\n✦ {label}: {wh_url}" if label else f"\n\n✦ [Check it out here]({wh_url})"
        else:
            link_line = f"\n\n✦ {link}"

    body_text = f"{SEP}\n\n{bulleted}\n\n{SEP}{link_line}"

    # Image embed (top) + text embed (below) — stacked in one message
    embeds = []
    if image_url:
        img_embed = discord.Embed(color=0x9B59B6)
        img_embed.set_image(url=image_url)
        embeds.append(img_embed)

    text_embed = discord.Embed(color=0x9B59B6)
    text_embed.set_author(name=f"【｡✦｡】 # {title.upper()} 【｡✦｡】")
    text_embed.description = body_text
    text_embed.set_footer(
        text=f"Posted by {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url,
    )
    text_embed.timestamp = datetime.now(timezone.utc)
    embeds.append(text_embed)

    try:
        if webhook_url:
            async with aiohttp.ClientSession() as session:
                wh = discord.Webhook.from_url(webhook_url, session=session)
                await wh.send(
                    content="@here", embeds=embeds,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
            await interaction.followup.send(f"✅ Ad posted via webhook **{webhook.lower()}**!", ephemeral=True)
        else:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(
                content="@here", embeds=embeds,
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )
            await interaction.followup.send("✅ Ad posted!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ Couldn't post — check I have **Send Messages** and **Embed Links** permissions.",
            ephemeral=True,
        )


# ── /announce ─────────────────────────────────────────────────────────────────

@tree.command(name="announce", description="Post a styled announcement to a channel or via a webhook.")
@app_commands.describe(
    title="Title of the announcement",
    message="Body text — use \\n for lines, --- for dividers, ##Header for sub-headers",
    channel="Channel to post the announcement in (not needed if using a webhook)",
    webhook="Optional: name of a registered webhook to post through instead of a channel",
)
async def announce(
    interaction: discord.Interaction,
    title: str,
    message: str,
    channel: discord.TextChannel = None,
    webhook: str = None,
):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    if not channel and not webhook:
        await interaction.response.send_message(
            "❌ Provide either a **channel** or a **webhook** name to post to.", ephemeral=True
        )
        return

    webhook_url = None
    if webhook:
        webhook_url = webhook_get(interaction.guild_id, webhook)
        if not webhook_url:
            await interaction.response.send_message(
                f"❌ No webhook named **{webhook.lower()}** found. Use `/webhook list` to see registered webhooks.",
                ephemeral=True,
            )
            return

    await log_command(interaction, extra=f"Channel: {channel.name if channel else 'None'} | Title: {title} | Webhook: {webhook or 'None'}")
    await interaction.response.defer(ephemeral=True)

    bulleted = format_body(message)

    description = f"""【｡✦｡】 # {title.upper()} 【｡✦｡】
{SEP}

{bulleted}

{SEP}"""

    embed = discord.Embed(description=description, color=discord.Color.purple())
    embed.set_footer(
        text=f"Posted by {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url,
    )

    try:
        if webhook_url:
            async with aiohttp.ClientSession() as session:
                wh = discord.Webhook.from_url(webhook_url, session=session)
                await wh.send(embed=embed)
            await interaction.followup.send(f"✅ Announcement posted via webhook **{webhook.lower()}**!", ephemeral=True)
        else:
            await channel.send(embed=embed)
            await interaction.followup.send(f"✅ Announcement posted to {channel.mention}!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ Couldn't post — check I have **Send Messages** and **Embed Links** permissions.",
            ephemeral=True,
        )


# ── /event ────────────────────────────────────────────────────────────────────

def parse_event_datetime(date_str: str, time_str: str) -> datetime | None:
    date_str = date_str.strip()
    time_str = time_str.strip().upper().replace(" ", "")
    year = datetime.now(timezone.utc).year
    try:
        if date_str.count("/") == 2:
            dt_date = datetime.strptime(date_str, "%m/%d/%Y")
        else:
            dt_date = datetime.strptime(f"{date_str}/{year}", "%m/%d/%Y")
    except ValueError:
        return None
    for fmt in ("%I:%M%p", "%I%p", "%H:%M"):
        try:
            dt_time = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    return datetime(
        dt_date.year, dt_date.month, dt_date.day,
        dt_time.hour, dt_time.minute, tzinfo=timezone.utc,
    )


@tree.command(name="event", description="Create a Discord scheduled event in this server.")
@app_commands.describe(
    name="Event title",
    description="What the event is about (use \\n for new lines)",
    date="Date of the event — MM/DD or MM/DD/YYYY",
    start_time="Start time — e.g. 11:00PM or 15:00 (UTC)",
    end_time="End time — e.g. 11:00PM or 17:00 (defaults to 1hr after start)",
    location="Location text shown on the event (default: This Server)",
)
async def event(
    interaction: discord.Interaction,
    name: str,
    description: str,
    date: str,
    start_time: str,
    end_time: str = None,
    location: str = "This Server",
):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    start_dt = parse_event_datetime(date, start_time)
    if not start_dt:
        await interaction.followup.send(
            "❌ Couldn't parse the start date/time. Use `MM/DD` and `11:00PM` or `23:00`.",
            ephemeral=True,
        )
        return

    if end_time:
        end_dt = parse_event_datetime(date, end_time)
        if not end_dt:
            await interaction.followup.send(
                "❌ Couldn't parse the end time. Use `11:00PM` or `23:00`.", ephemeral=True
            )
            return
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)
    else:
        end_dt = start_dt + timedelta(hours=1)

    clean_description = description.replace("\\n", "\n")

    try:
        scheduled_event = await interaction.guild.create_scheduled_event(
            name=name,
            description=clean_description,
            start_time=start_dt,
            end_time=end_dt,
            entity_type=discord.EntityType.external,
            location=location,
            privacy_level=discord.PrivacyLevel.guild_only,
        )
        await log_command(interaction, extra=f"Event: {name} | {date} {start_time}")
        await interaction.followup.send(
            f"✅ Event **{name}** created! [View it here]({scheduled_event.url})",
            ephemeral=True,
        )
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to create events — make sure I have **Manage Events**.",
            ephemeral=True,
        )
    except Exception as e:
        print(f"Event creation error: {e}")
        await interaction.followup.send(
            "❌ Something went wrong creating the event. Check bot permissions and try again.",
            ephemeral=True,
        )


# ── /cancel ───────────────────────────────────────────────────────────────────

@tree.command(name="cancel", description="Cancel a scheduled server event by name.")
@app_commands.describe(name="Full or partial name of the event to cancel")
async def cancel_event(interaction: discord.Interaction, name: str):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ You need **Manage Server** permission to use this command.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    events = await interaction.guild.fetch_scheduled_events()
    if not events:
        await interaction.followup.send("❌ There are no scheduled events in this server.", ephemeral=True)
        return

    matches = [e for e in events if name.lower() in e.name.lower()]
    if not matches:
        event_list = "\n".join(f"✦ {e.name}" for e in events)
        await interaction.followup.send(
            f"❌ No event found matching **{name}**. Current events:\n{event_list}", ephemeral=True
        )
        return

    if len(matches) > 1:
        event_list = "\n".join(f"✦ {e.name}" for e in matches)
        await interaction.followup.send(
            f"⚠️ Multiple events matched **{name}** — be more specific:\n{event_list}", ephemeral=True
        )
        return

    target = matches[0]
    try:
        await target.delete()
        await log_command(interaction, extra=f"Cancelled event: {target.name}")
        await interaction.followup.send(f"✅ Event **{target.name}** has been cancelled.", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to delete events — make sure I have **Manage Events**.",
            ephemeral=True,
        )


# ── /help ─────────────────────────────────────────────────────────────────────

def build_help_pages() -> list[discord.Embed]:
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

📢 **/botupdate** *(owner only)*
✦ Broadcast a changelog to all servers with an updates channel
✦ Uses the same formatting as /postad and /announce
✦ `Usage:` /botupdate version: title: changelog:
✦ `Example:` /botupdate version:v2.5 title:Security Patch changelog:##Changes\\nFixed webhook masking---##Notes\\nNo action needed

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


class HelpView(discord.ui.View):
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


@tree.command(name="help", description="Show all available bot commands and how to use them.")
async def help_command(interaction: discord.Interaction):
    await log_command(interaction)
    pages = build_help_pages()
    view = HelpView(pages)
    try:
        await interaction.user.send(embed=pages[0], view=view)
        await interaction.response.send_message("📬 Check your DMs!", ephemeral=True)
    except discord.errors.Forbidden:
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)


# ── Error Handler ─────────────────────────────────────────────────────────────

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    cmd_name = f"/{interaction.command.name}" if interaction.command else "/unknown"
    print(f"Command error in {cmd_name} by {interaction.user}: {error}")

    try:
        await set_bot_check_name(interaction.guild_id or 0, "🟡")
        config = get_config(interaction.guild_id or 0)
        channel_id = config.get("status_channel_id")
        if channel_id:
            description = f"""【｡✦｡】 # BOT ERROR 【｡✦｡】
{SEP}

✦ **Command:** {cmd_name}
✦ **Triggered by:** {interaction.user.mention}
✦ **Error:** {type(error).__name__}
✦ **Uptime:** {get_uptime_str()}

{SEP}

✦ 🟡 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"""
            embed = discord.Embed(description=description, color=discord.Color.yellow())
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(embed=embed)
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


# ── Periodic Health Check Task ────────────────────────────────────────────────

@tasks.loop(minutes=5)
async def health_check():
    """Silently monitor bot health every 5 min. Only rename/alert on status changes."""
    global CURRENT_BOT_STATUS

    # Determine health from gateway latency
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

    # Nothing changed — stay silent
    if new_status == CURRENT_BOT_STATUS:
        return

    old_status = CURRENT_BOT_STATUS
    CURRENT_BOT_STATUS = new_status

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT guild_id FROM guild_config WHERE bot_check_channel_id IS NOT NULL OR status_channel_id IS NOT NULL")
        rows = c.fetchall()

    status_labels = {"🟢": "ONLINE", "🟡": "DEGRADED", "🔴": "OFFLINE"}
    status_colors = {"🟢": discord.Color.green(), "🟡": discord.Color.yellow(), "🔴": discord.Color.red()}
    now = datetime.now(timezone.utc)

    for (guild_id,) in rows:
        config = get_config(guild_id)

        # Rename bot-check channel if configured
        if config.get("bot_check_channel_id"):
            await set_bot_check_name(guild_id, new_status)

        # Send alert to status channel if configured
        status_channel_id = config.get("status_channel_id")
        if status_channel_id:
            try:
                latency_ms = round(client.latency * 1000)
                description = f"""【｡✦｡】 # STATUS CHANGE 【｡✦｡】
{SEP}

✦ **Previous:** {old_status} {status_labels.get(old_status, old_status)}
✦ **Current:** {new_status} {status_labels.get(new_status, new_status)}
✦ **Latency:** {latency_ms}ms
✦ **Uptime:** {get_uptime_str()}

{SEP}

✦ {"All systems operational" if new_status == "🟢" else "Performance degraded — monitoring" if new_status == "🟡" else "Bot is experiencing issues"} {new_status}"""
                embed = discord.Embed(description=description, color=status_colors[new_status])
                embed.set_footer(text=f"Health Monitor • {now.strftime('%Y-%m-%d %H:%M UTC')}")
                ch = client.get_channel(status_channel_id) or await client.fetch_channel(status_channel_id)
                await ch.send(embed=embed)
            except Exception as e:
                print(f"Health alert error for guild {guild_id}: {e}")


@health_check.before_loop
async def before_health_check():
    await client.wait_until_ready()


# ── Weekly Status Task ────────────────────────────────────────────────────────

@tasks.loop(time=time(hour=12, minute=0, tzinfo=timezone.utc))
async def weekly_status():
    if datetime.now(timezone.utc).weekday() != 6:
        return
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT status_channel_id FROM guild_config WHERE status_channel_id IS NOT NULL")
        rows = c.fetchall()
    for (channel_id,) in rows:
        try:
            await post_status_to(channel_id)
        except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException) as e:
            print(f"Weekly status error for channel {channel_id}: {e}")


# ── Run ───────────────────────────────────────────────────────────────────────

client.run(TOKEN)
