"""Maintenance-mode utilities."""

from __future__ import annotations

from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .runtime_settings import get_runtime_settings


async def is_maintenance_enabled() -> bool:
    return bool(await get_runtime_settings().get("MAINTENANCE_MODE"))


async def maintenance_message() -> str:
    return str(await get_runtime_settings().get("MAINTENANCE_MESSAGE"))


async def _reply_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await maintenance_message()
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    elif update.inline_query:
        await update.inline_query.answer([], cache_time=0)


def maintenance_check(func):
    """Decorator that blocks user handlers during maintenance mode."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await is_maintenance_enabled():
            await _reply_maintenance(update, context)
            return
        return await func(update, context)

    return wrapper


def maintenance_conversation_check(func):
    """Decorator that cancels active report flow during maintenance mode."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await is_maintenance_enabled():
            context.user_data.pop("pending_report_zone", None)
            context.user_data.pop("pending_report_description", None)
            context.user_data.pop("pending_report_lat", None)
            context.user_data.pop("pending_report_lng", None)
            context.user_data.pop("report_region", None)
            await _reply_maintenance(update, context)
            if update.message:
                await update.message.reply_text("Your active report was cancelled due to maintenance.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("Your active report was cancelled due to maintenance.")
            return ConversationHandler.END
        return await func(update, context)

    return wrapper
