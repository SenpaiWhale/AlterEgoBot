"""Game night commands: /gamenight, /gameplan, /gamecheck."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.config import SEP
from bot.db import get_config
from bot.helpers import is_staff, log_command

if TYPE_CHECKING:
    from bot.client import AlterEgoClient

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


async def _get_gamenight_channel(interaction: discord.Interaction):
    """Fetch the configured game night channel or send an error."""
    client = interaction.client
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


def register(client: AlterEgoClient):
    """Attach game night commands to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    tree = client.tree

    @tree.command(name="gamenight", description="Announce Game Night with a hype message!")
    async def gamenight(interaction: discord.Interaction):
        if not is_staff(interaction):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )
            return
        channel = await _get_gamenight_channel(interaction)
        if not channel:
            return
        await log_command(client, interaction)
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
        game1="First game option", game2="Second game option",
        game3="Third game option (optional)", game4="Fourth game option (optional)",
    )
    async def gameplan(
        interaction: discord.Interaction,
        game1: str, game2: str, game3: str = None, game4: str = None,
    ):
        if not is_staff(interaction):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.", ephemeral=True
            )
            return
        channel = await _get_gamenight_channel(interaction)
        if not channel:
            return
        options = [g for g in [game1, game2, game3, game4] if g]
        await log_command(client, interaction, extra=f"Games: {', '.join(options)}")
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
        channel = await _get_gamenight_channel(interaction)
        if not channel:
            return
        await log_command(client, interaction)
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
