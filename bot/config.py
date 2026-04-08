"""Centralized configuration constants for AlterEgo."""

import os

import discord

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
BOT_VERSION = "v2.6"

SEP = "· · ───────────── ꒰ঌ·✦·໒꒱ ───────────── · ·"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.db")

OWNER_GUILD = discord.Object(id=1471048262285918210)

# ── Changelog ────────────────────────────────────────────────────────────────
# Edit this when bumping BOT_VERSION. The bot auto-posts it on first startup
# with a new version to every guild's configured updates channel.

CHANGELOG_TITLE = "Rich Ads & Fresh Update Logs"
CHANGELOG_BODY = """\
##🆕 What's New
📢 /postad now supports emoji-prefixed lines — 🏆, ✅, ❌ and more stay exactly as you type them
📝 Added **body2** and **body3** overflow fields for longer ads like crew recruitment posts
📣 New **ping** option — choose @here, @everyone, or no ping when posting ads
🎨 Update logs got a full makeover — friendlier tone, emoji sections, and a cleaner layout
---
##🔧 How It Works
✏️ Lines starting with an emoji are kept as-is instead of getting a ✦ bullet
📦 body2 and body3 are optional — only use them when your ad is too long for one field
🔍 NSFW filtering covers all body fields automatically
---
##💬 That's It!
🎉 No action needed — just enjoy the new features
❓ Questions? Run /help or reach out anytime\
"""
