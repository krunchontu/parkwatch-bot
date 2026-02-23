"""Admin repository.

Handles audit logging, global statistics, zone lookups, user banning,
GDPR user purge, and stats export.
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import cast

from ..models import AdminActionRow, BannedUserRow
from .base import BaseRepository


class AdminRepository(BaseRepository):
    """Admin audit, statistics, banning, and data management operations."""

    # --- Audit Logging ---

    async def log_admin_action(
        self, admin_id: int, action: str, target: str | None = None, detail: str | None = None
    ) -> None:
        """Record an admin action in the audit log."""
        ph = self._ph
        await self._execute(
            f"INSERT INTO admin_actions (admin_id, action, target, detail, created_at) "
            f"VALUES ({ph(1)}, {ph(2)}, {ph(3)}, {ph(4)}, {ph(5)})",
            (admin_id, action, target, detail, datetime.now(timezone.utc)),
        )

    async def get_admin_log(self, limit: int = 20) -> list[AdminActionRow]:
        """Get the most recent admin actions."""
        rows = await self._fetchall(
            f"SELECT * FROM admin_actions ORDER BY created_at DESC LIMIT {self._ph(1)}",
            (limit,),
        )
        return cast(list[AdminActionRow], rows)

    # --- Global Statistics ---

    async def get_global_stats(self) -> dict:
        """Get global statistics for the admin dashboard."""
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        twenty_four_hours_ago = now - timedelta(hours=24)

        total_users = await self._fetchone("SELECT COUNT(*) AS cnt FROM users")
        total_sightings = await self._fetchone("SELECT COUNT(*) AS cnt FROM sightings")
        sightings_24h = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM sightings WHERE reported_at > {self._ph(1)}",
            (twenty_four_hours_ago,),
        )
        active_subs = await self._fetchone("SELECT COUNT(*) AS cnt FROM subscriptions")
        unique_subscribers = await self._fetchone("SELECT COUNT(DISTINCT telegram_id) AS cnt FROM subscriptions")
        feedback_totals = await self._fetchone(
            "SELECT COALESCE(SUM(feedback_positive), 0) AS pos, "
            "COALESCE(SUM(feedback_negative), 0) AS neg FROM sightings"
        )

        # Active users: reported or gave feedback in last 7 days
        active_reporters = await self._fetchone(
            f"SELECT COUNT(DISTINCT reporter_id) AS cnt FROM sightings WHERE reported_at > {self._ph(1)}",
            (seven_days_ago,),
        )
        active_feedback_givers = await self._fetchone(
            f"SELECT COUNT(DISTINCT user_id) AS cnt FROM feedback WHERE created_at > {self._ph(1)}",
            (seven_days_ago,),
        )

        return {
            "total_users": total_users["cnt"] if total_users else 0,
            "active_reporters_7d": active_reporters["cnt"] if active_reporters else 0,
            "active_feedback_givers_7d": active_feedback_givers["cnt"] if active_feedback_givers else 0,
            "total_sightings": total_sightings["cnt"] if total_sightings else 0,
            "sightings_24h": sightings_24h["cnt"] if sightings_24h else 0,
            "active_subscriptions": active_subs["cnt"] if active_subs else 0,
            "unique_subscribers": unique_subscribers["cnt"] if unique_subscribers else 0,
            "feedback_positive": feedback_totals["pos"] if feedback_totals else 0,
            "feedback_negative": feedback_totals["neg"] if feedback_totals else 0,
        }

    async def get_top_zones_by_subscribers(self, limit: int = 5) -> list[dict]:
        """Get zones with the most subscribers."""
        return await self._fetchall(
            f"SELECT zone_name, COUNT(*) AS sub_count FROM subscriptions "
            f"GROUP BY zone_name ORDER BY sub_count DESC LIMIT {self._ph(1)}",
            (limit,),
        )

    async def get_top_zones_by_sightings(self, limit: int = 5, days: int = 7) -> list[dict]:
        """Get zones with the most sightings in the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await self._fetchall(
            f"SELECT zone, COUNT(*) AS sighting_count FROM sightings "
            f"WHERE reported_at > {self._ph(1)} "
            f"GROUP BY zone ORDER BY sighting_count DESC LIMIT {self._ph(2)}",
            (cutoff, limit),
        )

    # --- Zone Lookup ---

    async def get_zone_details(self, zone_name: str) -> dict:
        """Get detailed zone information for admin lookup."""
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(hours=24)
        seven_days_ago = now - timedelta(days=7)

        sub_count = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM subscriptions WHERE zone_name = {self._ph(1)}",
            (zone_name,),
        )
        sightings_24h = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM sightings WHERE zone = {self._ph(1)} AND reported_at > {self._ph(2)}",
            (zone_name, twenty_four_hours_ago),
        )
        sightings_7d = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM sightings WHERE zone = {self._ph(1)} AND reported_at > {self._ph(2)}",
            (zone_name, seven_days_ago),
        )
        sightings_all = await self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM sightings WHERE zone = {self._ph(1)}",
            (zone_name,),
        )

        return {
            "zone_name": zone_name,
            "subscriber_count": sub_count["cnt"] if sub_count else 0,
            "sightings_24h": sightings_24h["cnt"] if sightings_24h else 0,
            "sightings_7d": sightings_7d["cnt"] if sightings_7d else 0,
            "sightings_all": sightings_all["cnt"] if sightings_all else 0,
        }

    async def get_zone_top_reporters(self, zone_name: str, limit: int = 5) -> list[dict]:
        """Get top reporters in a specific zone."""
        return await self._fetchall(
            f"SELECT reporter_id, reporter_name, COUNT(*) AS report_count "
            f"FROM sightings WHERE zone = {self._ph(1)} "
            f"GROUP BY reporter_id, reporter_name ORDER BY report_count DESC LIMIT {self._ph(2)}",
            (zone_name, limit),
        )

    async def get_zone_recent_sightings(self, zone_name: str, limit: int = 5) -> list[dict]:
        """Get most recent sightings in a specific zone."""
        return await self._fetchall(
            f"SELECT id, description, reported_at, reporter_name, reporter_badge, "
            f"feedback_positive, feedback_negative "
            f"FROM sightings WHERE zone = {self._ph(1)} ORDER BY reported_at DESC LIMIT {self._ph(2)}",
            (zone_name, limit),
        )

    # --- User Banning ---

    async def ban_user(self, user_id: int, banned_by: int, reason: str | None = None) -> None:
        """Ban a user: insert into banned_users and clear their subscriptions."""
        now = datetime.now(timezone.utc)
        if self.driver == "sqlite":
            await self._execute(
                "INSERT OR REPLACE INTO banned_users (telegram_id, banned_by, reason, banned_at) VALUES (?, ?, ?, ?)",
                (user_id, banned_by, reason, now),
            )
        else:
            await self._execute(
                "INSERT INTO banned_users (telegram_id, banned_by, reason, banned_at) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (telegram_id) DO UPDATE SET banned_by = EXCLUDED.banned_by, "
                "reason = EXCLUDED.reason, banned_at = EXCLUDED.banned_at",
                (user_id, banned_by, reason, now),
            )
        # Clear subscriptions inline (avoids cross-repository dependency)
        await self._execute(f"DELETE FROM subscriptions WHERE telegram_id = {self._ph(1)}", (user_id,))

    async def unban_user(self, user_id: int) -> bool:
        """Remove a ban. Returns True if the user was actually banned."""
        row = await self._fetchone(
            f"SELECT telegram_id FROM banned_users WHERE telegram_id = {self._ph(1)}", (user_id,)
        )
        if not row:
            return False
        await self._execute(f"DELETE FROM banned_users WHERE telegram_id = {self._ph(1)}", (user_id,))
        return True

    async def is_banned(self, user_id: int) -> bool:
        """Check if a user is currently banned."""
        row = await self._fetchone(
            f"SELECT telegram_id FROM banned_users WHERE telegram_id = {self._ph(1)}", (user_id,)
        )
        return row is not None

    async def get_banned_users(self) -> list[BannedUserRow]:
        """Get all currently banned users, newest bans first."""
        rows = await self._fetchall(
            "SELECT telegram_id, banned_by, reason, banned_at FROM banned_users ORDER BY banned_at DESC"
        )
        return cast(list[BannedUserRow], rows)

    # --- Data Management ---

    async def purge_user_data(self, user_id: int) -> dict:
        """Purge all user-related data and repair affected feedback counters transactionally."""
        if self.driver == "sqlite":
            conn = self._conn
            await conn.execute("BEGIN")
            try:
                cursor = await conn.execute("SELECT sighting_id, vote FROM feedback WHERE user_id = ?", (user_id,))
                given_feedback = await cursor.fetchall()

                for row in given_feedback:
                    sighting_id = row["sighting_id"]
                    vote = row["vote"]
                    if vote == "positive":
                        await conn.execute(
                            "UPDATE sightings SET feedback_positive = MAX(0, feedback_positive - 1) WHERE id = ?",
                            (sighting_id,),
                        )
                    else:
                        await conn.execute(
                            "UPDATE sightings SET feedback_negative = MAX(0, feedback_negative - 1) WHERE id = ?",
                            (sighting_id,),
                        )

                await conn.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
                await conn.execute(
                    "DELETE FROM feedback WHERE sighting_id IN (SELECT id FROM sightings WHERE reporter_id = ?)",
                    (user_id,),
                )
                await conn.execute("DELETE FROM sightings WHERE reporter_id = ?", (user_id,))
                await conn.execute("DELETE FROM subscriptions WHERE telegram_id = ?", (user_id,))
                await conn.execute("DELETE FROM banned_users WHERE telegram_id = ?", (user_id,))
                await conn.execute("DELETE FROM user_rate_limits WHERE user_id = ?", (user_id,))
                await conn.execute("DELETE FROM users WHERE telegram_id = ?", (user_id,))
                await conn.execute(
                    "UPDATE admin_actions SET target = NULL, detail = NULL WHERE target = ?", (str(user_id),)
                )
                await conn.commit()
                return {"feedback_given_deleted": len(given_feedback)}
            except Exception:
                await conn.rollback()
                raise

        async with self._pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch("SELECT sighting_id, vote FROM feedback WHERE user_id = $1", user_id)
            given_feedback = [dict(r) for r in rows]

            for row in given_feedback:
                if row["vote"] == "positive":
                    await conn.execute(
                        "UPDATE sightings SET feedback_positive = GREATEST(0, feedback_positive - 1) WHERE id = $1",
                        row["sighting_id"],
                    )
                else:
                    await conn.execute(
                        "UPDATE sightings SET feedback_negative = GREATEST(0, feedback_negative - 1) WHERE id = $1",
                        row["sighting_id"],
                    )

            await conn.execute("DELETE FROM feedback WHERE user_id = $1", user_id)
            await conn.execute(
                "DELETE FROM feedback WHERE sighting_id IN (SELECT id FROM sightings WHERE reporter_id = $1)", user_id
            )
            await conn.execute("DELETE FROM sightings WHERE reporter_id = $1", user_id)
            await conn.execute("DELETE FROM subscriptions WHERE telegram_id = $1", user_id)
            await conn.execute("DELETE FROM banned_users WHERE telegram_id = $1", user_id)
            await conn.execute("DELETE FROM user_rate_limits WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM users WHERE telegram_id = $1", user_id)
            await conn.execute("UPDATE admin_actions SET target = NULL, detail = NULL WHERE target = $1", str(user_id))
            return {"feedback_given_deleted": len(given_feedback)}

    async def export_stats(self, format_type: str = "csv") -> str:
        """Export global stats in CSV (default) or JSON."""
        stats = await self.get_global_stats()
        top_sub = await self.get_top_zones_by_subscribers(10)
        top_sight = await self.get_top_zones_by_sightings(10, days=7)

        payload = {
            "global_stats": stats,
            "top_subscribed_zones": top_sub,
            "top_reported_zones_7d": top_sight,
        }

        if format_type == "json":
            import json

            return json.dumps(payload, default=str, indent=2)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "key", "value"])
        for key, value in stats.items():
            writer.writerow(["global_stats", key, value])
        for item in top_sub:
            writer.writerow(["top_subscribed_zones", item["zone_name"], item["sub_count"]])
        for item in top_sight:
            writer.writerow(["top_reported_zones_7d", item["zone"], item["sighting_count"]])
        return output.getvalue()
