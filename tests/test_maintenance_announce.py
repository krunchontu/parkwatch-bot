"""Tests for F-013: maintenance announcement via broadcast_message.

Covers:
- Confirm with pending announcement calls broadcast_message (not ad-hoc loop)
- Blocked users get subscriptions cleaned up
- Failed/blocked counts reported to admin
- Confirm without pending announcement shows error
- Maintenance mode and message are set after broadcast
- Audit log includes sent/failed/blocked counts
"""

import asyncio
from unittest.mock import AsyncMock, patch

from tests.helpers import make_context, make_mock_db, make_update


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestMaintenanceAnnounceConfirm:
    """Tests for /admin maintenance on confirm using broadcast_message."""

    def _make_update_and_context(self, pending=None):
        """Create an update and context with optional pending announcement."""
        update = make_update(user_id=1000)
        update.message.text = "/admin maintenance on confirm"
        context = make_context(user_data={})
        if pending is not None:
            context.user_data["pending_maintenance_announce"] = pending
        return update, context

    def test_confirm_no_pending_shows_error(self):
        """Confirm without a pending announcement shows an error."""
        from bot.handlers.admin.config import admin_maintenance

        update, context = self._make_update_and_context(pending=None)

        _run(admin_maintenance(update, context, "confirm"))

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "no pending" in text.lower()

    def test_confirm_calls_broadcast_message(self):
        """Confirm calls broadcast_message instead of a manual loop."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "Scheduled downtime tonight",
            "recipient_ids": [100, 200, 300],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            mock_broadcast.return_value = (3, 0, [])  # all sent, none failed

            _run(admin_maintenance(update, context, "confirm"))

            # broadcast_message was called with correct args
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][1] == [100, 200, 300]  # recipients
            assert "Scheduled downtime tonight" in call_args[0][2]  # text contains message

        # Pending data was consumed
        assert "pending_maintenance_announce" not in context.user_data

    def test_confirm_cleans_blocked_subscriptions(self):
        """Blocked users detected by broadcast_message get subscriptions cleared."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "Going down for maintenance",
            "recipient_ids": [100, 200, 300],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            # User 200 blocked the bot
            mock_broadcast.return_value = (2, 1, [200])

            _run(admin_maintenance(update, context, "confirm"))

        # Subscription cleanup was called for the blocked user
        mock_db.clear_subscriptions.assert_called_once_with(200)

    def test_confirm_reports_failures_to_admin(self):
        """Admin sees failed/blocked counts in the confirmation message."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "Maintenance window",
            "recipient_ids": [100, 200, 300, 400],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            # 2 sent, 1 failed, 1 blocked
            mock_broadcast.return_value = (2, 2, [300])

            _run(admin_maintenance(update, context, "confirm"))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "2 user(s)" in reply_text  # sent count
        assert "2 delivery failure" in reply_text  # failed count
        assert "1 blocked" in reply_text  # blocked count

    def test_confirm_sets_maintenance_mode(self):
        """Maintenance mode and message are set after successful broadcast."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "Quick restart",
            "recipient_ids": [100],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            mock_broadcast.return_value = (1, 0, [])

            _run(admin_maintenance(update, context, "confirm"))

        # Verify settings were set
        calls = mock_settings.set_override.call_args_list
        mode_call = [c for c in calls if c[0][0] == "MAINTENANCE_MODE"]
        msg_call = [c for c in calls if c[0][0] == "MAINTENANCE_MESSAGE"]
        assert len(mode_call) == 1
        assert mode_call[0][0][1] == "true"
        assert len(msg_call) == 1
        assert msg_call[0][0][1] == "Quick restart"

    def test_confirm_logs_with_counts(self):
        """Audit log includes sent, failed, and blocked counts."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "DB migration",
            "recipient_ids": [100, 200],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            mock_broadcast.return_value = (1, 1, [200])

            _run(admin_maintenance(update, context, "confirm"))

        # Check audit log call
        mock_db.log_admin_action.assert_called_once()
        log_call = mock_db.log_admin_action.call_args
        # The detail string should contain all three counts
        assert "sent=1" in str(log_call)
        assert "failed=1" in str(log_call)
        assert "blocked=1" in str(log_call)

    def test_all_sent_no_failure_message(self):
        """When all messages sent successfully, no failure line appears."""
        from bot.handlers.admin.config import admin_maintenance

        pending = {
            "message": "Brief maintenance",
            "recipient_ids": [100, 200],
        }
        update, context = self._make_update_and_context(pending=pending)

        mock_db = make_mock_db()
        mock_settings = AsyncMock()
        mock_settings.set_override = AsyncMock()

        with (
            patch("bot.handlers.admin.config.get_db", return_value=mock_db),
            patch("bot.handlers.admin.config.get_runtime_settings", return_value=mock_settings),
            patch("bot.handlers.admin.config.broadcast_message", new_callable=AsyncMock) as mock_broadcast,
        ):
            mock_broadcast.return_value = (2, 0, [])

            _run(admin_maintenance(update, context, "confirm"))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "2 user(s)" in reply_text
        assert "failure" not in reply_text.lower()
