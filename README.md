# AlterEgo — Discord Bot

**AlterEgo#5039** is a feature-rich Discord bot built for community servers. It handles game night coordination, styled announcements, advertisement posting with NSFW filtering, Discord scheduled events, and real-time bot status monitoring — all through clean slash commands.

---

## Features

- **Game Night Tools** — Hype announcements, voting polls, and community availability checks
- **Announcements** — Styled embeds posted to a configured channel or via webhook
- **Advertisement Posting** — Branded ad embeds with automatic NSFW content filtering
- **Discord Events** — Create and cancel Discord scheduled events directly from a command
- **Bot Status Monitoring** — Live stats panel and a channel that renames itself based on bot health (🟢 / 🔴 / 🟡)
- **Mod Logging** — Optional channel that records every command usage
- **Scheduled Tasks** — Automatic status updates and version announcements
- **24/7 Uptime** — Deployed on Replit Reserved VM, always online

---

## Commands

### General

| Command | Description |
|---|---|
| `/gamenight` | Post a hype Game Night announcement to the configured channel |
| `/gameplan` | Start a poll so the community can vote on what game to play |
| `/gamecheck` | Ask the community if they want a game night and which day works |
| `/postad` | Post a styled advertisement embed (with NSFW filtering) |
| `/announce` | Post a styled announcement to a channel or via webhook |
| `/event` | Create a Discord scheduled event in the server |
| `/cancel` | Cancel an existing scheduled event by name |
| `/status` | Post live bot stats to the status channel |
| `/help` | Show all available commands and usage info |

### Setup (Requires Manage Server)

| Command | Description |
|---|---|
| `/setup gamenight` | Set the channel for game night posts |
| `/setup announce` | Set the default announcements channel |
| `/setup ads` | Set the channel for advertisement posts |
| `/setup status` | Set the channel for bot status updates |
| `/setup modlog` | Set the channel for command usage logs |
| `/setup botcheck` | Set a channel that renames itself to reflect bot status |
| `/setup updates` | Set a channel for bot version/update notifications |

---

## Self-Hosting

### Requirements

- Python 3.12+
- A Discord bot token with the following intents enabled in the [Discord Developer Portal](https://discord.com/developers/applications):
  - `Server Members Intent`
  - `Message Content Intent` (optional)

### Installation

```bash
git clone https://github.com/SenpaiWhale/AlterEgoBot.git
cd AlterEgoBot
pip install -r requirements.txt
```

### Configuration

Set your bot token as an environment variable:

```bash
export DISCORD_TOKEN=your_token_here
```

### Running

```bash
python main.py
```

The bot will start, connect to Discord, and spin up a lightweight health check server on port 8000.

---

## Tech Stack

- [discord.py 2.4](https://discordpy.readthedocs.io/) — Discord API wrapper
- [Flask](https://flask.palletsprojects.com/) — Health check web server
- [better-profanity](https://github.com/snguyenthanh/better_profanity) — Profanity filtering for ads
- [aiohttp](https://docs.aiohttp.org/) — Async HTTP for webhook delivery
- SQLite — Per-guild configuration storage

---

## Contact

Have questions, suggestions, or want to report a bug? Reach out:

- **Twitter / X:** [@MrKarxsu](https://x.com/MrKarxsu)
- **Discord:** `@0u6`

---

## License

This project is open source. Feel free to fork and adapt it for your own server.
