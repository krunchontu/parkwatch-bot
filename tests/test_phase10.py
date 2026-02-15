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
