"""ParkWatch SG Bot — application wiring and entrypoint."""

import contextlib
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    BOT_VERSION,
    DATABASE_URL,
    HEALTH_CHECK_ENABLED,
    HEALTH_CHECK_PORT,
    LOG_FORMAT,
    PORT,
    SENTRY_DSN,
    SIGHTING_RETENTION_DAYS,
    TELEGRAM_BOT_TOKEN,
    WEBHOOK_URL,
)

from .database import close_db, get_db, init_db
from .handlers.admin import admin_command
from .handlers.report import (
    AWAITING_DESCRIPTION,
    AWAITING_LOCATION,
    CHOOSING_METHOD,
    CONFIRMING,
    SELECTING_REGION,
    SELECTING_ZONE,
    cancel_report,
    handle_description_input,
    handle_feedback,
    handle_location,
    handle_location_cancel_text,
    handle_report_back_to_regions,
    handle_report_cancel,
    handle_report_confirm,
    handle_report_location_button,
    handle_report_manual,
    handle_report_region_selection,
    handle_report_skip_description,
    handle_report_zone,
    recent,
    report,
)
from .handlers.user import (
    feedback_command,
    handle_back_to_regions,
    handle_region_selection,
    handle_unsubscribe_callback,
    handle_zone_done,
    handle_zone_selection,
    help_command,
    mystats,
    myzones,
    share,
    start,
    subscribe,
    unsubscribe,
)
from .health import start_health_server, stop_health_server
from .logging_config import setup_logging

# Backward-compatible re-exports (tests import these from bot.main)
from .handlers.admin import ADMIN_COMMANDS_DETAILED, ADMIN_COMMANDS_HELP, admin_only  # noqa: F401
from .services.moderation import _check_auto_flag, ban_check  # noqa: F401
from .ui.messages import build_alert_message  # noqa: F401
from .utils import (  # noqa: F401
    generate_sighting_id,
    get_accuracy_indicator,
    get_reporter_badge,
    haversine_meters,
    sanitize_description,
)
from .zones import ZONE_COORDS, ZONES  # noqa: F401

# Set up structured logging (must happen before any logger usage)
setup_logging(log_format=LOG_FORMAT)
logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context):
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


async def error_handler(update: object, context):
    """Global error handler — logs the full traceback and notifies the user."""
    logger.error("Unhandled exception:", exc_info=context.error)
    if update and isinstance(update, Update) and update.effective_chat:
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, something went wrong. Please try again later.",
            )


async def cleanup_job(context):
    """Scheduled job to clean up old sightings."""
    deleted = await get_db().cleanup_old_sightings(SIGHTING_RETENTION_DAYS)
    if deleted:
        logger.info(f"Cleaned up {deleted} old sighting(s)")


async def post_init(application):
    """Initialize database, health check, and Sentry after application startup."""
    await init_db(DATABASE_URL)

    # Start health check server
    run_mode = "webhook" if WEBHOOK_URL else "polling"
    if HEALTH_CHECK_ENABLED:
        await start_health_server(HEALTH_CHECK_PORT, run_mode=run_mode)


async def post_shutdown(application):
    """Shut down health check server and close database."""
    await stop_health_server()
    await close_db()


def _init_sentry() -> None:
    """Initialize Sentry error tracking if SENTRY_DSN is configured."""
    if not SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            release=f"parkwatch-bot@{BOT_VERSION}",
            traces_sample_rate=0.1,
            environment="production" if WEBHOOK_URL else "development",
        )
        logger.info("Sentry error tracking initialized")
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — skipping Sentry init")


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        return

    # Initialize Sentry error tracking (if configured)
    _init_sentry()

    # Create application with lifecycle hooks
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

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
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(handle_callback))

    # Global error handler
    app.add_error_handler(error_handler)

    # Schedule sighting cleanup every 6 hours
    app.job_queue.run_repeating(cleanup_job, interval=21600, first=60)

    # Start bot in webhook or polling mode
    if WEBHOOK_URL:
        logger.info(
            "ParkWatch SG Bot v%s starting in webhook mode on port %d",
            BOT_VERSION,
            PORT,
        )
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=f"webhook/{TELEGRAM_BOT_TOKEN}",
            webhook_url=f"{WEBHOOK_URL}/webhook/{TELEGRAM_BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("ParkWatch SG Bot v%s starting in polling mode", BOT_VERSION)
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
