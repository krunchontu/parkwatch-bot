"""Phase 11 data management tests."""

import json
from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_purge_sightings_older_than(db):
    now = datetime.now(timezone.utc)
    await db.ensure_user(1, "u")
    await db.add_sighting(
        {
            "id": "s1",
            "zone": "Bugis",
            "description": None,
            "time": now - timedelta(days=40),
            "reporter_id": 1,
            "reporter_name": "u",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )
    await db.add_sighting(
        {
            "id": "s2",
            "zone": "Bugis",
            "description": None,
            "time": now - timedelta(days=5),
            "reporter_id": 1,
            "reporter_name": "u",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )

    deleted = await db.purge_sightings_older_than(days=30)
    assert deleted == 1
    assert await db.get_sighting("s1") is None
    assert await db.get_sighting("s2") is not None


@pytest.mark.asyncio
async def test_purge_sightings_zone_scoped(db):
    """Zone-scoped purge only deletes sightings in the specified zone."""
    now = datetime.now(timezone.utc)
    await db.ensure_user(1, "u")
    # Old sighting in Bugis
    await db.add_sighting(
        {
            "id": "s1",
            "zone": "Bugis",
            "description": None,
            "time": now - timedelta(days=40),
            "reporter_id": 1,
            "reporter_name": "u",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )
    # Old sighting in Orchard
    await db.add_sighting(
        {
            "id": "s2",
            "zone": "Orchard",
            "description": None,
            "time": now - timedelta(days=40),
            "reporter_id": 1,
            "reporter_name": "u",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )

    deleted = await db.purge_sightings_older_than(days=30, zone="Bugis")
    assert deleted == 1
    # Bugis sighting gone, Orchard sighting remains
    assert await db.get_sighting("s1") is None
    assert await db.get_sighting("s2") is not None


@pytest.mark.asyncio
async def test_purge_sightings_returns_zero_when_none_match(db):
    """Purge returns 0 when no sightings match criteria."""
    deleted = await db.purge_sightings_older_than(days=30)
    assert deleted == 0


@pytest.mark.asyncio
async def test_purge_user_data_recalculates_feedback_counters(db):
    now = datetime.now(timezone.utc)
    await db.ensure_user(1, "reporter")
    await db.ensure_user(2, "voter")
    await db.add_sighting(
        {
            "id": "s1",
            "zone": "Bugis",
            "description": None,
            "time": now,
            "reporter_id": 1,
            "reporter_name": "reporter",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )
    await db.apply_feedback("s1", 2, "positive")

    sighting = await db.get_sighting("s1")
    assert sighting["feedback_positive"] == 1

    result = await db.purge_user_data(2)
    assert result["feedback_given_deleted"] == 1

    sighting_after = await db.get_sighting("s1")
    assert sighting_after["feedback_positive"] == 0


@pytest.mark.asyncio
async def test_purge_user_data_removes_all_tables(db):
    """GDPR-complete purge removes user data from all related tables."""
    now = datetime.now(timezone.utc)
    await db.ensure_user(100, "target_user")
    await db.add_subscription(100, "Bugis")
    await db.add_sighting(
        {
            "id": "purge_s1",
            "zone": "Bugis",
            "description": "test",
            "time": now,
            "reporter_id": 100,
            "reporter_name": "target_user",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )
    await db.ban_user(100, banned_by=999, reason="test")
    await db.log_admin_action(999, "test_action", target=str(100))

    await db.purge_user_data(100)

    # User row gone
    assert await db.get_user_details(100) is None
    # Subscriptions gone
    subs = await db.get_subscriptions(100)
    assert len(subs) == 0
    # Sightings gone
    assert await db.get_sighting("purge_s1") is None
    # Ban gone
    assert await db.is_banned(100) is False
    # Admin action target nulled
    log = await db.get_admin_log(100)
    for entry in log:
        if entry["action"] == "test_action":
            assert entry["target"] is None


@pytest.mark.asyncio
async def test_purge_user_data_scrubs_admin_action_detail(db):
    """GDPR purge must NULL both target AND detail in admin_actions."""
    now = datetime.now(timezone.utc)
    await db.ensure_user(100, "john_doe")
    await db.log_admin_action(999, "ban_user", target=str(100), detail="Banned user: @john_doe for spamming")
    await db.log_admin_action(999, "warn_user", target=str(100), detail="Warning #1: stop spamming")

    await db.purge_user_data(100)

    log = await db.get_admin_log(100)
    for entry in log:
        if entry["action"] in ("ban_user", "warn_user"):
            assert entry["target"] is None, "target should be NULLed"
            assert entry["detail"] is None, "detail should be NULLed to scrub PII"


@pytest.mark.asyncio
async def test_purge_user_does_not_delete_config_overrides(db):
    """purge_user_data should NOT delete config overrides set by the user (shared state)."""
    now = datetime.now(timezone.utc)
    await db.ensure_user(100, "admin_user")
    await db.upsert_config_override("MAX_WARNINGS", "5", updated_by=100, updated_at=now)

    await db.purge_user_data(100)

    # Config override should still exist since it's shared state
    row = await db.get_config_override("MAX_WARNINGS")
    assert row is not None
    assert row["value"] == "5"


@pytest.mark.asyncio
async def test_purge_user_recalculates_negative_feedback(db):
    """Purging a user who gave negative feedback correctly decrements negative count."""
    now = datetime.now(timezone.utc)
    await db.ensure_user(1, "reporter")
    await db.ensure_user(2, "neg_voter")
    await db.add_sighting(
        {
            "id": "s1",
            "zone": "Bugis",
            "description": None,
            "time": now,
            "reporter_id": 1,
            "reporter_name": "reporter",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )
    await db.apply_feedback("s1", 2, "negative")

    sighting = await db.get_sighting("s1")
    assert sighting["feedback_negative"] == 1

    await db.purge_user_data(2)

    sighting_after = await db.get_sighting("s1")
    assert sighting_after["feedback_negative"] == 0


@pytest.mark.asyncio
async def test_export_stats_csv_json(db):
    # Populate data so sections are non-empty
    now = datetime.now(timezone.utc)
    await db.ensure_user(1, "u")
    await db.add_subscription(1, "Bugis")
    await db.add_sighting(
        {
            "id": "exp1",
            "zone": "Bugis",
            "description": None,
            "time": now,
            "reporter_id": 1,
            "reporter_name": "u",
            "reporter_badge": "New",
            "lat": None,
            "lng": None,
        }
    )

    csv_data = await db.export_stats("csv")
    json_data = await db.export_stats("json")

    assert "section,key,value" in csv_data
    assert "global_stats" in csv_data
    assert "top_subscribed_zones" in csv_data
    assert "top_reported_zones_7d" in csv_data

    parsed = json.loads(json_data)
    assert "global_stats" in parsed
    assert "top_subscribed_zones" in parsed
    assert "top_reported_zones_7d" in parsed
    # Verify no PII fields in global stats
    stats = parsed["global_stats"]
    assert "telegram_id" not in str(stats).lower()
    assert "username" not in str(stats).lower()


@pytest.mark.asyncio
async def test_export_stats_csv_contains_all_stat_keys(db):
    """CSV export includes all global stat keys."""
    csv_data = await db.export_stats("csv")
    expected_keys = [
        "total_users",
        "active_reporters_7d",
        "active_feedback_givers_7d",
        "total_sightings",
        "sightings_24h",
        "active_subscriptions",
        "unique_subscribers",
        "feedback_positive",
        "feedback_negative",
    ]
    for key in expected_keys:
        assert key in csv_data
