"""Tests for feedback vote rate limiting (F-006).

Covers:
- Votes under rate limit proceed normally
- Votes at/above rate limit are blocked
- Rate limit check uses correct action name and time window
- Rate limit event is recorded after successful vote
- Rate limit event is NOT recorded when vote is rejected (duplicate, expired, etc.)
- Repository: count_feedback_votes_since returns correct counts
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import make_callback_update, make_context, make_mock_db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestFeedbackVoteRateLimit:
    """Handler-level tests for feedback vote rate limiting."""

    SIGHTING_ID = "a1b2c3d4-e5f6-4789-abcd-ef0123456789"
    REPORTER_ID = 200
    VOTER_ID = 100

    def _make_sighting(self, age_minutes=5):
        """Create a sighting dict that is within the feedback window."""
        return {
            "id": self.SIGHTING_ID,
            "zone": "Bugis",
            "description": "Test",
            "reported_at": datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
            "reporter_id": self.REPORTER_ID,
            "reporter_name": "reporter",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
            "feedback_positive": 1,
            "feedback_negative": 0,
            "flagged": 0,
        }

    def test_vote_under_limit_proceeds(self):
        """Vote succeeds when under the rate limit."""
        from bot.handlers.report import handle_feedback

        sighting = self._make_sighting()
        mock_db = make_mock_db(
            get_sighting_reporter=self.REPORTER_ID,
            get_sighting=sighting,
            count_feedback_votes_since=5,  # Under the 10/hr limit
            apply_feedback=sighting,
        )

        update = make_callback_update(
            user_id=self.VOTER_ID,
            callback_data=f"feedback_pos_{self.SIGHTING_ID}",
        )
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.edit_message_reply_markup = AsyncMock()

        with (
            patch("bot.handlers.report.get_db", return_value=mock_db),
            patch("bot.handlers.report.get_runtime_settings") as mock_settings,
            patch("bot.handlers.report._check_auto_flag", new_callable=AsyncMock),
            patch("bot.handlers.report.build_alert_message", return_value="alert"),
        ):
            settings_instance = AsyncMock()
            settings_instance.get = AsyncMock(return_value=24)  # FEEDBACK_WINDOW_HOURS
            mock_settings.return_value = settings_instance

            _run(handle_feedback(update, make_context(), is_positive=True))

        # apply_feedback should have been called
        mock_db.apply_feedback.assert_called_once_with(self.SIGHTING_ID, self.VOTER_ID, "positive")
        # rate limit event should be recorded
        mock_db.record_rate_limit_event.assert_called_once_with(self.VOTER_ID, "feedback_vote")

    def test_vote_at_limit_is_blocked(self):
        """Vote is rejected when at the rate limit."""
        from bot.handlers.report import _MAX_FEEDBACK_VOTES_PER_HOUR, handle_feedback

        mock_db = make_mock_db(
            get_sighting_reporter=self.REPORTER_ID,
            count_feedback_votes_since=_MAX_FEEDBACK_VOTES_PER_HOUR,  # At limit
        )

        update = make_callback_update(
            user_id=self.VOTER_ID,
            callback_data=f"feedback_pos_{self.SIGHTING_ID}",
        )

        with patch("bot.handlers.report.get_db", return_value=mock_db):
            _run(handle_feedback(update, make_context(), is_positive=True))

        # apply_feedback should NOT have been called
        mock_db.apply_feedback.assert_not_called()
        # User should get a rate limit message
        update.callback_query.answer.assert_called_once()
        answer_text = update.callback_query.answer.call_args[0][0]
        assert "limit" in answer_text.lower()

    def test_vote_above_limit_is_blocked(self):
        """Vote is rejected when above the rate limit."""
        from bot.handlers.report import _MAX_FEEDBACK_VOTES_PER_HOUR, handle_feedback

        mock_db = make_mock_db(
            get_sighting_reporter=self.REPORTER_ID,
            count_feedback_votes_since=_MAX_FEEDBACK_VOTES_PER_HOUR + 5,
        )

        update = make_callback_update(
            user_id=self.VOTER_ID,
            callback_data=f"feedback_pos_{self.SIGHTING_ID}",
        )

        with patch("bot.handlers.report.get_db", return_value=mock_db):
            _run(handle_feedback(update, make_context(), is_positive=True))

        mock_db.apply_feedback.assert_not_called()
        mock_db.record_rate_limit_event.assert_not_called()

    def test_rate_limit_not_recorded_on_duplicate_vote(self):
        """Rate limit event is NOT recorded when apply_feedback raises ValueError (duplicate)."""
        from bot.handlers.report import handle_feedback

        sighting = self._make_sighting()
        mock_db = make_mock_db(
            get_sighting_reporter=self.REPORTER_ID,
            get_sighting=sighting,
            count_feedback_votes_since=0,
        )
        mock_db.apply_feedback = AsyncMock(side_effect=ValueError("duplicate_vote"))

        update = make_callback_update(
            user_id=self.VOTER_ID,
            callback_data=f"feedback_pos_{self.SIGHTING_ID}",
        )

        with (
            patch("bot.handlers.report.get_db", return_value=mock_db),
            patch("bot.handlers.report.get_runtime_settings") as mock_settings,
        ):
            settings_instance = AsyncMock()
            settings_instance.get = AsyncMock(return_value=24)
            mock_settings.return_value = settings_instance

            _run(handle_feedback(update, make_context(), is_positive=True))

        # Rate limit event should NOT be recorded for a rejected vote
        mock_db.record_rate_limit_event.assert_not_called()

    def test_rate_limit_not_recorded_on_self_rating(self):
        """Rate limit event is NOT recorded when user tries to rate own sighting."""
        from bot.handlers.report import handle_feedback

        # Reporter ID matches voter ID
        mock_db = make_mock_db(
            get_sighting_reporter=self.VOTER_ID,
            count_feedback_votes_since=0,
        )

        update = make_callback_update(
            user_id=self.VOTER_ID,
            callback_data=f"feedback_pos_{self.SIGHTING_ID}",
        )

        with patch("bot.handlers.report.get_db", return_value=mock_db):
            _run(handle_feedback(update, make_context(), is_positive=True))

        # Self-rating is blocked before rate limit check, so no rate limit queries
        mock_db.apply_feedback.assert_not_called()
        mock_db.record_rate_limit_event.assert_not_called()

    def test_rate_limit_constant_value(self):
        """Verify the rate limit constant is set to a reasonable value."""
        from bot.handlers.report import _MAX_FEEDBACK_VOTES_PER_HOUR

        assert _MAX_FEEDBACK_VOTES_PER_HOUR == 10


class TestFeedbackVoteRateLimitRepository:
    """Repository-level tests for count_feedback_votes_since."""

    @pytest.mark.asyncio
    async def test_count_returns_zero_when_no_events(self, db):
        """Returns 0 when no feedback_vote events exist."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_feedback_votes_since(user_id=999, since=one_hour_ago)
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_returns_correct_count(self, db):
        """Returns correct count of feedback_vote events within time window."""
        user_id = 100
        now = datetime.now(timezone.utc)

        # Record 3 feedback_vote events
        for _ in range(3):
            await db.record_rate_limit_event(user_id, "feedback_vote")

        # Record 2 events with a different action (should not be counted)
        for _ in range(2):
            await db.record_rate_limit_event(user_id, "user_feedback")

        one_hour_ago = now - timedelta(hours=1)
        count = await db.count_feedback_votes_since(user_id, one_hour_ago)
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_excludes_other_users(self, db):
        """Only counts events for the specified user."""
        now = datetime.now(timezone.utc)

        await db.record_rate_limit_event(100, "feedback_vote")
        await db.record_rate_limit_event(200, "feedback_vote")
        await db.record_rate_limit_event(200, "feedback_vote")

        one_hour_ago = now - timedelta(hours=1)
        count_100 = await db.count_feedback_votes_since(100, one_hour_ago)
        count_200 = await db.count_feedback_votes_since(200, one_hour_ago)
        assert count_100 == 1
        assert count_200 == 2

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_events(self, db):
        """Rate limit events are cleaned up by cleanup_old_rate_limits."""
        user_id = 100
        await db.record_rate_limit_event(user_id, "feedback_vote")

        # Cleanup removes events older than 24h — our fresh event should survive
        deleted = await db.cleanup_old_rate_limits(max_age_hours=24)
        assert deleted == 0

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await db.count_feedback_votes_since(user_id, one_hour_ago)
        assert count == 1
