"""Database abstraction for ParkWatch SG.

Supports SQLite (dev) via aiosqlite and PostgreSQL (prod) via asyncpg.
Selected automatically based on DATABASE_URL scheme.

Phase 11.8: Business logic is now split into focused repository modules
under bot/repositories/. The Database class composes all repositories and
delegates method calls for full backward compatibility — all existing
`get_db().method()` call sites continue to work unchanged.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from .repositories import (
    AdminRepository,
    ConfigRepository,
    FeedbackRepository,
    SightingRepository,
    UserRepository,
)

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
    """Dual-driver database abstraction (SQLite / PostgreSQL).

    Composes five repository modules for organized data access while
    maintaining full backward compatibility via ``__getattr__`` delegation.

    Repositories:
        - ``users``: User CRUD, subscriptions, warnings
        - ``sightings``: Sighting CRUD, queries, cleanup, moderation
        - ``feedback``: Feedback votes, accuracy, rate limiting
        - ``admin``: Audit log, statistics, banning, data management
        - ``config``: Runtime configuration overrides
    """

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url
        self.driver: str = "sqlite"
        self._conn = None  # aiosqlite connection
        self._pool = None  # asyncpg pool

        if database_url and database_url.startswith(("postgresql://", "postgres://")):
            self.driver = "postgresql"

        # Initialize repository instances
        self.users = UserRepository(self)
        self.sightings = SightingRepository(self)
        self.feedback = FeedbackRepository(self)
        self.admin = AdminRepository(self)
        self.config = ConfigRepository(self)

    def __getattr__(self, name: str):
        """Delegate attribute lookups to repositories for backward compatibility.

        This allows existing code using ``db.method_name()`` to continue
        working without modification. New code can use ``db.users.method()``
        for explicit repository access.
        """
        # Search repositories for the requested attribute.
        # Use __dict__ to avoid infinite recursion during __init__.
        for attr in ("users", "sightings", "feedback", "admin", "config"):
            repo = self.__dict__.get(attr)
            if repo is not None and hasattr(repo, name):
                return getattr(repo, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

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

            async def _pool_init(conn):
                # Phase 11.7.1: Configure connection-level health settings
                await conn.execute("SET statement_timeout = '30s'")
                await conn.execute("SET idle_in_transaction_session_timeout = '60s'")

            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                init=_pool_init,
            )

    async def close(self):
        """Close the database connection."""
        if self.driver == "sqlite" and self._conn:
            await self._conn.close()
        elif self.driver == "postgresql" and self._pool:
            await self._pool.close()

    async def check_pool_health(self) -> dict:
        """Check connection pool health (Phase 11.7.1).

        Returns a dict with pool size, free connections, and a connectivity check.
        For SQLite, returns a simple connectivity check.
        """
        if self.driver == "sqlite":
            try:
                row = await self._fetchone("SELECT 1 AS ok")
                return {"driver": "sqlite", "healthy": row is not None and row["ok"] == 1}
            except Exception as e:
                logger.error("SQLite health check failed: %s", e)
                return {"driver": "sqlite", "healthy": False, "error": str(e)}

        if self._pool is None:
            return {"driver": "postgresql", "healthy": False, "error": "Pool not initialized"}

        try:
            pool_size = self._pool.get_size()
            pool_free = self._pool.get_idle_size()
            pool_min = self._pool.get_min_size()
            pool_max = self._pool.get_max_size()

            # Connectivity check
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 AS ok")
                connected = row is not None and row["ok"] == 1

            exhausted = pool_free == 0 and pool_size >= pool_max
            if exhausted:
                logger.warning(
                    "Connection pool exhausted: size=%d, free=%d, max=%d",
                    pool_size,
                    pool_free,
                    pool_max,
                )

            return {
                "driver": "postgresql",
                "healthy": connected and not exhausted,
                "pool_size": pool_size,
                "pool_free": pool_free,
                "pool_min": pool_min,
                "pool_max": pool_max,
                "pool_exhausted": exhausted,
            }
        except Exception as e:
            logger.error("PostgreSQL health check failed: %s", e)
            return {"driver": "postgresql", "healthy": False, "error": str(e)}

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
                first_name TEXT,
                report_count INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
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
                feedback_negative INTEGER DEFAULT 0,
                flagged INTEGER DEFAULT 0
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
            # Phase 8: Admin audit log
            """CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_admin_actions_time ON admin_actions (created_at)",
            # Phase 9: Banned users
            """CREATE TABLE IF NOT EXISTS banned_users (
                telegram_id BIGINT PRIMARY KEY,
                banned_by BIGINT NOT NULL,
                reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS config_overrides (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_by BIGINT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_config_overrides_updated_at ON config_overrides (updated_at)",
            # Phase 11.5: Decoupled rate limiting (independent of admin_actions)
            """CREATE TABLE IF NOT EXISTS user_rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_user_rate_limits_lookup ON user_rate_limits (user_id, action, created_at)",
        ]
        if self.driver == "postgresql":
            # PostgreSQL uses SERIAL instead of AUTOINCREMENT
            statements = [s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY") for s in statements]
            # PostgreSQL requires TIMESTAMPTZ to accept timezone-aware datetimes.
            # Protect CURRENT_TIMESTAMP from being mangled by the replacement.
            statements = [
                s.replace("CURRENT_TIMESTAMP", "CURRENT_TS_HOLD")
                .replace("TIMESTAMP", "TIMESTAMPTZ")
                .replace("CURRENT_TS_HOLD", "CURRENT_TIMESTAMP")
                for s in statements
            ]
        for stmt in statements:
            await self._execute(stmt)
