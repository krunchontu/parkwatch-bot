"""Phase 11 maintenance mode tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.services.maintenance import maintenance_check, maintenance_conversation_check


@pytest.mark.asyncio
async def test_maintenance_check_blocks_user_handler():
    called = {"ok": False}

    @maintenance_check
    async def sample_handler(update, context):
        called["ok"] = True

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)):
        await sample_handler(update, context)

    assert called["ok"] is False
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_maintenance_check_allows_when_off():
    """User handlers execute normally when maintenance is off."""
    called = {"ok": False}

    @maintenance_check
    async def sample_handler(update, context):
        called["ok"] = True

    update = MagicMock()
    context = MagicMock()

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=False)):
        await sample_handler(update, context)

    assert called["ok"] is True


@pytest.mark.asyncio
async def test_maintenance_check_blocks_callback_query():
    """maintenance_check blocks callback queries during maintenance."""
    called = {"ok": False}

    @maintenance_check
    async def sample_handler(update, context):
        called["ok"] = True

    update = MagicMock()
    update.message = None
    update.callback_query.answer = AsyncMock()
    update.inline_query = None
    context = MagicMock()

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)):
        await sample_handler(update, context)

    assert called["ok"] is False
    update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_maintenance_check_blocks_inline_query():
    """maintenance_check blocks inline queries during maintenance."""
    called = {"ok": False}

    @maintenance_check
    async def sample_handler(update, context):
        called["ok"] = True

    update = MagicMock()
    update.message = None
    update.callback_query = None
    update.inline_query.answer = AsyncMock()
    context = MagicMock()

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)):
        await sample_handler(update, context)

    assert called["ok"] is False
    update.inline_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_maintenance_conversation_ends_flow():
    @maintenance_conversation_check
    async def sample_handler(update, context):
        return 1

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    context = MagicMock()
    context.user_data = {
        "pending_report_zone": "Bugis",
        "pending_report_description": "x",
        "pending_report_lat": 1.0,
        "pending_report_lng": 2.0,
        "report_region": "central",
    }

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)):
        result = await sample_handler(update, context)

    assert result == ConversationHandler.END
    assert context.user_data == {}


@pytest.mark.asyncio
async def test_maintenance_conversation_sends_single_message():
    """Conversation cancellation sends a single combined message, not two."""

    @maintenance_conversation_check
    async def sample_handler(update, context):
        return 1

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    context = MagicMock()
    context.user_data = {"pending_report_zone": "Bugis"}

    with (
        patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)),
        patch(
            "bot.services.maintenance.maintenance_message",
            AsyncMock(return_value="Under maintenance."),
        ),
    ):
        await sample_handler(update, context)

    # Should send exactly ONE message containing both maintenance info and cancellation
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Under maintenance." in msg
    assert "cancelled due to maintenance" in msg


@pytest.mark.asyncio
async def test_maintenance_conversation_via_callback_query():
    """Conversation cancellation works via callback query."""

    @maintenance_conversation_check
    async def sample_handler(update, context):
        return 1

    update = MagicMock()
    update.message = None
    update.callback_query.message.reply_text = AsyncMock()
    context = MagicMock()
    context.user_data = {"pending_report_zone": "Bugis"}

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=True)):
        result = await sample_handler(update, context)

    assert result == ConversationHandler.END
    update.callback_query.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_maintenance_conversation_allows_when_off():
    """Conversation handlers execute normally when maintenance is off."""

    @maintenance_conversation_check
    async def sample_handler(update, context):
        return 42

    update = MagicMock()
    context = MagicMock()
    context.user_data = {"pending_report_zone": "Bugis"}

    with patch("bot.services.maintenance.is_maintenance_enabled", AsyncMock(return_value=False)):
        result = await sample_handler(update, context)

    assert result == 42
    # user_data should NOT be cleared
    assert context.user_data.get("pending_report_zone") == "Bugis"
