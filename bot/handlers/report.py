"""Report flow and feedback handlers for ParkWatch SG."""

import contextlib
import logging
from datetime import datetime, timedelta, timezone

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    DUPLICATE_RADIUS_METERS,
    DUPLICATE_WINDOW_MINUTES,
    FEEDBACK_WINDOW_HOURS,
    MAX_REPORTS_PER_HOUR,
    SIGHTING_EXPIRY_MINUTES,
)

from ..database import get_db
from ..services.moderation import _check_auto_flag, ban_check
from ..services.notifications import broadcast_alert
from ..ui.messages import build_alert_message
from ..utils import (
    generate_sighting_id,
    get_accuracy_indicator,
    get_reporter_badge,
    haversine_meters,
    sanitize_description,
)
from ..zones import ZONE_COORDS, ZONES

logger = logging.getLogger(__name__)

# ConversationHandler states for report flow
CHOOSING_METHOD, SELECTING_REGION, SELECTING_ZONE, AWAITING_LOCATION, AWAITING_DESCRIPTION, CONFIRMING = range(6)


@ban_check
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command."""
    keyboard = [
        [InlineKeyboardButton("\U0001f4cd Share Location", callback_data="report_location")],
        [InlineKeyboardButton("\U0001f4dd Select Zone Manually", callback_data="report_manual")],
    ]

    await update.message.reply_text(
        "\U0001f4cd Where did you spot the warden?\n\n"
        "Share your location for the most accurate alert, "
        "or select a zone manually.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_METHOD


async def handle_report_location_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Share Location button - show native GPS keyboard."""
    query = update.callback_query
    await query.answer()

    # Remove inline buttons from original message
    await query.edit_message_text("\U0001f4cd Tap the button below to share your location.")

    # Send reply keyboard with location button
    location_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("\U0001f4cd Share my location", request_location=True)], [KeyboardButton("\u274c Cancel")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Use the button below to share your GPS location:",
        reply_markup=location_keyboard,
    )
    return AWAITING_LOCATION


async def handle_location_cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel text from reply keyboard during location sharing."""
    context.user_data.pop("pending_report_zone", None)
    context.user_data.pop("pending_report_description", None)
    context.user_data.pop("pending_report_lat", None)
    context.user_data.pop("pending_report_lng", None)

    await update.message.reply_text("\u274c Report cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def handle_report_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manual zone selection for report - show regions."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"report_region_{key}")] for key, region in ZONES.items()
    ]
    keyboard.append([InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")])

    await query.edit_message_text("Select a region:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_REGION


async def handle_report_region_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle region selection in report flow - show zones."""
    query = update.callback_query
    await query.answer()

    region_key = query.data.replace("report_region_", "")
    region = ZONES.get(region_key)

    if not region:
        return SELECTING_REGION

    context.user_data["report_region"] = region_key

    keyboard = []
    for zone in region["zones"]:
        keyboard.append([InlineKeyboardButton(zone, callback_data=f"report_zone_{zone}")])
    keyboard.append([InlineKeyboardButton("\u25c0 Back to regions", callback_data="report_back_to_regions")])
    keyboard.append([InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")])

    await query.edit_message_text(f"Select a zone in {region['name']}:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_ZONE


async def handle_report_back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to region selection in report flow."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"report_region_{key}")] for key, region in ZONES.items()
    ]
    keyboard.append([InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")])

    await query.edit_message_text("Select a region:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_REGION


async def handle_report_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle zone selection for report."""
    query = update.callback_query
    await query.answer()

    zone_name = query.data.replace("report_zone_", "")
    context.user_data["pending_report_zone"] = zone_name
    context.user_data["pending_report_lat"] = None
    context.user_data["pending_report_lng"] = None

    await query.edit_message_text(
        f"\U0001f4cd Zone: {zone_name}\n\n"
        f"\U0001f4dd Send a short description of the location:\n"
        f"(e.g., 'outside Maxwell Food Centre' or 'Block 123 carpark')\n\n"
        f"Or tap Skip to report without description.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data="report_skip_description")],
                [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
            ]
        ),
    )
    return AWAITING_DESCRIPTION


async def handle_report_skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip description and go to confirm."""
    query = update.callback_query
    await query.answer()

    context.user_data["pending_report_description"] = None

    zone_name = context.user_data.get("pending_report_zone")
    lat = context.user_data.get("pending_report_lat")
    lng = context.user_data.get("pending_report_lng")

    confirm_text = f"\u26a0\ufe0f Confirm warden sighting:\n\n\U0001f4cd Zone: {zone_name}"
    if lat and lng:
        confirm_text += f"\n\U0001f310 GPS: {lat:.6f}, {lng:.6f}"

    await query.edit_message_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("\u2705 Confirm", callback_data="report_confirm")],
                [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
            ]
        ),
    )
    return CONFIRMING


async def handle_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for description."""
    description = sanitize_description(update.message.text)
    if description is None:
        await update.message.reply_text(
            "That description was empty after cleanup. Please try again, or tap Skip.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data="report_skip_description")],
                    [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
                ]
            ),
        )
        return AWAITING_DESCRIPTION
    context.user_data["pending_report_description"] = description

    zone_name = context.user_data.get("pending_report_zone")
    lat = context.user_data.get("pending_report_lat")
    lng = context.user_data.get("pending_report_lng")

    confirm_text = f"\u26a0\ufe0f Confirm warden sighting:\n\n\U0001f4cd Zone: {zone_name}\n\U0001f4dd Location: {description}"
    if lat and lng:
        confirm_text += f"\n\U0001f310 GPS: {lat:.6f}, {lng:.6f}"

    await update.message.reply_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("\u2705 Confirm", callback_data="report_confirm")],
                [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
            ]
        ),
    )
    return CONFIRMING


async def handle_report_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and broadcast the report."""
    query = update.callback_query
    await query.answer()

    zone_name = context.user_data.get("pending_report_zone")
    if not zone_name:
        await query.edit_message_text("\u274c Report expired. Please start again with /report")
        return ConversationHandler.END

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Anonymous"
    db = get_db()

    # --- Rate limiting ---
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    report_count_hour = await db.count_reports_since(user_id, one_hour_ago)

    if report_count_hour >= MAX_REPORTS_PER_HOUR:
        oldest = await db.get_oldest_report_since(user_id, one_hour_ago)
        wait_secs = (oldest + timedelta(hours=1) - now).total_seconds() if oldest else 3600
        wait_mins = max(1, int(wait_secs / 60) + 1)
        await query.edit_message_text(
            f"\u26a0\ufe0f Rate limit reached.\n\n"
            f"You can submit up to {MAX_REPORTS_PER_HOUR} reports per hour.\n"
            f"Please try again in ~{wait_mins} minute(s)."
        )
        return ConversationHandler.END

    # --- Duplicate detection (GPS-aware) ---
    lat = context.user_data.get("pending_report_lat")
    lng = context.user_data.get("pending_report_lng")
    recent_sightings = await db.find_recent_zone_sightings(zone_name, DUPLICATE_WINDOW_MINUTES)

    for existing in recent_sightings:
        existing_lat = existing.get("lat")
        existing_lng = existing.get("lng")
        has_both_gps = lat is not None and lng is not None and existing_lat is not None and existing_lng is not None

        if has_both_gps:
            dist = haversine_meters(lat, lng, existing_lat, existing_lng)
            if dist > DUPLICATE_RADIUS_METERS:
                continue  # Far enough apart — not a duplicate
            # Within radius — duplicate
            mins_ago = int((now - existing["reported_at"]).total_seconds() / 60)
            await query.edit_message_text(
                f"\u26a0\ufe0f Duplicate report.\n\n"
                f"A warden was already reported nearby ({int(dist)}m away) "
                f"in {zone_name} {mins_ago} minute(s) ago.\n\n"
                f"Check /recent for current sightings."
            )
            return ConversationHandler.END
        else:
            # No GPS on one or both — fall back to zone-level duplicate
            mins_ago = int((now - existing["reported_at"]).total_seconds() / 60)
            await query.edit_message_text(
                f"\u26a0\ufe0f Duplicate report.\n\n"
                f"A warden was already reported in {zone_name} "
                f"{mins_ago} minute(s) ago.\n\n"
                f"\U0001f4a1 Tip: Share your GPS location next time to report "
                f"multiple wardens in the same zone.\n\n"
                f"Check /recent for current sightings."
            )
            return ConversationHandler.END

    # Update user stats
    await db.ensure_user(user_id, username)
    report_count = await db.increment_report_count(user_id)
    badge = get_reporter_badge(report_count)

    # Get accuracy indicator
    accuracy_score, total_feedback = await db.calculate_accuracy(user_id)
    accuracy_indicator = get_accuracy_indicator(accuracy_score, total_feedback)

    # Get report details
    description = context.user_data.get("pending_report_description")

    # Generate unique sighting ID
    sighting_id = generate_sighting_id()

    # Store sighting
    sighting = {
        "id": sighting_id,
        "zone": zone_name,
        "description": description,
        "time": now,
        "reporter_id": user_id,
        "reporter_name": username,
        "reporter_badge": badge,
        "lat": lat,
        "lng": lng,
    }
    await db.add_sighting(sighting)

    # Build broadcast message from structured data
    sighting_for_msg = {
        "zone": zone_name,
        "reported_at": now,
        "description": description,
        "lat": lat,
        "lng": lng,
    }
    alert_msg = build_alert_message(
        sighting_for_msg,
        pos=0,
        neg=0,
        badge=badge,
        accuracy_indicator=accuracy_indicator,
    )

    # Feedback buttons
    feedback_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\U0001f44d Warden was there", callback_data=f"feedback_pos_{sighting_id}"),
                InlineKeyboardButton("\U0001f44e False alarm", callback_data=f"feedback_neg_{sighting_id}"),
            ]
        ]
    )

    sent_count, failed_count, blocked_users = await broadcast_alert(
        context.bot, zone_name, alert_msg, feedback_keyboard, user_id
    )

    confirm_msg = f"\u2705 Thanks! Alert sent to {sent_count} user(s) in {zone_name}."
    if failed_count > 0:
        confirm_msg += f"\n\u26a0\ufe0f {failed_count} delivery failure(s)."
        if blocked_users:
            confirm_msg += f" ({len(blocked_users)} inactive user(s) cleaned up.)"
    confirm_msg += f"\n\n\U0001f3c6 You've reported {report_count} sighting(s)!\nYour badge: {badge}\n"
    if total_feedback > 0:
        confirm_msg += f"Your accuracy: {accuracy_score * 100:.0f}% ({total_feedback} ratings)"
    else:
        confirm_msg += "Your accuracy: No ratings yet"
    await query.edit_message_text(confirm_msg)

    # Clear pending report data
    context.user_data.pop("pending_report_zone", None)
    context.user_data.pop("pending_report_description", None)
    context.user_data.pop("pending_report_lat", None)
    context.user_data.pop("pending_report_lng", None)
    return ConversationHandler.END


async def handle_report_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel report via inline button."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_report_zone", None)
    context.user_data.pop("pending_report_description", None)
    context.user_data.pop("pending_report_lat", None)
    context.user_data.pop("pending_report_lng", None)
    await query.edit_message_text("\u274c Report cancelled.")
    return ConversationHandler.END


async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command during report flow."""
    context.user_data.pop("pending_report_zone", None)
    context.user_data.pop("pending_report_description", None)
    context.user_data.pop("pending_report_lat", None)
    context.user_data.pop("pending_report_lng", None)

    await update.message.reply_text("\u274c Report cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, is_positive: bool):
    """Handle feedback on a sighting."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Extract sighting ID from callback data
    data = query.data
    sighting_id = data.replace("feedback_pos_", "").replace("feedback_neg_", "")
    db = get_db()

    # --- Self-rating prevention ---
    reporter_id = await db.get_sighting_reporter(sighting_id)
    if reporter_id is None:
        await query.answer("This sighting has expired.", show_alert=True)
        with contextlib.suppress(Exception):
            await query.edit_message_reply_markup(reply_markup=None)
        return
    if reporter_id == user_id:
        await query.answer("You cannot rate your own sighting.", show_alert=True)
        return

    # --- Feedback window check ---
    sighting_data = await db.get_sighting(sighting_id)
    if sighting_data:
        reported_at = sighting_data["reported_at"]
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=timezone.utc)
        sighting_age = datetime.now(timezone.utc) - reported_at
        if sighting_age > timedelta(hours=FEEDBACK_WINDOW_HOURS):
            await query.answer(
                f"Feedback window has closed ({FEEDBACK_WINDOW_HOURS}h limit).",
                show_alert=True,
            )
            with contextlib.suppress(Exception):
                await query.edit_message_reply_markup(reply_markup=None)
            return

    # Apply feedback in a single transaction (read->upsert->update counts)
    new_vote = "positive" if is_positive else "negative"
    try:
        sighting = await db.apply_feedback(sighting_id, user_id, new_vote)
    except ValueError:
        await query.answer("You've already submitted this feedback!", show_alert=True)
        return

    if not sighting:
        await query.answer("This sighting has expired.", show_alert=True)
        return

    pos = sighting["feedback_positive"]
    neg = sighting["feedback_negative"]

    # Update the message to show feedback was recorded
    if is_positive:
        await query.answer("\U0001f44d Thanks! Marked as accurate.", show_alert=False)
    else:
        await query.answer("\U0001f44e Thanks! Marked as false alarm.", show_alert=False)

    # Rebuild message from structured DB data (no string parsing)
    try:
        badge = sighting.get("reporter_badge", "\U0001f195 New")
        acc_score, total_fb = await db.calculate_accuracy(sighting["reporter_id"])
        accuracy_ind = get_accuracy_indicator(acc_score, total_fb)

        new_text = build_alert_message(
            sighting,
            pos=pos,
            neg=neg,
            badge=badge,
            accuracy_indicator=accuracy_ind,
            feedback_received=True,
        )

        feedback_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"\U0001f44d Accurate ({pos})", callback_data=f"feedback_pos_{sighting_id}"),
                    InlineKeyboardButton(f"\U0001f44e False alarm ({neg})", callback_data=f"feedback_neg_{sighting_id}"),
                ]
            ]
        )

        await query.edit_message_text(text=new_text, reply_markup=feedback_keyboard)
    except Exception as e:
        logger.error(f"Failed to update feedback message: {e}")

    # Phase 9: Auto-flag sighting if negative feedback ratio is high
    try:
        await _check_auto_flag(sighting_id)
    except Exception as e:
        logger.error(f"Auto-flag check failed for {sighting_id}: {e}")


@ban_check
async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recent command."""
    user_id = update.effective_user.id
    db = get_db()

    try:
        user_zones = await db.get_subscriptions(user_id)
    except Exception as e:
        logger.error(f"DB error in /recent (get_subscriptions): {e}")
        await update.message.reply_text("Sorry, something went wrong fetching your zones. Please try again.")
        return

    if not user_zones:
        await update.message.reply_text("You're not subscribed to any zones yet.\nUse /start to select zones first.")
        return

    try:
        relevant = await db.get_recent_sightings_for_zones(user_zones, SIGHTING_EXPIRY_MINUTES)
    except Exception as e:
        logger.error(f"DB error in /recent (get_recent_sightings): {e}")
        await update.message.reply_text("Sorry, something went wrong fetching recent sightings. Please try again.")
        return

    if not relevant:
        await update.message.reply_text(
            f"\u2705 No recent warden sightings in your zones (last {SIGHTING_EXPIRY_MINUTES} mins).\n\n"
            f"Your zones: {', '.join(sorted(user_zones))}"
        )
        return

    msg = "\U0001f4cb Recent sightings in your zones:\n"

    for s in relevant:  # already sorted by reported_at DESC from DB
        reported_at = s["reported_at"]
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=timezone.utc)
        mins_ago = int((datetime.now(timezone.utc) - reported_at).total_seconds() / 60)

        # Urgency indicator
        if mins_ago <= 5:
            urgency = "\U0001f534"
        elif mins_ago <= 15:
            urgency = "\U0001f7e1"
        else:
            urgency = "\U0001f7e2"

        msg += f"\n{urgency} {s['zone']} \u2014 {mins_ago} mins ago\n"

        if s.get("description"):
            msg += f"   \U0001f4dd {s['description']}\n"

        if s.get("lat") and s.get("lng"):
            msg += f"   \U0001f310 GPS: {s['lat']:.6f}, {s['lng']:.6f}\n"

        # Get reporter's current accuracy
        reporter_id = s.get("reporter_id")
        badge = s.get("reporter_badge", "\U0001f195 New")
        accuracy_indicator = ""
        if reporter_id:
            acc_score, total_fb = await db.calculate_accuracy(reporter_id)
            accuracy_indicator = get_accuracy_indicator(acc_score, total_fb)

        if accuracy_indicator:
            msg += f"   \U0001f464 {badge} {accuracy_indicator}\n"
        else:
            msg += f"   \U0001f464 {badge}\n"

        # Feedback stats
        pos = s.get("feedback_positive", 0)
        neg = s.get("feedback_negative", 0)
        if pos > 0 or neg > 0:
            msg += f"   \U0001f4ca Feedback: \U0001f44d {pos} / \U0001f44e {neg}\n"

    await update.message.reply_text(msg)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle shared location for report."""
    location = update.message.location
    lat, lng = location.latitude, location.longitude

    # Find nearest zone using module-level ZONE_COORDS
    nearest_zone = None
    min_dist = float("inf")

    for zone_name, (zone_lat, zone_lng) in ZONE_COORDS.items():
        dist = haversine_meters(lat, lng, zone_lat, zone_lng)
        if dist < min_dist:
            min_dist = dist
            nearest_zone = zone_name

    # Store zone and coordinates
    context.user_data["pending_report_zone"] = nearest_zone
    context.user_data["pending_report_lat"] = lat
    context.user_data["pending_report_lng"] = lng

    # Check if within reasonable range (2km)
    if min_dist > 2000:
        await update.message.reply_text(
            f"\U0001f4cd You're a bit far from known zones.\nNearest zone: {nearest_zone}\n\U0001f310 GPS: {lat:.6f}, {lng:.6f}",
            reply_markup=ReplyKeyboardRemove(),
        )
        await update.message.reply_text(
            "\U0001f4dd Send a short description of the location:\n"
            "(e.g., 'outside Maxwell Food Centre')\n\n"
            "Or tap Skip to continue without description.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data="report_skip_description")],
                    [InlineKeyboardButton("\U0001f4dd Select different zone", callback_data="report_manual")],
                    [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
                ]
            ),
        )
        return AWAITING_DESCRIPTION

    await update.message.reply_text(
        f"\U0001f4cd Detected zone: {nearest_zone}\n\U0001f310 GPS: {lat:.6f}, {lng:.6f}", reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        "\U0001f4dd Send a short description of the location:\n"
        "(e.g., 'outside Maxwell Food Centre' or 'Block 123 carpark')\n\n"
        "Or tap Skip to report without description.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("\u23ed\ufe0f Skip", callback_data="report_skip_description")],
                [InlineKeyboardButton("\u274c Cancel", callback_data="report_cancel")],
            ]
        ),
    )
    return AWAITING_DESCRIPTION
