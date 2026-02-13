"""Shared fixtures for ParkWatch SG tests."""

import os

import pytest_asyncio

# Ensure tests never use a real bot token or production DB
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-not-real")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_PRIVATE_URL", None)

from bot.database import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    """Provide a fresh SQLite database for each test."""
    db_path = str(tmp_path / "test_parkwatch.db")
    database = Database(f"sqlite:///{db_path}")
    await database.connect()
    await database.create_tables()
    yield database
    await database.close()
