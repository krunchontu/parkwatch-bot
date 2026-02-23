"""Add first_name column to users table.

Revision ID: 007
Revises: 006
Create Date: 2026-02-23

Aligns the users table schema with the TypedDict model (UserRow.first_name)
and create_tables() fallback.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS first_name")
