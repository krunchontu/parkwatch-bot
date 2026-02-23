"""User and subscription repository.

Handles user CRUD, subscription management, and warning operations.
"""

from typing import cast

from ..models import UserRow, UserStatsRow
from .base import BaseRepository


class UserRepository(BaseRepository):
    """User, subscription, and warning operations."""

    # --- Subscriptions ---

    async def get_subscriptions(self, user_id: int) -> set[str]:
        """Get all zone names a user is subscribed to."""
        rows = await self._fetchall(
            f"SELECT zone_name FROM subscriptions WHERE telegram_id = {self._ph(1)}", (user_id,)
        )
        return {r["zone_name"] for r in rows}

    async def add_subscription(self, user_id: int, zone: str) -> None:
        """Subscribe a user to a zone (idempotent)."""
        if self.driver == "sqlite":
            await self._execute(
                "INSERT OR IGNORE INTO subscriptions (telegram_id, zone_name) VALUES (?, ?)", (user_id, zone)
            )
        else:
            await self._execute(
                "INSERT INTO subscriptions (telegram_id, zone_name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                (user_id, zone),
            )

    async def remove_subscription(self, user_id: int, zone: str) -> None:
        """Unsubscribe a user from a single zone."""
        await self._execute(
            f"DELETE FROM subscriptions WHERE telegram_id = {self._ph(1)} AND zone_name = {self._ph(2)}",
            (user_id, zone),
        )

    async def clear_subscriptions(self, user_id: int) -> None:
        """Remove all subscriptions for a user."""
        await self._execute(f"DELETE FROM subscriptions WHERE telegram_id = {self._ph(1)}", (user_id,))

    async def get_zone_subscribers(self, zone: str) -> list[int]:
        """Get all telegram_ids subscribed to a zone (for broadcast)."""
        rows = await self._fetchall(f"SELECT telegram_id FROM subscriptions WHERE zone_name = {self._ph(1)}", (zone,))
        return [r["telegram_id"] for r in rows]

    async def get_subscriber_count(self) -> int:
        """Count distinct subscribed users."""
        row = await self._fetchone("SELECT COUNT(DISTINCT telegram_id) AS cnt FROM subscriptions")
        return row["cnt"] if row else 0

    async def get_user_subscriptions_list(self, user_id: int) -> list[str]:
        """Get user's subscribed zones as a sorted list."""
        rows = await self._fetchall(
            f"SELECT zone_name FROM subscriptions WHERE telegram_id = {self._ph(1)} ORDER BY zone_name",
            (user_id,),
        )
        return [r["zone_name"] for r in rows]

    # --- Users ---

    async def ensure_user(self, user_id: int, username: str, first_name: str | None = None) -> None:
        """Create user if not exists, update username/first_name if changed."""
        if self.driver == "sqlite":
            await self._execute(
                "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?) "
                "ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username, "
                "first_name = excluded.first_name",
                (user_id, username, first_name),
            )
        else:
            await self._execute(
                "INSERT INTO users (telegram_id, username, first_name) VALUES ($1, $2, $3) "
                "ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username, "
                "first_name = EXCLUDED.first_name",
                (user_id, username, first_name),
            )

    async def get_user_stats(self, user_id: int) -> UserStatsRow | None:
        """Get user row (telegram_id, username, report_count)."""
        row = await self._fetchone(
            f"SELECT telegram_id, username, report_count FROM users WHERE telegram_id = {self._ph(1)}", (user_id,)
        )
        return cast(UserStatsRow, row) if row else None

    async def increment_report_count(self, user_id: int) -> int:
        """Increment report_count and return new value."""
        if self.driver == "sqlite":
            await self._execute("UPDATE users SET report_count = report_count + 1 WHERE telegram_id = ?", (user_id,))
            row = await self._fetchone("SELECT report_count FROM users WHERE telegram_id = ?", (user_id,))
        else:
            row = await self._fetchone(
                "UPDATE users SET report_count = report_count + 1 WHERE telegram_id = $1 RETURNING report_count",
                (user_id,),
            )
        return row["report_count"] if row else 0

    async def get_user_details(self, user_id: int) -> UserRow | None:
        """Get detailed user information for admin lookup."""
        row = await self._fetchone(
            f"SELECT telegram_id, username, first_name, report_count, created_at FROM users WHERE telegram_id = {self._ph(1)}",
            (user_id,),
        )
        return cast(UserRow, row) if row else None

    async def get_user_by_username(self, username: str) -> dict | None:
        """Look up a user by their Telegram username."""
        username = username.lstrip("@")
        return await self._fetchone(
            f"SELECT telegram_id, username, report_count, created_at FROM users WHERE username = {self._ph(1)}",
            (username,),
        )

    async def get_all_user_ids(self) -> list[int]:
        """Get all registered user IDs (for broadcast)."""
        rows = await self._fetchall("SELECT telegram_id FROM users")
        return [r["telegram_id"] for r in rows]

    async def get_user_recent_sightings(self, user_id: int, limit: int = 10) -> list[dict]:
        """Get recent sightings by a specific user."""
        return await self._fetchall(
            f"SELECT id, zone, description, reported_at, lat, lng, feedback_positive, feedback_negative "
            f"FROM sightings WHERE reporter_id = {self._ph(1)} ORDER BY reported_at DESC LIMIT {self._ph(2)}",
            (user_id, limit),
        )

    # --- Warnings ---

    async def get_user_warnings(self, user_id: int) -> int:
        """Get the warning count for a user."""
        row = await self._fetchone(f"SELECT warnings FROM users WHERE telegram_id = {self._ph(1)}", (user_id,))
        return row["warnings"] if row else 0

    async def increment_warnings(self, user_id: int) -> int:
        """Increment warning count for a user. Returns the new count."""
        if self.driver == "sqlite":
            await self._execute("UPDATE users SET warnings = warnings + 1 WHERE telegram_id = ?", (user_id,))
            row = await self._fetchone("SELECT warnings FROM users WHERE telegram_id = ?", (user_id,))
        else:
            row = await self._fetchone(
                "UPDATE users SET warnings = warnings + 1 WHERE telegram_id = $1 RETURNING warnings",
                (user_id,),
            )
        return row["warnings"] if row else 0

    async def reset_warnings(self, user_id: int) -> None:
        """Reset warning count to zero for a user."""
        await self._execute(f"UPDATE users SET warnings = 0 WHERE telegram_id = {self._ph(1)}", (user_id,))
