"""Database abstraction for ParkWatch SG.

Supports SQLite (dev) via aiosqlite and PostgreSQL (prod) via asyncpg.
Selected automatically based on DATABASE_URL scheme.
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db: Optional["Database"] = None


def get_db() -> "Database":
    """Return the global Database singleton."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def init_db(database_url: str | None = None) -> "Database":
    """Initialize the database connection and create tables."""
    global _db
    db = Database(database_url)
    await db.connect()
    await db.create_tables()
    _db = db
    logger.info("Database initialized (%s driver)", db.driver)
    return db


async def close_db():
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database connection closed")


class Database:
    """Dual-driver database abstraction (SQLite / PostgreSQL)."""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url
        self.driver: str = "sqlite"
        self._conn = None  # aiosqlite connection
        self._pool = None  # asyncpg pool

        if database_url and database_url.startswith(("postgresql://", "postgres://")):
            self.driver = "postgresql"

    def _ph(self, n: int) -> str:
        """Return the nth placeholder: '?' for SQLite, '$n' for PostgreSQL."""
        return "?" if self.driver == "sqlite" else f"${n}"

    # --- Connection management ---

    async def connect(self):
        """Open the database connection."""
        if self.driver == "sqlite":
            import aiosqlite

            db_path = "parkwatch.db"
            if self.database_url:
                if self.database_url.startswith("sqlite:///"):
                    db_path = self.database_url[len("sqlite:///") :]
                elif not self.database_url.startswith(("postgresql://", "postgres://")):
                    db_path = self.database_url
            sqlite3.register_adapter(datetime, lambda d: d.isoformat())
            sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode()))
            self._conn = await aiosqlite.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._conn.commit()
        else:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)

    async def close(self):
        """Close the database connection."""
        if self.driver == "sqlite" and self._conn:
            await self._conn.close()
        elif self.driver == "postgresql" and self._pool:
            await self._pool.close()

    # --- Internal query helpers ---

    async def _execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a write query (INSERT/UPDATE/DELETE)."""
        if self.driver == "sqlite":
            await self._conn.execute(sql, params)
            await self._conn.commit()
        else:
            async with self._pool.acquire() as conn:
                await conn.execute(sql, *params)

    async def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute a query and return a single row as dict, or None."""
        if self.driver == "sqlite":
            cursor = await self._conn.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row else None
        else:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(sql, *params)
                return dict(row) if row else None

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a query and return all rows as list of dicts."""
        if self.driver == "sqlite":
            cursor = await self._conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(r) for r in rows]

    # --- Table creation ---

    async def create_tables(self):
        """Create all tables and indexes if they don't exist."""
        statements = [
            """CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                username TEXT,
                report_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS subscriptions (
                telegram_id BIGINT NOT NULL,
                zone_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (telegram_id, zone_name)
            )""",
            """CREATE TABLE IF NOT EXISTS sightings (
                id TEXT PRIMARY KEY,
                zone TEXT NOT NULL,
                description TEXT,
                reported_at TIMESTAMP NOT NULL,
                reporter_id BIGINT NOT NULL,
                reporter_name TEXT,
                reporter_badge TEXT,
                lat REAL,
                lng REAL,
                feedback_positive INTEGER DEFAULT 0,
                feedback_negative INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS feedback (
                sighting_id TEXT NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                vote TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (sighting_id, user_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_sightings_zone_time ON sightings (zone, reported_at)",
            "CREATE INDEX IF NOT EXISTS idx_sightings_reporter ON sightings (reporter_id)",
            "CREATE INDEX IF NOT EXISTS idx_subscriptions_zone ON subscriptions (zone_name)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_sighting ON feedback (sighting_id)",
        ]
        for stmt in statements:
            await self._execute(stmt)

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

    # --- Users ---

    async def ensure_user(self, user_id: int, username: str) -> None:
        """Create user if not exists, update username if changed."""
        if self.driver == "sqlite":
            await self._execute(
                "INSERT INTO users (telegram_id, username) VALUES (?, ?) "
                "ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username",
                (user_id, username),
            )
        else:
            await self._execute(
                "INSERT INTO users (telegram_id, username) VALUES ($1, $2) "
                "ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username",
                (user_id, username),
            )

    async def get_user_stats(self, user_id: int) -> dict | None:
        """Get user row (telegram_id, username, report_count)."""
        return await self._fetchone(
            f"SELECT telegram_id, username, report_count FROM users WHERE telegram_id = {self._ph(1)}", (user_id,)
        )

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

    # --- Sightings ---

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

    async def get_sighting(self, sighting_id: str) -> dict | None:
        """Fetch a single sighting by ID."""
        return await self._fetchone(f"SELECT * FROM sightings WHERE id = {self._ph(1)}", (sighting_id,))

    async def get_sighting_reporter(self, sighting_id: str) -> int | None:
        """Get reporter_id for a sighting (for self-rating prevention)."""
        row = await self._fetchone(f"SELECT reporter_id FROM sightings WHERE id = {self._ph(1)}", (sighting_id,))
        return row["reporter_id"] if row else None

    async def get_total_sightings_count(self) -> int:
        """Count all sightings."""
        row = await self._fetchone("SELECT COUNT(*) AS cnt FROM sightings")
        return row["cnt"] if row else 0

    async def cleanup_old_sightings(self, retention_days: int) -> int:
        """Delete sightings older than retention_days. Returns count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        if self.driver == "sqlite":
            # Delete related feedback first
            await self._conn.execute(
                "DELETE FROM feedback WHERE sighting_id IN (SELECT id FROM sightings WHERE reported_at < ?)", (cutoff,)
            )
            cursor = await self._conn.execute("DELETE FROM sightings WHERE reported_at < ?", (cutoff,))
            count = cursor.rowcount
            await self._conn.commit()
            return count
        else:
            async with self._pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "DELETE FROM feedback WHERE sighting_id IN (SELECT id FROM sightings WHERE reported_at < $1)",
                    cutoff,
                )
                result = await conn.execute("DELETE FROM sightings WHERE reported_at < $1", cutoff)
                # asyncpg returns status string like "DELETE 42"
                try:
                    return int(result.split()[-1])
                except (ValueError, IndexError):
                    return 0

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
            # SQLite: use the single connection; manual transaction via commit at end
            try:
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
