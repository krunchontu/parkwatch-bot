"""Moderation utilities for ParkWatch SG."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..database import get_db

logger = logging.getLogger(__name__)


def ban_check(func):
    """Decorator that blocks banned users from using a command.

    Banned users receive a static restriction message. Does NOT apply to /start.
    """

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        db = get_db()
        if await db.is_banned(user_id):
            await update.message.reply_text(
                "Your account has been restricted due to policy violations.\nContact the bot administrator for appeals."
            )
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
