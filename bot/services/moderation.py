"""Moderation utilities for ParkWatch SG."""

import functools
import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..database import get_db

logger = logging.getLogger(__name__)


_BAN_MESSAGE = "Your account has been restricted due to policy violations.\nContact the bot administrator for appeals."


def ban_check(func):
    """Decorator that blocks banned users from using a command or callback.

    Handles both message-based and callback-query-based updates.
    Banned users receive a static restriction message. Does NOT apply to /start.
    """

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        db = get_db()
        if await db.is_banned(user_id):
            if update.message is not None:
                await update.message.reply_text(_BAN_MESSAGE)
            elif update.callback_query is not None:
                await update.callback_query.answer(_BAN_MESSAGE, show_alert=True)
            return
        return await func(update, context)

    return wrapper


async def _check_auto_flag(sighting_id: str) -> None:
    """Check if a sighting should be auto-flagged after feedback update.

    Flags when negative feedback ratio exceeds 70% with at least 3 votes.
    """
    db = get_db()
    sighting = await db.get_sighting(sighting_id)
    if not sighting:
        return

    pos = sighting.get("feedback_positive", 0)
    neg = sighting.get("feedback_negative", 0)
    total = pos + neg

    if total >= 3 and neg / total > 0.7:
        await db.flag_sighting(sighting_id)
        logger.info(f"Auto-flagged sighting {sighting_id}: {neg}/{total} negative feedback")
