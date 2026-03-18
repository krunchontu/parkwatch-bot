"""Handler-level tests for callback query routing and feedback handling.

Tests: handle_callback routing, feedback positive/negative, zone toggle,
       report_from_start entry point.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from .helpers import make_callback_update, make_context, make_mock_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestHandleCallbackRouting:
    """Tests that handle_callback routes to the correct handler."""

    def test_start_back_routes_to_back_handler(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="start_back")
        with patch("bot.main.back_to_start_menu", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_start_report_is_skipped(self):
        """start_report should be a no-op in handle_callback (ConversationHandler owns it)."""
        from bot.main import handle_callback

        update = make_callback_update(callback_data="start_report")
        # Should not raise and should not call handle_start_menu
        with patch("bot.main.handle_start_menu", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_not_called()

    def test_start_subscribe_routes_to_menu(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="start_subscribe")
        with patch("bot.main.handle_start_menu", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_region_routes_to_region_handler(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="region_central")
        with patch("bot.main.handle_region_selection", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_zone_done_routes_correctly(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="zone_done")
        with patch("bot.main.handle_zone_done", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_zone_routes_to_zone_handler(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="zone_Bugis")
        with patch("bot.main.handle_zone_selection", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_unsub_routes_to_unsub_handler(self):
        from bot.main import handle_callback

        update = make_callback_update(callback_data="unsub_Bugis")
        with patch("bot.main.handle_unsubscribe_callback", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once()

    def test_feedback_pos_routes_correctly(self):
        from bot.main import handle_callback

        uid = "a1b2c3d4-e5f6-4789-abcd-ef0123456789"
        update = make_callback_update(callback_data=f"feedback_pos_{uid}")
        with patch("bot.main.handle_feedback", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once_with(update, mock_handler.call_args[0][1], is_positive=True)

    def test_feedback_neg_routes_correctly(self):
        from bot.main import handle_callback

        uid = "a1b2c3d4-e5f6-4789-abcd-ef0123456789"
        update = make_callback_update(callback_data=f"feedback_neg_{uid}")
        with patch("bot.main.handle_feedback", new_callable=AsyncMock) as mock_handler:
            _run(handle_callback(update, make_context()))
            mock_handler.assert_called_once_with(update, mock_handler.call_args[0][1], is_positive=False)


class TestReportFromStart:
    """Tests for the report_from_start ConversationHandler entry point."""

    def test_report_from_start_deletes_menu_and_sends_choice(self):
        from bot.handlers.report import CHOOSING_METHOD, report_from_start

        update = make_callback_update(callback_data="start_report")
        context = make_context()
        mock_db = make_mock_db()

        with patch("bot.services.moderation.get_db", return_value=mock_db):
            result = _run(report_from_start(update, context))

        update.callback_query.answer.assert_called_once()
        update.callback_query.message.delete.assert_called_once()
        context.bot.send_message.assert_called_once()
        assert result == CHOOSING_METHOD


class TestFeedbackCallbackValidation:
    """Tests for feedback callback data validation."""

    def test_invalid_uuid_returns_early(self):
        from bot.handlers.report import handle_feedback

        update = make_callback_update(callback_data="feedback_pos_not-a-uuid")
        update.callback_query.answer = AsyncMock()

        _run(handle_feedback(update, make_context(), is_positive=True))

        update.callback_query.answer.assert_called()
        answer_text = update.callback_query.answer.call_args[0][0]
        assert "invalid" in answer_text.lower()

    def test_valid_uuid_proceeds(self):
        from bot.handlers.report import handle_feedback

        uid = "a1b2c3d4-e5f6-4789-abcd-ef0123456789"
        update = make_callback_update(callback_data=f"feedback_pos_{uid}")
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.edit_message_reply_markup = AsyncMock()

        mock_db = make_mock_db(get_sighting_reporter=None)  # sighting expired

        with patch("bot.handlers.report.get_db", return_value=mock_db):
            _run(handle_feedback(update, make_context(), is_positive=True))

        # Should have tried to look up the sighting reporter
        mock_db.get_sighting_reporter.assert_called_once_with(uid)
