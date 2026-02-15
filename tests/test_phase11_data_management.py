"""Phase 11 data management tests."""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_purge_sightings_older_than(db):
    now = datetime.now(timezone.utc)
    await db.add_sighting("s1", "Bugis", None, now - timedelta(days=40), 1, "u", "New", None, None)
    await db.add_sighting("s2", "Bugis", None, now - timedelta(days=5), 1, "u", "New", None, None)

    deleted = await db.purge_sightings_older_than(days=30)
    assert deleted == 1
    assert await db.get_sighting("s1") is None
    assert await db.get_sighting("s2") is not None


@pytest.mark.asyncio
async def test_purge_user_data_recalculates_feedback_counters(db):
    now = datetime.now(timezone.utc)
    await db.add_user(1, "reporter")
    await db.add_user(2, "voter")
    await db.add_sighting("s1", "Bugis", None, now, 1, "reporter", "New", None, None)
    await db.apply_feedback("s1", 2, "positive")

    sighting = await db.get_sighting("s1")
    assert sighting["feedback_positive"] == 1

    result = await db.purge_user_data(2)
    assert result["feedback_given_deleted"] == 1

    sighting_after = await db.get_sighting("s1")
    assert sighting_after["feedback_positive"] == 0


@pytest.mark.asyncio
async def test_export_stats_csv_json(db):
    csv_data = await db.export_stats("csv")
    json_data = await db.export_stats("json")

    assert "section,key,value" in csv_data
    assert "global_stats" in json_data
