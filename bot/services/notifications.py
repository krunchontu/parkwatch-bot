"""Notification services for ParkWatch SG."""

import asyncio
import logging

from telegram.error import Forbidden, RetryAfter, TimedOut

from ..database import get_db

logger = logging.getLogger(__name__)

# Maximum concurrent outgoing messages
_MAX_CONCURRENCY = 20


async def _send_one(bot, uid, text, reply_markup, semaphore, retries=3):
    """Send a single message with bounded concurrency and exponential backoff.

    Uses exponential backoff (1s, 2s, 4s) on transient (non-RetryAfter) failures.
    Returns ("sent", uid), ("blocked", uid), or ("failed", uid).
    """
    async with semaphore:
        for attempt in range(1 + retries):
            try:
                await bot.send_message(chat_id=uid, text=text, reply_markup=reply_markup)
                return "sent", uid
            except Forbidden:
                return "blocked", uid
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
                continue
            except (TimedOut, OSError) as e:
                if attempt < retries:
                    backoff = 2**attempt  # 1s, 2s, 4s
                    logger.debug(
                        "Transient failure sending to %d (attempt %d), retrying in %ds: %s",
                        uid,
                        attempt + 1,
                        backoff,
                        e,
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Failed to send alert to %d after %d retries: %s", uid, retries, e)
                return "failed", uid
            except Exception as e:
                logger.error("Failed to send alert to %d: %s", uid, e)
                return "failed", uid
    return "failed", uid


async def broadcast_alert(bot, zone_name, alert_msg, feedback_keyboard, reporter_id):
    """Send alert to all zone subscribers except the reporter.

    Uses bounded concurrency (semaphore) and 1-retry on transient errors.
    Returns (sent_count, failed_count, blocked_users).
    Cleans up subscriptions for users who have blocked the bot.
    """
    db = get_db()
    subscribers = await db.get_zone_subscribers(zone_name)
    targets = [uid for uid in subscribers if uid != reporter_id]

    if not targets:
        return 0, 0, []

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    tasks = [_send_one(bot, uid, alert_msg, feedback_keyboard, semaphore) for uid in targets]
    results = await asyncio.gather(*tasks)

    sent_count = 0
    failed_count = 0
    blocked_users = []
    for status, uid in results:
        if status == "sent":
            sent_count += 1
        elif status == "blocked":
            blocked_users.append(uid)
            failed_count += 1
        else:
            failed_count += 1

    # Clean up subscriptions for users who blocked the bot
    for uid in blocked_users:
        try:
            await db.clear_subscriptions(uid)
        except Exception as e:
            logger.error("Failed to clean up subscriptions for blocked user %d: %s", uid, e)

    return sent_count, failed_count, blocked_users


async def broadcast_message(bot, recipients, text, *, reply_markup=None):
    """Send a message to a list of recipients with bounded concurrency + retry.

    Returns (sent_count, failed_count, blocked_users).
    """
    if not recipients:
        return 0, 0, []

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    tasks = [_send_one(bot, uid, text, reply_markup, semaphore) for uid in recipients]
    results = await asyncio.gather(*tasks)

    sent_count = 0
    failed_count = 0
    blocked_users = []
    for status, uid in results:
        if status == "sent":
            sent_count += 1
        elif status == "blocked":
            blocked_users.append(uid)
            failed_count += 1
        else:
            failed_count += 1

    return sent_count, failed_count, blocked_users
