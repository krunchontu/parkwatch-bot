"""Admin announcement handler."""

import asyncio
import contextlib
import logging

from telegram import Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes

from ...database import get_db
from ...formatting import DIVIDER
from ...zones import ZONES

logger = logging.getLogger(__name__)


async def admin_announce(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin announce all|zone|confirm."""
    if not args:
        await update.message.reply_text(
            "Usage:\n"
            "/admin announce all <message>\n"
            "/admin announce zone <zone_name> <message>\n"
            "/admin announce confirm \u2014 execute pending announcement"
        )
        return

    parts = args.split(maxsplit=1)
    subcmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    db = get_db()
    admin_id = update.effective_user.id

    # --- Execute pending announcement ---
    if subcmd == "confirm":
        pending = context.user_data.get("pending_announce")
        if not pending:
            await update.message.reply_text("No pending announcement. Use /admin announce all|zone first.")
            return

        message = pending["message"]
        recipients = pending["recipients"]
        scope = pending["scope"]

        sent = 0
        failed = 0
        blocked = []

        for uid in recipients:
            try:
                await context.bot.send_message(chat_id=uid, text=message)
                sent += 1
            except Forbidden:
                blocked.append(uid)
                failed += 1
            except Exception:
                failed += 1

            # Rate limit: ~20 messages/second
            if (sent + failed) % 20 == 0:
                await asyncio.sleep(1)

        # Clean up blocked users
        for uid in blocked:
            with contextlib.suppress(Exception):
                await db.clear_subscriptions(uid)

        # Log
        preview = pending["raw_text"][:80] + ("..." if len(pending["raw_text"]) > 80 else "")
        await db.log_admin_action(
            admin_id,
            "announce",
            target=scope,
            detail=f"sent={sent}, failed={failed}, blocked={len(blocked)}, msg={preview}",
        )

        # Clear pending
        context.user_data.pop("pending_announce", None)

        report = f"\u2705 Announcement delivered.\n\nScope: {scope}\nSent: {sent}\nFailed: {failed}"
        if blocked:
            report += f"\nBlocked users cleaned: {len(blocked)}"
        await update.message.reply_text(report)
        return

    # --- Prepare "all" announcement ---
    if subcmd == "all":
        if not rest:
            await update.message.reply_text("Usage: /admin announce all <message>")
            return

        recipients = await db.get_all_user_ids()
        scope = "all users"
        display_msg = f"\U0001f4e2 Announcement from ParkWatch SG\n{DIVIDER}\n\n{rest}"

    # --- Prepare "zone" announcement ---
    elif subcmd == "zone":
        if not rest:
            await update.message.reply_text("Usage: /admin announce zone <zone_name> <message>")
            return

        # Match zone name greedily against known zones
        rest_lower = rest.lower()
        resolved_zone = None
        msg_text = None

        for region in ZONES.values():
            for z in region["zones"]:
                if rest_lower.startswith(z.lower()):
                    remainder = rest[len(z) :].lstrip()
                    if remainder:  # must have message text after zone name
                        resolved_zone = z
                        msg_text = remainder
                        break
            if resolved_zone:
                break

        if not resolved_zone:
            await update.message.reply_text(
                "Could not parse zone name and message.\n\n"
                "Usage: /admin announce zone <zone_name> <message>\n"
                "Example: /admin announce zone Bugis Scheduled maintenance tonight"
            )
            return

        recipients = await db.get_zone_subscribers(resolved_zone)
        scope = f"zone: {resolved_zone}"
        assert msg_text is not None  # guaranteed by `if remainder:` check above
        rest = msg_text  # for raw_text storage
        display_msg = f"\U0001f4e2 Announcement \u2014 {resolved_zone}\n{DIVIDER}\n\n{msg_text}"

    else:
        await update.message.reply_text(
            "Usage:\n/admin announce all <message>\n/admin announce zone <zone_name> <message>"
        )
        return

    # Store pending and show preview
    context.user_data["pending_announce"] = {
        "message": display_msg,
        "recipients": recipients,
        "scope": scope,
        "raw_text": rest,
    }

    preview = (
        f"\U0001f4e2 Announcement Preview\n{DIVIDER}\n\n"
        f"Scope: {scope}\n"
        f"Recipients: {len(recipients)}\n\n"
        f"Message:\n{display_msg}\n\n"
        f"{DIVIDER}\n"
        f"To send, run: /admin announce confirm"
    )
    await update.message.reply_text(preview)
