"""Phase 11 runtime settings tests."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from bot.services.runtime_settings import (
    MUTABLE_SPECS,
    RuntimeSettingsError,
    get_runtime_settings,
)


@pytest.mark.asyncio
async def test_runtime_setting_set_and_get(db):
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        old_value, new_value = await settings.set_override("MAX_REPORTS_PER_HOUR", "7", actor_id=123)
        assert isinstance(old_value, int)
        assert new_value == 7
        effective = await settings.get("MAX_REPORTS_PER_HOUR")
        assert effective == 7


@pytest.mark.asyncio
async def test_runtime_setting_rejects_disallowed_key(db):
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("TELEGRAM_BOT_TOKEN", "abc", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_rejects_database_url(db):
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("DATABASE_URL", "postgres://x", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_rejects_admin_user_ids(db):
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("ADMIN_USER_IDS", "999", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_cast_validation(db):
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("MAX_WARNINGS", "abc", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_cast_float_validation(db):
    """Float keys reject non-numeric values."""
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("DUPLICATE_RADIUS_METERS", "not_a_number", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_cast_bool_validation(db):
    """Bool keys reject non-boolean values."""
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("MAINTENANCE_MODE", "maybe", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_bool_truthy_values(db):
    """Bool keys accept various truthy/falsy formats."""
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        for truthy in ("true", "1", "yes", "on"):
            await settings.set_override("MAINTENANCE_MODE", truthy, actor_id=1)
            assert await settings.get("MAINTENANCE_MODE") is True
        for falsy in ("false", "0", "no", "off"):
            await settings.set_override("MAINTENANCE_MODE", falsy, actor_id=1)
            assert await settings.get("MAINTENANCE_MODE") is False


@pytest.mark.asyncio
async def test_runtime_setting_str_rejects_empty(db):
    """String keys reject empty values."""
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("MAINTENANCE_MESSAGE", "   ", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_reset(db):
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        await settings.set_override("MAINTENANCE_MODE", "true", actor_id=1)
        assert await settings.get("MAINTENANCE_MODE") is True
        default_val = await settings.reset_override("MAINTENANCE_MODE", actor_id=1)
        assert default_val in (True, False)
        # After reset, get() should return default
        effective = await settings.get("MAINTENANCE_MODE")
        assert effective == default_val


@pytest.mark.asyncio
async def test_runtime_setting_reset_rejects_unknown_key(db):
    """reset_override rejects keys not in the allowlist."""
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.reset_override("UNKNOWN_KEY", actor_id=1)


@pytest.mark.asyncio
async def test_list_effective_shows_source(db):
    """list_effective() returns source='default' or 'override' correctly."""
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        items = await settings.list_effective()
        assert len(items) == len(MUTABLE_SPECS)
        # Before any override, all should be 'default'
        for item in items:
            assert item["source"] == "default"
            assert "key" in item
            assert "value" in item
            assert "type" in item

        # Set one override and verify
        await settings.set_override("MAX_WARNINGS", "5", actor_id=1)
        items = await settings.list_effective()
        warnings_item = next(i for i in items if i["key"] == "MAX_WARNINGS")
        assert warnings_item["source"] == "override"
        assert warnings_item["value"] == 5


@pytest.mark.asyncio
async def test_set_override_returns_old_new(db):
    """set_override returns (old_value, new_value) tuple."""
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        old, new = await settings.set_override("SIGHTING_RETENTION_DAYS", "60", actor_id=1)
        assert isinstance(old, int)
        assert new == 60
        # Set again: old should now be 60
        old2, new2 = await settings.set_override("SIGHTING_RETENTION_DAYS", "90", actor_id=1)
        assert old2 == 60
        assert new2 == 90


@pytest.mark.asyncio
async def test_allowlist_contains_exactly_ten_keys():
    """The mutable registry contains exactly the 10 specified keys."""
    expected = {
        "MAX_REPORTS_PER_HOUR",
        "DUPLICATE_WINDOW_MINUTES",
        "DUPLICATE_RADIUS_METERS",
        "SIGHTING_EXPIRY_MINUTES",
        "SIGHTING_RETENTION_DAYS",
        "FEEDBACK_WINDOW_HOURS",
        "MAX_WARNINGS",
        "MAINTENANCE_MODE",
        "MAINTENANCE_MESSAGE",
        "CLEANUP_INTERVAL_HOURS",
    }
    assert set(MUTABLE_SPECS.keys()) == expected


@pytest.mark.asyncio
async def test_get_returns_default_when_db_fails():
    """get() returns default when DB is unavailable (fail-safe path)."""
    settings = get_runtime_settings()
    # Without patching get_db, the real get_db() raises RuntimeError since DB isn't init'd.
    # The fail-safe path in get() catches this and returns the default.
    value = await settings.get("MAX_REPORTS_PER_HOUR")
    assert isinstance(value, int)


@pytest.mark.asyncio
async def test_db_override_methods(db):
    now = datetime.now(timezone.utc)
    await db.upsert_config_override("MAX_WARNINGS", "9", updated_by=9, updated_at=now)
    row = await db.get_config_override("MAX_WARNINGS")
    assert row is not None
    assert row["value"] == "9"
    assert row["updated_by"] == 9
    all_rows = await db.get_all_config_overrides()
    assert any(r["key"] == "MAX_WARNINGS" for r in all_rows)
    await db.delete_config_override("MAX_WARNINGS")
    assert await db.get_config_override("MAX_WARNINGS") is None


@pytest.mark.asyncio
async def test_db_upsert_overwrites_existing(db):
    """upsert_config_override updates an existing key rather than inserting a duplicate."""
    now = datetime.now(timezone.utc)
    await db.upsert_config_override("MAX_WARNINGS", "3", updated_by=1, updated_at=now)
    await db.upsert_config_override("MAX_WARNINGS", "5", updated_by=2, updated_at=now)
    row = await db.get_config_override("MAX_WARNINGS")
    assert row["value"] == "5"
    assert row["updated_by"] == 2
    # Should be exactly one row for this key
    all_rows = await db.get_all_config_overrides()
    matching = [r for r in all_rows if r["key"] == "MAX_WARNINGS"]
    assert len(matching) == 1
