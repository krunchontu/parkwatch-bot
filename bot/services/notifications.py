"""Notification services for ParkWatch SG."""

import logging

from telegram.error import Forbidden

from ..database import get_db

logger = logging.getLogger(__name__)


async def broadcast_alert(bot, zone_name, alert_msg, feedback_keyboard, reporter_id):
    """Send alert to all zone subscribers except the reporter.

    Returns (sent_count, failed_count, blocked_users).
    Cleans up subscriptions for users who have blocked the bot.
    """
    db = get_db()
    subscribers = await db.get_zone_subscribers(zone_name)
    sent_count = 0
    failed_count = 0
    blocked_users = []

    for uid in subscribers:
        if uid == reporter_id:
            continue
        try:
            await bot.send_message(chat_id=uid, text=alert_msg, reply_markup=feedback_keyboard)
            sent_count += 1
        except Forbidden:
            logger.warning(f"User {uid} blocked the bot \u2014 removing subscriptions")
            blocked_users.append(uid)
            failed_count += 1
        except Exception as e:
            logger.error(f"Failed to send alert to {uid}: {e}")
            failed_count += 1

    # Clean up subscriptions for users who blocked the bot
    for uid in blocked_users:
        try:
            await db.clear_subscriptions(uid)
        except Exception as e:
            logger.error(f"Failed to clean up subscriptions for blocked user {uid}: {e}")

    return sent_count, failed_count, blocked_users
