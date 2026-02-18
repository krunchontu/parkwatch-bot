"""Convert all TIMESTAMP columns to TIMESTAMPTZ (timezone-aware).

Revision ID: 005
Revises: 004
Create Date: 2026-02-18

Fixes a DataError raised by asyncpg when timezone-aware datetimes
(datetime.now(timezone.utc)) are passed to TIMESTAMP WITHOUT TIME ZONE
columns. Converting to TIMESTAMPTZ aligns the schema with the Python code
that consistently uses UTC-aware datetimes.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All existing timestamps are stored as UTC; preserve that via the USING clause.
_UPGRADE_STMTS = [
    "ALTER TABLE sightings ALTER COLUMN reported_at TYPE TIMESTAMPTZ USING reported_at AT TIME ZONE 'UTC'",
    "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE feedback ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE admin_actions ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE banned_users ALTER COLUMN banned_at TYPE TIMESTAMPTZ USING banned_at AT TIME ZONE 'UTC'",
    "ALTER TABLE config_overrides ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC'",
]

_DOWNGRADE_STMTS = [
    "ALTER TABLE sightings ALTER COLUMN reported_at TYPE TIMESTAMP USING reported_at AT TIME ZONE 'UTC'",
    "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE feedback ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE admin_actions ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'",
    "ALTER TABLE banned_users ALTER COLUMN banned_at TYPE TIMESTAMP USING banned_at AT TIME ZONE 'UTC'",
    "ALTER TABLE config_overrides ALTER COLUMN updated_at TYPE TIMESTAMP USING updated_at AT TIME ZONE 'UTC'",
]


def upgrade() -> None:
    for stmt in _UPGRADE_STMTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DOWNGRADE_STMTS:
        op.execute(stmt)
