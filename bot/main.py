import logging
import sys
import os

# Add parent directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes
import math
import time
import random
from datetime import datetime, timedelta

from config import TELEGRAM_BOT_TOKEN, SIGHTING_EXPIRY_MINUTES, MAX_REPORTS_PER_HOUR

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Zone data - comprehensive Singapore coverage
ZONES = {
    "central": {
        "name": "Central",
        "zones": [
            "Tanjong Pagar", "Bugis", "Orchard", "Chinatown", "Clarke Quay",
            "Raffles Place", "Marina Bay", "City Hall", "Dhoby Ghaut",
            "Somerset", "Tiong Bahru", "Outram", "Telok Ayer", "Boat Quay",
            "Robertson Quay", "River Valley"
        ]
    },
    "central_north": {
        "name": "Central North",
        "zones": [
            "Novena", "Toa Payoh", "Bishan", "Ang Mo Kio", "Marymount",
            "Caldecott", "Thomson", "Braddell", "Lorong Chuan"
        ]
    },
    "east": {
        "name": "East",
        "zones": [
            "Tampines", "Bedok", "Paya Lebar", "Katong", "Pasir Ris",
            "Changi", "Simei", "Eunos", "Kembangan", "Marine Parade",
            "East Coast", "Geylang", "Aljunied", "Kallang", "Lavender",
            "Joo Chiat", "Siglap", "Tai Seng", "Ubi", "MacPherson"
        ]
    },
    "west": {
        "name": "West",
        "zones": [
            "Jurong East", "Jurong West", "Clementi", "Buona Vista",
            "Boon Lay", "Pioneer", "Tuas", "Queenstown", "Commonwealth",
            "HarbourFront", "Telok Blangah", "West Coast", "Dover",
            "Holland Village", "Ghim Moh", "Lakeside", "Chinese Garden"
        ]
    },
    "north": {
        "name": "North",
        "zones": [
            "Woodlands", "Yishun", "Sembawang", "Admiralty", "Marsiling",
            "Kranji", "Canberra", "Khatib"
        ]
    },
    "northeast": {
        "name": "North-East",
        "zones": [
            "Hougang", "Sengkang", "Punggol", "Serangoon", "Kovan",
            "Potong Pasir", "Bartley", "Buangkok", "Rivervale", "Anchorvale"
        ]
    }
}

# In-memory storage (will move to database later)
user_subscriptions = {}  # telegram_id -> set of zone names
recent_sightings = []    # list of {zone, description, time, reporter, lat, lng, ...}
user_stats = {}          # telegram_id -> {report_count, username, accuracy_score, total_feedback}
sighting_feedback = {}   # sighting_id -> {user_id: 'positive'/'negative'}
user_report_times = {}   # user_id -> list of datetime (report timestamps)


def get_reporter_badge(report_count):
    """Return badge based on number of reports."""
    if report_count >= 51:
        return "🏆 Veteran"
    elif report_count >= 11:
        return "⭐⭐ Trusted"
    elif report_count >= 3:
        return "⭐ Regular"
    else:
        return "🆕 New"


def get_accuracy_indicator(accuracy_score, total_feedback):
    """Return accuracy indicator based on score."""
    if total_feedback < 3:
        return ""  # Not enough data
    if accuracy_score >= 0.8:
        return "✅"  # Highly accurate
    elif accuracy_score >= 0.5:
        return "⚠️"  # Mixed accuracy
    else:
        return "❌"  # Low accuracy - possible spammer


def calculate_accuracy_score(user_id):
    """Calculate accuracy score for a reporter based on all their sightings."""
    total_positive = 0
    total_negative = 0

    for sighting in recent_sightings:
        if sighting.get('reporter_id') == user_id:
            total_positive += sighting.get('feedback_positive', 0)
            total_negative += sighting.get('feedback_negative', 0)

    total = total_positive + total_negative
    if total == 0:
        return 1.0, 0  # No feedback yet, assume good

    return total_positive / total, total


def generate_sighting_id():
    """Generate unique sighting ID."""
    return f"{int(time.time())}_{random.randint(1000, 9999)}"


# ConversationHandler states for report flow
CHOOSING_METHOD, SELECTING_REGION, SELECTING_ZONE, AWAITING_LOCATION, AWAITING_DESCRIPTION, CONFIRMING = range(6)


def build_zone_keyboard(region_key, user_id):
    """Build zone keyboard with subscription status indicators."""
    region = ZONES.get(region_key)
    if not region:
        return InlineKeyboardMarkup([])

    user_zones = user_subscriptions.get(user_id, set())
    keyboard = []
    for zone in region["zones"]:
        prefix = "✅ " if zone in user_zones else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{zone}", callback_data=f"zone_{zone}")])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="zone_done")])
    keyboard.append([InlineKeyboardButton("◀ Back", callback_data="back_to_regions")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"region_{key}")]
        for key, region in ZONES.items()
    ]

    await update.message.reply_text(
        f"Welcome to ParkWatch SG! 🚗\n\n"
        f"I'll alert you when parking wardens are spotted nearby.\n\n"
        f"To get started, which areas do you want alerts for?",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    context.user_data['current_region'] = region_key

    await query.edit_message_text(
        f"Select zones in {region['name']}:\n\n"
        f"(Tap to subscribe/unsubscribe, then tap Done)",
        reply_markup=build_zone_keyboard(region_key, user_id)
    )


async def handle_zone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle zone button click - toggle subscription."""
    query = update.callback_query

    zone_name = query.data.replace("zone_", "")
    user_id = update.effective_user.id

    # Initialize user subscriptions if needed
    if user_id not in user_subscriptions:
        user_subscriptions[user_id] = set()

    # Toggle subscription
    if zone_name in user_subscriptions[user_id]:
        user_subscriptions[user_id].remove(zone_name)
        await query.answer(f"❌ Unsubscribed from {zone_name}")
    else:
        user_subscriptions[user_id].add(zone_name)
        await query.answer(f"✅ Subscribed to {zone_name}")

    # Rebuild keyboard to show updated status (keeps keyboard open)
    region_key = context.user_data.get('current_region')
    if not region_key:
        # Fallback: find which region this zone belongs to
        for key, region in ZONES.items():
            if zone_name in region["zones"]:
                region_key = key
                break

    if region_key:
        region = ZONES.get(region_key)
        await query.edit_message_text(
            f"Select zones in {region['name']}:\n\n"
            f"(Tap to subscribe/unsubscribe, then tap Done)",
            reply_markup=build_zone_keyboard(region_key, user_id)
        )


async def handle_zone_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Done button from zone selection."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    context.user_data.pop('current_region', None)

    subs = user_subscriptions.get(user_id, set())
    if subs:
        sub_list = ", ".join(sorted(subs))
        await query.edit_message_text(
            f"✅ Subscribed to {len(subs)} zone(s): {sub_list}\n\n"
            f"Use /subscribe to modify zones.\n"
            f"Use /report to report a warden sighting."
        )
    else:
        await query.edit_message_text(
            "You're not subscribed to any zones yet.\n"
            "Use /start to select zones."
        )


async def handle_back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to region selection."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"region_{key}")]
        for key, region in ZONES.items()
    ]

    await query.edit_message_text(
        "Which areas do you want alerts for?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command."""
    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"region_{key}")]
        for key, region in ZONES.items()
    ]

    await update.message.reply_text(
        "Which areas do you want to add?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def myzones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myzones command."""
    user_id = update.effective_user.id
    subs = user_subscriptions.get(user_id, set())

    if subs:
        sub_list = "\n".join(f"• {z}" for z in sorted(subs))
        await update.message.reply_text(
            f"📍 Your subscribed zones:\n\n{sub_list}\n\n"
            f"Use /subscribe to add more.\n"
            f"Use /unsubscribe to remove zones."
        )
    else:
        await update.message.reply_text(
            "You're not subscribed to any zones yet.\n"
            "Use /start to select zones."
        )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command."""
    user_id = update.effective_user.id
    subs = user_subscriptions.get(user_id, set())

    if not subs:
        await update.message.reply_text(
            "You're not subscribed to any zones yet.\n"
            "Use /start to select zones first."
        )
        return

    # Build keyboard with current subscriptions
    keyboard = []
    for zone in sorted(subs):
        keyboard.append([InlineKeyboardButton(f"❌ {zone}", callback_data=f"unsub_{zone}")])
    keyboard.append([InlineKeyboardButton("🗑️ Unsubscribe from ALL", callback_data="unsub_all")])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="unsub_done")])

    await update.message.reply_text(
        f"📍 Your subscribed zones ({len(subs)}):\n\n"
        f"Tap a zone to unsubscribe:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_unsubscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unsubscribe button clicks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if user_id not in user_subscriptions:
        user_subscriptions[user_id] = set()

    if data == "unsub_done":
        subs = user_subscriptions.get(user_id, set())
        if subs:
            await query.edit_message_text(
                f"✅ Done! You're subscribed to {len(subs)} zone(s):\n"
                f"{', '.join(sorted(subs))}"
            )
        else:
            await query.edit_message_text(
                "You've unsubscribed from all zones.\n"
                "Use /start to subscribe again."
            )
        return

    if data == "unsub_all":
        user_subscriptions[user_id] = set()
        await query.edit_message_text(
            "🗑️ Unsubscribed from all zones.\n\n"
            "Use /start to subscribe to new zones."
        )
        return

    # Single zone unsubscribe
    zone_name = data.replace("unsub_", "")

    if zone_name in user_subscriptions[user_id]:
        user_subscriptions[user_id].remove(zone_name)
        await query.answer(f"❌ Unsubscribed from {zone_name}")

    # Rebuild keyboard with remaining subscriptions
    subs = user_subscriptions.get(user_id, set())

    if not subs:
        await query.edit_message_text(
            "You've unsubscribed from all zones.\n\n"
            "Use /start to subscribe to new zones."
        )
        return

    keyboard = []
    for zone in sorted(subs):
        keyboard.append([InlineKeyboardButton(f"❌ {zone}", callback_data=f"unsub_{zone}")])
    keyboard.append([InlineKeyboardButton("🗑️ Unsubscribe from ALL", callback_data="unsub_all")])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="unsub_done")])

    await query.edit_message_text(
        f"📍 Your subscribed zones ({len(subs)}):\n\n"
        f"Tap a zone to unsubscribe:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command."""
    keyboard = [
        [InlineKeyboardButton("📍 Share Location", callback_data="report_location")],
        [InlineKeyboardButton("📝 Select Zone Manually", callback_data="report_manual")]
    ]

    await update.message.reply_text(
        "📍 Where did you spot the warden?\n\n"
        "Share your location for the most accurate alert, "
        "or select a zone manually.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_METHOD


async def handle_report_location_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Share Location button - show native GPS keyboard."""
    query = update.callback_query
    await query.answer()

    # Remove inline buttons from original message
    await query.edit_message_text(
        "📍 Tap the button below to share your location."
    )

    # Send reply keyboard with location button
    location_keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📍 Share my location", request_location=True)],
            [KeyboardButton("❌ Cancel")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Use the button below to share your GPS location:",
        reply_markup=location_keyboard
    )
    return AWAITING_LOCATION


async def handle_location_cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel text from reply keyboard during location sharing."""
    context.user_data.pop('pending_report_zone', None)
    context.user_data.pop('pending_report_description', None)
    context.user_data.pop('pending_report_lat', None)
    context.user_data.pop('pending_report_lng', None)

    await update.message.reply_text(
        "❌ Report cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def handle_report_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manual zone selection for report - show regions."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"report_region_{key}")]
        for key, region in ZONES.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")])

    await query.edit_message_text(
        "Select a region:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_REGION


async def handle_report_region_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle region selection in report flow - show zones."""
    query = update.callback_query
    await query.answer()

    region_key = query.data.replace("report_region_", "")
    region = ZONES.get(region_key)

    if not region:
        return SELECTING_REGION

    context.user_data['report_region'] = region_key

    keyboard = []
    for zone in region["zones"]:
        keyboard.append([InlineKeyboardButton(zone, callback_data=f"report_zone_{zone}")])
    keyboard.append([InlineKeyboardButton("◀ Back to regions", callback_data="report_back_to_regions")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")])

    await query.edit_message_text(
        f"Select a zone in {region['name']}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_ZONE


async def handle_report_back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to region selection in report flow."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(region["name"], callback_data=f"report_region_{key}")]
        for key, region in ZONES.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")])

    await query.edit_message_text(
        "Select a region:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_REGION


async def handle_report_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle zone selection for report."""
    query = update.callback_query
    await query.answer()

    zone_name = query.data.replace("report_zone_", "")
    context.user_data['pending_report_zone'] = zone_name
    context.user_data['pending_report_lat'] = None
    context.user_data['pending_report_lng'] = None

    await query.edit_message_text(
        f"📍 Zone: {zone_name}\n\n"
        f"📝 Send a short description of the location:\n"
        f"(e.g., 'outside Maxwell Food Centre' or 'Block 123 carpark')\n\n"
        f"Or tap Skip to report without description.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="report_skip_description")],
            [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")]
        ])
    )
    return AWAITING_DESCRIPTION


async def handle_report_skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip description and go to confirm."""
    query = update.callback_query
    await query.answer()

    context.user_data['pending_report_description'] = None

    zone_name = context.user_data.get('pending_report_zone')
    lat = context.user_data.get('pending_report_lat')
    lng = context.user_data.get('pending_report_lng')

    confirm_text = f"⚠️ Confirm warden sighting:\n\n📍 Zone: {zone_name}"
    if lat and lng:
        confirm_text += f"\n🌐 GPS: {lat:.6f}, {lng:.6f}"

    await query.edit_message_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="report_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")]
        ])
    )
    return CONFIRMING


async def handle_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for description."""
    description = update.message.text[:100]  # Limit to 100 chars
    context.user_data['pending_report_description'] = description

    zone_name = context.user_data.get('pending_report_zone')
    lat = context.user_data.get('pending_report_lat')
    lng = context.user_data.get('pending_report_lng')

    confirm_text = f"⚠️ Confirm warden sighting:\n\n📍 Zone: {zone_name}\n📝 Location: {description}"
    if lat and lng:
        confirm_text += f"\n🌐 GPS: {lat:.6f}, {lng:.6f}"

    await update.message.reply_text(
        confirm_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="report_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")]
        ])
    )
    return CONFIRMING


async def handle_report_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and broadcast the report."""
    query = update.callback_query
    await query.answer()

    zone_name = context.user_data.get('pending_report_zone')
    if not zone_name:
        await query.edit_message_text("❌ Report expired. Please start again with /report")
        return ConversationHandler.END

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Anonymous"

    # --- Rate limiting ---
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)

    if user_id not in user_report_times:
        user_report_times[user_id] = []

    # Prune timestamps older than 1 hour
    user_report_times[user_id] = [
        t for t in user_report_times[user_id] if t > one_hour_ago
    ]

    if len(user_report_times[user_id]) >= MAX_REPORTS_PER_HOUR:
        oldest = user_report_times[user_id][0]
        wait_mins = int((oldest + timedelta(hours=1) - now).seconds / 60) + 1
        await query.edit_message_text(
            f"⚠️ Rate limit reached.\n\n"
            f"You can submit up to {MAX_REPORTS_PER_HOUR} reports per hour.\n"
            f"Please try again in ~{wait_mins} minute(s)."
        )
        return ConversationHandler.END

    # --- Duplicate detection ---
    DUPLICATE_WINDOW_MINUTES = 5
    duplicate_cutoff = now - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)

    for existing in recent_sightings:
        if existing['zone'] == zone_name and existing['time'] > duplicate_cutoff:
            mins_ago = int((now - existing['time']).seconds / 60)
            await query.edit_message_text(
                f"⚠️ Duplicate report.\n\n"
                f"A warden was already reported in {zone_name} "
                f"{mins_ago} minute(s) ago.\n\n"
                f"Check /recent for current sightings."
            )
            return ConversationHandler.END

    # Update user stats
    if user_id not in user_stats:
        user_stats[user_id] = {'report_count': 0, 'username': username, 'accuracy_score': 1.0, 'total_feedback': 0}
    user_stats[user_id]['report_count'] += 1
    user_stats[user_id]['username'] = username

    report_count = user_stats[user_id]['report_count']
    badge = get_reporter_badge(report_count)

    # Get accuracy indicator
    accuracy_score, total_feedback = calculate_accuracy_score(user_id)
    accuracy_indicator = get_accuracy_indicator(accuracy_score, total_feedback)

    # Get report details
    description = context.user_data.get('pending_report_description')
    lat = context.user_data.get('pending_report_lat')
    lng = context.user_data.get('pending_report_lng')

    # Generate unique sighting ID
    sighting_id = generate_sighting_id()

    # Store sighting
    sighting = {
        'id': sighting_id,
        'zone': zone_name,
        'description': description,
        'time': datetime.now(),
        'reporter_id': user_id,
        'reporter_name': username,
        'reporter_badge': badge,
        'lat': lat,
        'lng': lng,
        'feedback_positive': 0,
        'feedback_negative': 0
    }
    recent_sightings.append(sighting)

    # Initialize feedback tracking for this sighting
    sighting_feedback[sighting_id] = {}

    # Keep only last 100 sightings
    if len(recent_sightings) > 100:
        old_sighting = recent_sightings.pop(0)
        # Clean up old feedback data
        if old_sighting.get('id') in sighting_feedback:
            del sighting_feedback[old_sighting['id']]

    # Build broadcast message
    time_str = sighting['time'].strftime('%I:%M %p')
    alert_msg = f"🚨 WARDEN ALERT — {zone_name}\n"
    alert_msg += f"🕐 Spotted: {time_str}\n"
    if description:
        alert_msg += f"📝 Location: {description}\n"
    if lat and lng:
        alert_msg += f"🌐 GPS: {lat:.6f}, {lng:.6f}\n"

    # Show badge with accuracy indicator if available
    if accuracy_indicator:
        alert_msg += f"👤 Reporter: {badge} {accuracy_indicator}\n"
    else:
        alert_msg += f"👤 Reporter: {badge}\n"

    alert_msg += f"\n⏰ Extend your parking now!\n"
    alert_msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
    alert_msg += f"Was this accurate? Your feedback helps!"

    # Feedback buttons
    feedback_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 Warden was there", callback_data=f"feedback_pos_{sighting_id}"),
            InlineKeyboardButton("👎 False alarm", callback_data=f"feedback_neg_{sighting_id}")
        ]
    ])

    sent_count = 0
    for uid, zones in user_subscriptions.items():
        if zone_name in zones and uid != user_id:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=alert_msg,
                    reply_markup=feedback_keyboard
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send alert to {uid}: {e}")

    # Record report timestamp for rate limiting
    user_report_times[user_id].append(datetime.now())

    # Update user's accuracy in stats
    user_stats[user_id]['accuracy_score'] = accuracy_score
    user_stats[user_id]['total_feedback'] = total_feedback

    await query.edit_message_text(
        f"✅ Thanks! Alert sent to {sent_count} users in {zone_name}.\n\n"
        f"🏆 You've reported {report_count} sighting(s)!\n"
        f"Your badge: {badge}\n"
        f"Your accuracy: {accuracy_score*100:.0f}% ({total_feedback} ratings)"
    )

    # Clear pending report data
    context.user_data.pop('pending_report_zone', None)
    context.user_data.pop('pending_report_description', None)
    context.user_data.pop('pending_report_lat', None)
    context.user_data.pop('pending_report_lng', None)
    return ConversationHandler.END


async def handle_report_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel report via inline button."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('pending_report_zone', None)
    context.user_data.pop('pending_report_description', None)
    context.user_data.pop('pending_report_lat', None)
    context.user_data.pop('pending_report_lng', None)
    await query.edit_message_text("❌ Report cancelled.")
    return ConversationHandler.END


async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command during report flow."""
    context.user_data.pop('pending_report_zone', None)
    context.user_data.pop('pending_report_description', None)
    context.user_data.pop('pending_report_lat', None)
    context.user_data.pop('pending_report_lng', None)

    await update.message.reply_text(
        "❌ Report cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, is_positive: bool):
    """Handle feedback on a sighting."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Extract sighting ID from callback data
    data = query.data
    sighting_id = data.replace("feedback_pos_", "").replace("feedback_neg_", "")

    # --- Self-rating prevention ---
    reporter_id_for_check = None
    for s in recent_sightings:
        if s.get('id') == sighting_id:
            reporter_id_for_check = s.get('reporter_id')
            break
    if reporter_id_for_check == user_id:
        await query.answer("You cannot rate your own sighting.", show_alert=True)
        return

    # Check if user already gave feedback on this sighting
    if sighting_id in sighting_feedback:
        if user_id in sighting_feedback[sighting_id]:
            previous = sighting_feedback[sighting_id][user_id]
            if (previous == 'positive' and is_positive) or (previous == 'negative' and not is_positive):
                await query.answer("You've already submitted this feedback!", show_alert=True)
                return
            else:
                # User is changing their feedback
                # Find and update the sighting
                for sighting in recent_sightings:
                    if sighting.get('id') == sighting_id:
                        if previous == 'positive':
                            sighting['feedback_positive'] = max(0, sighting.get('feedback_positive', 0) - 1)
                        else:
                            sighting['feedback_negative'] = max(0, sighting.get('feedback_negative', 0) - 1)
                        break
    else:
        sighting_feedback[sighting_id] = {}

    # Record the new feedback
    sighting_feedback[sighting_id][user_id] = 'positive' if is_positive else 'negative'

    # Find and update the sighting
    sighting_found = False
    reporter_id = None
    zone_name = ""

    for sighting in recent_sightings:
        if sighting.get('id') == sighting_id:
            sighting_found = True
            if is_positive:
                sighting['feedback_positive'] = sighting.get('feedback_positive', 0) + 1
            else:
                sighting['feedback_negative'] = sighting.get('feedback_negative', 0) + 1

            reporter_id = sighting.get('reporter_id')
            zone_name = sighting.get('zone', '')
            pos = sighting.get('feedback_positive', 0)
            neg = sighting.get('feedback_negative', 0)
            break

    if not sighting_found:
        await query.answer("This sighting has expired.", show_alert=True)
        return

    # Update reporter's accuracy score
    if reporter_id and reporter_id in user_stats:
        accuracy_score, total_feedback = calculate_accuracy_score(reporter_id)
        user_stats[reporter_id]['accuracy_score'] = accuracy_score
        user_stats[reporter_id]['total_feedback'] = total_feedback

    # Update the message to show feedback was recorded
    if is_positive:
        await query.answer("👍 Thanks! Marked as accurate.", show_alert=False)
    else:
        await query.answer("👎 Thanks! Marked as false alarm.", show_alert=False)

    # Update message text to show current feedback count
    try:
        original_text = query.message.text
        # Find and update or add feedback line
        lines = original_text.split('\n')
        new_lines = []
        feedback_updated = False

        for line in lines:
            if line.startswith("📊 Feedback:"):
                new_lines.append(f"📊 Feedback: 👍 {pos} / 👎 {neg}")
                feedback_updated = True
            elif line == "Was this accurate? Your feedback helps!":
                new_lines.append(f"📊 Feedback: 👍 {pos} / 👎 {neg}")
                new_lines.append("Thanks for your feedback!")
                feedback_updated = True
            else:
                new_lines.append(line)

        new_text = '\n'.join(new_lines)

        # Keep the feedback buttons so others can still vote
        feedback_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"👍 Accurate ({pos})", callback_data=f"feedback_pos_{sighting_id}"),
                InlineKeyboardButton(f"👎 False alarm ({neg})", callback_data=f"feedback_neg_{sighting_id}")
            ]
        ])

        await query.edit_message_text(text=new_text, reply_markup=feedback_keyboard)
    except Exception as e:
        logger.error(f"Failed to update feedback message: {e}")


async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recent command."""

    user_id = update.effective_user.id
    user_zones = user_subscriptions.get(user_id, set())

    if not user_zones:
        await update.message.reply_text(
            "You're not subscribed to any zones yet.\n"
            "Use /start to select zones first."
        )
        return

    cutoff = datetime.now() - timedelta(minutes=SIGHTING_EXPIRY_MINUTES)

    # Filter recent sightings for user's zones
    relevant = [
        s for s in recent_sightings
        if s['zone'] in user_zones and s['time'] > cutoff
    ]

    if not relevant:
        await update.message.reply_text(
            f"✅ No recent warden sightings in your zones (last {SIGHTING_EXPIRY_MINUTES} mins).\n\n"
            f"Your zones: {', '.join(sorted(user_zones))}"
        )
        return

    msg = "📋 Recent sightings in your zones:\n"

    for s in sorted(relevant, key=lambda x: x['time'], reverse=True):
        mins_ago = int((datetime.now() - s['time']).seconds / 60)

        # Urgency indicator
        if mins_ago <= 5:
            urgency = "🔴"
        elif mins_ago <= 15:
            urgency = "🟡"
        else:
            urgency = "🟢"

        msg += f"\n{urgency} {s['zone']} — {mins_ago} mins ago\n"

        if s.get('description'):
            msg += f"   📝 {s['description']}\n"

        if s.get('lat') and s.get('lng'):
            msg += f"   🌐 GPS: {s['lat']:.6f}, {s['lng']:.6f}\n"

        # Get reporter's current accuracy
        reporter_id = s.get('reporter_id')
        badge = s.get('reporter_badge', '🆕 New')
        accuracy_indicator = ""
        if reporter_id and reporter_id in user_stats:
            acc_score = user_stats[reporter_id].get('accuracy_score', 1.0)
            total_fb = user_stats[reporter_id].get('total_feedback', 0)
            accuracy_indicator = get_accuracy_indicator(acc_score, total_fb)

        if accuracy_indicator:
            msg += f"   👤 {badge} {accuracy_indicator}\n"
        else:
            msg += f"   👤 {badge}\n"

        # Feedback stats
        pos = s.get('feedback_positive', 0)
        neg = s.get('feedback_negative', 0)
        if pos > 0 or neg > 0:
            msg += f"   📊 Feedback: 👍 {pos} / 👎 {neg}\n"

    await update.message.reply_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "🚗 *ParkWatch SG Commands*\n\n"
        "*Getting Started:*\n"
        "/start — Set up your alert zones\n"
        "/subscribe — Add more zones\n"
        "/unsubscribe — Remove zones\n"
        "/myzones — View your subscriptions\n\n"
        "*Reporting & Alerts:*\n"
        "/report — Report a warden sighting\n"
        "/recent — See recent sightings (last 30 mins)\n\n"
        "*Your Profile:*\n"
        "/mystats — View your reporter stats & accuracy\n"
        "/share — Invite friends to join\n\n"
        "/help — Show this message\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips:*\n"
        "• Spot a warden? Use /report to alert others!\n"
        "• Rate alerts with 👍/👎 to build trust\n"
        "• Share with friends — more users = better alerts!",
        parse_mode='Markdown'
    )


async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats command - show user's reporter stats."""
    user_id = update.effective_user.id

    if user_id not in user_stats:
        await update.message.reply_text(
            "📊 *Your Reporter Stats*\n\n"
            "You haven't reported any sightings yet.\n"
            "Use /report when you spot a warden to get started!",
            parse_mode='Markdown'
        )
        return

    stats = user_stats[user_id]
    report_count = stats.get('report_count', 0)
    accuracy_score = stats.get('accuracy_score', 1.0)
    total_feedback = stats.get('total_feedback', 0)

    badge = get_reporter_badge(report_count)
    accuracy_indicator = get_accuracy_indicator(accuracy_score, total_feedback)

    # Calculate total feedback received on user's reports
    total_pos = 0
    total_neg = 0
    for sighting in recent_sightings:
        if sighting.get('reporter_id') == user_id:
            total_pos += sighting.get('feedback_positive', 0)
            total_neg += sighting.get('feedback_negative', 0)

    msg = "📊 *Your Reporter Stats*\n\n"
    msg += f"🏆 Badge: {badge}\n"
    msg += f"📝 Total reports: {report_count}\n"
    msg += f"\n*Accuracy Rating:*\n"
    msg += f"👍 Positive: {total_pos}\n"
    msg += f"👎 Negative: {total_neg}\n"

    if total_feedback >= 3:
        msg += f"\n✨ Accuracy score: {accuracy_score*100:.0f}%"
        if accuracy_indicator:
            msg += f" {accuracy_indicator}"
        msg += "\n"
    else:
        msg += f"\n_Need {3 - total_feedback} more ratings for accuracy score_\n"

    # Badge progression info
    msg += "\n*Badge Progression:*\n"
    if report_count < 3:
        msg += f"📈 {3 - report_count} more reports for ⭐ Regular\n"
    elif report_count < 11:
        msg += f"📈 {11 - report_count} more reports for ⭐⭐ Trusted\n"
    elif report_count < 51:
        msg += f"📈 {51 - report_count} more reports for 🏆 Veteran\n"
    else:
        msg += "🎉 You've reached the highest badge!\n"

    # Accuracy legend
    msg += "\n*Accuracy Indicators:*\n"
    msg += "✅ 80%+ — Highly reliable\n"
    msg += "⚠️ 50-79% — Mixed accuracy\n"
    msg += "❌ <50% — Low accuracy\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /share command - generate shareable invite message."""
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    # Get user's stats for personalized message
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "A friend"

    report_count = 0
    if user_id in user_stats:
        report_count = user_stats[user_id].get('report_count', 0)

    # Count total active users and sightings
    total_users = len(user_subscriptions)
    total_sightings = len(recent_sightings)

    share_msg = f"""🚗 *ParkWatch SG — Parking Warden Alerts*

Tired of parking tickets? Join {total_users}+ drivers getting real-time warden alerts!

✅ Crowdsourced warden sightings
✅ Alerts for your subscribed zones
✅ GPS location + descriptions
✅ Reporter accuracy ratings
✅ 80 zones across Singapore

*How it works:*
1. Subscribe to zones you park in
2. Get alerts when wardens spotted
3. Spot a warden? Report it to help others!

👉 Start now: https://t.me/{bot_username}

_Shared by {user_name}_"""

    # Send the shareable message
    await update.message.reply_text(
        "📤 *Share ParkWatch SG*\n\n"
        "Forward the message below to your friends, family, or driver groups!\n\n"
        "The more users we have, the better the alerts work for everyone.",
        parse_mode='Markdown'
    )

    # Send the actual share message (easy to forward)
    await update.message.reply_text(share_msg, parse_mode='Markdown')

    # Tips for sharing
    await update.message.reply_text(
        "💡 *Best places to share:*\n"
        "• WhatsApp family/friends groups\n"
        "• Office/condo/HDB Telegram groups\n"
        "• Facebook driver groups\n"
        "• Colleagues who drive to work\n\n"
        "Every new user makes the network stronger! 💪",
        parse_mode='Markdown'
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all callback queries (non-report flows)."""
    query = update.callback_query
    data = query.data

    if data.startswith("region_"):
        await handle_region_selection(update, context)
    elif data == "zone_done":
        await handle_zone_done(update, context)
    elif data.startswith("zone_"):
        await handle_zone_selection(update, context)
    elif data == "back_to_regions":
        await handle_back_to_regions(update, context)
    elif data.startswith("unsub_"):
        await handle_unsubscribe_callback(update, context)
    elif data.startswith("feedback_pos_"):
        await handle_feedback(update, context, is_positive=True)
    elif data.startswith("feedback_neg_"):
        await handle_feedback(update, context, is_positive=False)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle shared location for report."""
    location = update.message.location
    lat, lng = location.latitude, location.longitude

    # Zone centers (lat, lng) - comprehensive Singapore coverage
    ZONE_COORDS = {
        # Central
        "Tanjong Pagar": (1.2764, 103.8460),
        "Bugis": (1.3008, 103.8553),
        "Orchard": (1.3048, 103.8318),
        "Chinatown": (1.2836, 103.8444),
        "Clarke Quay": (1.2906, 103.8465),
        "Raffles Place": (1.2840, 103.8514),
        "Marina Bay": (1.2789, 103.8536),
        "City Hall": (1.2931, 103.8520),
        "Dhoby Ghaut": (1.2993, 103.8458),
        "Somerset": (1.3006, 103.8387),
        "Tiong Bahru": (1.2863, 103.8273),
        "Outram": (1.2803, 103.8394),
        "Telok Ayer": (1.2822, 103.8484),
        "Boat Quay": (1.2875, 103.8497),
        "Robertson Quay": (1.2908, 103.8382),
        "River Valley": (1.2953, 103.8328),

        # Central North
        "Novena": (1.3204, 103.8438),
        "Toa Payoh": (1.3343, 103.8497),
        "Bishan": (1.3526, 103.8352),
        "Ang Mo Kio": (1.3691, 103.8454),
        "Marymount": (1.3487, 103.8395),
        "Caldecott": (1.3374, 103.8395),
        "Thomson": (1.3280, 103.8420),
        "Braddell": (1.3405, 103.8469),
        "Lorong Chuan": (1.3519, 103.8618),

        # East
        "Tampines": (1.3532, 103.9453),
        "Bedok": (1.3236, 103.9273),
        "Paya Lebar": (1.3176, 103.8919),
        "Katong": (1.3050, 103.9050),
        "Pasir Ris": (1.3732, 103.9493),
        "Changi": (1.3576, 103.9885),
        "Simei": (1.3432, 103.9532),
        "Eunos": (1.3198, 103.9030),
        "Kembangan": (1.3209, 103.9128),
        "Marine Parade": (1.3025, 103.9053),
        "East Coast": (1.3010, 103.9125),
        "Geylang": (1.3166, 103.8840),
        "Aljunied": (1.3165, 103.8829),
        "Kallang": (1.3114, 103.8713),
        "Lavender": (1.3073, 103.8630),
        "Joo Chiat": (1.3137, 103.9016),
        "Siglap": (1.3109, 103.9236),
        "Tai Seng": (1.3358, 103.8876),
        "Ubi": (1.3299, 103.8998),
        "MacPherson": (1.3265, 103.8900),

        # West
        "Jurong East": (1.3329, 103.7436),
        "Jurong West": (1.3400, 103.7090),
        "Clementi": (1.3149, 103.7651),
        "Buona Vista": (1.3073, 103.7903),
        "Boon Lay": (1.3385, 103.7060),
        "Pioneer": (1.3376, 103.6972),
        "Tuas": (1.3270, 103.6500),
        "Queenstown": (1.2942, 103.8060),
        "Commonwealth": (1.3024, 103.7983),
        "HarbourFront": (1.2654, 103.8212),
        "Telok Blangah": (1.2708, 103.8098),
        "West Coast": (1.3050, 103.7650),
        "Dover": (1.3115, 103.7785),
        "Holland Village": (1.3111, 103.7958),
        "Ghim Moh": (1.3108, 103.7889),
        "Lakeside": (1.3440, 103.7209),
        "Chinese Garden": (1.3426, 103.7295),

        # North
        "Woodlands": (1.4360, 103.7865),
        "Yishun": (1.4291, 103.8354),
        "Sembawang": (1.4491, 103.8185),
        "Admiralty": (1.4406, 103.8009),
        "Marsiling": (1.4326, 103.7743),
        "Kranji": (1.4252, 103.7620),
        "Canberra": (1.4430, 103.8297),
        "Khatib": (1.4174, 103.8329),

        # North-East
        "Hougang": (1.3612, 103.8863),
        "Sengkang": (1.3917, 103.8953),
        "Punggol": (1.4041, 103.9025),
        "Serangoon": (1.3500, 103.8718),
        "Kovan": (1.3601, 103.8850),
        "Potong Pasir": (1.3313, 103.8688),
        "Bartley": (1.3428, 103.8795),
        "Buangkok": (1.3831, 103.8928),
        "Rivervale": (1.3924, 103.9024),
        "Anchorvale": (1.3964, 103.8903),
    }

    def distance(lat1, lng1, lat2, lng2):
        """Simple Euclidean distance (good enough for Singapore scale)."""
        return math.sqrt((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2)

    # Find nearest zone
    nearest_zone = None
    min_dist = float('inf')

    for zone_name, (zone_lat, zone_lng) in ZONE_COORDS.items():
        dist = distance(lat, lng, zone_lat, zone_lng)
        if dist < min_dist:
            min_dist = dist
            nearest_zone = zone_name

    # Store zone and coordinates
    context.user_data['pending_report_zone'] = nearest_zone
    context.user_data['pending_report_lat'] = lat
    context.user_data['pending_report_lng'] = lng

    # Check if within reasonable range (roughly 2km)
    if min_dist > 0.02:
        await update.message.reply_text(
            f"📍 You're a bit far from known zones.\n"
            f"Nearest zone: {nearest_zone}\n"
            f"🌐 GPS: {lat:.6f}, {lng:.6f}",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(
            f"📝 Send a short description of the location:\n"
            f"(e.g., 'outside Maxwell Food Centre')\n\n"
            f"Or tap Skip to continue without description.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭️ Skip", callback_data="report_skip_description")],
                [InlineKeyboardButton("📝 Select different zone", callback_data="report_manual")],
                [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")]
            ])
        )
        return AWAITING_DESCRIPTION

    await update.message.reply_text(
        f"📍 Detected zone: {nearest_zone}\n"
        f"🌐 GPS: {lat:.6f}, {lng:.6f}",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        f"📝 Send a short description of the location:\n"
        f"(e.g., 'outside Maxwell Food Centre' or 'Block 123 carpark')\n\n"
        f"Or tap Skip to report without description.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="report_skip_description")],
            [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")]
        ])
    )
    return AWAITING_DESCRIPTION


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("Create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        return

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ConversationHandler for report flow
    report_conv = ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            CHOOSING_METHOD: [
                CallbackQueryHandler(handle_report_location_button, pattern="^report_location$"),
                CallbackQueryHandler(handle_report_manual, pattern="^report_manual$"),
            ],
            SELECTING_REGION: [
                CallbackQueryHandler(handle_report_region_selection, pattern="^report_region_"),
                CallbackQueryHandler(handle_report_cancel, pattern="^report_cancel$"),
            ],
            SELECTING_ZONE: [
                CallbackQueryHandler(handle_report_zone, pattern="^report_zone_"),
                CallbackQueryHandler(handle_report_back_to_regions, pattern="^report_back_to_regions$"),
                CallbackQueryHandler(handle_report_cancel, pattern="^report_cancel$"),
            ],
            AWAITING_LOCATION: [
                MessageHandler(filters.LOCATION, handle_location),
                MessageHandler(filters.Regex("^❌ Cancel$"), handle_location_cancel_text),
                CallbackQueryHandler(handle_report_cancel, pattern="^report_cancel$"),
            ],
            AWAITING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description_input),
                CallbackQueryHandler(handle_report_skip_description, pattern="^report_skip_description$"),
                CallbackQueryHandler(handle_report_manual, pattern="^report_manual$"),
                CallbackQueryHandler(handle_report_cancel, pattern="^report_cancel$"),
            ],
            CONFIRMING: [
                CallbackQueryHandler(handle_report_confirm, pattern="^report_confirm$"),
                CallbackQueryHandler(handle_report_cancel, pattern="^report_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_report),
            CommandHandler("report", report),
        ],
        conversation_timeout=300,
    )

    # Add handlers - report_conv first (before general CallbackQueryHandler)
    app.add_handler(report_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("myzones", myzones))
    app.add_handler(CommandHandler("recent", recent))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(handle_callback))

    # Start bot
    logger.info("🚗 ParkWatch SG Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
