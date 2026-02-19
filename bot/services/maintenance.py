"""Maintenance-mode utilities."""

from __future__ import annotations

from functools import wraps

from telegram import Message, Update
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
            # Lazy import to avoid circular dependency
            from ..handlers.report import clear_pending_report

            clear_pending_report(context.user_data)
            context.user_data.pop("report_region", None)
            msg = await maintenance_message()
            cancel_text = f"{msg}\n\nYour active report was cancelled due to maintenance."
            if update.message:
                await update.message.reply_text(cancel_text)
            elif update.callback_query and isinstance(update.callback_query.message, Message):
                await update.callback_query.message.reply_text(cancel_text)
            elif update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            return ConversationHandler.END
        return await func(update, context)

    return wrapper
