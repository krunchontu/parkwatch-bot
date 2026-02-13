"""Database integration tests for ParkWatch SG.

Tests CRUD operations, duplicate detection queries, accuracy calculations,
feedback transactions, and cleanup logic using a temporary SQLite database.
"""

import contextlib
from datetime import datetime, timedelta, timezone

import pytest

from bot.database import Database


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
class TestSubscriptions:
    """Test subscription CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_get_subscription(self, db):
        await db.add_subscription(100, "Bugis")
        subs = await db.get_subscriptions(100)
        assert subs == {"Bugis"}

    @pytest.mark.asyncio
    async def test_add_multiple_subscriptions(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(100, "Tanjong Pagar")
        subs = await db.get_subscriptions(100)
        assert subs == {"Bugis", "Orchard", "Tanjong Pagar"}

    @pytest.mark.asyncio
    async def test_add_subscription_idempotent(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Bugis")
        subs = await db.get_subscriptions(100)
        assert subs == {"Bugis"}

    @pytest.mark.asyncio
    async def test_remove_subscription(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.remove_subscription(100, "Bugis")
        subs = await db.get_subscriptions(100)
        assert subs == {"Orchard"}

    @pytest.mark.asyncio
    async def test_clear_subscriptions(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.clear_subscriptions(100)
        subs = await db.get_subscriptions(100)
        assert subs == set()

    @pytest.mark.asyncio
    async def test_get_subscriptions_empty(self, db):
        subs = await db.get_subscriptions(999)
        assert subs == set()

    @pytest.mark.asyncio
    async def test_get_zone_subscribers(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(200, "Bugis")
        await db.add_subscription(300, "Orchard")
        subscribers = await db.get_zone_subscribers("Bugis")
        assert sorted(subscribers) == [100, 200]

    @pytest.mark.asyncio
    async def test_get_subscriber_count(self, db):
        await db.add_subscription(100, "Bugis")
        await db.add_subscription(100, "Orchard")
        await db.add_subscription(200, "Bugis")
        count = await db.get_subscriber_count()
        assert count == 2  # 2 distinct users


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class TestUsers:
    """Test user management operations."""

    @pytest.mark.asyncio
    async def test_ensure_user_creates_new(self, db):
        await db.ensure_user(100, "alice")
        stats = await db.get_user_stats(100)
        assert stats is not None
        assert stats["username"] == "alice"
        assert stats["report_count"] == 0

    @pytest.mark.asyncio
    async def test_ensure_user_updates_username(self, db):
        await db.ensure_user(100, "alice")
        await db.ensure_user(100, "alice_new")
        stats = await db.get_user_stats(100)
        assert stats["username"] == "alice_new"

    @pytest.mark.asyncio
    async def test_get_user_stats_nonexistent(self, db):
        stats = await db.get_user_stats(999)
        assert stats is None

    @pytest.mark.asyncio
    async def test_increment_report_count(self, db):
        await db.ensure_user(100, "alice")
        count1 = await db.increment_report_count(100)
        assert count1 == 1
        count2 = await db.increment_report_count(100)
        assert count2 == 2

    @pytest.mark.asyncio
    async def test_increment_preserves_username(self, db):
        await db.ensure_user(100, "alice")
        await db.increment_report_count(100)
        stats = await db.get_user_stats(100)
        assert stats["username"] == "alice"
        assert stats["report_count"] == 1


# ---------------------------------------------------------------------------
# Sightings
# ---------------------------------------------------------------------------
class TestSightings:
    """Test sighting CRUD operations."""

    @staticmethod
    def _make_sighting(sighting_id="s1", zone="Bugis", **overrides):
        base = {
            "id": sighting_id,
            "zone": zone,
            "description": "test sighting",
            "time": datetime.now(timezone.utc),
            "reporter_id": 100,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": 1.3008,
            "lng": 103.8553,
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_add_and_get_sighting(self, db):
        await db.add_sighting(self._make_sighting())
        sighting = await db.get_sighting("s1")
        assert sighting is not None
        assert sighting["zone"] == "Bugis"
        assert sighting["reporter_id"] == 100
        assert sighting["feedback_positive"] == 0
        assert sighting["feedback_negative"] == 0

    @pytest.mark.asyncio
    async def test_get_sighting_nonexistent(self, db):
        sighting = await db.get_sighting("nonexistent")
        assert sighting is None

    @pytest.mark.asyncio
    async def test_get_sighting_reporter(self, db):
        await db.add_sighting(self._make_sighting(reporter_id=100))
        reporter_id = await db.get_sighting_reporter("s1")
        assert reporter_id == 100

    @pytest.mark.asyncio
    async def test_get_sighting_reporter_nonexistent(self, db):
        reporter_id = await db.get_sighting_reporter("nonexistent")
        assert reporter_id is None

    @pytest.mark.asyncio
    async def test_get_total_sightings_count(self, db):
        assert await db.get_total_sightings_count() == 0
        await db.add_sighting(self._make_sighting("s1"))
        await db.add_sighting(self._make_sighting("s2", zone="Orchard"))
        assert await db.get_total_sightings_count() == 2


# ---------------------------------------------------------------------------
# Recent sightings & duplicate detection
# ---------------------------------------------------------------------------
class TestRecentSightings:
    """Test queries used for duplicate detection and /recent command."""

    @staticmethod
    def _make_sighting(sighting_id, zone="Bugis", minutes_ago=0, **overrides):
        base = {
            "id": sighting_id,
            "zone": zone,
            "description": "test",
            "time": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "reporter_id": 100,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": 1.3008,
            "lng": 103.8553,
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_find_recent_zone_sightings_within_window(self, db):
        await db.add_sighting(self._make_sighting("s1", minutes_ago=2))
        results = await db.find_recent_zone_sightings("Bugis", 5)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_recent_zone_sightings_outside_window(self, db):
        await db.add_sighting(self._make_sighting("s1", minutes_ago=10))
        results = await db.find_recent_zone_sightings("Bugis", 5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_find_recent_zone_sightings_different_zone(self, db):
        await db.add_sighting(self._make_sighting("s1", zone="Orchard", minutes_ago=2))
        results = await db.find_recent_zone_sightings("Bugis", 5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_recent_sightings_for_zones(self, db):
        await db.add_sighting(self._make_sighting("s1", zone="Bugis", minutes_ago=5))
        await db.add_sighting(self._make_sighting("s2", zone="Orchard", minutes_ago=5))
        await db.add_sighting(self._make_sighting("s3", zone="Chinatown", minutes_ago=5))
        results = await db.get_recent_sightings_for_zones({"Bugis", "Orchard"}, 30)
        assert len(results) == 2
        zones = {r["zone"] for r in results}
        assert zones == {"Bugis", "Orchard"}

    @pytest.mark.asyncio
    async def test_get_recent_sightings_excludes_expired(self, db):
        await db.add_sighting(self._make_sighting("s1", minutes_ago=5))
        await db.add_sighting(self._make_sighting("s2", minutes_ago=40))
        results = await db.get_recent_sightings_for_zones({"Bugis"}, 30)
        assert len(results) == 1
        assert results[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_get_recent_sightings_empty_zones(self, db):
        results = await db.get_recent_sightings_for_zones(set(), 30)
        assert results == []

    @pytest.mark.asyncio
    async def test_recent_sightings_ordered_newest_first(self, db):
        await db.add_sighting(self._make_sighting("s_old", minutes_ago=20))
        await db.add_sighting(self._make_sighting("s_new", minutes_ago=1))
        results = await db.get_recent_sightings_for_zones({"Bugis"}, 30)
        assert results[0]["id"] == "s_new"
        assert results[1]["id"] == "s_old"


# ---------------------------------------------------------------------------
# Rate limiting queries
# ---------------------------------------------------------------------------
class TestRateLimiting:
    """Test count_reports_since and get_oldest_report_since."""

    @staticmethod
    def _make_sighting(sighting_id, minutes_ago=0, reporter_id=100):
        return {
            "id": sighting_id,
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "reporter_id": reporter_id,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": None,
            "lng": None,
        }

    @pytest.mark.asyncio
    async def test_count_reports_since(self, db):
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.add_sighting(self._make_sighting("s1", minutes_ago=30))
        await db.add_sighting(self._make_sighting("s2", minutes_ago=10))
        await db.add_sighting(self._make_sighting("s3", minutes_ago=90))  # outside window
        count = await db.count_reports_since(100, since)
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_reports_since_different_user(self, db):
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.add_sighting(self._make_sighting("s1", reporter_id=100))
        await db.add_sighting(self._make_sighting("s2", reporter_id=200))
        count = await db.count_reports_since(100, since)
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_oldest_report_since(self, db):
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.add_sighting(self._make_sighting("s1", minutes_ago=50))
        await db.add_sighting(self._make_sighting("s2", minutes_ago=10))
        oldest = await db.get_oldest_report_since(100, since)
        assert oldest is not None
        # SQLite may return string; ensure we have a datetime
        if isinstance(oldest, str):
            oldest = datetime.fromisoformat(oldest)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        # oldest should be ~50 minutes ago (within tolerance)
        age = (datetime.now(timezone.utc) - oldest).total_seconds()
        assert 2900 < age < 3100  # roughly 50 minutes

    @pytest.mark.asyncio
    async def test_get_oldest_report_since_none(self, db):
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        oldest = await db.get_oldest_report_since(100, since)
        assert oldest is None


# ---------------------------------------------------------------------------
# Feedback & accuracy
# ---------------------------------------------------------------------------
class TestFeedback:
    """Test feedback operations and accuracy calculations."""

    @staticmethod
    def _make_sighting(sighting_id="s1", reporter_id=100):
        return {
            "id": sighting_id,
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc),
            "reporter_id": reporter_id,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": 1.3008,
            "lng": 103.8553,
        }

    @pytest.mark.asyncio
    async def test_apply_feedback_positive(self, db):
        await db.add_sighting(self._make_sighting())
        result = await db.apply_feedback("s1", 200, "positive")
        assert result is not None
        assert result["feedback_positive"] == 1
        assert result["feedback_negative"] == 0

    @pytest.mark.asyncio
    async def test_apply_feedback_negative(self, db):
        await db.add_sighting(self._make_sighting())
        result = await db.apply_feedback("s1", 200, "negative")
        assert result is not None
        assert result["feedback_positive"] == 0
        assert result["feedback_negative"] == 1

    @pytest.mark.asyncio
    async def test_apply_feedback_vote_change(self, db):
        """Changing vote from positive to negative should adjust counts."""
        await db.add_sighting(self._make_sighting())
        await db.apply_feedback("s1", 200, "positive")
        result = await db.apply_feedback("s1", 200, "negative")
        assert result["feedback_positive"] == 0
        assert result["feedback_negative"] == 1

    @pytest.mark.asyncio
    async def test_apply_feedback_duplicate_vote_raises(self, db):
        """Submitting the same vote twice should raise ValueError."""
        await db.add_sighting(self._make_sighting())
        await db.apply_feedback("s1", 200, "positive")
        with pytest.raises(ValueError):
            await db.apply_feedback("s1", 200, "positive")

    @pytest.mark.asyncio
    async def test_apply_feedback_multiple_users(self, db):
        await db.add_sighting(self._make_sighting())
        await db.apply_feedback("s1", 200, "positive")
        await db.apply_feedback("s1", 300, "positive")
        await db.apply_feedback("s1", 400, "negative")
        sighting = await db.get_sighting("s1")
        assert sighting["feedback_positive"] == 2
        assert sighting["feedback_negative"] == 1

    @pytest.mark.asyncio
    async def test_apply_feedback_nonexistent_sighting(self, db):
        # With FK constraints, inserting feedback for non-existent sighting should fail.
        # apply_feedback should either raise or return None.
        with contextlib.suppress(Exception):
            await db.apply_feedback("nonexistent", 200, "positive")

    @pytest.mark.asyncio
    async def test_get_user_feedback(self, db):
        await db.add_sighting(self._make_sighting())
        await db.set_feedback("s1", 200, "positive")
        vote = await db.get_user_feedback("s1", 200)
        assert vote == "positive"

    @pytest.mark.asyncio
    async def test_get_user_feedback_none(self, db):
        await db.add_sighting(self._make_sighting())
        vote = await db.get_user_feedback("s1", 200)
        assert vote is None

    @pytest.mark.asyncio
    async def test_set_feedback_upsert(self, db):
        await db.add_sighting(self._make_sighting())
        await db.set_feedback("s1", 200, "positive")
        await db.set_feedback("s1", 200, "negative")
        vote = await db.get_user_feedback("s1", 200)
        assert vote == "negative"


# ---------------------------------------------------------------------------
# Accuracy calculations
# ---------------------------------------------------------------------------
class TestAccuracy:
    """Test accuracy score calculation."""

    @staticmethod
    def _make_sighting(sighting_id, reporter_id=100, pos=0, neg=0):
        return {
            "id": sighting_id,
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc),
            "reporter_id": reporter_id,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": None,
            "lng": None,
        }

    @pytest.mark.asyncio
    async def test_accuracy_no_sightings(self, db):
        score, total = await db.calculate_accuracy(100)
        assert score == 0.0
        assert total == 0

    @pytest.mark.asyncio
    async def test_accuracy_no_feedback(self, db):
        await db.add_sighting(self._make_sighting("s1"))
        score, total = await db.calculate_accuracy(100)
        assert score == 0.0
        assert total == 0

    @pytest.mark.asyncio
    async def test_accuracy_all_positive(self, db):
        await db.add_sighting(self._make_sighting("s1"))
        await db.apply_feedback("s1", 200, "positive")
        await db.apply_feedback("s1", 300, "positive")
        score, total = await db.calculate_accuracy(100)
        assert score == 1.0
        assert total == 2

    @pytest.mark.asyncio
    async def test_accuracy_mixed_feedback(self, db):
        await db.add_sighting(self._make_sighting("s1"))
        await db.apply_feedback("s1", 200, "positive")
        await db.apply_feedback("s1", 300, "positive")
        await db.apply_feedback("s1", 400, "negative")
        score, total = await db.calculate_accuracy(100)
        assert abs(score - 2 / 3) < 0.01
        assert total == 3

    @pytest.mark.asyncio
    async def test_accuracy_across_multiple_sightings(self, db):
        """Accuracy is calculated across all sightings by the reporter."""
        await db.add_sighting(self._make_sighting("s1"))
        await db.add_sighting(self._make_sighting("s2"))
        await db.apply_feedback("s1", 200, "positive")  # s1: +1
        await db.apply_feedback("s2", 200, "negative")  # s2: -1
        score, total = await db.calculate_accuracy(100)
        assert score == 0.5
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_user_feedback_totals(self, db):
        await db.add_sighting(self._make_sighting("s1"))
        await db.apply_feedback("s1", 200, "positive")
        await db.apply_feedback("s1", 300, "negative")
        pos, neg = await db.get_user_feedback_totals(100)
        assert pos == 1
        assert neg == 1

    @pytest.mark.asyncio
    async def test_get_user_feedback_totals_no_data(self, db):
        pos, neg = await db.get_user_feedback_totals(100)
        assert pos == 0
        assert neg == 0


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
class TestCleanup:
    """Test old sighting cleanup."""

    @staticmethod
    def _make_sighting(sighting_id, days_ago=0):
        return {
            "id": sighting_id,
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc) - timedelta(days=days_ago),
            "reporter_id": 100,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": None,
            "lng": None,
        }

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_sightings(self, db):
        await db.add_sighting(self._make_sighting("s_old", days_ago=35))
        await db.add_sighting(self._make_sighting("s_new", days_ago=5))
        deleted = await db.cleanup_old_sightings(30)
        assert deleted == 1
        assert await db.get_sighting("s_old") is None
        assert await db.get_sighting("s_new") is not None

    @pytest.mark.asyncio
    async def test_cleanup_cascades_to_feedback(self, db):
        await db.add_sighting(self._make_sighting("s_old", days_ago=35))
        await db.set_feedback("s_old", 200, "positive")
        deleted = await db.cleanup_old_sightings(30)
        assert deleted == 1
        # Feedback should also be gone
        vote = await db.get_user_feedback("s_old", 200)
        assert vote is None

    @pytest.mark.asyncio
    async def test_cleanup_nothing_to_delete(self, db):
        await db.add_sighting(self._make_sighting("s1", days_ago=5))
        deleted = await db.cleanup_old_sightings(30)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_cleanup_empty_database(self, db):
        deleted = await db.cleanup_old_sightings(30)
        assert deleted == 0


# ---------------------------------------------------------------------------
# Feedback counts update
# ---------------------------------------------------------------------------
class TestFeedbackCounts:
    """Test direct feedback count updates."""

    @staticmethod
    def _make_sighting(sighting_id="s1"):
        return {
            "id": sighting_id,
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc),
            "reporter_id": 100,
            "reporter_name": "alice",
            "reporter_badge": "🆕 New",
            "lat": None,
            "lng": None,
        }

    @pytest.mark.asyncio
    async def test_update_feedback_counts(self, db):
        await db.add_sighting(self._make_sighting())
        await db.update_feedback_counts("s1", 3, 1)
        sighting = await db.get_sighting("s1")
        assert sighting["feedback_positive"] == 3
        assert sighting["feedback_negative"] == 1

    @pytest.mark.asyncio
    async def test_update_feedback_counts_incremental(self, db):
        await db.add_sighting(self._make_sighting())
        await db.update_feedback_counts("s1", 1, 0)
        await db.update_feedback_counts("s1", 1, 1)
        sighting = await db.get_sighting("s1")
        assert sighting["feedback_positive"] == 2
        assert sighting["feedback_negative"] == 1


# ---------------------------------------------------------------------------
# Database driver detection
# ---------------------------------------------------------------------------
class TestDatabaseInit:
    """Test database driver selection."""

    def test_default_driver_is_sqlite(self):
        db = Database()
        assert db.driver == "sqlite"

    def test_sqlite_url_uses_sqlite(self):
        db = Database("sqlite:///test.db")
        assert db.driver == "sqlite"

    def test_postgresql_url_uses_postgresql(self):
        db = Database("postgresql://user:pass@localhost/dbname")
        assert db.driver == "postgresql"

    def test_postgres_url_uses_postgresql(self):
        db = Database("postgres://user:pass@localhost/dbname")
        assert db.driver == "postgresql"

    def test_placeholder_sqlite(self):
        db = Database()
        assert db._ph(1) == "?"
        assert db._ph(2) == "?"

    def test_placeholder_postgresql(self):
        db = Database("postgresql://localhost/test")
        assert db._ph(1) == "$1"
        assert db._ph(2) == "$2"
