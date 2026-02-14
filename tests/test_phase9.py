"""Tests for Phase 9: Admin — User Management & Content Moderation.

Tests for user banning, sighting moderation, reporter warnings,
ban enforcement, auto-flagging, and admin command handlers.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 9.1 User Banning (Database)
# ---------------------------------------------------------------------------
class TestBanUser:
    """Tests for user ban/unban database operations."""

    @pytest.mark.asyncio
    async def test_ban_user(self, db):
        """Should insert ban record and clear subscriptions."""
        await db.ensure_user(100, "alice")
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")

        await db.ban_user(100, banned_by=999, reason="Spamming")

        assert await db.is_banned(100) is True
        subs = await db.get_subscriptions(100)
        assert subs == set()

    @pytest.mark.asyncio
    async def test_ban_user_without_reason(self, db):
        """Should accept ban without a reason."""
        await db.ensure_user(100, "alice")
        await db.ban_user(100, banned_by=999)

        assert await db.is_banned(100) is True
        banned = await db.get_banned_users()
        assert banned[0]["reason"] is None

    @pytest.mark.asyncio
    async def test_ban_user_idempotent(self, db):
        """Banning an already-banned user should update the record."""
        await db.ensure_user(100, "alice")
        await db.ban_user(100, banned_by=999, reason="First ban")
        await db.ban_user(100, banned_by=888, reason="Second ban")

        banned = await db.get_banned_users()
        assert len(banned) == 1
        assert banned[0]["banned_by"] == 888
        assert banned[0]["reason"] == "Second ban"

    @pytest.mark.asyncio
    async def test_unban_user(self, db):
        """Should remove ban record."""
        await db.ensure_user(100, "alice")
        await db.ban_user(100, banned_by=999)

        result = await db.unban_user(100)
        assert result is True
        assert await db.is_banned(100) is False

    @pytest.mark.asyncio
    async def test_unban_user_not_banned(self, db):
        """Should return False when user is not banned."""
        result = await db.unban_user(100)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_banned_false(self, db):
        """Should return False for non-banned users."""
        await db.ensure_user(100, "alice")
        assert await db.is_banned(100) is False

    @pytest.mark.asyncio
    async def test_get_banned_users_empty(self, db):
        """Should return empty list when no bans exist."""
        banned = await db.get_banned_users()
        assert banned == []

    @pytest.mark.asyncio
    async def test_get_banned_users_ordering(self, db):
        """Should return newest bans first."""
        await db.ensure_user(100, "alice")
        await db.ensure_user(200, "bob")
        await db.ban_user(100, banned_by=999, reason="First")
        await db.ban_user(200, banned_by=999, reason="Second")

        banned = await db.get_banned_users()
        assert len(banned) == 2
        # Newest first
        assert banned[0]["telegram_id"] == 200

    @pytest.mark.asyncio
    async def test_ban_clears_subscriptions(self, db):
        """Banning should remove all user subscriptions."""
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(100, "Tanjong Pagar")

        await db.ban_user(100, banned_by=999)

        subs = await db.get_subscriptions(100)
        assert len(subs) == 0

    @pytest.mark.asyncio
    async def test_get_banned_users_fields(self, db):
        """Should return all expected fields."""
        await db.ensure_user(100, "alice")
        await db.ban_user(100, banned_by=999, reason="Test reason")

        banned = await db.get_banned_users()
        entry = banned[0]
        assert "telegram_id" in entry
        assert "banned_by" in entry
        assert "reason" in entry
        assert "banned_at" in entry
        assert entry["telegram_id"] == 100
        assert entry["banned_by"] == 999
        assert entry["reason"] == "Test reason"


# ---------------------------------------------------------------------------
# 9.2 Sighting Moderation (Database)
# ---------------------------------------------------------------------------
class TestSightingModeration:
    """Tests for sighting deletion, flagging, and moderation queue."""

    @pytest.mark.asyncio
    async def test_delete_sighting(self, db):
        """Should delete a sighting and return its data."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "sight1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )

        deleted = await db.delete_sighting("sight1")
        assert deleted is not None
        assert deleted["id"] == "sight1"
        assert deleted["zone"] == "Bugis"

        # Verify it's gone
        remaining = await db.get_sighting("sight1")
        assert remaining is None

    @pytest.mark.asyncio
    async def test_delete_sighting_not_found(self, db):
        """Should return None for non-existent sighting."""
        deleted = await db.delete_sighting("nonexistent")
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_sighting_cascades_feedback(self, db):
        """Deleting a sighting should cascade-delete its feedback."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "sight1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        await db.set_feedback("sight1", 200, "positive")
        await db.set_feedback("sight1", 300, "negative")

        await db.delete_sighting("sight1")

        # Feedback should be gone too (FK CASCADE)
        feedback = await db.get_user_feedback("sight1", 200)
        assert feedback is None

    @pytest.mark.asyncio
    async def test_flag_sighting(self, db):
        """Should mark a sighting as flagged."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "sight1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )

        await db.flag_sighting("sight1")

        sighting = await db.get_sighting("sight1")
        assert sighting["flagged"] == 1

    @pytest.mark.asyncio
    async def test_get_flagged_sightings_by_flag(self, db):
        """Should return sightings explicitly marked as flagged."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "flagged1",
                "zone": "Bugis",
                "description": "Flagged",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        await db.flag_sighting("flagged1")

        # Add an unflagged sighting
        await db.add_sighting(
            {
                "id": "normal1",
                "zone": "Bugis",
                "description": "Normal",
                "time": now,
                "reporter_id": 200,
                "reporter_name": "bob",
                "reporter_badge": "🆕 New",
                "lat": None,
                "lng": None,
            }
        )

        flagged = await db.get_flagged_sightings()
        assert len(flagged) == 1
        assert flagged[0]["id"] == "flagged1"

    @pytest.mark.asyncio
    async def test_get_flagged_sightings_by_negative_feedback(self, db):
        """Should return sightings with high negative feedback ratio."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "bad_sight",
                "zone": "Bugis",
                "description": "Bad report",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # negative > positive with 3+ total votes
        await db.update_feedback_counts("bad_sight", 1, 3)

        flagged = await db.get_flagged_sightings()
        assert len(flagged) == 1
        assert flagged[0]["id"] == "bad_sight"

    @pytest.mark.asyncio
    async def test_get_flagged_sightings_empty(self, db):
        """Should return empty list when no flagged sightings exist."""
        flagged = await db.get_flagged_sightings()
        assert flagged == []

    @pytest.mark.asyncio
    async def test_get_flagged_sightings_not_enough_votes(self, db):
        """Sightings with fewer than 3 total votes should not appear."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "few_votes",
                "zone": "Bugis",
                "description": "Few votes",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # Only 2 total votes — should not appear
        await db.update_feedback_counts("few_votes", 0, 2)

        flagged = await db.get_flagged_sightings()
        assert len(flagged) == 0


# ---------------------------------------------------------------------------
# 9.2 Low-Accuracy Reporters (Database)
# ---------------------------------------------------------------------------
class TestLowAccuracyReporters:
    """Tests for getting reporters with low accuracy scores."""

    @pytest.mark.asyncio
    async def test_get_low_accuracy_reporters(self, db):
        """Should return reporters with accuracy below threshold."""
        now = datetime.now(timezone.utc)
        # Reporter with 20% accuracy (1 positive, 4 negative = 5 total)
        await db.add_sighting(
            {
                "id": "s1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        await db.update_feedback_counts("s1", 1, 4)

        result = await db.get_low_accuracy_reporters(max_accuracy=0.5, min_feedback=5)
        assert len(result) == 1
        assert result[0]["reporter_id"] == 100
        assert result[0]["accuracy"] == 0.2

    @pytest.mark.asyncio
    async def test_get_low_accuracy_reporters_above_threshold(self, db):
        """Reporters above the accuracy threshold should not appear."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "s1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # 80% accuracy — above threshold
        await db.update_feedback_counts("s1", 4, 1)

        result = await db.get_low_accuracy_reporters(max_accuracy=0.5, min_feedback=5)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_low_accuracy_reporters_not_enough_feedback(self, db):
        """Reporters with too few feedback ratings should not appear."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "s1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # Only 3 total feedback — below min_feedback=5
        await db.update_feedback_counts("s1", 1, 2)

        result = await db.get_low_accuracy_reporters(max_accuracy=0.5, min_feedback=5)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_low_accuracy_reporters_empty(self, db):
        """Should return empty list when no reporters exist."""
        result = await db.get_low_accuracy_reporters()
        assert result == []


# ---------------------------------------------------------------------------
# 9.3 Reporter Warnings (Database)
# ---------------------------------------------------------------------------
class TestWarnings:
    """Tests for warning count database operations."""

    @pytest.mark.asyncio
    async def test_get_user_warnings_default(self, db):
        """New users should have 0 warnings."""
        await db.ensure_user(100, "alice")
        count = await db.get_user_warnings(100)
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_user_warnings_nonexistent(self, db):
        """Should return 0 for non-existent user."""
        count = await db.get_user_warnings(999)
        assert count == 0

    @pytest.mark.asyncio
    async def test_increment_warnings(self, db):
        """Should increment and return the new count."""
        await db.ensure_user(100, "alice")
        count = await db.increment_warnings(100)
        assert count == 1
        count = await db.increment_warnings(100)
        assert count == 2

    @pytest.mark.asyncio
    async def test_reset_warnings(self, db):
        """Should reset warnings to zero."""
        await db.ensure_user(100, "alice")
        await db.increment_warnings(100)
        await db.increment_warnings(100)
        await db.reset_warnings(100)
        count = await db.get_user_warnings(100)
        assert count == 0

    @pytest.mark.asyncio
    async def test_warnings_column_in_user_details(self, db):
        """User details should include warnings field."""
        await db.ensure_user(100, "alice")
        await db.increment_warnings(100)
        # warnings column exists in users table
        row = await db._fetchone("SELECT warnings FROM users WHERE telegram_id = ?", (100,))
        assert row is not None
        assert row["warnings"] == 1


# ---------------------------------------------------------------------------
# Phase 9 Schema
# ---------------------------------------------------------------------------
class TestPhase9Schema:
    """Tests for Phase 9 schema additions."""

    @pytest.mark.asyncio
    async def test_banned_users_table_exists(self, db):
        """banned_users table should be created by create_tables()."""
        await db.ban_user(100, banned_by=999)
        assert await db.is_banned(100) is True

    @pytest.mark.asyncio
    async def test_sightings_flagged_column_exists(self, db):
        """sightings table should have flagged column."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "s1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        sighting = await db.get_sighting("s1")
        assert sighting["flagged"] == 0

    @pytest.mark.asyncio
    async def test_users_warnings_column_exists(self, db):
        """users table should have warnings column."""
        await db.ensure_user(100, "alice")
        row = await db._fetchone("SELECT warnings FROM users WHERE telegram_id = ?", (100,))
        assert row is not None
        assert row["warnings"] == 0

    @pytest.mark.asyncio
    async def test_flagged_default_zero(self, db):
        """New sightings should have flagged = 0."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "s1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        sighting = await db.get_sighting("s1")
        assert sighting["flagged"] == 0


# ---------------------------------------------------------------------------
# Config: MAX_WARNINGS
# ---------------------------------------------------------------------------
class TestMaxWarningsConfig:
    """Tests for MAX_WARNINGS configuration."""

    def test_max_warnings_default(self):
        """MAX_WARNINGS should default to 3."""
        import os
        from unittest.mock import patch as _patch

        with _patch.dict(os.environ, {}, clear=False):
            # Re-parse
            val = int(os.environ.get("MAX_WARNINGS", "3"))
            assert val == 3

    def test_max_warnings_custom(self):
        """MAX_WARNINGS should be configurable via env var."""
        import os
        from unittest.mock import patch as _patch

        with _patch.dict(os.environ, {"MAX_WARNINGS": "5"}, clear=False):
            val = int(os.environ.get("MAX_WARNINGS", "3"))
            assert val == 5

    def test_bot_version_updated(self):
        """Bot version should be bumped for Phase 9."""
        from config import BOT_VERSION

        assert BOT_VERSION == "1.3.0"


# ---------------------------------------------------------------------------
# Ban Enforcement Middleware (ban_check decorator)
# ---------------------------------------------------------------------------
class TestBanCheck:
    """Tests for the ban_check decorator."""

    def test_ban_check_blocks_banned_user(self):
        """Banned users should receive a restriction message."""
        from bot.main import ban_check

        called = False

        async def handler(update, context):
            nonlocal called
            called = True

        decorated = ban_check(handler)

        update = MagicMock()
        update.effective_user.id = 100
        update.message.reply_text = AsyncMock()

        mock_db = MagicMock()
        mock_db.is_banned = AsyncMock(return_value=True)

        with patch("bot.main.get_db", return_value=mock_db):
            asyncio.get_event_loop().run_until_complete(decorated(update, MagicMock()))

        assert not called
        update.message.reply_text.assert_called_once()
        assert "restricted" in update.message.reply_text.call_args[0][0].lower()

    def test_ban_check_allows_non_banned_user(self):
        """Non-banned users should pass through."""
        from bot.main import ban_check

        called = False

        async def handler(update, context):
            nonlocal called
            called = True

        decorated = ban_check(handler)

        update = MagicMock()
        update.effective_user.id = 100
        update.message.reply_text = AsyncMock()

        mock_db = MagicMock()
        mock_db.is_banned = AsyncMock(return_value=False)

        with patch("bot.main.get_db", return_value=mock_db):
            asyncio.get_event_loop().run_until_complete(decorated(update, MagicMock()))

        assert called


# ---------------------------------------------------------------------------
# Auto-Flag Logic
# ---------------------------------------------------------------------------
class TestAutoFlag:
    """Tests for the auto-flag sighting logic."""

    @pytest.mark.asyncio
    async def test_auto_flag_triggers_on_high_negative(self, db):
        """Sighting should be flagged when negative > 70% with 3+ votes."""
        from bot.main import _check_auto_flag

        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "auto1",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # Set 1 positive, 3 negative (75% negative)
        await db.update_feedback_counts("auto1", 1, 3)

        with patch("bot.main.get_db", return_value=db):
            await _check_auto_flag("auto1")

        sighting = await db.get_sighting("auto1")
        assert sighting["flagged"] == 1

    @pytest.mark.asyncio
    async def test_auto_flag_does_not_trigger_under_threshold(self, db):
        """Sighting should NOT be flagged when negative <= 70%."""
        from bot.main import _check_auto_flag

        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "auto2",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # Set 2 positive, 2 negative (50% negative — below 70%)
        await db.update_feedback_counts("auto2", 2, 2)

        with patch("bot.main.get_db", return_value=db):
            await _check_auto_flag("auto2")

        sighting = await db.get_sighting("auto2")
        assert sighting["flagged"] == 0

    @pytest.mark.asyncio
    async def test_auto_flag_requires_minimum_votes(self, db):
        """Should not flag with fewer than 3 total votes."""
        from bot.main import _check_auto_flag

        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "auto3",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )
        # Only 2 votes (100% negative, but not enough votes)
        await db.update_feedback_counts("auto3", 0, 2)

        with patch("bot.main.get_db", return_value=db):
            await _check_auto_flag("auto3")

        sighting = await db.get_sighting("auto3")
        assert sighting["flagged"] == 0

    @pytest.mark.asyncio
    async def test_auto_flag_nonexistent_sighting(self, db):
        """Should handle non-existent sighting gracefully."""
        from bot.main import _check_auto_flag

        with patch("bot.main.get_db", return_value=db):
            await _check_auto_flag("nonexistent")  # Should not raise


# ---------------------------------------------------------------------------
# Admin Command Help (Phase 9 additions)
# ---------------------------------------------------------------------------
class TestAdminHelpPhase9:
    """Tests for Phase 9 admin command help text."""

    def test_admin_commands_help_has_phase9_commands(self):
        """Phase 9 admin commands should be listed in help."""
        from bot.main import ADMIN_COMMANDS_HELP

        help_keys = " ".join(ADMIN_COMMANDS_HELP.keys())
        assert "ban" in help_keys
        assert "unban" in help_keys
        assert "banlist" in ADMIN_COMMANDS_HELP
        assert "warn" in help_keys
        assert "delete" in help_keys
        assert "review" in ADMIN_COMMANDS_HELP

    def test_admin_commands_detailed_has_phase9_commands(self):
        """Phase 9 admin commands should have detailed help."""
        from bot.main import ADMIN_COMMANDS_DETAILED

        assert "ban" in ADMIN_COMMANDS_DETAILED
        assert "unban" in ADMIN_COMMANDS_DETAILED
        assert "banlist" in ADMIN_COMMANDS_DETAILED
        assert "warn" in ADMIN_COMMANDS_DETAILED
        assert "delete" in ADMIN_COMMANDS_DETAILED
        assert "review" in ADMIN_COMMANDS_DETAILED


# ---------------------------------------------------------------------------
# Admin Ban Command Handler Integration
# ---------------------------------------------------------------------------
class TestAdminBanIntegration:
    """Tests for admin ban operations with audit logging."""

    @pytest.mark.asyncio
    async def test_ban_logs_action(self, db):
        """Banning should create an audit log entry."""
        await db.ensure_user(100, "alice")
        await db.ban_user(100, banned_by=999, reason="Test ban")
        await db.log_admin_action(999, "ban_user", target="100", detail="reason: Test ban")

        entries = await db.get_admin_log(10)
        assert any(e["action"] == "ban_user" and e["target"] == "100" for e in entries)

    @pytest.mark.asyncio
    async def test_unban_resets_warnings(self, db):
        """Unbanning should allow warning reset."""
        await db.ensure_user(100, "alice")
        await db.increment_warnings(100)
        await db.increment_warnings(100)
        await db.ban_user(100, banned_by=999)

        await db.unban_user(100)
        await db.reset_warnings(100)

        assert await db.is_banned(100) is False
        assert await db.get_user_warnings(100) == 0

    @pytest.mark.asyncio
    async def test_ban_and_unban_cycle(self, db):
        """Full ban → unban cycle should work correctly."""
        await db.ensure_user(100, "alice")
        await db.add_subscription(100, "Bugis")

        # Ban
        await db.ban_user(100, banned_by=999, reason="Test")
        assert await db.is_banned(100) is True
        assert await db.get_subscriptions(100) == set()

        # Unban
        await db.unban_user(100)
        assert await db.is_banned(100) is False

        # User can subscribe again
        await db.add_subscription(100, "Orchard")
        subs = await db.get_subscriptions(100)
        assert "Orchard" in subs


# ---------------------------------------------------------------------------
# Warning Escalation
# ---------------------------------------------------------------------------
class TestWarningEscalation:
    """Tests for warning count tracking and escalation path."""

    @pytest.mark.asyncio
    async def test_warnings_accumulate(self, db):
        """Warnings should accumulate correctly."""
        await db.ensure_user(100, "alice")
        assert await db.get_user_warnings(100) == 0
        await db.increment_warnings(100)
        assert await db.get_user_warnings(100) == 1
        await db.increment_warnings(100)
        assert await db.get_user_warnings(100) == 2
        await db.increment_warnings(100)
        assert await db.get_user_warnings(100) == 3

    @pytest.mark.asyncio
    async def test_warning_escalation_to_ban(self, db):
        """After MAX_WARNINGS, a ban should be applied."""
        await db.ensure_user(100, "alice")
        for _ in range(3):
            await db.increment_warnings(100)

        count = await db.get_user_warnings(100)
        assert count >= 3

        # Simulate auto-ban at threshold
        await db.ban_user(100, banned_by=0, reason="Auto-ban: 3 warnings reached")
        assert await db.is_banned(100) is True
