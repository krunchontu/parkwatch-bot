"""Admin data management handlers: purge, export."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ...database import get_db
from ...zones import find_zone

logger = logging.getLogger(__name__)


async def admin_purge(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin purge commands with preview + confirm flow."""
    db = get_db()
    admin_id = update.effective_user.id
    if not args:
        await update.message.reply_text(
            "Usage:\n/admin purge sightings [days]\n/admin purge sightings zone <zone> [days]\n/admin purge user <user_id>"
        )
        return

    if args.strip().lower() == "confirm":
        pending = context.user_data.pop("pending_purge", None)
        if not pending:
            await update.message.reply_text("No pending purge operation.")
            return
        if pending["type"] == "sightings":
            deleted = await db.purge_sightings_older_than(pending["days"], zone=pending.get("zone"))
            await db.log_admin_action(
                admin_id,
                "purge_sightings",
                detail=f"days={pending['days']}, zone={pending.get('zone')}, deleted={deleted}",
            )
            await update.message.reply_text(f"\U0001f5d1\ufe0f Purged {deleted} sightings.")
            return
        if pending["type"] == "user":
            result = await db.purge_user_data(pending["user_id"])
            await db.log_admin_action(
                admin_id,
                "purge_user",
                target=str(pending["user_id"]),
                detail=f"feedback_given_deleted={result['feedback_given_deleted']}",
            )
            await update.message.reply_text(f"\U0001f5d1\ufe0f Purged user {pending['user_id']} data.")
            return

    parts = args.split()
    if parts[0].lower() == "sightings":
        zone = None
        days = 30
        if len(parts) >= 2 and parts[1].lower() == "zone":
            if len(parts) < 3:
                await update.message.reply_text("Usage: /admin purge sightings zone <zone_name> [days]")
                return
            resolved = find_zone(parts[2])
            if not resolved:
                await update.message.reply_text(
                    f"Zone not found: {parts[2]}\n\nUse exact zone names (e.g., 'Tanjong Pagar', 'Bugis')."
                )
                return
            zone = resolved
            if len(parts) >= 4 and parts[3].isdigit():
                days = int(parts[3])
        elif len(parts) >= 2 and parts[1].isdigit():
            days = int(parts[1])

        context.user_data["pending_purge"] = {"type": "sightings", "zone": zone, "days": days}
        scope = f"zone={zone}" if zone else "all zones"
        await update.message.reply_text(
            f"\u26a0\ufe0f Preview: purge sightings older than {days} day(s) in {scope}.\nRun /admin purge confirm to execute."
        )
        return

    if parts[0].lower() == "user":
        if len(parts) < 2 or not parts[1].isdigit():
            await update.message.reply_text("Usage: /admin purge user <user_id>")
            return
        user_id = int(parts[1])
        context.user_data["pending_purge"] = {"type": "user", "user_id": user_id}
        await update.message.reply_text(
            f"\u26a0\ufe0f Preview: purge all data for user {user_id}.\nRun /admin purge confirm to execute."
        )
        return

    await update.message.reply_text(
        "Usage:\n/admin purge sightings [days]\n/admin purge sightings zone <zone> [days]\n/admin purge user <user_id>"
    )


async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin export stats [csv|json] with preview + confirm."""
    db = get_db()
    admin_id = update.effective_user.id
    parts = args.split()
    if not parts or parts[0].lower() != "stats":
        await update.message.reply_text("Usage: /admin export stats [csv|json]")
        return

    format_type = "csv"
    if len(parts) > 1:
        format_type = parts[1].lower()
        if format_type not in {"csv", "json"}:
            await update.message.reply_text("Format must be csv or json.")
            return

    if len(parts) > 2 and parts[2].lower() == "confirm":
        data = await db.export_stats(format_type)
        await db.log_admin_action(admin_id, "export_stats", detail=f"format={format_type}")
        await update.message.reply_text(
            f"\U0001f4e4 Export ({format_type.upper()}):\n<pre>{data[:3500]}</pre>", parse_mode="HTML"
        )
        return

    await update.message.reply_text(
        f"Preview: export non-PII stats in {format_type.upper()} format.\n"
        f"Run /admin export stats {format_type} confirm to generate."
    )
