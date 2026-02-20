"""Admin config and maintenance handlers."""

import contextlib
import logging

from telegram import Update
from telegram.ext import ContextTypes

from ...database import get_db
from ...services.runtime_settings import RuntimeSettingsError, get_runtime_settings

logger = logging.getLogger(__name__)


async def admin_config(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin config operations."""
    db = get_db()
    admin_id = update.effective_user.id
    settings = get_runtime_settings()

    if not args:
        rows = await settings.list_effective()
        msg = "\u2699\ufe0f Runtime Settings\n\n"
        for row in rows:
            msg += f"{row['key']} = {row['value']} ({row['source']})\n"
        await update.message.reply_text(msg)
        await db.log_admin_action(admin_id, "config_list")
        return

    parts = args.split(maxsplit=2)
    if parts[0].lower() == "reset":
        if len(parts) < 2:
            await update.message.reply_text("Usage: /admin config reset <KEY>")
            return
        key = parts[1].strip().upper()
        try:
            old_value = await settings.get(key)
            default_value = await settings.reset_override(key, actor_id=admin_id)
        except RuntimeSettingsError as exc:
            await update.message.reply_text(str(exc))
            return
        detail = f"{key}: {old_value} -> {default_value}"
        await db.log_admin_action(admin_id, "config_reset", target=key, detail=detail)
        await update.message.reply_text(f"\u2705 Reset {key}. Effective value: {default_value}")
        return

    if len(parts) < 2:
        await update.message.reply_text("Usage: /admin config <KEY> <VALUE>")
        return

    key = parts[0].strip().upper()
    value = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]

    try:
        old_value, new_value = await settings.set_override(key, value, admin_id)
    except RuntimeSettingsError as exc:
        await update.message.reply_text(str(exc))
        return

    detail = f"{key}: {old_value} -> {new_value}"
    await db.log_admin_action(admin_id, "config_set", target=key, detail=detail)
    await update.message.reply_text(f"\u2705 Updated {key}: {old_value} \u2192 {new_value}")


async def admin_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE, args: str):
    """Handle /admin maintenance on|off [message]."""
    db = get_db()
    admin_id = update.effective_user.id
    settings = get_runtime_settings()

    if not args:
        await update.message.reply_text("Usage: /admin maintenance on [message]\n/admin maintenance off")
        return

    parts = args.split(maxsplit=1)
    action = parts[0].lower()

    if action == "off":
        await settings.set_override("MAINTENANCE_MODE", "false", admin_id)
        await db.log_admin_action(admin_id, "maintenance_off", detail="mode=false")
        await update.message.reply_text("\u2705 Maintenance mode disabled.")
        return

    if action != "on":
        await update.message.reply_text("Usage: /admin maintenance on [message]\n/admin maintenance off")
        return

    message = parts[1].strip() if len(parts) > 1 else ""
    announce_prefix = "--announce "

    if message.lower() == "confirm":
        pending = context.user_data.pop("pending_maintenance_announce", None)
        if not pending:
            await update.message.reply_text("No pending maintenance announcement.")
            return
        sent = 0
        for uid in pending["recipient_ids"]:
            with contextlib.suppress(Exception):
                await context.bot.send_message(chat_id=uid, text=f"\U0001f4e3 {pending['message']}")
                sent += 1
        await settings.set_override("MAINTENANCE_MODE", "true", admin_id)
        await settings.set_override("MAINTENANCE_MESSAGE", pending["message"], admin_id)
        await db.log_admin_action(admin_id, "maintenance_on", detail=f"announce_sent={sent}")
        await update.message.reply_text(f"\u2705 Maintenance mode enabled. Announcement sent to {sent} users.")
        return

    if message.startswith(announce_prefix):
        ann_message = message[len(announce_prefix) :].strip()
        if not ann_message:
            await update.message.reply_text("Usage: /admin maintenance on --announce <message>")
            return
        recipients = await db.get_all_user_ids()
        context.user_data["pending_maintenance_announce"] = {
            "message": ann_message,
            "recipient_ids": recipients,
        }
        await update.message.reply_text(
            f"\U0001f4e3 Maintenance announcement preview\nRecipients: {len(recipients)}\n\n{ann_message}\n\n"
            "Run /admin maintenance on confirm to broadcast and enable maintenance."
        )
        return

    if message:
        await settings.set_override("MAINTENANCE_MESSAGE", message, admin_id)
    await settings.set_override("MAINTENANCE_MODE", "true", admin_id)
    await db.log_admin_action(admin_id, "maintenance_on", detail=f"message={message[:120] if message else ''}")
    await update.message.reply_text("\u2705 Maintenance mode enabled.")
