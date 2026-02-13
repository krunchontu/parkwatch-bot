"""Add admin_actions table for Phase 8 audit logging.

Revision ID: 002
Revises: 001
Create Date: 2026-02-13

Adds the admin_actions table used by all admin commands to record
an audit trail of administrative operations.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_admin_actions_time ON admin_actions (created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_admin_actions_time")
    op.execute("DROP TABLE IF EXISTS admin_actions")
