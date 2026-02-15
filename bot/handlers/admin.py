"""Admin command handlers for ParkWatch SG."""

import contextlib
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_USER_IDS, MAX_WARNINGS

from ..database import get_db
from ..utils import SGT, get_accuracy_indicator, get_reporter_badge
from ..zones import ZONES

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator that restricts a handler to authorized admin users.

    Unauthorized users receive a generic "Unknown command" response so as not
    to reveal that admin commands exist.
    """

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
        f"\u2022 Auto-ban after {MAX_WARNINGS} warnings (configurable via MAX_WARNINGS env var)\n"
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
}


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

    if subcommand == "help":
        return await _admin_help(update, context, args.strip() if args else None)
    elif subcommand == "stats":
        return await _admin_stats(update, context)
    elif subcommand == "user":
        return await _admin_user(update, context, args.strip())
    elif subcommand == "zone":
        return await _admin_zone(update, context, args.strip())
    elif subcommand == "log":
        return await _admin_log(update, context, args.strip())
    elif subcommand == "ban":
        return await _admin_ban(update, context, args.strip())
    elif subcommand == "unban":
        return await _admin_unban(update, context, args.strip())
    elif subcommand == "banlist":
        return await _admin_banlist(update, context)
    elif subcommand == "warn":
        return await _admin_warn(update, context, args.strip())
    elif subcommand == "delete":
        return await _admin_delete(update, context, args.strip())
    elif subcommand == "review":
        return await _admin_review(update, context)
    else:
        await update.message.reply_text(f"Unknown admin command: {subcommand}\n\nUse /admin to see available commands.")


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


async def _admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin stats — global statistics dashboard."""
    db = get_db()
    admin_id = update.effective_user.id

    stats = await db.get_global_stats()
    top_sub_zones = await db.get_top_zones_by_subscribers(5)
    top_sight_zones = await db.get_top_zones_by_sightings(5, days=7)

    # Calculate active users (union of reporters and feedback givers)
    active_users = stats["active_reporters_7d"] + stats["active_feedback_givers_7d"]
    # This is an approximation; exact dedup would require a union query

    total_feedback = stats["feedback_positive"] + stats["feedback_negative"]
    accuracy_rate = f"{stats['feedback_positive'] / total_feedback * 100:.0f}%" if total_feedback > 0 else "N/A"

    msg = "\U0001f4ca Global Statistics Dashboard\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"

    msg += "\U0001f465 Users\n"
    msg += f"  Total registered: {stats['total_users']}\n"
    msg += f"  Active (7 days): ~{active_users}\n\n"

    msg += "\U0001f6a8 Sightings\n"
    msg += f"  All-time: {stats['total_sightings']}\n"
    msg += f"  Last 24 hours: {stats['sightings_24h']}\n\n"

    msg += "\U0001f4cd Subscriptions\n"
    msg += f"  Total subscriptions: {stats['active_subscriptions']}\n"
    msg += f"  Unique subscribers: {stats['unique_subscribers']}\n\n"

    if top_sub_zones:
        msg += "\U0001f3c6 Top 5 Zones (by subscribers)\n"
        for i, z in enumerate(top_sub_zones, 1):
            msg += f"  {i}. {z['zone_name']} ({z['sub_count']} subs)\n"
        msg += "\n"

    if top_sight_zones:
        msg += "\U0001f4c8 Top 5 Zones (by sightings, 7 days)\n"
        for i, z in enumerate(top_sight_zones, 1):
            msg += f"  {i}. {z['zone']} ({z['sighting_count']} sightings)\n"
        msg += "\n"

    msg += "\U0001f4ca Feedback\n"
    msg += f"  \U0001f44d Positive: {stats['feedback_positive']}\n"
    msg += f"  \U0001f44e Negative: {stats['feedback_negative']}\n"
    msg += f"  Overall accuracy: {accuracy_rate}\n"

    await update.message.reply_text(msg)

    # Audit log
    await db.log_admin_action(admin_id, "view_stats")


async def _admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin user <id or @username>."""
    if not args:
        await update.message.reply_text("Usage: /admin user <telegram_id or @username>")
        return

    db = get_db()
    admin_id = update.effective_user.id

    # Try to look up by ID first, then by username
    user = None
    if args.isdigit():
        user = await db.get_user_details(int(args))
    elif args.startswith("@"):
        user = await db.get_user_by_username(args)
    else:
        # Try as ID, then as username
        if args.isdigit():
            user = await db.get_user_details(int(args))
        else:
            user = await db.get_user_by_username(args)

    if not user:
        await update.message.reply_text(f"User not found: {args}")
        return

    user_id = user["telegram_id"]
    username = user.get("username") or "N/A"
    report_count = user.get("report_count", 0)
    created_at = user.get("created_at")

    badge = get_reporter_badge(report_count)
    accuracy_score, total_feedback = await db.calculate_accuracy(user_id)
    accuracy_indicator = get_accuracy_indicator(accuracy_score, total_feedback)
    total_pos, total_neg = await db.get_user_feedback_totals(user_id)

    # Format created_at
    created_str = "Unknown"
    if created_at and hasattr(created_at, "strftime"):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_str = created_at.astimezone(SGT).strftime("%Y-%m-%d %I:%M %p SGT")

    # Phase 9: Check ban status and warnings
    is_banned = await db.is_banned(user_id)
    warning_count = await db.get_user_warnings(user_id)

    msg = f"\U0001f464 User Details \u2014 {user_id}\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
    msg += f"Username: @{username}\n"
    msg += f"Telegram ID: {user_id}\n"
    msg += f"Registered: {created_str}\n"
    msg += f"Reports: {report_count}\n"
    msg += f"Badge: {badge}\n"

    if total_feedback > 0:
        acc_pct = f"{accuracy_score * 100:.0f}%"
        msg += f"Accuracy: {acc_pct} {accuracy_indicator} ({total_feedback} ratings)\n"
    else:
        msg += "Accuracy: No ratings yet\n"

    msg += f"Feedback received: \U0001f44d {total_pos} / \U0001f44e {total_neg}\n"
    msg += f"Warnings: {warning_count}\n"
    status_text = "\U0001f6ab BANNED" if is_banned else "\u2705 Active"
    msg += f"Status: {status_text}\n"

    # Subscriptions
    subs = await db.get_user_subscriptions_list(user_id)
    if subs:
        msg += f"\n\U0001f4cd Subscriptions ({len(subs)}):\n"
        msg += "  " + ", ".join(subs) + "\n"
    else:
        msg += "\n\U0001f4cd Subscriptions: None\n"

    # Recent sightings
    recent = await db.get_user_recent_sightings(user_id, 10)
    if recent:
        msg += f"\n\U0001f6a8 Recent Sightings ({len(recent)}):\n"
        for s in recent:
            reported_at = s["reported_at"]
            if hasattr(reported_at, "strftime"):
                if reported_at.tzinfo is None:
                    reported_at = reported_at.replace(tzinfo=timezone.utc)
                time_str = reported_at.astimezone(SGT).strftime("%m/%d %I:%M %p")
            else:
                time_str = str(reported_at)
            desc = s.get("description") or "No description"
            msg += f"  \u2022 {s['zone']} \u2014 {time_str}\n"
            msg += f"    {desc} (\U0001f44d{s['feedback_positive']}/\U0001f44e{s['feedback_negative']})\n"
    else:
        msg += "\n\U0001f6a8 Recent Sightings: None\n"

    await update.message.reply_text(msg)

    # Audit log
    await db.log_admin_action(admin_id, "lookup_user", target=str(user_id))


async def _admin_zone(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin zone <zone_name>."""
    if not args:
        await update.message.reply_text("Usage: /admin zone <zone_name>")
        return

    db = get_db()
    admin_id = update.effective_user.id

    # Validate zone exists
    zone_name = args
    zone_exists = False
    for region in ZONES.values():
        if zone_name in region["zones"]:
            zone_exists = True
            break

    if not zone_exists:
        # Try case-insensitive match
        for region in ZONES.values():
            for z in region["zones"]:
                if z.lower() == zone_name.lower():
                    zone_name = z
                    zone_exists = True
                    break
            if zone_exists:
                break

    if not zone_exists:
        await update.message.reply_text(
            f"Zone not found: {args}\n\nUse exact zone names (e.g., 'Tanjong Pagar', 'Bugis')."
        )
        return

    details = await db.get_zone_details(zone_name)
    top_reporters = await db.get_zone_top_reporters(zone_name, 5)
    recent_sightings = await db.get_zone_recent_sightings(zone_name, 5)

    msg = f"\U0001f4cd Zone Details \u2014 {zone_name}\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
    msg += f"Subscribers: {details['subscriber_count']}\n\n"

    msg += "\U0001f6a8 Sightings\n"
    msg += f"  Last 24h: {details['sightings_24h']}\n"
    msg += f"  Last 7 days: {details['sightings_7d']}\n"
    msg += f"  All-time: {details['sightings_all']}\n"

    if top_reporters:
        msg += f"\n\U0001f3c6 Top Reporters ({len(top_reporters)})\n"
        for i, r in enumerate(top_reporters, 1):
            name = r.get("reporter_name") or "Unknown"
            msg += f"  {i}. {name} ({r['report_count']} reports)\n"

    if recent_sightings:
        msg += f"\n\U0001f4cb Recent Sightings ({len(recent_sightings)})\n"
        for s in recent_sightings:
            reported_at = s["reported_at"]
            if hasattr(reported_at, "strftime"):
                if reported_at.tzinfo is None:
                    reported_at = reported_at.replace(tzinfo=timezone.utc)
                time_str = reported_at.astimezone(SGT).strftime("%m/%d %I:%M %p")
            else:
                time_str = str(reported_at)
            desc = s.get("description") or "No description"
            msg += f"  \u2022 {time_str} \u2014 {desc}\n"
            msg += f"    \U0001f44d{s['feedback_positive']}/\U0001f44e{s['feedback_negative']}\n"
    else:
        msg += "\n\U0001f4cb Recent Sightings: None\n"

    await update.message.reply_text(msg)

    # Audit log
    await db.log_admin_action(admin_id, "lookup_zone", target=zone_name)


async def _admin_log(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin log [count]."""
    db = get_db()

    limit = 20
    if args and args.isdigit():
        limit = min(int(args), 100)

    entries = await db.get_admin_log(limit)

    if not entries:
        await update.message.reply_text("\U0001f4dc Admin Log\n\nNo admin actions recorded yet.")
        return

    msg = f"\U0001f4dc Admin Log (last {len(entries)} entries)\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"

    for entry in entries:
        created_at = entry.get("created_at")
        if hasattr(created_at, "strftime"):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            time_str = created_at.astimezone(SGT).strftime("%m/%d %H:%M")
        else:
            time_str = str(created_at)

        action = entry.get("action", "unknown")
        target = entry.get("target")
        detail = entry.get("detail")
        admin_id = entry.get("admin_id")

        line = f"[{time_str}] {action}"
        if target:
            line += f" \u2192 {target}"
        if detail:
            line += f" ({detail})"
        line += f" (by {admin_id})"
        msg += line + "\n"

    await update.message.reply_text(msg)


async def _admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin ban <user_id> [reason]."""
    if not args:
        await update.message.reply_text("Usage: /admin ban <user_id> [reason]")
        return

    db = get_db()
    admin_id = update.effective_user.id

    parts = args.split(maxsplit=1)
    target_str = parts[0]
    reason = parts[1] if len(parts) > 1 else None

    if not target_str.isdigit():
        await update.message.reply_text("User ID must be a number.\nUsage: /admin ban <user_id> [reason]")
        return

    target_id = int(target_str)

    # Prevent banning admins
    if target_id in ADMIN_USER_IDS:
        await update.message.reply_text("Cannot ban an admin user.")
        return

    # Check if already banned
    if await db.is_banned(target_id):
        await update.message.reply_text(f"User {target_id} is already banned.")
        return

    # Execute ban
    await db.ban_user(target_id, admin_id, reason)

    # Log action
    detail = f"reason: {reason}" if reason else None
    await db.log_admin_action(admin_id, "ban_user", target=str(target_id), detail=detail)

    # Notify the banned user
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="Your account has been restricted due to policy violations.\n"
            "Contact the bot administrator for appeals.",
        )
    except Exception:
        logger.warning(f"Could not notify banned user {target_id}")

    reason_msg = f"\nReason: {reason}" if reason else ""
    await update.message.reply_text(f"\U0001f6ab User {target_id} has been banned.{reason_msg}\nSubscriptions cleared.")


async def _admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin unban <user_id>."""
    if not args:
        await update.message.reply_text("Usage: /admin unban <user_id>")
        return

    db = get_db()
    admin_id = update.effective_user.id

    if not args.isdigit():
        await update.message.reply_text("User ID must be a number.\nUsage: /admin unban <user_id>")
        return

    target_id = int(args)

    was_banned = await db.unban_user(target_id)
    if not was_banned:
        await update.message.reply_text(f"User {target_id} is not currently banned.")
        return

    # Reset warnings on unban
    await db.reset_warnings(target_id)

    # Log action
    await db.log_admin_action(admin_id, "unban_user", target=str(target_id))

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="Your account restriction has been lifted. You can use the bot again.\n"
            "Use /start to set up your zones.",
        )
    except Exception:
        logger.warning(f"Could not notify unbanned user {target_id}")

    await update.message.reply_text(f"\u2705 User {target_id} has been unbanned. Warnings reset.")


async def _admin_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin banlist."""
    db = get_db()
    admin_id = update.effective_user.id

    banned = await db.get_banned_users()

    if not banned:
        await update.message.reply_text("\U0001f6ab Ban List\n\nNo users are currently banned.")
        return

    msg = f"\U0001f6ab Ban List ({len(banned)} user(s))\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"

    for entry in banned:
        banned_at = entry.get("banned_at")
        if hasattr(banned_at, "strftime"):
            if banned_at.tzinfo is None:
                banned_at = banned_at.replace(tzinfo=timezone.utc)
            time_str = banned_at.astimezone(SGT).strftime("%Y-%m-%d %I:%M %p SGT")
        else:
            time_str = str(banned_at)

        reason = entry.get("reason") or "No reason given"
        msg += f"\u2022 {entry['telegram_id']}\n"
        msg += f"  Banned: {time_str}\n"
        msg += f"  By: {entry['banned_by']}\n"
        msg += f"  Reason: {reason}\n\n"

    await update.message.reply_text(msg)

    await db.log_admin_action(admin_id, "view_banlist")


async def _admin_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin warn <user_id> [message]."""
    if not args:
        await update.message.reply_text("Usage: /admin warn <user_id> [message]")
        return

    db = get_db()
    admin_id = update.effective_user.id

    parts = args.split(maxsplit=1)
    target_str = parts[0]
    warning_message = parts[1] if len(parts) > 1 else "You have received a warning for violating community guidelines."

    if not target_str.isdigit():
        await update.message.reply_text("User ID must be a number.\nUsage: /admin warn <user_id> [message]")
        return

    target_id = int(target_str)

    # Ensure user exists
    user = await db.get_user_details(target_id)
    if not user:
        await update.message.reply_text(f"User not found: {target_id}")
        return

    # Increment warning count
    new_count = await db.increment_warnings(target_id)

    # Log action
    await db.log_admin_action(
        admin_id, "warn_user", target=str(target_id), detail=f"warning {new_count}: {warning_message[:100]}"
    )

    # Send warning to user
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"\u26a0\ufe0f Warning from ParkWatch SG\n\n{warning_message}\n\n"
            f"This is warning {new_count} of {MAX_WARNINGS}. "
            f"Repeated violations may result in a ban.",
        )
        notified = True
    except Exception:
        logger.warning(f"Could not notify warned user {target_id}")
        notified = False

    # Check auto-ban escalation
    if MAX_WARNINGS > 0 and new_count >= MAX_WARNINGS:
        await db.ban_user(target_id, admin_id, reason=f"Auto-ban: {new_count} warnings reached")
        await db.log_admin_action(
            admin_id, "auto_ban", target=str(target_id), detail=f"Warning count reached {MAX_WARNINGS}"
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                chat_id=target_id,
                text="Your account has been restricted due to repeated violations.\n"
                "Contact the bot administrator for appeals.",
            )
        await update.message.reply_text(
            f"\u26a0\ufe0f Warning {new_count} sent to user {target_id}.\n"
            f"\U0001f6ab AUTO-BAN triggered ({new_count}/{MAX_WARNINGS} warnings). User has been banned."
        )
    else:
        notify_status = "Notification sent." if notified else "Could not notify user."
        await update.message.reply_text(
            f"\u26a0\ufe0f Warning {new_count}/{MAX_WARNINGS} sent to user {target_id}.\n{notify_status}"
        )


async def _admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin delete <sighting_id> [confirm]."""
    if not args:
        await update.message.reply_text("Usage: /admin delete <sighting_id> [confirm]")
        return

    db = get_db()
    admin_id = update.effective_user.id

    parts = args.split(maxsplit=1)
    sighting_id = parts[0]
    confirm = len(parts) > 1 and parts[1].lower() == "confirm"

    # Look up the sighting
    sighting = await db.get_sighting(sighting_id)
    if not sighting:
        await update.message.reply_text(f"Sighting not found: {sighting_id}")
        return

    if not confirm:
        # Show details and ask for confirmation
        reported_at = sighting["reported_at"]
        if hasattr(reported_at, "strftime"):
            if reported_at.tzinfo is None:
                reported_at = reported_at.replace(tzinfo=timezone.utc)
            time_str = reported_at.astimezone(SGT).strftime("%Y-%m-%d %I:%M %p SGT")
        else:
            time_str = str(reported_at)

        desc = sighting.get("description") or "No description"
        pos = sighting.get("feedback_positive", 0)
        neg = sighting.get("feedback_negative", 0)

        msg = "\U0001f5d1\ufe0f Delete Sighting \u2014 Confirmation Required\n"
        msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        msg += f"ID: {sighting_id}\n"
        msg += f"Zone: {sighting['zone']}\n"
        msg += f"Time: {time_str}\n"
        msg += f"Description: {desc}\n"
        msg += f"Reporter: {sighting.get('reporter_name', 'Unknown')} ({sighting['reporter_id']})\n"
        msg += f"Feedback: \U0001f44d {pos} / \U0001f44e {neg}\n"
        msg += f"\nTo confirm deletion, run:\n/admin delete {sighting_id} confirm"

        await update.message.reply_text(msg)
        return

    # Execute deletion
    deleted = await db.delete_sighting(sighting_id)
    if not deleted:
        await update.message.reply_text(f"Sighting not found: {sighting_id}")
        return

    # Log action
    await db.log_admin_action(
        admin_id,
        "delete_sighting",
        target=sighting_id,
        detail=f"zone={deleted['zone']}, reporter={deleted['reporter_id']}",
    )

    await update.message.reply_text(f"\U0001f5d1\ufe0f Sighting {sighting_id} has been deleted.\nZone: {deleted['zone']}")


async def _admin_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin review — show moderation queue of flagged sightings."""
    db = get_db()
    admin_id = update.effective_user.id

    flagged = await db.get_flagged_sightings(20)
    low_accuracy = await db.get_low_accuracy_reporters(max_accuracy=0.5, min_feedback=5)

    if not flagged and not low_accuracy:
        await update.message.reply_text("\U0001f4cb Moderation Queue\n\nNo items require review.")
        return

    msg = "\U0001f4cb Moderation Queue\n"
    msg += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"

    if flagged:
        msg += f"\n\U0001f6a9 Flagged Sightings ({len(flagged)})\n\n"
        for s in flagged[:10]:  # Limit to 10 for message size
            reported_at = s["reported_at"]
            if hasattr(reported_at, "strftime"):
                if reported_at.tzinfo is None:
                    reported_at = reported_at.replace(tzinfo=timezone.utc)
                time_str = reported_at.astimezone(SGT).strftime("%m/%d %I:%M %p")
            else:
                time_str = str(reported_at)

            desc = s.get("description") or "No description"
            pos = s.get("feedback_positive", 0)
            neg = s.get("feedback_negative", 0)
            total = pos + neg

            msg += f"\u2022 {s['zone']} \u2014 {time_str}\n"
            msg += f"  ID: {s['id'][:12]}...\n"
            msg += f"  {desc[:50]}\n"
            msg += f"  Reporter: {s.get('reporter_name', '?')} ({s['reporter_id']})\n"
            msg += f"  Feedback: \U0001f44d {pos} / \U0001f44e {neg}"
            if total > 0:
                msg += f" ({neg / total * 100:.0f}% negative)"
            msg += "\n\n"

    if low_accuracy:
        msg += f"\n\u26a0\ufe0f Low-Accuracy Reporters ({len(low_accuracy)})\n\n"
        for r in low_accuracy[:10]:
            msg += f"\u2022 User {r['reporter_id']}: {r['accuracy'] * 100:.0f}% accuracy "
            msg += f"(\U0001f44d{r['total_positive']}/\U0001f44e{r['total_negative']}, {r['sighting_count']} sightings)\n"

    msg += "\nUse /admin delete <id> confirm to remove a sighting."
    msg += "\nUse /admin ban <user_id> [reason] to ban a user."
    msg += "\nUse /admin warn <user_id> [message] to warn a user."

    await update.message.reply_text(msg)

    await db.log_admin_action(admin_id, "view_review_queue")
