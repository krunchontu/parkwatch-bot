"""Feedback repository.

Handles feedback votes, transaction-safe feedback application, accuracy
calculations, and rate-limit event tracking.
"""

from datetime import datetime, timedelta, timezone

from .base import BaseRepository


class FeedbackRepository(BaseRepository):
    """Feedback, accuracy, and rate-limit operations."""

    # --- Feedback ---

    async def get_user_feedback(self, sighting_id: str, user_id: int) -> str | None:
        """Get user's existing vote on a sighting. Returns 'positive'/'negative' or None."""
        row = await self._fetchone(
            f"SELECT vote FROM feedback WHERE sighting_id = {self._ph(1)} AND user_id = {self._ph(2)}",
            (sighting_id, user_id),
        )
        return row["vote"] if row else None

    async def set_feedback(self, sighting_id: str, user_id: int, vote: str) -> None:
        """Set or update a user's feedback vote (upsert)."""
        if self.driver == "sqlite":
            await self._execute(
                "INSERT INTO feedback (sighting_id, user_id, vote) VALUES (?, ?, ?) "
                "ON CONFLICT(sighting_id, user_id) DO UPDATE SET vote = excluded.vote",
                (sighting_id, user_id, vote),
            )
        else:
            await self._execute(
                "INSERT INTO feedback (sighting_id, user_id, vote) VALUES ($1, $2, $3) "
                "ON CONFLICT (sighting_id, user_id) DO UPDATE SET vote = EXCLUDED.vote",
                (sighting_id, user_id, vote),
            )

    # --- Transaction-safe feedback ---

    async def apply_feedback(self, sighting_id: str, user_id: int, new_vote: str) -> dict | None:
        """Atomically apply a feedback vote: read previous, upsert vote, update counts.

        Returns the updated sighting dict, or None if sighting not found.
        Raises ValueError if user already submitted the same vote.
        """
        if self.driver == "sqlite":
            # SQLite: use BEGIN IMMEDIATE to prevent concurrent interleaving
            try:
                await self._conn.execute("BEGIN IMMEDIATE")
                previous_row = await self._conn.execute(
                    "SELECT vote FROM feedback WHERE sighting_id = ? AND user_id = ?", (sighting_id, user_id)
                )
                previous = await previous_row.fetchone()
                previous_vote = dict(previous)["vote"] if previous else None

                if previous_vote == new_vote:
                    raise ValueError("duplicate_vote")

                # Reverse old vote if changing
                pos_delta, neg_delta = 0, 0
                if previous_vote == "positive":
                    pos_delta -= 1
                elif previous_vote == "negative":
                    neg_delta -= 1

                # Apply new vote
                if new_vote == "positive":
                    pos_delta += 1
                else:
                    neg_delta += 1

                # Upsert feedback
                await self._conn.execute(
                    "INSERT INTO feedback (sighting_id, user_id, vote) VALUES (?, ?, ?) "
                    "ON CONFLICT(sighting_id, user_id) DO UPDATE SET vote = excluded.vote",
                    (sighting_id, user_id, new_vote),
                )

                # Update counts
                await self._conn.execute(
                    "UPDATE sightings SET feedback_positive = feedback_positive + ?, "
                    "feedback_negative = feedback_negative + ? WHERE id = ?",
                    (pos_delta, neg_delta, sighting_id),
                )

                await self._conn.commit()

                # Fetch updated sighting
                cursor = await self._conn.execute("SELECT * FROM sightings WHERE id = ?", (sighting_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None
            except ValueError:
                raise
            except Exception:
                await self._conn.commit()  # release any partial state
                raise
        else:
            async with self._pool.acquire() as conn, conn.transaction():
                previous_row = await conn.fetchrow(
                    "SELECT vote FROM feedback WHERE sighting_id = $1 AND user_id = $2", sighting_id, user_id
                )
                previous_vote = dict(previous_row)["vote"] if previous_row else None

                if previous_vote == new_vote:
                    raise ValueError("duplicate_vote")

                pos_delta, neg_delta = 0, 0
                if previous_vote == "positive":
                    pos_delta -= 1
                elif previous_vote == "negative":
                    neg_delta -= 1

                if new_vote == "positive":
                    pos_delta += 1
                else:
                    neg_delta += 1

                await conn.execute(
                    "INSERT INTO feedback (sighting_id, user_id, vote) VALUES ($1, $2, $3) "
                    "ON CONFLICT (sighting_id, user_id) DO UPDATE SET vote = EXCLUDED.vote",
                    sighting_id,
                    user_id,
                    new_vote,
                )

                await conn.execute(
                    "UPDATE sightings SET feedback_positive = feedback_positive + $1, "
                    "feedback_negative = feedback_negative + $2 WHERE id = $3",
                    pos_delta,
                    neg_delta,
                    sighting_id,
                )

                row = await conn.fetchrow("SELECT * FROM sightings WHERE id = $1", sighting_id)
                return dict(row) if row else None

    # --- Accuracy (aggregate queries) ---

    async def calculate_accuracy(self, user_id: int) -> tuple[float, int]:
        """Calculate accuracy score from ALL sightings by this user.

        Returns (accuracy_score, total_feedback_count).
        Score is 0.0 when there is no feedback (not 1.0) to avoid misleading display.
        """
        row = await self._fetchone(
            f"SELECT COALESCE(SUM(feedback_positive), 0) AS pos, "
            f"COALESCE(SUM(feedback_negative), 0) AS neg "
            f"FROM sightings WHERE reporter_id = {self._ph(1)}",
            (user_id,),
        )
        if not row:
            return 0.0, 0
        pos, neg = row["pos"], row["neg"]
        total = pos + neg
        if total == 0:
            return 0.0, 0
        return pos / total, total

    async def get_user_feedback_totals(self, user_id: int) -> tuple[int, int]:
        """Get total positive and negative feedback across all user's sightings."""
        row = await self._fetchone(
            f"SELECT COALESCE(SUM(feedback_positive), 0) AS pos, "
            f"COALESCE(SUM(feedback_negative), 0) AS neg "
            f"FROM sightings WHERE reporter_id = {self._ph(1)}",
            (user_id,),
        )
        if not row:
            return 0, 0
        return row["pos"], row["neg"]

    # --- Rate limiting ---

    async def record_rate_limit_event(self, user_id: int, action: str) -> None:
        """Record a rate-limited action for the given user."""
        ph = self._ph
        await self._execute(
            f"INSERT INTO user_rate_limits (user_id, action, created_at) VALUES ({ph(1)}, {ph(2)}, {ph(3)})",
            (user_id, action, datetime.now(timezone.utc)),
        )

    async def cleanup_old_rate_limits(self, max_age_hours: int = 24) -> int:
        """Delete rate limit entries older than max_age_hours. Returns count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        if self.driver == "sqlite":
            cursor = await self._conn.execute("DELETE FROM user_rate_limits WHERE created_at < ?", (cutoff,))
            count = cursor.rowcount
            await self._conn.commit()
            return count
        else:
            async with self._pool.acquire() as conn, conn.transaction():
                result = await conn.execute("DELETE FROM user_rate_limits WHERE created_at < $1", cutoff)
                try:
                    return int(result.split()[-1])
                except (ValueError, IndexError):
                    return 0

    async def count_user_feedback_since(self, user_id: int, since: datetime) -> int:
        """Count feedback messages sent by a user since a given time (for rate limiting).

        Uses the dedicated user_rate_limits table (decoupled from audit log).
        """
        row = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM user_rate_limits "
            f"WHERE user_id = {self._ph(1)} AND action = 'user_feedback' AND created_at > {self._ph(2)}",
            (user_id, since),
        )
        return row["cnt"] if row else 0
