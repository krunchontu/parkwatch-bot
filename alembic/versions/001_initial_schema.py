"""Initial schema — matches create_tables() from bot/database.py.

Revision ID: 001
Revises: None
Create Date: 2026-02-13

This baseline migration captures the existing 4-table schema so that future
schema changes can be tracked as incremental migrations. Existing databases
that already have these tables will simply skip the IF NOT EXISTS statements.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            report_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    op.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            telegram_id BIGINT NOT NULL,
            zone_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (telegram_id, zone_name)
        )"""
    )

    op.execute(
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
        )"""
    )

    op.execute(
        """CREATE TABLE IF NOT EXISTS feedback (
            sighting_id TEXT NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            vote TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (sighting_id, user_id)
        )"""
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_sightings_zone_time ON sightings (zone, reported_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sightings_reporter ON sightings (reporter_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_zone ON subscriptions (zone_name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_feedback_sighting ON feedback (sighting_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_feedback_sighting")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_zone")
    op.execute("DROP INDEX IF EXISTS idx_sightings_reporter")
    op.execute("DROP INDEX IF EXISTS idx_sightings_zone_time")
    op.execute("DROP TABLE IF EXISTS feedback")
    op.execute("DROP TABLE IF EXISTS sightings")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS users")
