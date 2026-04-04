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
##What's New
Modular codebase — cleaner, faster, easier to extend
Webhook URLs are now masked in /webhook list
Bot update changelogs now post automatically on version bumps
---
##Security
Image URLs restricted to HTTPS only
Error details no longer leaked to Discord channels
SQL injection prevention added to config system
All database connections now use safe context managers
Specific exception handling throughout (no more silent failures)
---
##Notes
No action needed — all changes are automatic\
"""
