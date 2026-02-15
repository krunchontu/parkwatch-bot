"""Keyboard builders for ParkWatch SG."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..database import get_db
from ..zones import ZONES


async def build_zone_keyboard(region_key, user_id):
    """Build zone keyboard with subscription status indicators."""
    region = ZONES.get(region_key)
    if not region:
        return InlineKeyboardMarkup([])

    user_zones = await get_db().get_subscriptions(user_id)
    keyboard = []
    for zone in region["zones"]:
        prefix = "\u2705 " if zone in user_zones else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{zone}", callback_data=f"zone_{zone}")])
    keyboard.append([InlineKeyboardButton("\u2705 Done", callback_data="zone_done")])
    keyboard.append([InlineKeyboardButton("\u25c0 Back", callback_data="back_to_regions")])
    return InlineKeyboardMarkup(keyboard)
