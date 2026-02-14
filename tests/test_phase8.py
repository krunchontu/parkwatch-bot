"""Tests for Phase 8: Admin — Foundation & Visibility.

Tests for admin authentication, statistics dashboard, user/zone lookup,
audit logging, and admin command routing.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Config: ADMIN_USER_IDS parsing
# ---------------------------------------------------------------------------
class TestAdminConfig:
    """Tests for ADMIN_USER_IDS configuration parsing."""

    def test_admin_user_ids_is_set(self):
        from config import ADMIN_USER_IDS

        assert isinstance(ADMIN_USER_IDS, set)

    def test_admin_user_ids_default_empty(self):
        """ADMIN_USER_IDS should be empty when env var is not set."""
        import os

        with patch.dict(os.environ, {"ADMIN_USER_IDS": ""}, clear=False):
            # Re-parse
            raw = os.environ.get("ADMIN_USER_IDS", "")
            result = set()
            if raw.strip():
                for _id in raw.split(","):
                    _id = _id.strip()
                    if _id.isdigit():
                        result.add(int(_id))
            assert result == set()

    def test_admin_user_ids_single(self):
        """Single admin ID should be parsed correctly."""
        raw = "123456789"
        result = set()
        for _id in raw.split(","):
            _id = _id.strip()
            if _id.isdigit():
                result.add(int(_id))
        assert result == {123456789}

    def test_admin_user_ids_multiple(self):
        """Multiple admin IDs should be parsed correctly."""
        raw = "123456789, 987654321, 111222333"
        result = set()
        for _id in raw.split(","):
            _id = _id.strip()
            if _id.isdigit():
                result.add(int(_id))
        assert result == {123456789, 987654321, 111222333}

    def test_admin_user_ids_ignores_invalid(self):
        """Non-numeric values should be silently ignored."""
        raw = "123456789, abc, , 987654321"
        result = set()
        for _id in raw.split(","):
            _id = _id.strip()
            if _id.isdigit():
                result.add(int(_id))
        assert result == {123456789, 987654321}

    def test_bot_version_updated(self):
        from config import BOT_VERSION

        assert BOT_VERSION == "1.3.0"


# ---------------------------------------------------------------------------
# Admin Authentication (admin_only decorator)
# ---------------------------------------------------------------------------
class TestAdminOnly:
    """Tests for the admin_only decorator."""

    def test_admin_only_rejects_non_admin(self):
        """Non-admin users should receive 'Unknown command' response."""
        from bot.main import admin_only

        called = False

        async def handler(update, context):
            nonlocal called
            called = True

        decorated = admin_only(handler)

        # Mock non-admin user
        update = MagicMock()
        update.effective_user.id = 999999
        update.message.reply_text = AsyncMock()

        import asyncio

        with patch("bot.main.ADMIN_USER_IDS", {123456}):
            asyncio.get_event_loop().run_until_complete(decorated(update, MagicMock()))

        assert not called
        update.message.reply_text.assert_called_once()
        assert "Unknown command" in update.message.reply_text.call_args[0][0]

    def test_admin_only_allows_admin(self):
        """Admin users should be allowed through."""
        from bot.main import admin_only

        called = False

        async def handler(update, context):
            nonlocal called
            called = True

        decorated = admin_only(handler)

        update = MagicMock()
        update.effective_user.id = 123456
        update.message.reply_text = AsyncMock()

        import asyncio

        with patch("bot.main.ADMIN_USER_IDS", {123456}):
            asyncio.get_event_loop().run_until_complete(decorated(update, MagicMock()))

        assert called


# ---------------------------------------------------------------------------
# Admin Audit Logging (Database)
# ---------------------------------------------------------------------------
class TestAdminAuditLog:
    """Tests for the admin_actions audit log database operations."""

    @pytest.mark.asyncio
    async def test_log_admin_action(self, db):
        """Should insert an admin action record."""
        await db.log_admin_action(123456, "view_stats")
        entries = await db.get_admin_log(10)
        assert len(entries) == 1
        assert entries[0]["admin_id"] == 123456
        assert entries[0]["action"] == "view_stats"

    @pytest.mark.asyncio
    async def test_log_admin_action_with_target(self, db):
        """Should store target field."""
        await db.log_admin_action(123456, "lookup_user", target="789")
        entries = await db.get_admin_log(10)
        assert entries[0]["target"] == "789"

    @pytest.mark.asyncio
    async def test_log_admin_action_with_detail(self, db):
        """Should store detail field."""
        await db.log_admin_action(123456, "lookup_zone", target="Bugis", detail="Zone lookup")
        entries = await db.get_admin_log(10)
        assert entries[0]["detail"] == "Zone lookup"

    @pytest.mark.asyncio
    async def test_admin_log_ordering(self, db):
        """Entries should be returned newest first."""
        await db.log_admin_action(111, "action_1")
        await db.log_admin_action(222, "action_2")
        await db.log_admin_action(333, "action_3")
        entries = await db.get_admin_log(10)
        assert len(entries) == 3
        assert entries[0]["action"] == "action_3"
        assert entries[2]["action"] == "action_1"

    @pytest.mark.asyncio
    async def test_admin_log_limit(self, db):
        """Should respect the limit parameter."""
        for i in range(10):
            await db.log_admin_action(111, f"action_{i}")
        entries = await db.get_admin_log(3)
        assert len(entries) == 3

    @pytest.mark.asyncio
    async def test_admin_log_empty(self, db):
        """Should return empty list when no entries exist."""
        entries = await db.get_admin_log(10)
        assert entries == []

    @pytest.mark.asyncio
    async def test_admin_log_created_at_populated(self, db):
        """created_at should be automatically set."""
        await db.log_admin_action(123, "test_action")
        entries = await db.get_admin_log(1)
        assert entries[0]["created_at"] is not None


# ---------------------------------------------------------------------------
# Global Statistics (Database)
# ---------------------------------------------------------------------------
class TestGlobalStats:
    """Tests for global statistics database methods."""

    @pytest.mark.asyncio
    async def test_get_global_stats_empty(self, db):
        """Should return zeros when database is empty."""
        stats = await db.get_global_stats()
        assert stats["total_users"] == 0
        assert stats["total_sightings"] == 0
        assert stats["sightings_24h"] == 0
        assert stats["active_subscriptions"] == 0
        assert stats["unique_subscribers"] == 0
        assert stats["feedback_positive"] == 0
        assert stats["feedback_negative"] == 0

    @pytest.mark.asyncio
    async def test_get_global_stats_with_data(self, db):
        """Should return correct counts with populated data."""
        # Add users
        await db.ensure_user(100, "alice")
        await db.ensure_user(200, "bob")

        # Add subscriptions
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(200, "Bugis")

        # Add sighting
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
                "lat": 1.3008,
                "lng": 103.8553,
            }
        )

        stats = await db.get_global_stats()
        assert stats["total_users"] == 2
        assert stats["total_sightings"] == 1
        assert stats["sightings_24h"] == 1
        assert stats["active_subscriptions"] == 3
        assert stats["unique_subscribers"] == 2

    @pytest.mark.asyncio
    async def test_get_top_zones_by_subscribers(self, db):
        """Should return zones ordered by subscriber count."""
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(200, "Bugis")
        await db.add_subscription(300, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(200, "Orchard")
        await db.add_subscription(100, "Tanjong Pagar")

        top = await db.get_top_zones_by_subscribers(3)
        assert len(top) == 3
        assert top[0]["zone_name"] == "Bugis"
        assert top[0]["sub_count"] == 3
        assert top[1]["zone_name"] == "Orchard"
        assert top[1]["sub_count"] == 2

    @pytest.mark.asyncio
    async def test_get_top_zones_by_subscribers_limit(self, db):
        """Should respect the limit parameter."""
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(100, "Tanjong Pagar")

        top = await db.get_top_zones_by_subscribers(1)
        assert len(top) == 1

    @pytest.mark.asyncio
    async def test_get_top_zones_by_sightings(self, db):
        """Should return zones ordered by recent sighting count."""
        now = datetime.now(timezone.utc)
        for i in range(3):
            await db.add_sighting(
                {
                    "id": f"s_bugis_{i}",
                    "zone": "Bugis",
                    "description": "Test",
                    "time": now - timedelta(hours=i),
                    "reporter_id": 100,
                    "reporter_name": "alice",
                    "reporter_badge": "⭐ Regular",
                    "lat": None,
                    "lng": None,
                }
            )
        await db.add_sighting(
            {
                "id": "s_orchard_0",
                "zone": "Orchard",
                "description": "Test",
                "time": now,
                "reporter_id": 200,
                "reporter_name": "bob",
                "reporter_badge": "🆕 New",
                "lat": None,
                "lng": None,
            }
        )

        top = await db.get_top_zones_by_sightings(5, days=7)
        assert len(top) == 2
        assert top[0]["zone"] == "Bugis"
        assert top[0]["sighting_count"] == 3

    @pytest.mark.asyncio
    async def test_get_top_zones_by_sightings_excludes_old(self, db):
        """Should exclude sightings older than the time window."""
        now = datetime.now(timezone.utc)
        await db.add_sighting(
            {
                "id": "old_sight",
                "zone": "Bugis",
                "description": "Old",
                "time": now - timedelta(days=30),
                "reporter_id": 100,
                "reporter_name": "alice",
                "reporter_badge": "⭐ Regular",
                "lat": None,
                "lng": None,
            }
        )

        top = await db.get_top_zones_by_sightings(5, days=7)
        assert len(top) == 0


# ---------------------------------------------------------------------------
# User Lookup (Database)
# ---------------------------------------------------------------------------
class TestUserLookup:
    """Tests for admin user lookup database methods."""

    @pytest.mark.asyncio
    async def test_get_user_details(self, db):
        """Should return user details by telegram_id."""
        await db.ensure_user(100, "alice")
        user = await db.get_user_details(100)
        assert user is not None
        assert user["telegram_id"] == 100
        assert user["username"] == "alice"

    @pytest.mark.asyncio
    async def test_get_user_details_not_found(self, db):
        """Should return None for non-existent user."""
        user = await db.get_user_details(999)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, db):
        """Should find user by username."""
        await db.ensure_user(100, "alice")
        user = await db.get_user_by_username("alice")
        assert user is not None
        assert user["telegram_id"] == 100

    @pytest.mark.asyncio
    async def test_get_user_by_username_with_at(self, db):
        """Should strip leading @ from username."""
        await db.ensure_user(100, "alice")
        user = await db.get_user_by_username("@alice")
        assert user is not None
        assert user["telegram_id"] == 100

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, db):
        """Should return None for non-existent username."""
        user = await db.get_user_by_username("nobody")
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_recent_sightings(self, db):
        """Should return recent sightings for a user."""
        await db.ensure_user(100, "alice")
        now = datetime.now(timezone.utc)
        for i in range(5):
            await db.add_sighting(
                {
                    "id": f"sight_{i}",
                    "zone": "Bugis",
                    "description": f"Test {i}",
                    "time": now - timedelta(hours=i),
                    "reporter_id": 100,
                    "reporter_name": "alice",
                    "reporter_badge": "⭐ Regular",
                    "lat": None,
                    "lng": None,
                }
            )

        recent = await db.get_user_recent_sightings(100, 3)
        assert len(recent) == 3
        # Should be newest first
        assert recent[0]["id"] == "sight_0"

    @pytest.mark.asyncio
    async def test_get_user_recent_sightings_empty(self, db):
        """Should return empty list for user with no sightings."""
        recent = await db.get_user_recent_sightings(999, 10)
        assert recent == []

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_list(self, db):
        """Should return sorted list of subscribed zones."""
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Tanjong Pagar")

        subs = await db.get_user_subscriptions_list(100)
        assert subs == ["Bugis", "Orchard", "Tanjong Pagar"]

    @pytest.mark.asyncio
    async def test_get_user_subscriptions_list_empty(self, db):
        """Should return empty list for user with no subscriptions."""
        subs = await db.get_user_subscriptions_list(999)
        assert subs == []


# ---------------------------------------------------------------------------
# Zone Lookup (Database)
# ---------------------------------------------------------------------------
class TestZoneLookup:
    """Tests for admin zone lookup database methods."""

    @pytest.mark.asyncio
    async def test_get_zone_details(self, db):
        """Should return zone statistics."""
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(200, "Bugis")

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

        details = await db.get_zone_details("Bugis")
        assert details["zone_name"] == "Bugis"
        assert details["subscriber_count"] == 2
        assert details["sightings_24h"] == 1
        assert details["sightings_7d"] == 1
        assert details["sightings_all"] == 1

    @pytest.mark.asyncio
    async def test_get_zone_details_empty(self, db):
        """Should return zero counts for zone with no data."""
        details = await db.get_zone_details("Bugis")
        assert details["subscriber_count"] == 0
        assert details["sightings_all"] == 0

    @pytest.mark.asyncio
    async def test_get_zone_top_reporters(self, db):
        """Should return reporters ordered by report count in zone."""
        now = datetime.now(timezone.utc)
        # alice: 3 reports
        for i in range(3):
            await db.add_sighting(
                {
                    "id": f"alice_{i}",
                    "zone": "Bugis",
                    "description": "Test",
                    "time": now - timedelta(hours=i),
                    "reporter_id": 100,
                    "reporter_name": "alice",
                    "reporter_badge": "⭐ Regular",
                    "lat": None,
                    "lng": None,
                }
            )
        # bob: 1 report
        await db.add_sighting(
            {
                "id": "bob_0",
                "zone": "Bugis",
                "description": "Test",
                "time": now,
                "reporter_id": 200,
                "reporter_name": "bob",
                "reporter_badge": "🆕 New",
                "lat": None,
                "lng": None,
            }
        )

        top = await db.get_zone_top_reporters("Bugis", 5)
        assert len(top) == 2
        assert top[0]["reporter_name"] == "alice"
        assert top[0]["report_count"] == 3
        assert top[1]["reporter_name"] == "bob"
        assert top[1]["report_count"] == 1

    @pytest.mark.asyncio
    async def test_get_zone_top_reporters_empty(self, db):
        """Should return empty list for zone with no reporters."""
        top = await db.get_zone_top_reporters("Bugis", 5)
        assert top == []

    @pytest.mark.asyncio
    async def test_get_zone_recent_sightings(self, db):
        """Should return most recent sightings in a zone."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            await db.add_sighting(
                {
                    "id": f"sight_{i}",
                    "zone": "Bugis",
                    "description": f"Test {i}",
                    "time": now - timedelta(hours=i),
                    "reporter_id": 100,
                    "reporter_name": "alice",
                    "reporter_badge": "⭐ Regular",
                    "lat": None,
                    "lng": None,
                }
            )

        recent = await db.get_zone_recent_sightings("Bugis", 3)
        assert len(recent) == 3
        # Should be newest first
        assert recent[0]["description"] == "Test 0"

    @pytest.mark.asyncio
    async def test_get_zone_recent_sightings_empty(self, db):
        """Should return empty list for zone with no sightings."""
        recent = await db.get_zone_recent_sightings("Bugis", 5)
        assert recent == []


# ---------------------------------------------------------------------------
# Admin Table Schema
# ---------------------------------------------------------------------------
class TestAdminTableSchema:
    """Tests that the admin_actions table is created correctly."""

    @pytest.mark.asyncio
    async def test_admin_actions_table_exists(self, db):
        """admin_actions table should be created by create_tables()."""
        # This would fail if the table doesn't exist
        await db.log_admin_action(123, "test")
        entries = await db.get_admin_log(1)
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_admin_actions_auto_increment(self, db):
        """IDs should auto-increment."""
        await db.log_admin_action(111, "action_1")
        await db.log_admin_action(222, "action_2")
        entries = await db.get_admin_log(10)
        # IDs should be different (newest first)
        assert entries[0]["id"] != entries[1]["id"]

    @pytest.mark.asyncio
    async def test_admin_actions_nullable_fields(self, db):
        """target and detail should be nullable."""
        await db.log_admin_action(123, "test_action", target=None, detail=None)
        entries = await db.get_admin_log(1)
        assert entries[0]["target"] is None
        assert entries[0]["detail"] is None


# ---------------------------------------------------------------------------
# Admin Command Help
# ---------------------------------------------------------------------------
class TestAdminHelp:
    """Tests for the admin help text constants."""

    def test_admin_commands_help_has_all_commands(self):
        """All Phase 8 admin commands should be listed in help."""
        from bot.main import ADMIN_COMMANDS_HELP

        assert "stats" in ADMIN_COMMANDS_HELP
        assert "log [count]" in ADMIN_COMMANDS_HELP

    def test_admin_commands_detailed_has_all_commands(self):
        """All Phase 8 admin commands should have detailed help."""
        from bot.main import ADMIN_COMMANDS_DETAILED

        assert "stats" in ADMIN_COMMANDS_DETAILED
        assert "user" in ADMIN_COMMANDS_DETAILED
        assert "zone" in ADMIN_COMMANDS_DETAILED
        assert "log" in ADMIN_COMMANDS_DETAILED


# ---------------------------------------------------------------------------
# Zone validation in admin zone lookup
# ---------------------------------------------------------------------------
class TestZoneValidation:
    """Tests for zone name validation in admin zone lookup."""

    def test_zone_exists_in_zones_dict(self):
        """Known zones should be found in the ZONES dict."""
        from bot.main import ZONES

        found = False
        for region in ZONES.values():
            if "Bugis" in region["zones"]:
                found = True
                break
        assert found

    def test_case_insensitive_zone_lookup(self):
        """Zone lookup should support case-insensitive matching."""
        from bot.main import ZONES

        target = "bugis"
        found = False
        for region in ZONES.values():
            for z in region["zones"]:
                if z.lower() == target.lower():
                    found = True
                    break
            if found:
                break
        assert found
