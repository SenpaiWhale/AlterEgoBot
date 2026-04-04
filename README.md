# AlterEgo — Discord Bot

**AlterEgo#5039** is a feature-rich Discord bot built for community servers. It handles game night coordination, styled announcements, advertisement posting with NSFW filtering, Discord scheduled events, and real-time bot status monitoring — all through clean slash commands.

**[+ Add AlterEgo to your server](https://discord.com/oauth2/authorize?client_id=1230302180603596822&scope=bot+applications.commands&permissions=8590151672)**

---

## Features

- **Game Night Tools** — Hype announcements, voting polls, and community availability checks
- **Announcements** — Styled embeds posted to a configured channel or via webhook
- **Advertisement Posting** — Branded ad embeds with automatic NSFW content filtering
- **Discord Events** — Create and cancel Discord scheduled events directly from a command
- **Bot Status Monitoring** — Live stats panel and a channel that renames itself based on bot health (🟢 / 🔴 / 🟡)
- **Mod Logging** — Optional channel that records every command usage
- **Bot Updates** — Automatic changelog posts to all servers when the bot starts with a new version
- **Scheduled Tasks** — Automatic weekly status reports and health monitoring

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

### Webhooks (Requires Manage Server)

| Command | Description |
|---|---|
| `/webhook add` | Register a Discord webhook by name |
| `/webhook remove` | Remove a registered webhook |
| `/webhook list` | List all registered webhooks (URLs masked) |

---

## Project Structure

```
AlterEgoBot/
├── main.py                  # Entrypoint — Flask health server + bot startup
├── bot/
│   ├── __init__.py
│   ├── client.py            # Client factory, lifecycle events, shutdown
│   ├── config.py            # Constants (token, version, paths)
│   ├── db.py                # SQLite data layer (config + webhooks)
│   ├── filters.py           # NSFW content detection
│   ├── formatting.py        # Styled text formatting
│   ├── helpers.py           # Shared utilities (staff check, modlog, status)
│   ├── tasks.py             # Background tasks (health monitor, weekly status)
│   └── commands/
│       ├── __init__.py
│       ├── admin.py         # /status
│       ├── content.py       # /postad, /announce
│       ├── events.py        # /event, /cancel
│       ├── gamenight.py     # /gamenight, /gameplan, /gamecheck
│       ├── general.py       # /help
│       ├── setup.py         # /setup group
│       └── webhooks.py      # /webhook group
├── requirements.txt
├── pyproject.toml
├── push_to_github.sh
├── .replit
├── .gitignore
└── README.md
```

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
export DISCORD_BOT_TOKEN=your_token_here
```

### Running

```bash
python main.py
```

The bot will start, connect to Discord, and spin up a health check server on port 8000.

### Formatting Guide

The `/postad`, `/announce`, and `/botupdate` commands support rich formatting:

| Syntax | Effect |
|---|---|
| `\n` | New bullet line |
| `\n\n` | Blank gap between sections |
| `---` | Styled section divider |
| `##Title` | Styled sub-header |
| `[label](url)` | Inline clickable hyperlink |

---

## Tech Stack

- [discord.py 2.4](https://discordpy.readthedocs.io/) — Discord API wrapper
- [Flask](https://flask.palletsprojects.com/) — Health check server (Replit uptime)
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

Copyright (c) 2026 MrKarxsu

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to use, copy, modify, and distribute the Software, subject to the following conditions:

**Non-Commercial Use Only.** The Software may not be used, in whole or in part, for commercial purposes. Commercial purposes include, but are not limited to, selling the Software, offering it as a paid service, or using it in any product or service that generates revenue.

**Attribution.** All copies or substantial portions of the Software must include this license notice and credit the original author.

**Distribution.** Any modified versions distributed publicly must also be released under these same terms.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY ARISING FROM THE USE OF THE SOFTWARE.
