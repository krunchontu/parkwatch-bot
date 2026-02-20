"""Add user_rate_limits table for decoupled rate limiting.

Revision ID: 006
Revises: 005
Create Date: 2026-02-20

Decouples feedback rate limiting from the admin_actions audit log
so that purging audit logs cannot silently break rate limits.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_rate_limits",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_user_rate_limits_lookup", "user_rate_limits", ["user_id", "action", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_user_rate_limits_lookup")
    op.drop_table("user_rate_limits")
