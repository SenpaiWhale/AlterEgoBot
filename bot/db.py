"""SQLite database layer for per-guild configuration and webhooks."""

import sqlite3

from bot.config import DB_PATH

_ALLOWED_CONFIG_COLUMNS = frozenset({
    "gamenight_channel_id",
    "announce_channel_id",
    "ad_channel_id",
    "status_channel_id",
    "modlog_channel_id",
    "bot_check_channel_id",
    "updates_channel_id",
})

_CONFIG_KEYS = [
    "guild_id",
    "gamenight_channel_id",
    "announce_channel_id",
    "ad_channel_id",
    "status_channel_id",
    "modlog_channel_id",
    "bot_check_channel_id",
    "updates_channel_id",
]


def init_db():
    """Create tables and run schema migrations."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id             INTEGER PRIMARY KEY,
                gamenight_channel_id INTEGER,
                announce_channel_id  INTEGER,
                ad_channel_id        INTEGER,
                status_channel_id    INTEGER,
                modlog_channel_id    INTEGER,
                bot_check_channel_id INTEGER
            )
        """)
        try:
            c.execute("ALTER TABLE guild_config ADD COLUMN bot_check_channel_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE guild_config ADD COLUMN updates_channel_id INTEGER")
        except sqlite3.OperationalError:
            pass
        c.execute("""
            CREATE TABLE IF NOT EXISTS guild_webhooks (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name     TEXT    NOT NULL,
                url      TEXT    NOT NULL,
                UNIQUE(guild_id, name)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS bot_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()


def get_config(guild_id: int) -> dict:
    """Retrieve the guild configuration row as a dict.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.

    Returns
    -------
    dict
        Mapping of config column names to values, or empty dict if not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
    if not row:
        return {}
    return dict(zip(_CONFIG_KEYS, row))


def set_config(guild_id: int, **kwargs):
    """Upsert guild configuration values.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    **kwargs
        Column-value pairs validated against an allowlist.

    Raises
    ------
    ValueError
        If an unknown column name is supplied.
    """
    bad_keys = set(kwargs) - _ALLOWED_CONFIG_COLUMNS
    if bad_keys:
        raise ValueError(f"Invalid config keys: {bad_keys}")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        for key, value in kwargs.items():
            c.execute(f"UPDATE guild_config SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        conn.commit()


def webhook_add(guild_id: int, name: str, url: str) -> bool:
    """Register a new webhook. Returns False if the name already exists.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Short label for the webhook.
    url : str
        Discord webhook URL.

    Returns
    -------
    bool
        True if inserted, False if the name already exists.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO guild_webhooks (guild_id, name, url) VALUES (?, ?, ?)",
                (guild_id, name.lower(), url),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def webhook_update(guild_id: int, name: str, url: str) -> bool:
    """Update an existing webhook URL by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to update.
    url : str
        New Discord webhook URL.

    Returns
    -------
    bool
        True if a row was updated, False if the name was not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE guild_webhooks SET url = ? WHERE guild_id = ? AND name = ?",
            (url, guild_id, name.lower()),
        )
        updated = c.rowcount > 0
        conn.commit()
    return updated


def webhook_remove(guild_id: int, name: str) -> bool:
    """Delete a webhook registration by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to remove.

    Returns
    -------
    bool
        True if a row was deleted, False if the name was not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM guild_webhooks WHERE guild_id = ? AND name = ?",
            (guild_id, name.lower()),
        )
        removed = c.rowcount > 0
        conn.commit()
    return removed


def webhook_list(guild_id: int) -> list[dict]:
    """List all registered webhooks for a guild.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.

    Returns
    -------
    list[dict]
        Each entry has ``name`` and ``url`` keys, sorted alphabetically.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT name, url FROM guild_webhooks WHERE guild_id = ? ORDER BY name",
            (guild_id,),
        )
        rows = c.fetchall()
    return [{"name": r[0], "url": r[1]} for r in rows]


def webhook_get(guild_id: int, name: str) -> str | None:
    """Fetch a single webhook URL by name.

    Parameters
    ----------
    guild_id : int
        Discord guild snowflake.
    name : str
        Webhook label to look up.

    Returns
    -------
    str or None
        The webhook URL, or None if not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT url FROM guild_webhooks WHERE guild_id = ? AND name = ?",
            (guild_id, name.lower()),
        )
        row = c.fetchone()
    return row[0] if row else None


def query_guild_ids(column: str) -> list[int]:
    """Return guild IDs where the given config column is not NULL.

    Parameters
    ----------
    column : str
        Must be a valid config column name.

    Returns
    -------
    list[int]
        Guild IDs with a non-NULL value for the column.
    """
    if column not in _ALLOWED_CONFIG_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(f"SELECT guild_id FROM guild_config WHERE {column} IS NOT NULL")
        return [row[0] for row in c.fetchall()]


def query_channel_ids(column: str) -> list[int]:
    """Return non-NULL channel IDs for the given config column.

    Parameters
    ----------
    column : str
        Must be a valid config column name.

    Returns
    -------
    list[int]
        Channel IDs from all guilds where the column is set.
    """
    if column not in _ALLOWED_CONFIG_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(f"SELECT {column} FROM guild_config WHERE {column} IS NOT NULL")
        return [row[0] for row in c.fetchall()]


def query_guild_channel_pairs(*columns: str) -> list[tuple]:
    """Return (guild_id, col1, col2, ...) for rows where any column is non-NULL.

    Parameters
    ----------
    *columns : str
        Config column names to select alongside guild_id.

    Returns
    -------
    list[tuple]
        Rows with guild_id followed by each requested column value.
    """
    for col in columns:
        if col not in _ALLOWED_CONFIG_COLUMNS:
            raise ValueError(f"Invalid column: {col}")
    col_list = ", ".join(columns)
    where = " OR ".join(f"{col} IS NOT NULL" for col in columns)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(f"SELECT guild_id, {col_list} FROM guild_config WHERE {where}")
        return c.fetchall()


# ── Bot Metadata ─────────────────────────────────────────────────────────────


def get_meta(key: str) -> str | None:
    """Retrieve a value from the bot_meta key-value store.

    Parameters
    ----------
    key : str
        The metadata key.

    Returns
    -------
    str or None
        The stored value, or None if not set.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM bot_meta WHERE key = ?", (key,))
        row = c.fetchone()
    return row[0] if row else None


def set_meta(key: str, value: str):
    """Insert or update a value in the bot_meta key-value store.

    Parameters
    ----------
    key : str
        The metadata key.
    value : str
        The value to store.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO bot_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
