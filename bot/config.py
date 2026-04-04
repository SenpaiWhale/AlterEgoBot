"""Centralized configuration constants for AlterEgo."""

import os

import discord

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
BOT_VERSION = "v2.5"

SEP = "· · ───────────── ꒰ঌ·✦·໒꒱ ───────────── · ·"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.db")

OWNER_GUILD = discord.Object(id=1471048262285918210)
