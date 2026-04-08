"""Centralized configuration constants for AlterEgo."""

import os

import discord

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
BOT_VERSION = "v2.5"

SEP = "· · ───────────── ꒰ঌ·✦·໒꒱ ───────────── · ·"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.db")

OWNER_GUILD = discord.Object(id=1471048262285918210)

# ── Changelog ────────────────────────────────────────────────────────────────
# Edit this when bumping BOT_VERSION. The bot auto-posts it on first startup
# with a new version to every guild's configured updates channel.

CHANGELOG_TITLE = "Security Hardening & Code Revamp"
CHANGELOG_BODY = """\
##🆕 What's New
🛠️ Rebuilt the entire codebase from the ground up — faster, cleaner, and way easier to add new stuff
🔗 Webhook URLs are now hidden in /webhook list so your links stay safe
📣 Update logs like this one now post automatically whenever we drop a new version
---
##🔒 Security Upgrades
🔐 Image URLs are now HTTPS-only — no more sketchy links
🛡️ Error details are no longer leaked into Discord channels
💉 SQL injection prevention baked into the config system
🗄️ All database connections use safe context managers now
🎯 Every error is handled specifically — no more silent failures
---
##💬 That's It!
🎉 No action needed on your end — everything updates automatically
❓ Questions? Run /help or reach out anytime\
"""
