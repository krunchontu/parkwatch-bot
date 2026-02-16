"""Add Phase 11 runtime config overrides table.

Revision ID: 004
Revises: 003
Create Date: 2026-02-16
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE IF NOT EXISTS config_overrides (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_by BIGINT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_config_overrides_updated_at ON config_overrides (updated_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_config_overrides_updated_at")
    op.execute("DROP TABLE IF EXISTS config_overrides")
