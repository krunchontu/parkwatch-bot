"""Phase 11.8 repository split tests.

Verifies that:
1. Repository classes exist and expose the expected methods
2. Repositories work correctly via the Database facade (backward compat)
3. Repositories can be accessed directly via db.users, db.sightings, etc.
4. Database.__getattr__ delegation works for all repository methods
5. Repository operations produce correct results through SQLite integration
"""

from datetime import datetime, timedelta, timezone

import pytest

from bot.database import Database
from bot.repositories import (
    AdminRepository,
    BaseRepository,
    ConfigRepository,
    FeedbackRepository,
    SightingRepository,
    UserRepository,
)


# ---------------------------------------------------------------------------
# Repository class structure
# ---------------------------------------------------------------------------
class TestRepositoryStructure:
    """Verify repository classes exist and have expected attributes."""

    def test_base_repository_has_helpers(self):
        db = Database()
        base = BaseRepository(db)
        assert hasattr(base, "_db")
        assert hasattr(base, "driver")
        assert hasattr(base, "_ph")
        assert hasattr(base, "_execute")
        assert hasattr(base, "_fetchone")
        assert hasattr(base, "_fetchall")
        assert hasattr(base, "_conn")
        assert hasattr(base, "_pool")

    def test_user_repository_methods(self):
        """UserRepository exposes all expected user/subscription methods."""
        db = Database()
        repo = UserRepository(db)
        expected = [
            "get_subscriptions",
            "add_subscription",
            "remove_subscription",
            "clear_subscriptions",
            "get_zone_subscribers",
            "get_subscriber_count",
            "get_user_subscriptions_list",
            "ensure_user",
            "get_user_stats",
            "increment_report_count",
            "get_user_details",
            "get_user_by_username",
            "get_all_user_ids",
            "get_user_recent_sightings",
            "get_user_warnings",
            "increment_warnings",
            "reset_warnings",
        ]
        for method in expected:
            assert hasattr(repo, method), f"UserRepository missing method: {method}"

    def test_sighting_repository_methods(self):
        """SightingRepository exposes all expected sighting methods."""
        db = Database()
        repo = SightingRepository(db)
        expected = [
            "add_sighting",
            "get_sighting",
            "get_sighting_reporter",
            "get_total_sightings_count",
            "get_recent_sightings_for_zones",
            "find_recent_zone_sightings",
            "count_reports_since",
            "get_oldest_report_since",
            "update_feedback_counts",
            "cleanup_old_sightings",
            "purge_sightings_older_than",
            "delete_sighting",
            "flag_sighting",
            "get_flagged_sightings",
            "get_low_accuracy_reporters",
        ]
        for method in expected:
            assert hasattr(repo, method), f"SightingRepository missing method: {method}"

    def test_feedback_repository_methods(self):
        """FeedbackRepository exposes all expected feedback methods."""
        db = Database()
        repo = FeedbackRepository(db)
        expected = [
            "get_user_feedback",
            "set_feedback",
            "apply_feedback",
            "calculate_accuracy",
            "get_user_feedback_totals",
            "record_rate_limit_event",
            "cleanup_old_rate_limits",
            "count_user_feedback_since",
        ]
        for method in expected:
            assert hasattr(repo, method), f"FeedbackRepository missing method: {method}"

    def test_admin_repository_methods(self):
        """AdminRepository exposes all expected admin methods."""
        db = Database()
        repo = AdminRepository(db)
        expected = [
            "log_admin_action",
            "get_admin_log",
            "get_global_stats",
            "get_top_zones_by_subscribers",
            "get_top_zones_by_sightings",
            "get_zone_details",
            "get_zone_top_reporters",
            "get_zone_recent_sightings",
            "ban_user",
            "unban_user",
            "is_banned",
            "get_banned_users",
            "purge_user_data",
            "export_stats",
        ]
        for method in expected:
            assert hasattr(repo, method), f"AdminRepository missing method: {method}"

    def test_config_repository_methods(self):
        """ConfigRepository exposes all expected config methods."""
        db = Database()
        repo = ConfigRepository(db)
        expected = [
            "get_config_override",
            "get_all_config_overrides",
            "upsert_config_override",
            "delete_config_override",
        ]
        for method in expected:
            assert hasattr(repo, method), f"ConfigRepository missing method: {method}"


# ---------------------------------------------------------------------------
# Database composition
# ---------------------------------------------------------------------------
class TestDatabaseComposition:
    """Verify Database composes repository instances."""

    def test_database_has_repository_attributes(self):
        db = Database()
        assert isinstance(db.users, UserRepository)
        assert isinstance(db.sightings, SightingRepository)
        assert isinstance(db.feedback, FeedbackRepository)
        assert isinstance(db.admin, AdminRepository)
        assert isinstance(db.config, ConfigRepository)

    def test_repositories_share_database_reference(self):
        """All repositories reference the same Database instance."""
        db = Database()
        assert db.users._db is db
        assert db.sightings._db is db
        assert db.feedback._db is db
        assert db.admin._db is db
        assert db.config._db is db

    def test_repositories_inherit_driver(self):
        """Repositories correctly inherit the driver setting."""
        db_sqlite = Database()
        assert db_sqlite.users.driver == "sqlite"

        db_pg = Database("postgresql://localhost/test")
        assert db_pg.users.driver == "postgresql"
        assert db_pg.sightings.driver == "postgresql"


# ---------------------------------------------------------------------------
# __getattr__ delegation
# ---------------------------------------------------------------------------
class TestGetAttrDelegation:
    """Verify backward-compatible method delegation via __getattr__."""

    def test_user_method_delegation(self):
        """User methods accessible directly on Database via __getattr__."""
        db = Database()
        assert db.ensure_user == db.users.ensure_user
        assert db.get_subscriptions == db.users.get_subscriptions
        assert db.get_user_warnings == db.users.get_user_warnings

    def test_sighting_method_delegation(self):
        """Sighting methods accessible directly on Database."""
        db = Database()
        assert db.add_sighting == db.sightings.add_sighting
        assert db.get_sighting == db.sightings.get_sighting
        assert db.cleanup_old_sightings == db.sightings.cleanup_old_sightings

    def test_feedback_method_delegation(self):
        """Feedback methods accessible directly on Database."""
        db = Database()
        assert db.apply_feedback == db.feedback.apply_feedback
        assert db.calculate_accuracy == db.feedback.calculate_accuracy
        assert db.record_rate_limit_event == db.feedback.record_rate_limit_event

    def test_admin_method_delegation(self):
        """Admin methods accessible directly on Database."""
        db = Database()
        assert db.log_admin_action == db.admin.log_admin_action
        assert db.ban_user == db.admin.ban_user
        assert db.export_stats == db.admin.export_stats

    def test_config_method_delegation(self):
        """Config methods accessible directly on Database."""
        db = Database()
        assert db.get_config_override == db.config.get_config_override
        assert db.upsert_config_override == db.config.upsert_config_override

    def test_unknown_attribute_raises(self):
        """Accessing a non-existent method raises AttributeError."""
        db = Database()
        with pytest.raises(AttributeError):
            db.nonexistent_method  # noqa: B018

    def test_database_own_methods_not_delegated(self):
        """Database's own methods (connect, close, etc.) are accessed directly."""
        db = Database()
        assert db.connect is not None
        assert db.close is not None
        assert db.check_pool_health is not None
        assert db.create_tables is not None


# ---------------------------------------------------------------------------
# Integration: repository operations via Database facade
# ---------------------------------------------------------------------------
class TestRepositoryIntegration:
    """Integration tests verifying repository operations work through Database."""

    @staticmethod
    def _make_sighting(sighting_id="s1", zone="Bugis", **overrides):
        base = {
            "id": sighting_id,
            "zone": zone,
            "description": "test sighting",
            "time": datetime.now(timezone.utc),
            "reporter_id": 100,
            "reporter_name": "alice",
            "reporter_badge": "New",
            "lat": 1.3008,
            "lng": 103.8553,
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_user_repo_via_facade(self, db):
        """User operations work through both db.method() and db.users.method()."""
        # Via facade (backward compatible)
        await db.ensure_user(100, "alice", "Alice")
        stats = await db.get_user_stats(100)
        assert stats is not None
        assert stats["username"] == "alice"

        # Via direct repository access
        stats2 = await db.users.get_user_stats(100)
        assert stats2 is not None
        assert stats2 == stats

    @pytest.mark.asyncio
    async def test_subscription_repo_via_facade(self, db):
        """Subscription operations work through both paths."""
        await db.add_subscription(100, "Bugis")
        await db.users.add_subscription(100, "Orchard")

        # Both should be visible from either access path
        subs_facade = await db.get_subscriptions(100)
        subs_direct = await db.users.get_subscriptions(100)
        assert subs_facade == {"Bugis", "Orchard"}
        assert subs_direct == {"Bugis", "Orchard"}

    @pytest.mark.asyncio
    async def test_sighting_repo_via_facade(self, db):
        """Sighting operations work through both paths."""
        await db.add_sighting(self._make_sighting())
        sighting_facade = await db.get_sighting("s1")
        sighting_direct = await db.sightings.get_sighting("s1")
        assert sighting_facade is not None
        assert sighting_direct is not None
        assert sighting_facade["zone"] == sighting_direct["zone"]

    @pytest.mark.asyncio
    async def test_feedback_repo_via_facade(self, db):
        """Feedback operations work through both paths."""
        await db.add_sighting(self._make_sighting())
        result_facade = await db.apply_feedback("s1", 200, "positive")
        assert result_facade["feedback_positive"] == 1

        # Direct repo access
        vote = await db.feedback.get_user_feedback("s1", 200)
        assert vote == "positive"

    @pytest.mark.asyncio
    async def test_admin_repo_via_facade(self, db):
        """Admin operations work through both paths."""
        await db.log_admin_action(1, "test_action", "target", "detail")
        log_facade = await db.get_admin_log(10)
        log_direct = await db.admin.get_admin_log(10)
        assert len(log_facade) == 1
        assert log_facade == log_direct

    @pytest.mark.asyncio
    async def test_config_repo_via_facade(self, db):
        """Config operations work through both paths."""
        now = datetime.now(timezone.utc)
        await db.upsert_config_override("TEST_KEY", "value", 1, now)
        override_facade = await db.get_config_override("TEST_KEY")
        override_direct = await db.config.get_config_override("TEST_KEY")
        assert override_facade is not None
        assert override_direct is not None
        assert override_facade["value"] == "value"
        assert override_facade == override_direct

    @pytest.mark.asyncio
    async def test_ban_clears_subscriptions(self, db):
        """ban_user in AdminRepository correctly clears subscriptions."""
        await db.ensure_user(100, "alice")
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        subs_before = await db.get_subscriptions(100)
        assert len(subs_before) == 2

        await db.ban_user(100, 999, "test ban")
        subs_after = await db.get_subscriptions(100)
        assert len(subs_after) == 0
        assert await db.is_banned(100) is True

    @pytest.mark.asyncio
    async def test_export_stats_via_admin_repo(self, db):
        """export_stats correctly calls other AdminRepository methods."""
        csv_output = await db.export_stats("csv")
        assert "section,key,value" in csv_output
        assert "global_stats" in csv_output

        json_output = await db.admin.export_stats("json")
        assert "global_stats" in json_output

    @pytest.mark.asyncio
    async def test_cross_repo_operations(self, db):
        """Operations spanning multiple repositories work correctly."""
        # User repo: create user and subscribe
        await db.users.ensure_user(100, "alice", "Alice")
        await db.users.add_subscription(100, "Bugis")

        # Sighting repo: add sighting
        await db.sightings.add_sighting(self._make_sighting())

        # Feedback repo: apply feedback
        await db.feedback.apply_feedback("s1", 200, "positive")

        # Admin repo: get stats (queries across tables)
        stats = await db.admin.get_global_stats()
        assert stats["total_users"] >= 1
        assert stats["total_sightings"] == 1
        assert stats["feedback_positive"] == 1

    @pytest.mark.asyncio
    async def test_sighting_moderation_via_repo(self, db):
        """Sighting moderation operations work through SightingRepository."""
        await db.sightings.add_sighting(self._make_sighting())
        await db.sightings.flag_sighting("s1")
        flagged = await db.sightings.get_flagged_sightings()
        assert len(flagged) == 1
        assert flagged[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_rate_limiting_via_feedback_repo(self, db):
        """Rate limiting operations work through FeedbackRepository."""
        await db.feedback.record_rate_limit_event(100, "user_feedback")
        await db.feedback.record_rate_limit_event(100, "user_feedback")

        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.feedback.count_user_feedback_since(100, since)
        assert count == 2

    @pytest.mark.asyncio
    async def test_purge_user_data_via_admin_repo(self, db):
        """GDPR purge via AdminRepository cleans all user data."""
        await db.users.ensure_user(100, "alice", "Alice")
        await db.users.add_subscription(100, "Bugis")
        await db.sightings.add_sighting(self._make_sighting())
        await db.feedback.record_rate_limit_event(100, "user_feedback")

        result = await db.admin.purge_user_data(100)
        assert "feedback_given_deleted" in result

        # Verify cleanup
        assert await db.users.get_user_details(100) is None
        subs = await db.users.get_subscriptions(100)
        assert len(subs) == 0


# ---------------------------------------------------------------------------
# Database line count verification
# ---------------------------------------------------------------------------
class TestDatabaseModularity:
    """Verify the refactor achieved meaningful code reduction."""

    def test_database_module_is_smaller(self):
        """database.py should be significantly smaller after the split."""
        import inspect

        import bot.database as db_module

        source = inspect.getsource(db_module)
        line_count = len(source.splitlines())
        # Original was ~1147 lines. After refactor, should be under 300
        # (connection mgmt + query helpers + table creation + __getattr__)
        assert line_count < 350, f"database.py is {line_count} lines — expected under 350 after split"

    def test_repository_modules_contain_business_logic(self):
        """Repository modules should contain substantial business logic."""
        import inspect

        import bot.repositories.admin as admin_mod
        import bot.repositories.config as config_mod
        import bot.repositories.feedback as feedback_mod
        import bot.repositories.sighting as sighting_mod
        import bot.repositories.user as user_mod

        for mod, min_lines in [
            (user_mod, 80),
            (sighting_mod, 100),
            (feedback_mod, 80),
            (admin_mod, 150),
            (config_mod, 30),
        ]:
            source = inspect.getsource(mod)
            line_count = len(source.splitlines())
            assert line_count >= min_lines, f"{mod.__name__} is {line_count} lines — expected at least {min_lines}"
