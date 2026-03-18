"""Shared test helpers for building mock Telegram objects."""

from unittest.mock import AsyncMock, MagicMock


def make_update(user_id=100, username="testuser", first_name="Test", chat_id=None):
    """Create a mock Telegram Update for command handler testing."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = first_name
    update.effective_chat.id = chat_id or user_id
    update.message.reply_text = AsyncMock()
    update.message.text = ""
    # Explicitly set callback_query to None for command handlers
    update.callback_query = None
    return update


def make_callback_update(user_id=100, callback_data="", username="testuser"):
    """Create a mock Telegram Update for callback query testing."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = "Test"
    update.effective_chat.id = user_id
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message.delete = AsyncMock()
    # Set message to None for callback-only updates
    update.message = None
    return update


def make_context(user_data=None):
    """Create a mock Telegram Context."""
    context = MagicMock()
    context.user_data = user_data or {}
    context.bot.send_message = AsyncMock()
    context.bot.get_me = AsyncMock(return_value=MagicMock(username="testbot"))
    return context


def make_mock_db(**overrides):
    """Create a mock Database with common async methods.

    Pass keyword arguments to override default return values, e.g.:
        make_mock_db(is_banned=True, get_subscriptions={"Bugis"})
    """
    db = MagicMock()
    db.is_banned = AsyncMock(return_value=overrides.get("is_banned", False))
    db.get_subscriptions = AsyncMock(return_value=overrides.get("get_subscriptions", set()))
    db.get_user_stats = AsyncMock(return_value=overrides.get("get_user_stats", {"report_count": 0}))
    db.calculate_accuracy = AsyncMock(return_value=overrides.get("calculate_accuracy", (0.0, 0)))
    db.get_user_feedback_totals = AsyncMock(return_value=overrides.get("get_user_feedback_totals", (0, 0)))
    db.get_recent_sightings_for_zones = AsyncMock(return_value=overrides.get("get_recent_sightings_for_zones", []))
    db.ensure_user = AsyncMock()
    db.add_subscription = AsyncMock()
    db.remove_subscription = AsyncMock()
    db.clear_subscriptions = AsyncMock()
    db.log_admin_action = AsyncMock()
    db.record_rate_limit_event = AsyncMock()
    db.count_user_feedback_since = AsyncMock(return_value=overrides.get("count_user_feedback_since", 0))
    db.count_feedback_votes_since = AsyncMock(return_value=overrides.get("count_feedback_votes_since", 0))
    db.get_zone_subscribers = AsyncMock(return_value=overrides.get("get_zone_subscribers", []))
    db.get_sighting = AsyncMock(return_value=overrides.get("get_sighting"))
    db.get_sighting_reporter = AsyncMock(return_value=overrides.get("get_sighting_reporter"))
    db.apply_feedback = AsyncMock(return_value=overrides.get("apply_feedback"))
    db.calculate_accuracy_batch = AsyncMock(return_value=overrides.get("calculate_accuracy_batch", {}))
    return db
