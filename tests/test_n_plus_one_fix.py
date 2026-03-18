"""Tests for F-008: N+1 accuracy query elimination in /recent.

Covers:
- Repository: calculate_accuracy_batch returns correct results for multiple users
- Repository: calculate_accuracy_batch handles empty list
- Repository: calculate_accuracy_batch handles users with no feedback
- Repository: calculate_accuracy_batch handles duplicate user IDs
- Repository: calculate_accuracy_batch matches calculate_accuracy for same user
- Handler: _build_recent_text calls calculate_accuracy_batch instead of per-row calculate_accuracy
- Handler: _build_recent_text produces identical output with batched queries
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import make_mock_db


class TestCalculateAccuracyBatchRepository:
    """Repository-level tests for calculate_accuracy_batch."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_dict(self, db):
        result = await db.calculate_accuracy_batch([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_user_with_feedback(self, db):
        """Single user with positive and negative feedback."""
        user_id = 100
        await db.ensure_user(user_id, "reporter1")
        sighting = {
            "id": "s1",
            "zone": "Bugis",
            "description": "test",
            "time": datetime.now(timezone.utc),
            "reporter_id": user_id,
            "reporter_name": "reporter1",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
        await db.add_sighting(sighting)
        # Manually set feedback counts
        await db._execute(
            "UPDATE sightings SET feedback_positive = 8, feedback_negative = 2 WHERE id = ?",
            ("s1",),
        )

        result = await db.calculate_accuracy_batch([user_id])
        assert user_id in result
        acc, total = result[user_id]
        assert total == 10
        assert abs(acc - 0.8) < 0.001

    @pytest.mark.asyncio
    async def test_multiple_users(self, db):
        """Multiple users with different feedback profiles."""
        now = datetime.now(timezone.utc)
        for uid, name in [(100, "alice"), (200, "bob"), (300, "carol")]:
            await db.ensure_user(uid, name)

        # Alice: 2 sightings, total 9pos + 1neg = 90% accuracy
        for i, sid in enumerate(["a1", "a2"]):
            await db.add_sighting({
                "id": sid, "zone": "Bugis", "description": "test",
                "time": now - timedelta(minutes=i),
                "reporter_id": 100, "reporter_name": "alice",
                "reporter_badge": "New", "lat": None, "lng": None,
            })
        await db._execute("UPDATE sightings SET feedback_positive = 5, feedback_negative = 0 WHERE id = ?", ("a1",))
        await db._execute("UPDATE sightings SET feedback_positive = 4, feedback_negative = 1 WHERE id = ?", ("a2",))

        # Bob: 1 sighting, 0 feedback
        await db.add_sighting({
            "id": "b1", "zone": "Orchard", "description": "test",
            "time": now - timedelta(minutes=5),
            "reporter_id": 200, "reporter_name": "bob",
            "reporter_badge": "New", "lat": None, "lng": None,
        })

        # Carol: 1 sighting, 1pos + 4neg = 20% accuracy
        await db.add_sighting({
            "id": "c1", "zone": "Tampines", "description": "test",
            "time": now - timedelta(minutes=10),
            "reporter_id": 300, "reporter_name": "carol",
            "reporter_badge": "New", "lat": None, "lng": None,
        })
        await db._execute("UPDATE sightings SET feedback_positive = 1, feedback_negative = 4 WHERE id = ?", ("c1",))

        result = await db.calculate_accuracy_batch([100, 200, 300])

        # Alice: 9/10 = 0.9
        acc_alice, total_alice = result[100]
        assert total_alice == 10
        assert abs(acc_alice - 0.9) < 0.001

        # Bob: 0 feedback
        acc_bob, total_bob = result[200]
        assert total_bob == 0
        assert acc_bob == 0.0

        # Carol: 1/5 = 0.2
        acc_carol, total_carol = result[300]
        assert total_carol == 5
        assert abs(acc_carol - 0.2) < 0.001

    @pytest.mark.asyncio
    async def test_unknown_user_returns_default(self, db):
        """User IDs not in the database get (0.0, 0)."""
        result = await db.calculate_accuracy_batch([999, 998])
        assert result[999] == (0.0, 0)
        assert result[998] == (0.0, 0)

    @pytest.mark.asyncio
    async def test_duplicate_ids_handled(self, db):
        """Duplicate user IDs in input don't cause issues."""
        await db.ensure_user(100, "alice")
        await db.add_sighting({
            "id": "s1", "zone": "Bugis", "description": "test",
            "time": datetime.now(timezone.utc),
            "reporter_id": 100, "reporter_name": "alice",
            "reporter_badge": "New", "lat": None, "lng": None,
        })
        await db._execute(
            "UPDATE sightings SET feedback_positive = 3, feedback_negative = 1 WHERE id = ?",
            ("s1",),
        )

        result = await db.calculate_accuracy_batch([100, 100, 100])
        assert 100 in result
        acc, total = result[100]
        assert total == 4
        assert abs(acc - 0.75) < 0.001

    @pytest.mark.asyncio
    async def test_batch_matches_individual(self, db):
        """Batch results must match individual calculate_accuracy calls."""
        now = datetime.now(timezone.utc)
        for uid, name in [(100, "alice"), (200, "bob")]:
            await db.ensure_user(uid, name)
            await db.add_sighting({
                "id": f"s{uid}", "zone": "Bugis", "description": "test",
                "time": now,
                "reporter_id": uid, "reporter_name": name,
                "reporter_badge": "New", "lat": None, "lng": None,
            })
        await db._execute("UPDATE sightings SET feedback_positive = 7, feedback_negative = 3 WHERE id = ?", ("s100",))
        await db._execute("UPDATE sightings SET feedback_positive = 2, feedback_negative = 8 WHERE id = ?", ("s200",))

        # Individual queries
        ind_100 = await db.calculate_accuracy(100)
        ind_200 = await db.calculate_accuracy(200)

        # Batch query
        batch = await db.calculate_accuracy_batch([100, 200])

        assert abs(batch[100][0] - ind_100[0]) < 0.001
        assert batch[100][1] == ind_100[1]
        assert abs(batch[200][0] - ind_200[0]) < 0.001
        assert batch[200][1] == ind_200[1]


class TestBuildRecentTextNoPlusOne:
    """Verify _build_recent_text uses batch query, not per-row queries."""

    @pytest.mark.asyncio
    async def test_batch_called_instead_of_individual(self):
        """_build_recent_text must call calculate_accuracy_batch, not calculate_accuracy per row."""
        from bot.handlers.user import _build_recent_text

        now = datetime.now(timezone.utc)
        sightings = [
            {
                "zone": "Bugis", "reported_at": now - timedelta(minutes=2),
                "description": "Near MRT", "lat": None, "lng": None,
                "reporter_id": 100, "reporter_badge": "New",
                "feedback_positive": 3, "feedback_negative": 1,
            },
            {
                "zone": "Orchard", "reported_at": now - timedelta(minutes=8),
                "description": "Outside mall", "lat": 1.3, "lng": 103.8,
                "reporter_id": 200, "reporter_badge": "Regular",
                "feedback_positive": 0, "feedback_negative": 0,
            },
            {
                "zone": "Bugis", "reported_at": now - timedelta(minutes=20),
                "description": None, "lat": None, "lng": None,
                "reporter_id": 100, "reporter_badge": "New",
                "feedback_positive": 1, "feedback_negative": 0,
            },
        ]

        mock_db = make_mock_db(
            get_subscriptions={"Bugis", "Orchard"},
            get_recent_sightings_for_zones=sightings,
        )
        # Add the batch method to the mock
        mock_db.calculate_accuracy_batch = AsyncMock(return_value={
            100: (0.85, 8),
            200: (0.0, 0),
        })

        with (
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_runtime_settings") as mock_settings,
        ):
            settings_instance = AsyncMock()
            settings_instance.get = AsyncMock(return_value=30)
            mock_settings.return_value = settings_instance

            text = await _build_recent_text(999)

        # Batch was called once with all reporter IDs
        mock_db.calculate_accuracy_batch.assert_called_once()
        call_args = mock_db.calculate_accuracy_batch.call_args[0][0]
        assert sorted(call_args) == [100, 100, 200]  # includes duplicates from input

        # Individual calculate_accuracy should NOT have been called
        mock_db.calculate_accuracy.assert_not_called()

        # Output should contain sighting data
        assert "Bugis" in text
        assert "Orchard" in text

    @pytest.mark.asyncio
    async def test_empty_sightings_skips_batch(self):
        """No sightings means no batch query is issued."""
        from bot.handlers.user import _build_recent_text

        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=[],
        )
        mock_db.calculate_accuracy_batch = AsyncMock()

        with (
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_runtime_settings") as mock_settings,
        ):
            settings_instance = AsyncMock()
            settings_instance.get = AsyncMock(return_value=30)
            mock_settings.return_value = settings_instance

            text = await _build_recent_text(999)

        mock_db.calculate_accuracy_batch.assert_not_called()
        assert "no recent" in text.lower()

    @pytest.mark.asyncio
    async def test_accuracy_indicators_rendered(self):
        """Accuracy indicators from batch query appear in output."""
        from bot.handlers.user import _build_recent_text

        now = datetime.now(timezone.utc)
        sightings = [
            {
                "zone": "Bugis", "reported_at": now - timedelta(minutes=2),
                "description": "test", "lat": None, "lng": None,
                "reporter_id": 100, "reporter_badge": "Trusted",
                "feedback_positive": 5, "feedback_negative": 0,
            },
        ]

        mock_db = make_mock_db(
            get_subscriptions={"Bugis"},
            get_recent_sightings_for_zones=sightings,
        )
        mock_db.calculate_accuracy_batch = AsyncMock(return_value={
            100: (0.95, 20),  # High accuracy -> checkmark indicator
        })

        with (
            patch("bot.handlers.user.get_db", return_value=mock_db),
            patch("bot.handlers.user.get_runtime_settings") as mock_settings,
        ):
            settings_instance = AsyncMock()
            settings_instance.get = AsyncMock(return_value=30)
            mock_settings.return_value = settings_instance

            text = await _build_recent_text(999)

        assert "\u2705" in text  # accuracy checkmark indicator
