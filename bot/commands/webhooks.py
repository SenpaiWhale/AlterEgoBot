"""Webhook management commands (/webhook group)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.config import SEP
from bot.db import webhook_add, webhook_list, webhook_remove, webhook_update
from bot.helpers import is_staff, log_command

if TYPE_CHECKING:
    from bot.client import AlterEgoClient

webhook_group = app_commands.Group(
    name="webhook",
    description="Manage and post to Discord webhooks",
)


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
        webhook_update(interaction.guild_id, name, url)
        await interaction.response.send_message(f"🔄 Webhook **{name.lower()}** already existed — URL updated.", ephemeral=True)
    await log_command(interaction.client, interaction)


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
    await log_command(interaction.client, interaction)


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


def register(client: AlterEgoClient):
    """Attach the webhook command group to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    client.tree.add_command(webhook_group)
