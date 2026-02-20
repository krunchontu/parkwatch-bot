"""Handler-level tests for user command handlers.

Tests: /start, /subscribe, /myzones, /help, /mystats, /feedback,
       start menu callbacks, back button navigation.
"""

import asyncio
from unittest.mock import patch

import pytest

from .helpers import make_callback_update, make_context, make_mock_db, make_update


def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestStartCommand:
    """Tests for /start command."""

    def test_start_sends_welcome_and_keyboard(self):
        from bot.handlers.user import start

        update = make_update()
        _run(start(update, make_context()))

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "ParkWatch SG" in text
        reply_markup = call_args[1]["reply_markup"]
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_subscribe" in buttons
        assert "start_report" in buttons
        assert "start_recent" in buttons
        assert "start_mystats" in buttons
        assert "start_feedback" in buttons
        assert "start_help" in buttons


class TestStartMenuCallbacks:
    """Tests for start menu button callbacks."""

    def test_recent_shows_content_with_back_button(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_recent")
        mock_db = make_mock_db(get_subscriptions={"Bugis"})

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        reply_markup = call_args[1].get("reply_markup")
        assert reply_markup is not None
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_back" in buttons

    def test_mystats_shows_content_with_back_button(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_mystats")
        mock_db = make_mock_db()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        text = call_args[0][0]
        assert "Reporter Stats" in text
        assert call_args[1].get("parse_mode") == "Markdown"
        reply_markup = call_args[1].get("reply_markup")
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_back" in buttons

    def test_help_shows_commands_with_back_button(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_help")
        mock_db = make_mock_db()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        text = call_args[0][0]
        assert "/subscribe" in text
        assert "/report" in text
        reply_markup = call_args[1].get("reply_markup")
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_back" in buttons

    def test_feedback_shows_instructions_with_back_button(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_feedback")
        mock_db = make_mock_db()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        text = call_args[0][0]
        assert "/feedback" in text
        reply_markup = call_args[1].get("reply_markup")
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_back" in buttons

    def test_subscribe_shows_regions(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_subscribe")
        mock_db = make_mock_db()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        reply_markup = call_args[1].get("reply_markup")
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert any(d.startswith("region_") for d in buttons)


class TestBackToStartMenu:
    """Tests for the '<< Back to Menu' button."""

    def test_back_restores_start_menu(self):
        from bot.handlers.user import back_to_start_menu

        update = make_callback_update(callback_data="start_back")
        _run(back_to_start_menu(update, make_context()))

        call_args = update.callback_query.edit_message_text.call_args
        text = call_args[0][0]
        assert "ParkWatch SG" in text
        reply_markup = call_args[1].get("reply_markup")
        buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert "start_subscribe" in buttons


class TestHelpCommand:
    """Tests for /help command handler."""

    def test_help_includes_all_commands(self):
        from bot.handlers.user import help_command

        update = make_update()
        _run(help_command(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "/start" in text
        assert "/subscribe" in text
        assert "/report" in text
        assert "/recent" in text
        assert "/mystats" in text
        assert "/feedback" in text
        assert "/help" in text


class TestMyZonesCommand:
    """Tests for /myzones command handler."""

    def test_myzones_no_subscriptions(self):
        from bot.handlers.user import myzones

        update = make_update()
        mock_db = make_mock_db(get_subscriptions=set())

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(myzones(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "not subscribed" in text.lower()

    def test_myzones_with_subscriptions(self):
        from bot.handlers.user import myzones

        update = make_update()
        mock_db = make_mock_db(get_subscriptions={"Bugis", "Orchard"})

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(myzones(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "Bugis" in text
        assert "Orchard" in text


class TestMyStatsCommand:
    """Tests for /mystats command handler."""

    def test_mystats_no_reports(self):
        from bot.handlers.user import mystats

        update = make_update()
        mock_db = make_mock_db()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(mystats(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "haven't reported" in text.lower()

    def test_mystats_with_reports(self):
        from bot.handlers.user import mystats

        update = make_update()
        mock_db = make_mock_db(
            get_user_stats={"report_count": 5},
            calculate_accuracy=(0.85, 4),
            get_user_feedback_totals=(4, 1),
        )

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(mystats(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "5" in text  # report count
        assert "85%" in text  # accuracy


class TestBanCheckOnCallbacks:
    """Tests verifying ban_check works on callback queries."""

    def test_banned_user_gets_alert_on_callback(self):
        from bot.handlers.user import handle_start_menu

        update = make_callback_update(callback_data="start_help")
        mock_db = make_mock_db(is_banned=True)

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(handle_start_menu(update, make_context()))

        # Should NOT have edited the message (ban_check returned early)
        update.callback_query.edit_message_text.assert_not_called()

    def test_banned_user_gets_rejection_on_command(self):
        from bot.handlers.user import myzones

        update = make_update()
        mock_db = make_mock_db(is_banned=True)

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
        ):
            _run(myzones(update, make_context()))

        text = update.message.reply_text.call_args[0][0]
        assert "restricted" in text.lower()


class TestTextBuilders:
    """Tests for the extracted text builder functions."""

    @pytest.mark.asyncio
    async def test_build_help_text_has_all_commands(self):
        from bot.handlers.user import _build_help_text

        text = _build_help_text()
        assert "/start" in text
        assert "/report" in text
        assert "/subscribe" in text
        assert "/recent" in text
        assert "/mystats" in text
        assert "/feedback" in text

    @pytest.mark.asyncio
    async def test_build_recent_text_no_zones(self):
        from bot.handlers.user import _build_recent_text

        mock_db = make_mock_db(get_subscriptions=set())
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_recent_text(100)
        assert "not subscribed" in text.lower()

    @pytest.mark.asyncio
    async def test_build_recent_text_no_sightings(self):
        from bot.handlers.user import _build_recent_text

        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=[],
        )
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_recent_text(100)
        assert "no recent" in text.lower()

    @pytest.mark.asyncio
    async def test_build_mystats_text_no_reports(self):
        from bot.handlers.user import _build_mystats_text

        mock_db = make_mock_db()
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_mystats_text(100)
        assert "haven't reported" in text.lower()

    @pytest.mark.asyncio
    async def test_build_mystats_text_with_reports(self):
        from bot.handlers.user import _build_mystats_text

        mock_db = make_mock_db(
            get_user_stats={"report_count": 12},
            calculate_accuracy=(0.9, 10),
            get_user_feedback_totals=(9, 1),
        )
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_mystats_text(100)
        assert "12" in text
        assert "90%" in text
        assert "Trusted" in text
