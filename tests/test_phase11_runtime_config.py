"""Phase 11 runtime settings tests."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from bot.services.runtime_settings import RuntimeSettingsError, get_runtime_settings


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
async def test_runtime_setting_cast_validation(db):
    settings = get_runtime_settings()
    with (
        patch("bot.services.runtime_settings.get_db", return_value=db),
        pytest.raises(RuntimeSettingsError),
    ):
        await settings.set_override("MAX_WARNINGS", "abc", actor_id=1)


@pytest.mark.asyncio
async def test_runtime_setting_reset(db):
    settings = get_runtime_settings()
    with patch("bot.services.runtime_settings.get_db", return_value=db):
        await settings.set_override("MAINTENANCE_MODE", "true", actor_id=1)
        assert await settings.get("MAINTENANCE_MODE") is True
        default_val = await settings.reset_override("MAINTENANCE_MODE")
        assert default_val in (True, False)


@pytest.mark.asyncio
async def test_db_override_methods(db):
    now = datetime.now(timezone.utc)
    await db.upsert_config_override("MAX_WARNINGS", "9", updated_by=9, updated_at=now)
    row = await db.get_config_override("MAX_WARNINGS")
    assert row is not None
    assert row["value"] == "9"
    all_rows = await db.get_all_config_overrides()
    assert any(r["key"] == "MAX_WARNINGS" for r in all_rows)
    await db.delete_config_override("MAX_WARNINGS")
    assert await db.get_config_override("MAX_WARNINGS") is None
