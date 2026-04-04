"""Content posting commands: /postad, /announce."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands

from bot.config import SEP
from bot.db import get_config, webhook_get
from bot.filters import is_nsfw
from bot.formatting import format_body
from bot.helpers import is_staff, log_command

if TYPE_CHECKING:
    from bot.client import AlterEgoClient


def register(client: AlterEgoClient):
    """Attach content commands to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    tree = client.tree

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
                client, interaction,
                extra=f"⚠️ BLOCKED — NSFW content in: {', '.join(flagged_fields)}",
            )
            await interaction.response.send_message(
                f"❌ Your ad was blocked — NSFW content detected in the **{', '.join(flagged_fields)}**. Keep it SFW.",
                ephemeral=True,
            )
            return

        if image_url and not re.match(r"https://.+\..+", image_url):
            await interaction.response.send_message(
                "❌ `image_url` must be a valid HTTPS URL (e.g. `https://example.com/image.png`).",
                ephemeral=True,
            )
            return

        await log_command(client, interaction, extra=f"Title: {title} | Link: {link or 'None'} | Webhook: {webhook or 'None'}")
        await interaction.response.defer(ephemeral=True)

        bulleted = format_body(description)

        link_line = ""
        if link:
            url_match = re.search(r"https?://\S+", link)
            if url_match:
                wh_url = url_match.group()
                label = link[: url_match.start()].strip().rstrip(":").strip()
                link_line = f"\n\n✦ {label}: {wh_url}" if label else f"\n\n✦ [Check it out here]({wh_url})"
            else:
                link_line = f"\n\n✦ {link}"

        body_text = f"{SEP}\n\n{bulleted}\n\n{SEP}{link_line}"

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
                ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                await ch.send(
                    content="@here", embeds=embeds,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
                await interaction.followup.send("✅ Ad posted!", ephemeral=True)
        except discord.errors.Forbidden:
            await interaction.followup.send(
                "❌ Couldn't post — check I have **Send Messages** and **Embed Links** permissions.",
                ephemeral=True,
            )

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

        await log_command(client, interaction, extra=f"Channel: {channel.name if channel else 'None'} | Title: {title} | Webhook: {webhook or 'None'}")
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
