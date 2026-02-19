"""Admin moderation handlers: ban, unban, banlist, warn, delete, review."""

import contextlib
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_USER_IDS

from ...database import get_db
from ...formatting import DIVIDER, format_sgt, format_sgt_short
from ...services.runtime_settings import get_runtime_settings
from ...utils import get_accuracy_indicator

logger = logging.getLogger(__name__)


async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
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


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
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


async def admin_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin banlist."""
    db = get_db()
    admin_id = update.effective_user.id

    banned = await db.get_banned_users()

    if not banned:
        await update.message.reply_text("\U0001f6ab Ban List\n\nNo users are currently banned.")
        return

    msg = f"\U0001f6ab Ban List ({len(banned)} user(s))\n{DIVIDER}\n\n"

    for entry in banned:
        banned_at = entry.get("banned_at")
        if hasattr(banned_at, "strftime"):
            time_str = format_sgt(banned_at)
        else:
            time_str = str(banned_at)

        reason = entry.get("reason") or "No reason given"
        msg += f"\u2022 {entry['telegram_id']}\n"
        msg += f"  Banned: {time_str}\n"
        msg += f"  By: {entry['banned_by']}\n"
        msg += f"  Reason: {reason}\n\n"

    await update.message.reply_text(msg)

    await db.log_admin_action(admin_id, "view_banlist")


async def admin_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
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

    max_warnings = await get_runtime_settings().get("MAX_WARNINGS")

    # Send warning to user
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"\u26a0\ufe0f Warning from ParkWatch SG\n\n{warning_message}\n\n"
            f"This is warning {new_count} of {max_warnings}. "
            f"Repeated violations may result in a ban.",
        )
        notified = True
    except Exception:
        logger.warning(f"Could not notify warned user {target_id}")
        notified = False

    # Check auto-ban escalation
    if max_warnings > 0 and new_count >= max_warnings:
        await db.ban_user(target_id, admin_id, reason=f"Auto-ban: {new_count} warnings reached")
        await db.log_admin_action(
            admin_id, "auto_ban", target=str(target_id), detail=f"Warning count reached {max_warnings}"
        )
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                chat_id=target_id,
                text="Your account has been restricted due to repeated violations.\n"
                "Contact the bot administrator for appeals.",
            )
        await update.message.reply_text(
            f"\u26a0\ufe0f Warning {new_count} sent to user {target_id}.\n"
            f"\U0001f6ab AUTO-BAN triggered ({new_count}/{max_warnings} warnings). User has been banned."
        )
    else:
        notify_status = "Notification sent." if notified else "Could not notify user."
        await update.message.reply_text(
            f"\u26a0\ufe0f Warning {new_count}/{max_warnings} sent to user {target_id}.\n{notify_status}"
        )


async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
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
            time_str = format_sgt(reported_at)
        else:
            time_str = str(reported_at)

        desc = sighting.get("description") or "No description"
        pos = sighting.get("feedback_positive", 0)
        neg = sighting.get("feedback_negative", 0)

        msg = f"\U0001f5d1\ufe0f Delete Sighting \u2014 Confirmation Required\n{DIVIDER}\n\n"
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

    await update.message.reply_text(
        f"\U0001f5d1\ufe0f Sighting {sighting_id} has been deleted.\nZone: {deleted['zone']}"
    )


async def admin_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin review — show moderation queue of flagged sightings."""
    db = get_db()
    admin_id = update.effective_user.id

    flagged = await db.get_flagged_sightings(20)
    low_accuracy = await db.get_low_accuracy_reporters(max_accuracy=0.5, min_feedback=5)

    if not flagged and not low_accuracy:
        await update.message.reply_text("\U0001f4cb Moderation Queue\n\nNo items require review.")
        return

    msg = f"\U0001f4cb Moderation Queue\n{DIVIDER}\n"

    if flagged:
        msg += f"\n\U0001f6a9 Flagged Sightings ({len(flagged)})\n\n"
        for s in flagged[:10]:  # Limit to 10 for message size
            reported_at = s["reported_at"]
            if hasattr(reported_at, "strftime"):
                time_str = format_sgt_short(reported_at)
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
            msg += (
                f"(\U0001f44d{r['total_positive']}/\U0001f44e{r['total_negative']}, {r['sighting_count']} sightings)\n"
            )

    msg += "\nUse /admin delete <id> confirm to remove a sighting."
    msg += "\nUse /admin ban <user_id> [reason] to ban a user."
    msg += "\nUse /admin warn <user_id> [message] to warn a user."

    await update.message.reply_text(msg)

    await db.log_admin_action(admin_id, "view_review_queue")
