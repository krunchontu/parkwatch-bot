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
async def test_maintenance_conversation_ends_flow():
    @maintenance_conversation_check
    async def sample_handler(update, context):
        return 1

    update = MagicMock()
    update.message.reply_text = AsyncMock()
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
