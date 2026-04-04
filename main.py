"""AlterEgo Discord bot — entrypoint.

Starts the bot and a lightweight Flask health server for Replit uptime.
"""

import threading

from flask import Flask, jsonify

from bot.client import create_client
from bot.commands import admin, content, events, gamenight, general, setup, webhooks
from bot.config import TOKEN

# ── Health Check Server (keeps Replit deployment alive) ──────────────────────

health_app = Flask(__name__)


@health_app.route("/")
def index():
    """Root endpoint confirming the bot is running."""
    return jsonify({"status": "AlterEgo bot is running"})


@health_app.route("/healthz")
def healthz():
    """Kubernetes-style health probe."""
    return jsonify({"status": "ok"})


def _run_health_server():
    import os

    port = int(os.environ.get("PORT", 8000))
    health_app.run(host="0.0.0.0", port=port, use_reloader=False)


# ── Bot Bootstrap ────────────────────────────────────────────────────────────

def main():
    """Create, configure, and run the bot."""
    client = create_client()

    setup.register(client)
    webhooks.register(client)
    gamenight.register(client)
    content.register(client)
    events.register(client)
    admin.register(client)
    general.register(client)

    threading.Thread(target=_run_health_server, daemon=True).start()

    client.run(TOKEN)


if __name__ == "__main__":
    main()
