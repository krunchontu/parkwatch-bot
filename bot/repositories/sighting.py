"""Sighting repository.

Handles sighting CRUD, recent/duplicate queries, cleanup, moderation,
and purge operations.
"""

from datetime import datetime, timedelta, timezone
from typing import cast

from ..models import SightingRow
from .base import BaseRepository


class SightingRepository(BaseRepository):
    """Sighting CRUD, queries, cleanup, and moderation operations."""

    # --- Sighting CRUD ---

    async def add_sighting(self, sighting: dict) -> None:
        """Insert a new sighting record."""
        ph = self._ph
        await self._execute(
            f"""INSERT INTO sightings (id, zone, description, reported_at, reporter_id,
                reporter_name, reporter_badge, lat, lng, feedback_positive, feedback_negative)
                VALUES ({ph(1)}, {ph(2)}, {ph(3)}, {ph(4)}, {ph(5)},
                        {ph(6)}, {ph(7)}, {ph(8)}, {ph(9)}, {ph(10)}, {ph(11)})""",
            (
                sighting["id"],
                sighting["zone"],
                sighting.get("description"),
                sighting["time"],
                sighting["reporter_id"],
                sighting["reporter_name"],
                sighting["reporter_badge"],
                sighting.get("lat"),
                sighting.get("lng"),
                0,
                0,
            ),
        )

    async def get_sighting(self, sighting_id: str) -> SightingRow | None:
        """Fetch a single sighting by ID."""
        row = await self._fetchone(f"SELECT * FROM sightings WHERE id = {self._ph(1)}", (sighting_id,))
        return cast(SightingRow, row) if row else None

    async def get_sighting_reporter(self, sighting_id: str) -> int | None:
        """Get reporter_id for a sighting (for self-rating prevention)."""
        row = await self._fetchone(f"SELECT reporter_id FROM sightings WHERE id = {self._ph(1)}", (sighting_id,))
        return row["reporter_id"] if row else None

    async def get_total_sightings_count(self) -> int:
        """Count all sightings."""
        row = await self._fetchone("SELECT COUNT(*) AS cnt FROM sightings")
        return row["cnt"] if row else 0

    # --- Recent sightings & duplicate detection ---

    async def get_recent_sightings_for_zones(self, zones: set[str], expiry_minutes: int) -> list[dict]:
        """Get non-expired sightings in given zones, newest first."""
        if not zones:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=expiry_minutes)
        zone_list = list(zones)
        if self.driver == "sqlite":
            placeholders = ", ".join("?" for _ in zone_list)
            sql = (
                f"SELECT * FROM sightings WHERE zone IN ({placeholders}) AND reported_at > ? ORDER BY reported_at DESC"
            )
            params = (*zone_list, cutoff)
        else:
            placeholders = ", ".join(f"${i}" for i in range(1, len(zone_list) + 1))
            n = len(zone_list) + 1
            sql = (
                f"SELECT * FROM sightings WHERE zone IN ({placeholders}) "
                f"AND reported_at > ${n} ORDER BY reported_at DESC"
            )
            params = (*zone_list, cutoff)
        return await self._fetchall(sql, params)

    async def find_recent_zone_sightings(self, zone: str, window_minutes: int) -> list[dict]:
        """Find all sightings in the same zone within the duplicate window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return await self._fetchall(
            f"SELECT * FROM sightings WHERE zone = {self._ph(1)} AND reported_at > {self._ph(2)} "
            f"ORDER BY reported_at DESC",
            (zone, cutoff),
        )

    async def count_reports_since(self, user_id: int, since: datetime) -> int:
        """Count how many reports a user has submitted since a given time."""
        row = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM sightings WHERE reporter_id = {self._ph(1)} AND reported_at > {self._ph(2)}",
            (user_id, since),
        )
        return row["cnt"] if row else 0

    async def get_oldest_report_since(self, user_id: int, since: datetime) -> datetime | None:
        """Get the oldest report timestamp since a given time (for rate-limit wait calculation)."""
        row = await self._fetchone(
            f"SELECT MIN(reported_at) AS oldest FROM sightings WHERE reporter_id = {self._ph(1)} AND reported_at > {self._ph(2)}",
            (user_id, since),
        )
        if row and row["oldest"]:
            return row["oldest"]
        return None

    async def update_feedback_counts(self, sighting_id: str, positive_delta: int, negative_delta: int) -> None:
        """Atomically adjust feedback counts on a sighting."""
        await self._execute(
            f"UPDATE sightings SET feedback_positive = feedback_positive + {self._ph(1)}, "
            f"feedback_negative = feedback_negative + {self._ph(2)} "
            f"WHERE id = {self._ph(3)}",
            (positive_delta, negative_delta, sighting_id),
        )

    # --- Cleanup ---

    async def cleanup_old_sightings(self, retention_days: int) -> int:
        """Delete sightings older than retention_days. Returns count deleted.

        Relies on ON DELETE CASCADE to clean up associated feedback rows.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        if self.driver == "sqlite":
            cursor = await self._conn.execute("DELETE FROM sightings WHERE reported_at < ?", (cutoff,))
            count = cursor.rowcount
            await self._conn.commit()
            return count
        else:
            async with self._pool.acquire() as conn, conn.transaction():
                result = await conn.execute("DELETE FROM sightings WHERE reported_at < $1", cutoff)
                try:
                    return int(result.split()[-1])
                except (ValueError, IndexError):
                    return 0

    async def purge_sightings_older_than(self, days: int, zone: str | None = None) -> int:
        """Purge sightings older than days, optionally scoped to zone. Returns deleted count."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        if self.driver == "sqlite":
            if zone:
                cursor = await self._conn.execute(
                    "DELETE FROM sightings WHERE reported_at < ? AND zone = ?",
                    (cutoff, zone),
                )
            else:
                cursor = await self._conn.execute(
                    "DELETE FROM sightings WHERE reported_at < ?",
                    (cutoff,),
                )
            count = cursor.rowcount
            await self._conn.commit()
            return count
        else:
            async with self._pool.acquire() as conn, conn.transaction():
                if zone:
                    result = await conn.execute(
                        "DELETE FROM sightings WHERE reported_at < $1 AND zone = $2",
                        cutoff,
                        zone,
                    )
                else:
                    result = await conn.execute(
                        "DELETE FROM sightings WHERE reported_at < $1",
                        cutoff,
                    )
                try:
                    return int(result.split()[-1])
                except (ValueError, IndexError):
                    return 0

    # --- Moderation ---

    async def delete_sighting(self, sighting_id: str) -> SightingRow | None:
        """Delete a sighting by ID. Returns the sighting data before deletion, or None."""
        sighting = await self.get_sighting(sighting_id)
        if not sighting:
            return None
        # FK CASCADE handles feedback deletion
        await self._execute(f"DELETE FROM sightings WHERE id = {self._ph(1)}", (sighting_id,))
        return sighting

    async def flag_sighting(self, sighting_id: str) -> None:
        """Mark a sighting as flagged for review."""
        await self._execute(f"UPDATE sightings SET flagged = 1 WHERE id = {self._ph(1)}", (sighting_id,))

    async def get_flagged_sightings(self, limit: int = 20) -> list[dict]:
        """Get sightings flagged for moderation review.

        Returns sightings that are either:
        - Explicitly flagged (flagged = 1)
        - Have negative feedback > positive feedback with 3+ total votes
        """
        return await self._fetchall(
            f"SELECT * FROM sightings WHERE "
            f"flagged = 1 OR "
            f"(feedback_negative > feedback_positive AND (feedback_positive + feedback_negative) >= 3) "
            f"ORDER BY reported_at DESC LIMIT {self._ph(1)}",
            (limit,),
        )

    async def get_low_accuracy_reporters(self, max_accuracy: float = 0.5, min_feedback: int = 5) -> list[dict]:
        """Get reporters whose accuracy is below the threshold.

        Returns users with accuracy < max_accuracy and at least min_feedback total ratings.
        """
        rows = await self._fetchall(
            f"SELECT reporter_id, "
            f"SUM(feedback_positive) AS total_pos, "
            f"SUM(feedback_negative) AS total_neg, "
            f"COUNT(*) AS sighting_count "
            f"FROM sightings "
            f"GROUP BY reporter_id "
            f"HAVING (SUM(feedback_positive) + SUM(feedback_negative)) >= {self._ph(1)}",
            (min_feedback,),
        )
        result = []
        for r in rows:
            total = r["total_pos"] + r["total_neg"]
            if total > 0 and r["total_pos"] / total < max_accuracy:
                result.append(
                    {
                        "reporter_id": r["reporter_id"],
                        "total_positive": r["total_pos"],
                        "total_negative": r["total_neg"],
                        "accuracy": r["total_pos"] / total,
                        "sighting_count": r["sighting_count"],
                    }
                )
        return result
