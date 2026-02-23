"""PostgreSQL-specific test suite for ParkWatch SG (Phase 11.8.2).

Tests PostgreSQL code paths that differ from SQLite: placeholder syntax,
DDL transformations, driver detection, and PostgreSQL-specific SQL patterns.

Since we cannot run a real PostgreSQL instance in CI, these tests use
mocking to verify PostgreSQL-specific code paths and SQL generation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.database import Database


class AsyncContextManagerMock:
    """Helper to create a mock that supports `async with` protocol."""

    def __init__(self, return_value):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, *args):
        return False


def make_pg_mock_pool(mock_conn):
    """Build a mock asyncpg pool with proper nested async context managers.

    Supports ``async with pool.acquire() as conn, conn.transaction():``.
    """
    mock_conn.transaction = MagicMock(return_value=AsyncContextManagerMock(None))
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
    return mock_pool


# ---------------------------------------------------------------------------
# Driver detection
# ---------------------------------------------------------------------------
class TestPostgresDriverDetection:
    """Verify driver selection based on DATABASE_URL."""

    def test_postgresql_scheme_detected(self):
        db = Database("postgresql://user:pass@localhost/dbname")
        assert db.driver == "postgresql"

    def test_postgres_scheme_detected(self):
        db = Database("postgres://user:pass@localhost/dbname")
        assert db.driver == "postgresql"

    def test_sqlite_scheme_fallback(self):
        db = Database("sqlite:///test.db")
        assert db.driver == "sqlite"

    def test_no_url_defaults_to_sqlite(self):
        db = Database()
        assert db.driver == "sqlite"

    def test_none_url_defaults_to_sqlite(self):
        db = Database(None)
        assert db.driver == "sqlite"


# ---------------------------------------------------------------------------
# Placeholder syntax
# ---------------------------------------------------------------------------
class TestPostgresPlaceholders:
    """Verify PostgreSQL placeholder generation ($1, $2, ...)."""

    def test_postgresql_placeholder_syntax(self):
        db = Database("postgresql://localhost/test")
        assert db._ph(1) == "$1"
        assert db._ph(2) == "$2"
        assert db._ph(10) == "$10"

    def test_sqlite_placeholder_syntax(self):
        db = Database()
        assert db._ph(1) == "?"
        assert db._ph(2) == "?"
        assert db._ph(10) == "?"


# ---------------------------------------------------------------------------
# DDL transformations for PostgreSQL
# ---------------------------------------------------------------------------
class TestPostgresDDLTransformations:
    """Verify DDL statement transformations applied for PostgreSQL."""

    @pytest.mark.asyncio
    async def test_autoincrement_to_serial(self):
        """PostgreSQL replaces INTEGER PRIMARY KEY AUTOINCREMENT with SERIAL PRIMARY KEY."""
        db = Database("postgresql://localhost/test")
        # Capture SQL executed during create_tables
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.create_tables()

        # Check that no statement contains AUTOINCREMENT
        for stmt in executed_sql:
            assert "AUTOINCREMENT" not in stmt, f"AUTOINCREMENT found in PostgreSQL DDL: {stmt}"

        # Check that SERIAL PRIMARY KEY is present in table creation statements
        serial_stmts = [s for s in executed_sql if "SERIAL PRIMARY KEY" in s]
        assert len(serial_stmts) >= 2, "Expected SERIAL PRIMARY KEY in admin_actions and user_rate_limits"

    @pytest.mark.asyncio
    async def test_timestamp_to_timestamptz(self):
        """PostgreSQL replaces TIMESTAMP with TIMESTAMPTZ (except in CURRENT_TIMESTAMP)."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.create_tables()

        table_stmts = [s for s in executed_sql if "CREATE TABLE" in s]
        for stmt in table_stmts:
            # Column types should use TIMESTAMPTZ, not bare TIMESTAMP
            # CURRENT_TIMESTAMP in DEFAULT clauses should remain unchanged
            lines = stmt.split("\n")
            for line in lines:
                stripped = line.strip()
                if "TIMESTAMPTZ" in stripped:
                    # Correct — PostgreSQL column type
                    continue
                if "TIMESTAMP" in stripped and "CURRENT_TIMESTAMP" not in stripped:
                    pytest.fail(f"Bare TIMESTAMP found in PostgreSQL DDL line: {stripped}")

    @pytest.mark.asyncio
    async def test_current_timestamp_preserved(self):
        """CURRENT_TIMESTAMP defaults are not mangled by the TIMESTAMPTZ replacement."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.create_tables()

        # Find statements that have DEFAULT CURRENT_TIMESTAMP
        stmts_with_default_ts = [s for s in executed_sql if "DEFAULT CURRENT_TIMESTAMP" in s]
        # At least users, subscriptions, feedback, admin_actions, banned_users,
        # config_overrides, user_rate_limits tables have DEFAULT CURRENT_TIMESTAMP
        assert len(stmts_with_default_ts) >= 5, "Expected DEFAULT CURRENT_TIMESTAMP in multiple tables"

        # Ensure no intermediate placeholder leaked
        for stmt in executed_sql:
            assert "CURRENT_TS_HOLD" not in stmt, "Intermediate placeholder should not appear in final SQL"


# ---------------------------------------------------------------------------
# PostgreSQL upsert syntax
# ---------------------------------------------------------------------------
class TestPostgresUpsertSyntax:
    """Verify PostgreSQL ON CONFLICT syntax in repository methods."""

    @pytest.mark.asyncio
    async def test_ensure_user_uses_excluded(self):
        """PostgreSQL upsert uses EXCLUDED (uppercase)."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.ensure_user(123, "testuser", "Test")

        assert len(executed_sql) == 1
        assert "EXCLUDED.username" in executed_sql[0]
        assert "$1" in executed_sql[0]
        assert "$2" in executed_sql[0]
        assert "$3" in executed_sql[0]

    @pytest.mark.asyncio
    async def test_add_subscription_pg_conflict(self):
        """PostgreSQL subscription upsert uses ON CONFLICT DO NOTHING."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.add_subscription(123, "Bugis")

        assert len(executed_sql) == 1
        assert "ON CONFLICT DO NOTHING" in executed_sql[0]
        assert "$1" in executed_sql[0]

    @pytest.mark.asyncio
    async def test_set_feedback_pg_conflict(self):
        """PostgreSQL feedback upsert uses EXCLUDED (uppercase)."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.set_feedback("s1", 123, "positive")

        assert len(executed_sql) == 1
        assert "EXCLUDED.vote" in executed_sql[0]

    @pytest.mark.asyncio
    async def test_ban_user_pg_conflict(self):
        """PostgreSQL ban_user uses ON CONFLICT ... DO UPDATE with EXCLUDED."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.ban_user(123, 456, "spam")

        # ban_user executes two statements: INSERT + DELETE subscriptions
        assert len(executed_sql) == 2
        assert "EXCLUDED.banned_by" in executed_sql[0]

    @pytest.mark.asyncio
    async def test_upsert_config_override_pg(self):
        """PostgreSQL config override upsert uses EXCLUDED."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_execute(sql, params=()):
            executed_sql.append(sql)

        db._execute = capture_execute  # type: ignore[assignment]
        await db.upsert_config_override("KEY", "val", 1, datetime.now(timezone.utc))

        assert len(executed_sql) == 1
        assert "EXCLUDED.value" in executed_sql[0]


# ---------------------------------------------------------------------------
# PostgreSQL increment with RETURNING
# ---------------------------------------------------------------------------
class TestPostgresReturning:
    """Verify PostgreSQL uses RETURNING clause for atomic increment-and-read."""

    @pytest.mark.asyncio
    async def test_increment_report_count_returning(self):
        """PostgreSQL uses a single UPDATE ... RETURNING instead of UPDATE + SELECT."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_fetchone(sql, params=()):
            executed_sql.append(sql)
            return {"report_count": 5}

        db._fetchone = capture_fetchone  # type: ignore[assignment]
        result = await db.increment_report_count(123)

        assert result == 5
        assert len(executed_sql) == 1
        assert "RETURNING report_count" in executed_sql[0]

    @pytest.mark.asyncio
    async def test_increment_warnings_returning(self):
        """PostgreSQL uses RETURNING for warnings increment."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_fetchone(sql, params=()):
            executed_sql.append(sql)
            return {"warnings": 2}

        db._fetchone = capture_fetchone  # type: ignore[assignment]
        result = await db.increment_warnings(123)

        assert result == 2
        assert len(executed_sql) == 1
        assert "RETURNING warnings" in executed_sql[0]


# ---------------------------------------------------------------------------
# PostgreSQL GREATEST vs SQLite MAX
# ---------------------------------------------------------------------------
class TestPostgresGreatest:
    """Verify PostgreSQL uses GREATEST() instead of MAX() for floor clamping."""

    @pytest.mark.asyncio
    async def test_purge_user_data_uses_greatest(self):
        """PostgreSQL purge_user_data uses GREATEST(0, ...) instead of MAX(0, ...)."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        feedback_row = {"sighting_id": "s1", "vote": "positive"}
        mock_conn.fetch = AsyncMock(return_value=[feedback_row])
        mock_conn.execute = AsyncMock()

        db._pool = make_pg_mock_pool(mock_conn)

        await db.purge_user_data(123)

        # Check that GREATEST was used in the UPDATE call
        update_calls = [
            str(call) for call in mock_conn.execute.call_args_list if "GREATEST" in str(call) or "MAX" in str(call)
        ]
        for call in update_calls:
            assert "GREATEST" in call, f"PostgreSQL should use GREATEST, not MAX: {call}"


# ---------------------------------------------------------------------------
# PostgreSQL IN-clause placeholder generation
# ---------------------------------------------------------------------------
class TestPostgresInClause:
    """Verify PostgreSQL generates $1, $2, ... for IN clauses."""

    @pytest.mark.asyncio
    async def test_recent_sightings_in_clause(self):
        """PostgreSQL generates $1, $2, ... $N for zone IN clause."""
        db = Database("postgresql://localhost/test")
        executed_sql = []

        async def capture_fetchall(sql, params=()):
            executed_sql.append(sql)
            return []

        db._fetchall = capture_fetchall  # type: ignore[assignment]
        await db.get_recent_sightings_for_zones({"Bugis", "Orchard", "Tanjong Pagar"}, 30)

        assert len(executed_sql) == 1
        sql = executed_sql[0]
        # Should have $1, $2, $3 for three zones and $4 for cutoff
        assert "$1" in sql
        assert "$2" in sql
        assert "$3" in sql
        assert "$4" in sql
        assert "?" not in sql


# ---------------------------------------------------------------------------
# PostgreSQL cleanup return value parsing
# ---------------------------------------------------------------------------
class TestPostgresDeleteParsing:
    """Verify PostgreSQL DELETE result parsing (e.g., 'DELETE 5')."""

    @pytest.mark.asyncio
    async def test_cleanup_parses_delete_result(self):
        """cleanup_old_sightings parses PostgreSQL 'DELETE N' status string."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 7")
        db._pool = make_pg_mock_pool(mock_conn)

        count = await db.cleanup_old_sightings(30)
        assert count == 7

    @pytest.mark.asyncio
    async def test_purge_sightings_parses_delete_result(self):
        """purge_sightings_older_than parses PostgreSQL 'DELETE N' status string."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 3")
        db._pool = make_pg_mock_pool(mock_conn)

        count = await db.purge_sightings_older_than(30)
        assert count == 3

    @pytest.mark.asyncio
    async def test_cleanup_handles_malformed_result(self):
        """cleanup_old_sightings returns 0 for unparseable PostgreSQL results."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UNEXPECTED")
        db._pool = make_pg_mock_pool(mock_conn)

        count = await db.cleanup_old_sightings(30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_rate_limit_cleanup_parses_delete_result(self):
        """cleanup_old_rate_limits parses PostgreSQL 'DELETE N' status string."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 12")
        db._pool = make_pg_mock_pool(mock_conn)

        count = await db.cleanup_old_rate_limits(24)
        assert count == 12


# ---------------------------------------------------------------------------
# PostgreSQL pool health check
# ---------------------------------------------------------------------------
class TestPostgresPoolHealth:
    """Verify pool health check for PostgreSQL driver."""

    @pytest.mark.asyncio
    async def test_pool_not_initialized(self):
        """Health check returns unhealthy when pool is None."""
        db = Database("postgresql://localhost/test")
        db._pool = None
        result = await db.check_pool_health()
        assert result["driver"] == "postgresql"
        assert result["healthy"] is False
        assert "Pool not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_pool_health_metrics(self):
        """Health check returns pool size metrics."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ok": 1})

        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 5
        mock_pool.get_idle_size.return_value = 3
        mock_pool.get_min_size.return_value = 2
        mock_pool.get_max_size.return_value = 10
        mock_pool.acquire.return_value = AsyncContextManagerMock(mock_conn)

        db._pool = mock_pool

        result = await db.check_pool_health()
        assert result["driver"] == "postgresql"
        assert result["healthy"] is True
        assert result["pool_size"] == 5
        assert result["pool_free"] == 3
        assert result["pool_min"] == 2
        assert result["pool_max"] == 10
        assert result["pool_exhausted"] is False

    @pytest.mark.asyncio
    async def test_pool_exhausted(self):
        """Health check detects pool exhaustion."""
        db = Database("postgresql://localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ok": 1})

        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 0
        mock_pool.get_min_size.return_value = 2
        mock_pool.get_max_size.return_value = 10
        mock_pool.acquire.return_value = AsyncContextManagerMock(mock_conn)

        db._pool = mock_pool

        result = await db.check_pool_health()
        assert result["pool_exhausted"] is True
        assert result["healthy"] is False
