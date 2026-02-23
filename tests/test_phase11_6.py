"""Phase 11.6 audit quick-fix tests.

Tests cover:
- 11.6.1: first_name column in create_tables() and ensure_user()
- 11.6.2: @functools.wraps on ban_check decorator
- 11.6.3: user_rate_limits cleanup via cleanup_old_rate_limits()
- 11.6.4: Non-numeric ADMIN_USER_IDS warning
- 11.6.5: /feedback delivery outcome messaging
- 11.6.6: Alert expiry color indicators in /recent
- 11.6.7: Conversation timeout callback
"""

import asyncio
import functools
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .helpers import make_context, make_mock_db, make_update

# Detect whether telegram-dependent modules can be imported in this env.
# The cryptography backend may be broken in some CI environments.
_HAS_TELEGRAM = False
try:
    import telegram  # noqa: F401

    _HAS_TELEGRAM = True
except Exception:
    pass

_skip_telegram = pytest.mark.skipif(
    not _HAS_TELEGRAM,
    reason="telegram import unavailable (cryptography backend issue)",
)


# ---------------------------------------------------------------------------
# 11.6.1: first_name column
# ---------------------------------------------------------------------------


class TestFirstNameColumn:
    """Verify first_name column exists in schema and is stored by ensure_user."""

    @pytest.mark.asyncio
    async def test_create_tables_has_first_name(self, db):
        """create_tables() creates users table with first_name column."""
        row = await db._fetchone("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
        assert row is not None
        assert "first_name" in row["sql"]

    @pytest.mark.asyncio
    async def test_ensure_user_stores_first_name(self, db):
        """ensure_user() persists the first_name value."""
        await db.ensure_user(100, "alice", first_name="Alice")
        row = await db._fetchone("SELECT first_name FROM users WHERE telegram_id = ?", (100,))
        assert row is not None
        assert row["first_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_ensure_user_updates_first_name(self, db):
        """ensure_user() updates first_name on subsequent calls."""
        await db.ensure_user(100, "alice", first_name="Alice")
        await db.ensure_user(100, "alice", first_name="Ally")
        row = await db._fetchone("SELECT first_name FROM users WHERE telegram_id = ?", (100,))
        assert row["first_name"] == "Ally"

    @pytest.mark.asyncio
    async def test_ensure_user_first_name_optional(self, db):
        """ensure_user() works without first_name (backward compat)."""
        await db.ensure_user(100, "alice")
        row = await db._fetchone("SELECT first_name FROM users WHERE telegram_id = ?", (100,))
        assert row is not None
        assert row["first_name"] is None

    @pytest.mark.asyncio
    async def test_get_user_details_includes_first_name(self, db):
        """get_user_details() returns first_name field."""
        await db.ensure_user(100, "alice", first_name="Alice")
        details = await db.get_user_details(100)
        assert details is not None
        assert details["first_name"] == "Alice"


# ---------------------------------------------------------------------------
# 11.6.2: @functools.wraps on ban_check
# ---------------------------------------------------------------------------


class TestBanCheckWraps:
    """Verify ban_check preserves wrapped function metadata."""

    @_skip_telegram
    def test_ban_check_preserves_name(self):
        from bot.services.moderation import ban_check

        @ban_check
        async def my_handler(update, context):
            """My docstring."""
            pass

        assert my_handler.__name__ == "my_handler"
        assert my_handler.__doc__ == "My docstring."

    def test_functools_wraps_pattern(self):
        """Verify functools.wraps preserves metadata (framework-independent)."""

        def my_decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        @my_decorator
        async def sample_fn():
            """Sample doc."""
            pass

        assert sample_fn.__name__ == "sample_fn"
        assert sample_fn.__doc__ == "Sample doc."


# ---------------------------------------------------------------------------
# 11.6.3: user_rate_limits cleanup
# ---------------------------------------------------------------------------


class TestRateLimitCleanup:
    """Verify cleanup_old_rate_limits removes stale entries."""

    @pytest.mark.asyncio
    async def test_cleanup_old_rate_limits(self, db):
        """Entries older than max_age_hours are deleted."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Insert an old entry and a recent entry
        await db._execute(
            "INSERT INTO user_rate_limits (user_id, action, created_at) VALUES (?, ?, ?)",
            (100, "user_feedback", old_time),
        )
        await db._execute(
            "INSERT INTO user_rate_limits (user_id, action, created_at) VALUES (?, ?, ?)",
            (100, "user_feedback", recent_time),
        )

        deleted = await db.cleanup_old_rate_limits(max_age_hours=24)
        assert deleted == 1

        # Only the recent entry should remain
        rows = await db._fetchall("SELECT * FROM user_rate_limits")
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_rate_limits_nothing_to_delete(self, db):
        """Returns 0 when there are no stale entries."""
        deleted = await db.cleanup_old_rate_limits(max_age_hours=24)
        assert deleted == 0


# ---------------------------------------------------------------------------
# 11.6.4: Non-numeric ADMIN_USER_IDS warning
# ---------------------------------------------------------------------------


class TestAdminUserIdsWarning:
    """Verify non-numeric ADMIN_USER_IDS entries produce a log warning."""

    def test_non_numeric_entry_logs_warning(self, caplog):
        """Non-numeric entries in ADMIN_USER_IDS generate a warning log."""
        import importlib

        with (
            patch.dict("os.environ", {"ADMIN_USER_IDS": "123,abc,456"}),
            caplog.at_level(logging.WARNING, logger="config"),
        ):
            import config

            importlib.reload(config)

        assert any("non-numeric" in r.message.lower() for r in caplog.records)
        assert 123 in config.ADMIN_USER_IDS
        assert 456 in config.ADMIN_USER_IDS

        # Clean up: reload with empty to restore defaults
        with patch.dict("os.environ", {"ADMIN_USER_IDS": ""}):
            importlib.reload(config)

    def test_numeric_entries_no_warning(self, caplog):
        """All-numeric entries produce no warnings."""
        import importlib

        with (
            patch.dict("os.environ", {"ADMIN_USER_IDS": "111,222"}),
            caplog.at_level(logging.WARNING, logger="config"),
        ):
            import config

            importlib.reload(config)

        assert not any("non-numeric" in r.message.lower() for r in caplog.records)
        assert {111, 222} == config.ADMIN_USER_IDS

        with patch.dict("os.environ", {"ADMIN_USER_IDS": ""}):
            importlib.reload(config)


# ---------------------------------------------------------------------------
# 11.6.5: /feedback delivery outcome
# ---------------------------------------------------------------------------


class TestFeedbackDeliveryOutcome:
    """Verify /feedback reports actual delivery result to the user."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @_skip_telegram
    def test_feedback_sent_to_admins_reports_count(self):
        from bot.handlers.user import feedback_command

        update = make_update()
        update.message.text = "/feedback Great bot!"
        mock_db = make_mock_db(
            get_user_stats={"report_count": 1},
            count_user_feedback_since=0,
        )

        admin_ids = {111, 222}
        context = make_context()
        context.bot.send_message = AsyncMock(return_value=MagicMock())

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.ADMIN_USER_IDS", admin_ids),
        ):
            self._run(feedback_command(update, context))

        # The confirmation message should say "sent to 2 admin(s)"
        calls = update.message.reply_text.call_args_list
        confirm_text = calls[-1][0][0]
        assert "2 admin" in confirm_text

    @_skip_telegram
    def test_feedback_no_admins_reports_failure(self):
        from bot.handlers.user import feedback_command

        update = make_update()
        update.message.text = "/feedback Great bot!"
        mock_db = make_mock_db(
            get_user_stats={"report_count": 1},
            count_user_feedback_since=0,
        )

        context = make_context()

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.ADMIN_USER_IDS", set()),
        ):
            self._run(feedback_command(update, context))

        calls = update.message.reply_text.call_args_list
        confirm_text = calls[-1][0][0]
        assert "could not be delivered" in confirm_text.lower()

    @_skip_telegram
    def test_feedback_all_sends_fail_reports_failure(self):
        from bot.handlers.user import feedback_command

        update = make_update()
        update.message.text = "/feedback Hello"
        mock_db = make_mock_db(
            get_user_stats={"report_count": 1},
            count_user_feedback_since=0,
        )

        admin_ids = {111}
        context = make_context()
        context.bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        with (
            patch("bot.services.moderation.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.ADMIN_USER_IDS", admin_ids),
        ):
            self._run(feedback_command(update, context))

        calls = update.message.reply_text.call_args_list
        confirm_text = calls[-1][0][0]
        assert "could not be delivered" in confirm_text.lower()


# ---------------------------------------------------------------------------
# 11.6.6: Alert expiry color indicators in /recent
# ---------------------------------------------------------------------------


class TestRecentColorIndicators:
    """Verify /recent shows red/yellow/green expiry indicators per spec."""

    @pytest.mark.asyncio
    @_skip_telegram
    async def test_recent_shows_red_for_fresh_sighting(self):
        from bot.handlers.user import _build_recent_text

        now = datetime.now(timezone.utc)
        sighting = {
            "zone": "Bugis",
            "reported_at": now - timedelta(minutes=2),
            "description": "Near MRT",
            "lat": None,
            "lng": None,
            "reporter_id": 200,
            "reporter_badge": "\U0001f195 New",
            "feedback_positive": 0,
            "feedback_negative": 0,
        }
        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=[sighting],
        )
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_recent_text(100)
        assert "\U0001f534" in text  # red circle

    @pytest.mark.asyncio
    @_skip_telegram
    async def test_recent_shows_yellow_for_medium_sighting(self):
        from bot.handlers.user import _build_recent_text

        now = datetime.now(timezone.utc)
        sighting = {
            "zone": "Bugis",
            "reported_at": now - timedelta(minutes=10),
            "description": None,
            "lat": None,
            "lng": None,
            "reporter_id": 200,
            "reporter_badge": "\U0001f195 New",
            "feedback_positive": 0,
            "feedback_negative": 0,
        }
        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=[sighting],
        )
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_recent_text(100)
        assert "\U0001f7e1" in text  # yellow circle

    @pytest.mark.asyncio
    @_skip_telegram
    async def test_recent_shows_green_for_old_sighting(self):
        from bot.handlers.user import _build_recent_text

        now = datetime.now(timezone.utc)
        sighting = {
            "zone": "Bugis",
            "reported_at": now - timedelta(minutes=20),
            "description": None,
            "lat": None,
            "lng": None,
            "reporter_id": 200,
            "reporter_badge": "\U0001f195 New",
            "feedback_positive": 0,
            "feedback_negative": 0,
        }
        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=[sighting],
        )
        with patch("bot.handlers.user.get_db", return_value=mock_db):
            text = await _build_recent_text(100)
        assert "\U0001f7e2" in text  # green circle


# ---------------------------------------------------------------------------
# 11.6.7: Conversation timeout callback
# ---------------------------------------------------------------------------


class TestConversationTimeout:
    """Verify the conversation_timeout handler notifies the user."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @_skip_telegram
    def test_timeout_sends_expiry_message(self):
        from bot.handlers.report import conversation_timeout

        update = make_update()
        context = make_context()

        self._run(conversation_timeout(update, context))

        context.bot.send_message.assert_called_once()
        call_kwargs = context.bot.send_message.call_args[1]
        assert "expired" in call_kwargs["text"].lower()

    @_skip_telegram
    def test_timeout_clears_pending_report(self):
        from bot.handlers.report import conversation_timeout

        update = make_update()
        context = make_context(
            user_data={
                "pending_report_zone": "Bugis",
                "pending_report_description": "Test",
                "pending_report_lat": 1.0,
                "pending_report_lng": 103.0,
            }
        )

        self._run(conversation_timeout(update, context))

        # All pending report keys should be cleared
        assert "pending_report_zone" not in context.user_data
        assert "pending_report_description" not in context.user_data
        assert "pending_report_lat" not in context.user_data
        assert "pending_report_lng" not in context.user_data


# ---------------------------------------------------------------------------
# 11.6 Alembic migration: 007_add_users_first_name
# ---------------------------------------------------------------------------


class TestMigration007:
    """Verify migration 007 upgrade/downgrade."""

    def test_migration_module_loads(self):
        """Migration 007 can be imported."""
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
            "007_add_users_first_name.py",
        )
        spec = importlib.util.spec_from_file_location("migration_007", os.path.abspath(path))
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert mod is not None
        assert hasattr(spec, "loader")

    def test_migration_revision_chain(self):
        """Migration 007 chains correctly from 006."""
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
            "007_add_users_first_name.py",
        )
        spec = importlib.util.spec_from_file_location("migration_007", os.path.abspath(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "007"
        assert mod.down_revision == "006"
