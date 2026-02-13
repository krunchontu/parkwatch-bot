"""Alembic environment configuration for ParkWatch SG.

Reads DATABASE_URL from config.py (which loads .env) so migrations
use the same connection string as the bot. Supports both SQLite and
PostgreSQL.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from config import DATABASE_URL

# Alembic Config object (provides access to alembic.ini values)
config = context.config

# Set up loggers from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the runtime DATABASE_URL if available
if DATABASE_URL:
    # asyncpg:// is not understood by sync SQLAlchemy; convert to psycopg2
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = create_engine(config.get_main_option("sqlalchemy.url", "sqlite:///parkwatch.db"))

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
