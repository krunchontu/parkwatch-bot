"""Admin stats / lookup handlers: stats, user, zone, log."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ...database import get_db
from ...formatting import DIVIDER, format_sgt, format_sgt_short
from ...services.maintenance import is_maintenance_enabled
from ...utils import get_accuracy_indicator, get_reporter_badge
from ...zones import find_zone

logger = logging.getLogger(__name__)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    msg = f"\U0001f4ca Global Statistics Dashboard\n{DIVIDER}\n\n"

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

    maintenance = await is_maintenance_enabled()
    msg += "\U0001f6e0\ufe0f Operations\n"
    msg += f"  Maintenance mode: {'ON' if maintenance else 'OFF'}\n\n"

    msg += "\U0001f4ca Feedback\n"
    msg += f"  \U0001f44d Positive: {stats['feedback_positive']}\n"
    msg += f"  \U0001f44e Negative: {stats['feedback_negative']}\n"
    msg += f"  Overall accuracy: {accuracy_rate}\n"

    await update.message.reply_text(msg)

    # Audit log
    await db.log_admin_action(admin_id, "view_stats")


async def admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
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
        created_str = format_sgt(created_at)

    # Check ban status and warnings
    is_banned = await db.is_banned(user_id)
    warning_count = await db.get_user_warnings(user_id)

    msg = f"\U0001f464 User Details \u2014 {user_id}\n{DIVIDER}\n\n"
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
                time_str = format_sgt_short(reported_at)
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


async def admin_zone(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin zone <zone_name>."""
    if not args:
        await update.message.reply_text("Usage: /admin zone <zone_name>")
        return

    db = get_db()
    admin_id = update.effective_user.id

    zone_name = find_zone(args)
    if not zone_name:
        await update.message.reply_text(
            f"Zone not found: {args}\n\nUse exact zone names (e.g., 'Tanjong Pagar', 'Bugis')."
        )
        return

    details = await db.get_zone_details(zone_name)
    top_reporters = await db.get_zone_top_reporters(zone_name, 5)
    recent_sightings = await db.get_zone_recent_sightings(zone_name, 5)

    msg = f"\U0001f4cd Zone Details \u2014 {zone_name}\n{DIVIDER}\n\n"
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
                time_str = format_sgt_short(reported_at)
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


async def admin_log(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin log [count]."""
    db = get_db()

    limit = 20
    if args and args.isdigit():
        limit = min(int(args), 100)

    entries = await db.get_admin_log(limit)

    if not entries:
        await update.message.reply_text("\U0001f4dc Admin Log\n\nNo admin actions recorded yet.")
        return

    msg = f"\U0001f4dc Admin Log (last {len(entries)} entries)\n{DIVIDER}\n\n"

    for entry in entries:
        created_at = entry.get("created_at")
        if hasattr(created_at, "strftime"):
            time_str = format_sgt(created_at, "%m/%d %H:%M")
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
