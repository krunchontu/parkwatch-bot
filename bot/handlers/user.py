"""User command handlers for ParkWatch SG."""

import logging
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_USER_IDS

from ..database import get_db
from ..services.moderation import ban_check
from ..ui.keyboards import build_zone_keyboard
from ..utils import get_accuracy_indicator, get_reporter_badge
from ..zones import ZONES

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [[InlineKeyboardButton(region["name"], callback_data=f"region_{key}")] for key, region in ZONES.items()]

    await update.message.reply_text(
        "Welcome to ParkWatch SG! \U0001f697\n\n"
        "I'll alert you when parking wardens are spotted nearby.\n\n"
        "To get started, which areas do you want alerts for?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_region_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle region button click."""
    query = update.callback_query
    await query.answer()

    region_key = query.data.replace("region_", "")
    region = ZONES.get(region_key)

    if not region:
        return

    user_id = update.effective_user.id
    context.user_data["current_region"] = region_key

    await query.edit_message_text(
        f"Select zones in {region['name']}:\n\n(Tap to subscribe/unsubscribe, then tap Done)",
        reply_markup=await build_zone_keyboard(region_key, user_id),
    )


async def handle_zone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle zone button click - toggle subscription."""
    query = update.callback_query

    zone_name = query.data.replace("zone_", "")
    user_id = update.effective_user.id

    db = get_db()
    current_zones = await db.get_subscriptions(user_id)

    # Toggle subscription
    if zone_name in current_zones:
        await db.remove_subscription(user_id, zone_name)
        await query.answer(f"\u274c Unsubscribed from {zone_name}")
    else:
        await db.add_subscription(user_id, zone_name)
        await query.answer(f"\u2705 Subscribed to {zone_name}")

    # Rebuild keyboard to show updated status (keeps keyboard open)
    region_key = context.user_data.get("current_region")
    if not region_key:
        # Fallback: find which region this zone belongs to
        for key, region in ZONES.items():
            if zone_name in region["zones"]:
                region_key = key
                break

    if region_key and region_key in ZONES:
        await query.edit_message_text(
            f"Select zones in {ZONES[region_key]['name']}:\n\n(Tap to subscribe/unsubscribe, then tap Done)",
            reply_markup=await build_zone_keyboard(region_key, user_id),
        )


async def handle_zone_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Done button from zone selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    context.user_data.pop("current_region", None)

    subs = await get_db().get_subscriptions(user_id)
    if subs:
        sub_list = ", ".join(sorted(subs))
        await query.edit_message_text(
            f"\u2705 Subscribed to {len(subs)} zone(s): {sub_list}\n\n"
            f"Use /subscribe to modify zones.\n"
            f"Use /report to report a warden sighting."
        )
    else:
        await query.edit_message_text("You're not subscribed to any zones yet.\nUse /start to select zones.")


async def handle_back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to region selection."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton(region["name"], callback_data=f"region_{key}")] for key, region in ZONES.items()]

    await query.edit_message_text("Which areas do you want alerts for?", reply_markup=InlineKeyboardMarkup(keyboard))


@ban_check
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command."""
    keyboard = [[InlineKeyboardButton(region["name"], callback_data=f"region_{key}")] for key, region in ZONES.items()]

    await update.message.reply_text("Which areas do you want to add?", reply_markup=InlineKeyboardMarkup(keyboard))


@ban_check
async def myzones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myzones command."""
    user_id = update.effective_user.id
    subs = await get_db().get_subscriptions(user_id)

    if subs:
        sub_list = "\n".join(f"\u2022 {z}" for z in sorted(subs))
        await update.message.reply_text(
            f"\U0001f4cd Your subscribed zones:\n\n{sub_list}\n\nUse /subscribe to add more.\nUse /unsubscribe to remove zones."
        )
    else:
        await update.message.reply_text("You're not subscribed to any zones yet.\nUse /start to select zones.")


@ban_check
async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command."""
    user_id = update.effective_user.id
    subs = await get_db().get_subscriptions(user_id)

    if not subs:
        await update.message.reply_text("You're not subscribed to any zones yet.\nUse /start to select zones first.")
        return

    # Build keyboard with current subscriptions
    keyboard = []
    for zone in sorted(subs):
        keyboard.append([InlineKeyboardButton(f"\u274c {zone}", callback_data=f"unsub_{zone}")])
    keyboard.append([InlineKeyboardButton("\U0001f5d1\ufe0f Unsubscribe from ALL", callback_data="unsub_all")])
    keyboard.append([InlineKeyboardButton("\u2705 Done", callback_data="unsub_done")])

    await update.message.reply_text(
        f"\U0001f4cd Your subscribed zones ({len(subs)}):\n\nTap a zone to unsubscribe:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_unsubscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unsubscribe button clicks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data
    db = get_db()

    if data == "unsub_done":
        subs = await db.get_subscriptions(user_id)
        if subs:
            await query.edit_message_text(
                f"\u2705 Done! You're subscribed to {len(subs)} zone(s):\n{', '.join(sorted(subs))}"
            )
        else:
            await query.edit_message_text("You've unsubscribed from all zones.\nUse /start to subscribe again.")
        return

    if data == "unsub_all":
        await db.clear_subscriptions(user_id)
        await query.edit_message_text("\U0001f5d1\ufe0f Unsubscribed from all zones.\n\nUse /start to subscribe to new zones.")
        return

    # Single zone unsubscribe
    zone_name = data.replace("unsub_", "")
    await db.remove_subscription(user_id, zone_name)

    # Rebuild keyboard with remaining subscriptions
    subs = await db.get_subscriptions(user_id)

    if not subs:
        await query.edit_message_text("You've unsubscribed from all zones.\n\nUse /start to subscribe to new zones.")
        return

    keyboard = []
    for zone in sorted(subs):
        keyboard.append([InlineKeyboardButton(f"\u274c {zone}", callback_data=f"unsub_{zone}")])
    keyboard.append([InlineKeyboardButton("\U0001f5d1\ufe0f Unsubscribe from ALL", callback_data="unsub_all")])
    keyboard.append([InlineKeyboardButton("\u2705 Done", callback_data="unsub_done")])

    await query.edit_message_text(
        f"\U0001f4cd Your subscribed zones ({len(subs)}):\n\nTap a zone to unsubscribe:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "\U0001f697 *ParkWatch SG Commands*\n\n"
        "*Getting Started:*\n"
        "/start \u2014 Set up your alert zones\n"
        "/subscribe \u2014 Add more zones\n"
        "/unsubscribe \u2014 Remove zones\n"
        "/myzones \u2014 View your subscriptions\n\n"
        "*Reporting & Alerts:*\n"
        "/report \u2014 Report a warden sighting\n"
        "/recent \u2014 See recent sightings (last 30 mins)\n\n"
        "*Your Profile:*\n"
        "/mystats \u2014 View your reporter stats & accuracy\n"
        "/share \u2014 Invite friends to join\n"
        "/feedback \u2014 Send feedback to the admins\n\n"
        "/help \u2014 Show this message\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4a1 *Tips:*\n"
        "\u2022 Spot a warden? Use /report to alert others!\n"
        "\u2022 Rate alerts with \U0001f44d/\U0001f44e to build trust\n"
        "\u2022 Share with friends \u2014 more users = better alerts!",
        parse_mode="Markdown",
    )


@ban_check
async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats command - show user's reporter stats."""
    user_id = update.effective_user.id
    db = get_db()

    stats = await db.get_user_stats(user_id)
    if not stats or stats["report_count"] == 0:
        await update.message.reply_text(
            "\U0001f4ca *Your Reporter Stats*\n\n"
            "You haven't reported any sightings yet.\n"
            "Use /report when you spot a warden to get started!",
            parse_mode="Markdown",
        )
        return

    report_count = stats["report_count"]
    accuracy_score, total_feedback = await db.calculate_accuracy(user_id)

    badge = get_reporter_badge(report_count)
    accuracy_indicator = get_accuracy_indicator(accuracy_score, total_feedback)

    # Calculate total feedback received on user's reports
    total_pos, total_neg = await db.get_user_feedback_totals(user_id)

    msg = "\U0001f4ca *Your Reporter Stats*\n\n"
    msg += f"\U0001f3c6 Badge: {badge}\n"
    msg += f"\U0001f4dd Total reports: {report_count}\n"
    msg += "\n*Accuracy Rating:*\n"
    msg += f"\U0001f44d Positive: {total_pos}\n"
    msg += f"\U0001f44e Negative: {total_neg}\n"

    if total_feedback >= 3:
        msg += f"\n\u2728 Accuracy score: {accuracy_score * 100:.0f}%"
        if accuracy_indicator:
            msg += f" {accuracy_indicator}"
        msg += "\n"
    else:
        msg += f"\n_Need {3 - total_feedback} more ratings for accuracy score_\n"

    # Badge progression info
    msg += "\n*Badge Progression:*\n"
    if report_count < 3:
        msg += f"\U0001f4c8 {3 - report_count} more reports for \u2b50 Regular\n"
    elif report_count < 11:
        msg += f"\U0001f4c8 {11 - report_count} more reports for \u2b50\u2b50 Trusted\n"
    elif report_count < 51:
        msg += f"\U0001f4c8 {51 - report_count} more reports for \U0001f3c6 Veteran\n"
    else:
        msg += "\U0001f389 You've reached the highest badge!\n"

    # Accuracy legend
    msg += "\n*Accuracy Indicators:*\n"
    msg += "\u2705 80%+ \u2014 Highly reliable\n"
    msg += "\u26a0\ufe0f 50-79% \u2014 Mixed accuracy\n"
    msg += "\u274c <50% \u2014 Low accuracy\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


@ban_check
async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /share command - generate shareable invite message."""
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    user_name = update.effective_user.first_name or "A friend"

    # Count total active users
    total_users = await get_db().get_subscriber_count()

    if total_users >= 10:
        user_line = f"Join {total_users}+ drivers getting real-time warden alerts!"
    else:
        user_line = "Join drivers getting real-time warden alerts!"

    share_msg = f"""\U0001f697 *ParkWatch SG \u2014 Parking Warden Alerts*

Tired of parking tickets? {user_line}

\u2705 Crowdsourced warden sightings
\u2705 Alerts for your subscribed zones
\u2705 GPS location + descriptions
\u2705 Reporter accuracy ratings
\u2705 80 zones across Singapore

*How it works:*
1. Subscribe to zones you park in
2. Get alerts when wardens spotted
3. Spot a warden? Report it to help others!

\U0001f449 Start now: https://t.me/{bot_username}

_Shared by {user_name}_"""

    # Send the shareable message
    await update.message.reply_text(
        "\U0001f4e4 *Share ParkWatch SG*\n\n"
        "Forward the message below to your friends, family, or driver groups!\n\n"
        "The more users we have, the better the alerts work for everyone.",
        parse_mode="Markdown",
    )

    # Send the actual share message (easy to forward)
    await update.message.reply_text(share_msg, parse_mode="Markdown")

    # Tips for sharing
    await update.message.reply_text(
        "\U0001f4a1 *Best places to share:*\n"
        "\u2022 WhatsApp family/friends groups\n"
        "\u2022 Office/condo/HDB Telegram groups\n"
        "\u2022 Facebook driver groups\n"
        "\u2022 Colleagues who drive to work\n\n"
        "Every new user makes the network stronger! \U0001f4aa",
        parse_mode="Markdown",
    )


@ban_check
async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /feedback <message> — relay user text to all admin users."""
    text = update.message.text
    parts = text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "\U0001f4ac *Send Feedback*\n\n"
            "Usage: `/feedback <your message>`\n\n"
            "Send suggestions, bug reports, or general feedback to the bot admins.",
            parse_mode="Markdown",
        )
        return

    message = parts[1].strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Anonymous"
    db = get_db()

    # Rate limit: 1 feedback message per user per hour
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    recent_count = await db.count_user_feedback_since(user_id, one_hour_ago)

    if recent_count >= 1:
        await update.message.reply_text(
            "\u23f3 You can only send one feedback message per hour.\n"
            "Please try again later."
        )
        return

    # Get user stats for admin context
    stats = await db.get_user_stats(user_id)
    report_count = stats["report_count"] if stats else 0
    badge = get_reporter_badge(report_count)

    # Build admin notification
    admin_msg = (
        "\U0001f4ec User Feedback\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f464 From: {username} (ID: {user_id})\n"
        f"\U0001f3c6 Badge: {badge} ({report_count} reports)\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4ac {message}\n"
    )

    # Relay to all admins
    sent = 0
    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_msg)
            sent += 1
        except Exception as e:
            logger.error(f"Failed to relay feedback to admin {admin_id}: {e}")

    # Log to audit trail
    preview = message[:100] + ("..." if len(message) > 100 else "")
    await db.log_admin_action(user_id, "user_feedback", target=str(user_id), detail=preview)

    # Confirm to user
    await update.message.reply_text(
        "\u2705 Thanks! Your feedback has been sent to the bot admins.\n"
        "We appreciate your input!"
    )
