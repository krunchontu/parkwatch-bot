"""Admin command handlers for ParkWatch SG."""

import functools
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_USER_IDS

from .announce import admin_announce
from .config import admin_config, admin_maintenance
from .data import admin_export, admin_purge
from .moderation import admin_ban, admin_banlist, admin_delete, admin_review, admin_unban, admin_warn
from .stats import admin_log, admin_stats, admin_user, admin_zone

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator that restricts a handler to authorized admin users.

    Unauthorized users receive a generic "Unknown command" response so as not
    to reveal that admin commands exist.
    """

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("Unknown command. Use /help to see available commands.")
            return
        return await func(update, context)

    return wrapper


# Admin help text — kept as a constant so it's easy to maintain
ADMIN_COMMANDS_HELP = {
    "stats": "Show global statistics dashboard (users, sightings, zones, feedback)",
    "user <id or @username>": "Look up a user's details, subscriptions, and activity",
    "zone <zone_name>": "Look up a zone's subscribers, sightings, and top reporters",
    "log [count]": "View recent admin actions (default: 20)",
    "ban <user_id> [reason]": "Ban a user from using the bot",
    "unban <user_id>": "Remove a user's ban",
    "banlist": "List all currently banned users",
    "warn <user_id> [message]": "Send a warning to a user",
    "delete <sighting_id> [confirm]": "Delete a sighting",
    "review": "Show moderation queue of flagged sightings",
    "announce all <msg>": "Broadcast a message to all registered users",
    "announce zone <zone> <msg>": "Broadcast to subscribers of a specific zone",
    "config [<key> <value>|reset <key>]": "View/update runtime settings",
    "maintenance on|off [message]": "Toggle maintenance mode",
    "purge sightings [days]": "Purge old sightings manually",
    "purge sightings zone <zone> [days]": "Purge old sightings for one zone",
    "purge user <user_id>": "Purge user data (preview + confirm)",
    "export stats [csv|json]": "Export non-PII operational stats",
    "help [command]": "Show admin help (this message) or help for a specific command",
}

ADMIN_COMMANDS_DETAILED = {
    "stats": (
        "/admin stats\n\n"
        "Displays a global statistics dashboard including:\n"
        "\u2022 Total registered users and active users (7 days)\n"
        "\u2022 Total sightings (all-time and last 24 hours)\n"
        "\u2022 Active subscriptions and unique subscribers\n"
        "\u2022 Top 5 most-subscribed zones\n"
        "\u2022 Top 5 most-reported zones (last 7 days)\n"
        "\u2022 Feedback totals (positive vs negative)"
    ),
    "user": (
        "/admin user <telegram_id or @username>\n\n"
        "Looks up a specific user and displays:\n"
        "\u2022 Registration date, report count, badge, accuracy score\n"
        "\u2022 Subscribed zones\n"
        "\u2022 Recent sightings (last 10)\n"
        "\u2022 Feedback received (positive/negative totals)\n"
        "\u2022 Ban status and warning count"
    ),
    "zone": (
        "/admin zone <zone_name>\n\n"
        "Looks up a specific zone and displays:\n"
        "\u2022 Subscriber count\n"
        "\u2022 Sighting count (last 24h / 7d / all-time)\n"
        "\u2022 Top reporters in this zone\n"
        "\u2022 Most recent sightings"
    ),
    "log": (
        "/admin log [count]\n\n"
        "Shows the most recent admin actions from the audit log.\n"
        "Default: 20 entries. Maximum: 100."
    ),
    "ban": (
        "/admin ban <user_id> [reason]\n\n"
        "Bans a user from the bot:\n"
        "\u2022 Clears all their subscriptions\n"
        "\u2022 Blocks them from /report, /subscribe, /recent, /mystats, /share\n"
        "\u2022 Notifies the banned user\n"
        "\u2022 Logs action to the audit trail"
    ),
    "unban": (
        "/admin unban <user_id>\n\n"
        "Removes a user's ban:\n"
        "\u2022 User can use the bot again\n"
        "\u2022 Resets warning count to zero\n"
        "\u2022 Notifies the user\n"
        "\u2022 Logs action to the audit trail"
    ),
    "banlist": (
        "/admin banlist\n\nLists all currently banned users with:\n\u2022 Telegram ID\n\u2022 Ban date\n\u2022 Reason (if provided)"
    ),
    "warn": (
        "/admin warn <user_id> [message]\n\n"
        "Sends a warning to a user:\n"
        "\u2022 Bot messages the user with the warning text\n"
        "\u2022 Increments the user's warning count\n"
        "\u2022 Auto-ban after MAX_WARNINGS warnings (runtime configurable)\n"
        "\u2022 Logs action to the audit trail"
    ),
    "delete": (
        "/admin delete <sighting_id> [confirm]\n\n"
        "Deletes a specific sighting:\n"
        "\u2022 First call shows sighting details for review\n"
        "\u2022 Add 'confirm' to execute the deletion\n"
        "\u2022 Cascading delete removes associated feedback\n"
        "\u2022 Logs action to the audit trail"
    ),
    "review": (
        "/admin review\n\n"
        "Shows the moderation queue of flagged sightings:\n"
        "\u2022 Sightings with negative feedback > positive (3+ total votes)\n"
        "\u2022 Sightings explicitly flagged for review\n"
        "\u2022 Shows reporter info, feedback ratio, and sighting details\n"
        "\u2022 Use /admin delete <id> confirm to remove bad sightings"
    ),
    "announce": (
        "/admin announce all <message>\n"
        "/admin announce zone <zone_name> <message>\n"
        "/admin announce confirm\n\n"
        "Broadcast a message to users:\n"
        "\u2022 'all' targets every registered user\n"
        "\u2022 'zone' targets subscribers of a specific zone\n"
        "\u2022 First run shows a preview with recipient count\n"
        "\u2022 Run /admin announce confirm to send\n"
        "\u2022 Rate-limited delivery (20 msgs/sec)\n"
        "\u2022 Delivery report with sent/failed/blocked counts"
    ),
    "config": "/admin config\n/admin config <KEY> <VALUE>\n/admin config reset <KEY>",
    "maintenance": "/admin maintenance on [message]\n/admin maintenance off",
    "purge": "/admin purge sightings [days]\n/admin purge sightings zone <zone> [days]\n/admin purge user <id>",
    "export": "/admin export stats [csv|json]",
}


async def _admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str | None):
    """Handle /admin or /admin help [command]."""
    if command:
        detail = ADMIN_COMMANDS_DETAILED.get(command)
        if detail:
            await update.message.reply_text(f"\U0001f4d6 Admin Command Help\n\n{detail}")
        else:
            await update.message.reply_text(f"No help available for '{command}'.\n\nUse /admin to see all commands.")
        return

    msg = "\U0001f527 Admin Commands\n\n"
    for cmd, desc in ADMIN_COMMANDS_HELP.items():
        msg += f"/admin {cmd}\n  \u2014 {desc}\n\n"
    await update.message.reply_text(msg)


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route /admin subcommands to the appropriate handler."""
    text = update.message.text or ""
    # Parse: /admin <subcommand> [args...]
    parts = text.split(maxsplit=2)  # ["/admin", subcommand, rest]

    if len(parts) < 2:
        # Just "/admin" — show help
        return await _admin_help(update, context, None)

    subcommand = parts[1].lower()
    args = parts[2] if len(parts) > 2 else ""

    handlers = {
        "help": lambda: _admin_help(update, context, args.strip() if args else None),
        "stats": lambda: admin_stats(update, context),
        "user": lambda: admin_user(update, context, args.strip()),
        "zone": lambda: admin_zone(update, context, args.strip()),
        "log": lambda: admin_log(update, context, args.strip()),
        "ban": lambda: admin_ban(update, context, args.strip()),
        "unban": lambda: admin_unban(update, context, args.strip()),
        "banlist": lambda: admin_banlist(update, context),
        "warn": lambda: admin_warn(update, context, args.strip()),
        "delete": lambda: admin_delete(update, context, args.strip()),
        "review": lambda: admin_review(update, context),
        "announce": lambda: admin_announce(update, context, args.strip()),
        "config": lambda: admin_config(update, context, args.strip()),
        "maintenance": lambda: admin_maintenance(update, context, args.strip()),
        "purge": lambda: admin_purge(update, context, args.strip()),
        "export": lambda: admin_export(update, context, args.strip()),
    }

    handler = handlers.get(subcommand)
    if handler:
        return await handler()
    await update.message.reply_text(f"Unknown admin command: {subcommand}\n\nUse /admin to see available commands.")
