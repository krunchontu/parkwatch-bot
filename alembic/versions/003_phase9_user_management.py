"""Add Phase 9 tables and columns for user management and content moderation.

Revision ID: 003
Revises: 002
Create Date: 2026-02-14

Adds:
- banned_users table for user banning
- sightings.flagged column for moderation queue
- users.warnings column for warning tracking
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New table: banned_users
    op.execute(
        """CREATE TABLE IF NOT EXISTS banned_users (
            telegram_id BIGINT PRIMARY KEY,
            banned_by BIGINT NOT NULL,
            reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # New column: sightings.flagged (boolean as integer, default 0)
    op.execute("ALTER TABLE sightings ADD COLUMN flagged INTEGER DEFAULT 0")

    # New column: users.warnings (integer, default 0)
    op.execute("ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS banned_users")
    # SQLite does not support DROP COLUMN; for PostgreSQL:
    op.execute("ALTER TABLE sightings DROP COLUMN IF EXISTS flagged")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS warnings")
