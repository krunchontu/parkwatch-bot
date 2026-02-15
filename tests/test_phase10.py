"""Tests for Phase 10: Architecture, UX & Communication.

Tests for /feedback command, rate limiting, admin relay,
audit logging, and database rate-limit method.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 10.3.3 Database: count_user_feedback_since
# ---------------------------------------------------------------------------
class TestCountUserFeedbackSince:
    """Tests for the count_user_feedback_since database method."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_feedback(self, db):
        """Should return 0 when user has sent no feedback."""
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 0

    @pytest.mark.asyncio
    async def test_counts_recent_feedback(self, db):
        """Should count feedback messages within the time window."""
        await db.log_admin_action(100, "user_feedback", target="100", detail="test")
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 1

    @pytest.mark.asyncio
    async def test_excludes_old_feedback(self, db):
        """Should not count feedback older than the time window."""
        # Log a feedback action, then check with a future 'since' time
        await db.log_admin_action(100, "user_feedback", target="100", detail="old message")
        since = datetime.now(timezone.utc) + timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 0

    @pytest.mark.asyncio
    async def test_excludes_other_actions(self, db):
        """Should not count non-feedback admin actions."""
        await db.log_admin_action(100, "view_stats", target="100")
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 0

    @pytest.mark.asyncio
    async def test_excludes_other_users(self, db):
        """Should not count feedback from other users."""
        await db.log_admin_action(200, "user_feedback", target="200", detail="other user")
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 0

    @pytest.mark.asyncio
    async def test_counts_multiple_feedback(self, db):
        """Should count multiple feedback messages within the window."""
        await db.log_admin_action(100, "user_feedback", target="100", detail="first")
        await db.log_admin_action(100, "user_feedback", target="100", detail="second")
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_user_feedback_since(100, since)
        assert count == 2


# ---------------------------------------------------------------------------
# 10.3.1 /feedback command handler
# ---------------------------------------------------------------------------
class TestFeedbackCommand:
    """Tests for the /feedback command handler."""

    def _make_update(self, user_id=100, username="testuser", text="/feedback hello"):
        """Create a mock Update for testing."""
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_user.username = username
        update.effective_user.first_name = "Test"
        update.message.text = text
        update.message.reply_text = AsyncMock()
        return update

    def _mock_db(self, is_banned=False, feedback_count=0, report_count=0):
        """Create a mock DB that satisfies both ban_check and feedback_command."""
        mock = MagicMock()
        mock.is_banned = AsyncMock(return_value=is_banned)
        mock.count_user_feedback_since = AsyncMock(return_value=feedback_count)
        mock.get_user_stats = AsyncMock(return_value={"report_count": report_count})
        mock.log_admin_action = AsyncMock()
        return mock

    def _run(self, update, context, mock_db, admin_ids=None):
        """Run feedback_command with both get_db patches (ban_check + handler)."""
        from bot.handlers.user import feedback_command

        if admin_ids is None:
            admin_ids = {111}
        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.ADMIN_USER_IDS", admin_ids),
        ):
            asyncio.get_event_loop().run_until_complete(feedback_command(update, context))

    def test_feedback_no_message_shows_usage(self):
        """Should show usage when no message is provided."""
        update = self._make_update(text="/feedback")
        context = MagicMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "Usage" in call_text

    def test_feedback_empty_message_shows_usage(self):
        """Should show usage when message is just whitespace."""
        update = self._make_update(text="/feedback   ")
        context = MagicMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "Usage" in call_text

    def test_feedback_sends_to_admins(self):
        """Should relay the feedback message to all admin users."""
        update = self._make_update(text="/feedback Great bot!")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db(report_count=5)

        self._run(update, context, mock_db, admin_ids={111, 222})

        # Should send to both admins
        assert context.bot.send_message.call_count == 2
        admin_ids_called = {call.kwargs["chat_id"] for call in context.bot.send_message.call_args_list}
        assert admin_ids_called == {111, 222}

        # Message should contain the feedback text
        sent_text = context.bot.send_message.call_args_list[0].kwargs["text"]
        assert "Great bot!" in sent_text
        assert "testuser" in sent_text

    def test_feedback_confirms_to_user(self):
        """Should confirm to the user that feedback was sent."""
        update = self._make_update(text="/feedback Nice work")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        # Last call to reply_text should be the confirmation
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Thanks" in reply_text or "feedback" in reply_text.lower()

    def test_feedback_rate_limited(self):
        """Should block if user already sent feedback within the hour."""
        update = self._make_update(text="/feedback More stuff")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db(feedback_count=1)

        self._run(update, context, mock_db)

        # Should show rate limit message, not relay
        reply_text = update.message.reply_text.call_args[0][0]
        assert "hour" in reply_text.lower()
        context.bot.send_message.assert_not_called()

    def test_feedback_logs_audit_action(self):
        """Should log the feedback to admin_actions audit trail."""
        update = self._make_update(text="/feedback Bug report: zones not loading")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db(report_count=2)

        self._run(update, context, mock_db)

        mock_db.log_admin_action.assert_called_once()
        call_args = mock_db.log_admin_action.call_args
        assert call_args[0][0] == 100  # user_id
        assert call_args[0][1] == "user_feedback"
        assert call_args[1]["target"] == "100"
        assert "Bug report" in call_args[1]["detail"]

    def test_feedback_truncates_long_detail(self):
        """Should truncate detail preview to 100 chars in audit log."""
        long_msg = "x" * 200
        update = self._make_update(text=f"/feedback {long_msg}")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        detail = mock_db.log_admin_action.call_args[1]["detail"]
        assert len(detail) == 103  # 100 chars + "..."
        assert detail.endswith("...")

    def test_feedback_with_no_admins_configured(self):
        """Should still confirm to user even if no admins are configured."""
        update = self._make_update(text="/feedback hello")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db, admin_ids=set())

        # No admin messages sent
        context.bot.send_message.assert_not_called()
        # But user gets confirmation
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Thanks" in reply_text

    def test_feedback_includes_user_badge(self):
        """Admin notification should include the user's reporter badge."""
        update = self._make_update(text="/feedback test")
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db(report_count=15)

        self._run(update, context, mock_db)

        sent_text = context.bot.send_message.call_args.kwargs["text"]
        assert "Trusted" in sent_text  # 15 reports = Trusted badge
        assert "15 reports" in sent_text

    def test_feedback_blocked_for_banned_user(self):
        """Banned users should not be able to send feedback."""
        update = self._make_update(text="/feedback test")
        context = MagicMock()
        mock_db = self._mock_db(is_banned=True)

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "restricted" in reply_text.lower()
        mock_db.count_user_feedback_since.assert_not_called()


# ---------------------------------------------------------------------------
# 10.3.4 /help includes /feedback
# ---------------------------------------------------------------------------
class TestHelpIncludesFeedback:
    """Tests that /help output mentions /feedback."""

    def test_help_text_mentions_feedback(self):
        """The /help command should list /feedback."""
        from bot.handlers.user import help_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(help_command(update, MagicMock()))

        help_text = update.message.reply_text.call_args[0][0]
        assert "/feedback" in help_text


# ---------------------------------------------------------------------------
# 10.3.3 Database: get_all_user_ids
# ---------------------------------------------------------------------------
class TestGetAllUserIds:
    """Tests for the get_all_user_ids database method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_users(self, db):
        """Should return empty list when no users exist."""
        ids = await db.get_all_user_ids()
        assert ids == []

    @pytest.mark.asyncio
    async def test_returns_all_user_ids(self, db):
        """Should return all registered user IDs."""
        await db.ensure_user(100, "alice")
        await db.ensure_user(200, "bob")
        await db.ensure_user(300, "charlie")
        ids = await db.get_all_user_ids()
        assert set(ids) == {100, 200, 300}


# ---------------------------------------------------------------------------
# 10.4 /admin announce command
# ---------------------------------------------------------------------------
class TestAdminAnnounce:
    """Tests for the /admin announce command."""

    def _make_update(self, user_id=999, text="/admin announce"):
        """Create a mock Update for admin testing."""
        update = MagicMock()
        update.effective_user.id = user_id
        update.message.text = text
        update.message.reply_text = AsyncMock()
        return update

    def _mock_db(self, user_ids=None, zone_subscribers=None):
        """Create a mock DB for announce testing."""
        mock = MagicMock()
        mock.is_banned = AsyncMock(return_value=False)
        mock.get_all_user_ids = AsyncMock(return_value=user_ids or [])
        mock.get_zone_subscribers = AsyncMock(return_value=zone_subscribers or [])
        mock.log_admin_action = AsyncMock()
        mock.clear_subscriptions = AsyncMock()
        return mock

    def _run(self, update, context, mock_db, admin_ids=None):
        """Run admin_command with mock DB and admin auth."""
        from bot.handlers.admin import admin_command

        if admin_ids is None:
            admin_ids = {999}
        with (
            patch("bot.handlers.admin.ADMIN_USER_IDS", admin_ids),
            patch("bot.handlers.admin.get_db", return_value=mock_db),
        ):
            asyncio.get_event_loop().run_until_complete(admin_command(update, context))

    def test_announce_no_args_shows_usage(self):
        """Should show usage when no arguments provided."""
        update = self._make_update(text="/admin announce")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply_text

    def test_announce_all_shows_preview(self):
        """Should show preview with recipient count for 'all' scope."""
        update = self._make_update(text="/admin announce all Hello everyone!")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db(user_ids=[100, 200, 300])

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Preview" in reply_text
        assert "3" in reply_text  # 3 recipients
        assert "Hello everyone!" in reply_text
        assert "confirm" in reply_text.lower()

    def test_announce_all_stores_pending(self):
        """Should store pending announcement in context.user_data."""
        update = self._make_update(text="/admin announce all Test message")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db(user_ids=[100, 200])

        self._run(update, context, mock_db)

        pending = context.user_data.get("pending_announce")
        assert pending is not None
        assert pending["scope"] == "all users"
        assert pending["recipients"] == [100, 200]
        assert "Test message" in pending["message"]

    def test_announce_zone_shows_preview(self):
        """Should show preview for zone-scoped announcement."""
        update = self._make_update(text="/admin announce zone Bugis Watch out for roadworks")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db(zone_subscribers=[100, 200])

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Preview" in reply_text
        assert "Bugis" in reply_text
        assert "Watch out for roadworks" in reply_text

    def test_announce_zone_invalid_zone(self):
        """Should reject announcements to non-existent zones."""
        update = self._make_update(text="/admin announce zone NonExistentZone Hello")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Could not parse" in reply_text or "not found" in reply_text.lower()

    def test_announce_confirm_sends_messages(self):
        """Should send messages to all recipients on confirm."""
        update = self._make_update(text="/admin announce confirm")
        context = MagicMock()
        context.user_data = {
            "pending_announce": {
                "message": "Test broadcast",
                "recipients": [100, 200, 300],
                "scope": "all users",
                "raw_text": "Test broadcast",
            }
        }
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        assert context.bot.send_message.call_count == 3
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Sent: 3" in reply_text

    def test_announce_confirm_no_pending(self):
        """Should show error when no pending announcement."""
        update = self._make_update(text="/admin announce confirm")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "No pending" in reply_text

    def test_announce_confirm_handles_blocked_users(self):
        """Should handle Forbidden errors and clean up blocked users."""
        from telegram.error import Forbidden as TgForbidden

        update = self._make_update(text="/admin announce confirm")
        context = MagicMock()
        context.user_data = {
            "pending_announce": {
                "message": "Test",
                "recipients": [100, 200],
                "scope": "all users",
                "raw_text": "Test",
            }
        }

        # First send succeeds, second raises Forbidden
        context.bot.send_message = AsyncMock(side_effect=[None, TgForbidden("Forbidden: bot was blocked by the user")])
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Sent: 1" in reply_text
        assert "Failed: 1" in reply_text
        assert "Blocked" in reply_text
        mock_db.clear_subscriptions.assert_called_once_with(200)

    def test_announce_confirm_logs_action(self):
        """Should log the announcement to audit trail."""
        update = self._make_update(text="/admin announce confirm")
        context = MagicMock()
        context.user_data = {
            "pending_announce": {
                "message": "Hello world",
                "recipients": [100],
                "scope": "all users",
                "raw_text": "Hello world",
            }
        }
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        mock_db.log_admin_action.assert_called_once()
        call_args = mock_db.log_admin_action.call_args
        assert call_args[0][1] == "announce"
        assert "all users" in call_args[1]["target"]

    def test_announce_confirm_clears_pending(self):
        """Should clear pending announcement after sending."""
        update = self._make_update(text="/admin announce confirm")
        context = MagicMock()
        context.user_data = {
            "pending_announce": {
                "message": "Test",
                "recipients": [100],
                "scope": "all users",
                "raw_text": "Test",
            }
        }
        context.bot.send_message = AsyncMock()
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        assert "pending_announce" not in context.user_data

    def test_announce_all_no_message(self):
        """Should show usage when 'all' has no message."""
        update = self._make_update(text="/admin announce all")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply_text

    def test_announce_zone_no_message(self):
        """Should show usage when 'zone' has no message."""
        update = self._make_update(text="/admin announce zone")
        context = MagicMock()
        context.user_data = {}
        mock_db = self._mock_db()

        self._run(update, context, mock_db)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply_text


# ---------------------------------------------------------------------------
# 10.4.4 Admin help includes announce
# ---------------------------------------------------------------------------
class TestAdminHelpIncludesAnnounce:
    """Tests that admin help includes announce commands."""

    def test_admin_help_has_announce(self):
        """ADMIN_COMMANDS_HELP should include announce."""
        from bot.handlers.admin import ADMIN_COMMANDS_HELP

        help_text = " ".join(ADMIN_COMMANDS_HELP.keys())
        assert "announce" in help_text

    def test_admin_detailed_has_announce(self):
        """ADMIN_COMMANDS_DETAILED should include announce."""
        from bot.handlers.admin import ADMIN_COMMANDS_DETAILED

        assert "announce" in ADMIN_COMMANDS_DETAILED


# ---------------------------------------------------------------------------
# 10.5 UX Discoverability — Richer /start Menu
# ---------------------------------------------------------------------------
class TestStartMenu:
    """Tests for the richer /start menu with quick-action buttons."""

    def test_start_shows_quick_action_buttons(self):
        """The /start command should show quick-action inline buttons."""
        from bot.handlers.user import start

        update = MagicMock()
        update.message.reply_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(start(update, MagicMock()))

        call_kwargs = update.message.reply_text.call_args
        reply_markup = call_kwargs[1].get("reply_markup") or call_kwargs.kwargs.get("reply_markup")
        assert reply_markup is not None

        # Extract all callback_data values from the keyboard
        callback_datas = []
        for row in reply_markup.inline_keyboard:
            for button in row:
                callback_datas.append(button.callback_data)

        assert "start_subscribe" in callback_datas
        assert "start_report" in callback_datas
        assert "start_recent" in callback_datas
        assert "start_mystats" in callback_datas
        assert "start_feedback" in callback_datas
        assert "start_help" in callback_datas

    def test_start_menu_subscribe_callback(self):
        """Clicking 'Subscribe to Zones' should show region selection."""
        from bot.handlers.user import handle_start_menu

        update = MagicMock()
        update.callback_query.data = "start_subscribe"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_start_menu(update, MagicMock()))

        update.callback_query.answer.assert_called_once()
        call_kwargs = update.callback_query.edit_message_text.call_args
        # Should show region keyboard
        reply_markup = call_kwargs[1].get("reply_markup") or call_kwargs.kwargs.get("reply_markup")
        assert reply_markup is not None
        # Should contain region buttons
        callback_datas = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        assert any(d.startswith("region_") for d in callback_datas)

    def test_start_menu_report_callback(self):
        """Clicking 'Report a Sighting' should show report instructions."""
        from bot.handlers.user import handle_start_menu

        update = MagicMock()
        update.callback_query.data = "start_report"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_start_menu(update, MagicMock()))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/report" in text

    def test_start_menu_feedback_callback(self):
        """Clicking 'Send Feedback' should show feedback instructions."""
        from bot.handlers.user import handle_start_menu

        update = MagicMock()
        update.callback_query.data = "start_feedback"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_start_menu(update, MagicMock()))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/feedback" in text

    def test_start_menu_help_callback(self):
        """Clicking 'Help' should show help instructions."""
        from bot.handlers.user import handle_start_menu

        update = MagicMock()
        update.callback_query.data = "start_help"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_start_menu(update, MagicMock()))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/help" in text


class TestPostActionPrompts:
    """Tests for contextual next-step prompts after actions."""

    def test_zone_done_shows_next_steps(self):
        """After subscribing, Done message should suggest next actions."""
        from bot.handlers.user import handle_zone_done

        update = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user.id = 100

        mock_db = MagicMock()
        mock_db.get_subscriptions = AsyncMock(return_value={"Bugis", "Orchard"})

        context = MagicMock()
        context.user_data = {}

        with patch("bot.handlers.user.get_db", return_value=mock_db):
            asyncio.get_event_loop().run_until_complete(handle_zone_done(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/subscribe" in text
        assert "/report" in text
        assert "/recent" in text


class TestHelpDescribesStartMenu:
    """Tests that /help mentions the /start menu."""

    def test_help_describes_start_as_main_menu(self):
        """Help text should describe /start as 'Main menu'."""
        from bot.handlers.user import help_command

        update = MagicMock()
        update.message.reply_text = AsyncMock()

        asyncio.get_event_loop().run_until_complete(help_command(update, MagicMock()))

        help_text = update.message.reply_text.call_args[0][0]
        assert "Main menu" in help_text or "main menu" in help_text
