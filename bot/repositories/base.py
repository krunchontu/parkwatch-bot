"""Base repository with shared database access helpers.

All repository classes inherit from BaseRepository to get transparent
access to the dual-driver query helpers (_execute, _fetchone, _fetchall)
and connection objects (_conn, _pool) for transaction-level control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database


class BaseRepository:
    """Base class providing database access to all repository modules."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def driver(self) -> str:
        return self._db.driver

    @property
    def _conn(self):
        """Direct access to the aiosqlite connection (SQLite only)."""
        return self._db._conn

    @property
    def _pool(self):
        """Direct access to the asyncpg pool (PostgreSQL only)."""
        return self._db._pool

    def _ph(self, n: int) -> str:
        """Return the nth placeholder: '?' for SQLite, '$n' for PostgreSQL."""
        return self._db._ph(n)

    async def _execute(self, sql: str, params: tuple = ()) -> None:
        return await self._db._execute(sql, params)

    async def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        return await self._db._fetchone(sql, params)

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return await self._db._fetchall(sql, params)
