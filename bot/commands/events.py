"""Discord scheduled event commands: /event, /cancel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.helpers import is_staff, log_command

if TYPE_CHECKING:
    from bot.client import AlterEgoClient


def _parse_event_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse MM/DD or MM/DD/YYYY date + time string into a UTC datetime."""
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


def register(client: AlterEgoClient):
    """Attach event commands to the client's command tree.

    Parameters
    ----------
    client : AlterEgoClient
        The bot client instance.
    """
    tree = client.tree

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

        start_dt = _parse_event_datetime(date, start_time)
        if not start_dt:
            await interaction.followup.send(
                "❌ Couldn't parse the start date/time. Use `MM/DD` and `11:00PM` or `23:00`.",
                ephemeral=True,
            )
            return

        if end_time:
            end_dt = _parse_event_datetime(date, end_time)
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
            await log_command(client, interaction, extra=f"Event: {name} | {date} {start_time}")
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
            await log_command(client, interaction, extra=f"Cancelled event: {target.name}")
            await interaction.followup.send(f"✅ Event **{target.name}** has been cancelled.", ephemeral=True)
        except discord.errors.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete events — make sure I have **Manage Events**.",
                ephemeral=True,
            )
