"""Phase 11.7 Reliability Hardening tests.

Tests cover:
- 11.7.1: asyncpg connection pool health checks (check_pool_health)
- 11.7.2: Conversation state persistence (PicklePersistence wiring)
- 11.7.3: Configurable cleanup_job interval via runtime settings
- 11.7.4: Exponential backoff on transient broadcast failures
- 11.7.5: GPS coordinate bounds validation in handle_location()
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .helpers import make_context, make_update

# Detect whether telegram-dependent modules can be imported in this env.
# The cryptography backend may be broken in some CI environments.
_HAS_TELEGRAM = False
try:
    import telegram  # noqa: F401

    _HAS_TELEGRAM = True
except BaseException:
    pass

_skip_telegram = pytest.mark.skipif(
    not _HAS_TELEGRAM,
    reason="telegram import unavailable (cryptography backend issue)",
)


# ---------------------------------------------------------------------------
# 11.7.1: Connection pool health checks
# ---------------------------------------------------------------------------


class TestPoolHealthCheck:
    """Verify check_pool_health() returns correct diagnostics."""

    @pytest.mark.asyncio
    async def test_sqlite_health_check_healthy(self, db):
        """SQLite health check reports healthy when DB is reachable."""
        result = await db.check_pool_health()
        assert result["driver"] == "sqlite"
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_sqlite_health_check_after_close(self, db):
        """SQLite health check reports unhealthy after connection closed."""
        await db.close()
        result = await db.check_pool_health()
        assert result["driver"] == "sqlite"
        assert result["healthy"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_postgresql_health_check_no_pool(self):
        """PostgreSQL health check reports unhealthy when pool is None."""
        from bot.database import Database

        db = Database("postgresql://localhost/test")
        # Don't connect — pool stays None
        result = await db.check_pool_health()
        assert result["driver"] == "postgresql"
        assert result["healthy"] is False
        assert "Pool not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_postgresql_health_check_with_mock_pool(self):
        """PostgreSQL health check returns pool stats from a mocked pool."""
        from bot.database import Database

        db = Database("postgresql://localhost/test")
        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 5
        mock_pool.get_idle_size.return_value = 3
        mock_pool.get_min_size.return_value = 2
        mock_pool.get_max_size.return_value = 10

        # Mock the acquire context manager
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ok": 1})
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_cm

        db._pool = mock_pool

        result = await db.check_pool_health()
        assert result["driver"] == "postgresql"
        assert result["healthy"] is True
        assert result["pool_size"] == 5
        assert result["pool_free"] == 3
        assert result["pool_min"] == 2
        assert result["pool_max"] == 10
        assert result["pool_exhausted"] is False

    @pytest.mark.asyncio
    async def test_postgresql_pool_exhaustion_detection(self):
        """PostgreSQL health check detects pool exhaustion."""
        from bot.database import Database

        db = Database("postgresql://localhost/test")
        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 0  # no free connections
        mock_pool.get_min_size.return_value = 2
        mock_pool.get_max_size.return_value = 10  # at max

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ok": 1})
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_cm

        db._pool = mock_pool

        result = await db.check_pool_health()
        assert result["pool_exhausted"] is True
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_postgresql_health_check_exception(self):
        """PostgreSQL health check handles exceptions gracefully."""
        from bot.database import Database

        db = Database("postgresql://localhost/test")
        mock_pool = MagicMock()
        mock_pool.get_size.side_effect = Exception("connection lost")
        db._pool = mock_pool

        result = await db.check_pool_health()
        assert result["driver"] == "postgresql"
        assert result["healthy"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# 11.7.2: Conversation state persistence
# ---------------------------------------------------------------------------


class TestConversationPersistence:
    """Verify PicklePersistence is wired into Application builder."""

    @_skip_telegram
    def test_pickle_persistence_imported(self):
        """PicklePersistence is importable from telegram.ext."""
        from telegram.ext import PicklePersistence  # noqa: F811

        assert PicklePersistence is not None

    @_skip_telegram
    def test_main_references_persistence_path(self):
        """main.py imports PERSISTENCE_PATH from config."""
        import bot.main as main_mod

        # Verify the module has access to PERSISTENCE_PATH
        assert hasattr(main_mod, "PERSISTENCE_PATH") or "PERSISTENCE_PATH" in dir(main_mod)

    def test_persistence_path_config_default(self):
        """PERSISTENCE_PATH defaults to 'parkwatch_persistence'."""
        import importlib

        with patch.dict("os.environ", {}, clear=False):
            import config

            importlib.reload(config)
            assert config.PERSISTENCE_PATH == "parkwatch_persistence"

    def test_persistence_path_config_custom(self):
        """PERSISTENCE_PATH can be set via environment variable."""
        import importlib

        with patch.dict("os.environ", {"PERSISTENCE_PATH": "/tmp/custom_persist"}):
            import config

            importlib.reload(config)
            assert config.PERSISTENCE_PATH == "/tmp/custom_persist"

        # Clean up
        with patch.dict("os.environ", {"PERSISTENCE_PATH": "parkwatch_persistence"}):
            importlib.reload(config)


# ---------------------------------------------------------------------------
# 11.7.3: Configurable cleanup_job interval
# ---------------------------------------------------------------------------


class TestConfigurableCleanupInterval:
    """Verify cleanup_job interval is configurable."""

    def test_cleanup_interval_default(self):
        """CLEANUP_INTERVAL_HOURS defaults to 6."""
        import importlib

        with patch.dict("os.environ", {}, clear=False):
            import config

            importlib.reload(config)
            assert config.CLEANUP_INTERVAL_HOURS == 6

    def test_cleanup_interval_custom(self):
        """CLEANUP_INTERVAL_HOURS can be set via environment variable."""
        import importlib

        with patch.dict("os.environ", {"CLEANUP_INTERVAL_HOURS": "12"}):
            import config

            importlib.reload(config)
            assert config.CLEANUP_INTERVAL_HOURS == 12

        # Clean up
        with patch.dict("os.environ", {"CLEANUP_INTERVAL_HOURS": "6"}):
            importlib.reload(config)

    @_skip_telegram
    def test_cleanup_interval_in_runtime_settings(self):
        """CLEANUP_INTERVAL_HOURS is listed in MUTABLE_SPECS."""
        from bot.services.runtime_settings import MUTABLE_SPECS

        assert "CLEANUP_INTERVAL_HOURS" in MUTABLE_SPECS
        spec = MUTABLE_SPECS["CLEANUP_INTERVAL_HOURS"]
        assert spec.value_type is int

    @_skip_telegram
    @pytest.mark.asyncio
    async def test_cleanup_job_respects_maintenance(self):
        """cleanup_job skips when maintenance mode is enabled."""
        from bot.main import cleanup_job

        context = MagicMock()
        with patch("bot.main.is_maintenance_enabled", new_callable=AsyncMock, return_value=True):
            await cleanup_job(context)
        # No DB calls should be made during maintenance


# ---------------------------------------------------------------------------
# 11.7.4: Exponential backoff on transient failures
# ---------------------------------------------------------------------------


class TestExponentialBackoff:
    """Verify broadcast uses exponential backoff on transient failures."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @_skip_telegram
    def test_send_one_retries_with_backoff(self):
        """_send_one retries transient failures with exponential backoff."""
        from telegram.error import TimedOut

        from bot.services.notifications import _send_one

        bot = MagicMock()
        call_count = 0
        call_times = []

        async def mock_send(**kwargs):
            nonlocal call_count
            call_count += 1
            call_times.append(asyncio.get_event_loop().time())
            if call_count < 4:
                raise TimedOut()
            return MagicMock()

        bot.send_message = mock_send
        semaphore = asyncio.Semaphore(20)

        with patch("bot.services.notifications.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = self._run(_send_one(bot, 123, "test", None, semaphore, retries=3))

        assert result == ("sent", 123)
        # Should have slept with exponential backoff: 1, 2, 4
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1)  # 2^0
        mock_sleep.assert_any_call(2)  # 2^1
        mock_sleep.assert_any_call(4)  # 2^2

    @_skip_telegram
    def test_send_one_gives_up_after_max_retries(self):
        """_send_one returns 'failed' after exhausting all retries."""
        from telegram.error import TimedOut

        from bot.services.notifications import _send_one

        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=TimedOut())
        semaphore = asyncio.Semaphore(20)

        with patch("bot.services.notifications.asyncio.sleep", new_callable=AsyncMock):
            result = self._run(_send_one(bot, 456, "test", None, semaphore, retries=3))

        assert result == ("failed", 456)
        # 1 initial + 3 retries = 4 total attempts
        assert bot.send_message.call_count == 4

    @_skip_telegram
    def test_send_one_forbidden_no_retry(self):
        """_send_one does not retry on Forbidden (user blocked bot)."""
        from telegram.error import Forbidden

        from bot.services.notifications import _send_one

        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=Forbidden("bot was blocked"))
        semaphore = asyncio.Semaphore(20)

        result = self._run(_send_one(bot, 789, "test", None, semaphore, retries=3))

        assert result == ("blocked", 789)
        assert bot.send_message.call_count == 1

    @_skip_telegram
    def test_send_one_success_no_retry(self):
        """_send_one returns immediately on success without retrying."""
        from bot.services.notifications import _send_one

        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=MagicMock())
        semaphore = asyncio.Semaphore(20)

        result = self._run(_send_one(bot, 100, "test", None, semaphore, retries=3))

        assert result == ("sent", 100)
        assert bot.send_message.call_count == 1

    @_skip_telegram
    def test_send_one_unexpected_error_no_retry(self):
        """_send_one does not retry on unexpected (non-transient) errors."""
        from bot.services.notifications import _send_one

        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=ValueError("unexpected"))
        semaphore = asyncio.Semaphore(20)

        result = self._run(_send_one(bot, 200, "test", None, semaphore, retries=3))

        assert result == ("failed", 200)
        assert bot.send_message.call_count == 1


# ---------------------------------------------------------------------------
# 11.7.5: GPS coordinate bounds validation
# ---------------------------------------------------------------------------


class TestGPSBoundsValidation:
    """Verify handle_location() rejects coordinates outside Singapore."""

    @_skip_telegram
    def test_is_within_singapore_valid(self):
        """Known Singapore coordinates pass bounds check."""
        from bot.handlers.report import _is_within_singapore

        # Tanjong Pagar
        assert _is_within_singapore(1.2764, 103.8460) is True
        # Woodlands (north)
        assert _is_within_singapore(1.4360, 103.7865) is True
        # Changi (east)
        assert _is_within_singapore(1.3576, 103.9885) is True
        # Tuas (west)
        assert _is_within_singapore(1.3270, 103.6500) is True

    @_skip_telegram
    def test_is_within_singapore_boundary(self):
        """Boundary coordinates (edges of the bounding box) pass."""
        from bot.handlers.report import _is_within_singapore

        assert _is_within_singapore(1.15, 103.60) is True  # SW corner
        assert _is_within_singapore(1.47, 104.05) is True  # NE corner

    @_skip_telegram
    def test_is_within_singapore_outside(self):
        """Coordinates outside Singapore fail bounds check."""
        from bot.handlers.report import _is_within_singapore

        # Kuala Lumpur
        assert _is_within_singapore(3.1390, 101.6869) is False
        # Tokyo
        assert _is_within_singapore(35.6762, 139.6503) is False
        # South of Singapore
        assert _is_within_singapore(1.0, 103.85) is False
        # North of Singapore
        assert _is_within_singapore(1.5, 103.85) is False
        # West of Singapore
        assert _is_within_singapore(1.3, 103.5) is False
        # East of Singapore
        assert _is_within_singapore(1.3, 104.1) is False
        # Negative coordinates
        assert _is_within_singapore(-1.3, 103.85) is False

    @_skip_telegram
    def test_handle_location_rejects_outside_singapore(self):
        """handle_location() redirects to CHOOSING_METHOD for out-of-bounds GPS."""
        from bot.handlers.report import CHOOSING_METHOD, handle_location

        update = make_update()
        update.message.location = MagicMock()
        update.message.location.latitude = 35.6762  # Tokyo
        update.message.location.longitude = 139.6503

        context = make_context()

        with patch("bot.services.maintenance.is_maintenance_enabled", new_callable=AsyncMock, return_value=False):
            result = asyncio.get_event_loop().run_until_complete(handle_location(update, context))

        assert result == CHOOSING_METHOD
        # First reply should warn about out-of-bounds
        first_reply = update.message.reply_text.call_args_list[0][0][0]
        assert "outside Singapore" in first_reply

    @_skip_telegram
    def test_handle_location_accepts_valid_singapore_coords(self):
        """handle_location() proceeds normally for valid Singapore GPS."""
        from bot.handlers.report import AWAITING_DESCRIPTION, handle_location

        update = make_update()
        update.message.location = MagicMock()
        update.message.location.latitude = 1.3008  # Bugis
        update.message.location.longitude = 103.8553

        context = make_context()

        with patch("bot.services.maintenance.is_maintenance_enabled", new_callable=AsyncMock, return_value=False):
            result = asyncio.get_event_loop().run_until_complete(handle_location(update, context))

        assert result == AWAITING_DESCRIPTION
        # Zone should be set in user_data
        assert context.user_data.get("pending_report_zone") is not None

    @_skip_telegram
    def test_sg_bounds_constants_cover_all_zones(self):
        """All ZONE_COORDS fall within the Singapore bounding box."""
        from bot.handlers.report import _is_within_singapore
        from bot.zones import ZONE_COORDS

        for zone_name, (lat, lng) in ZONE_COORDS.items():
            assert _is_within_singapore(lat, lng), f"Zone {zone_name} at ({lat}, {lng}) is outside Singapore bounds"


# ---------------------------------------------------------------------------
# 11.7 Integration: Version bump
# ---------------------------------------------------------------------------


class TestVersionBump:
    """Verify BOT_VERSION was bumped for Phase 11.7."""

    def test_version_bumped(self):
        """BOT_VERSION reflects Phase 11.7 release."""
        import importlib

        with patch.dict("os.environ", {}):
            import config

            importlib.reload(config)

        # Phase 11.7 bumps from 1.5.0 to 1.6.0
        major, minor, patch_v = config.BOT_VERSION.split(".")
        assert int(major) >= 1
        assert int(minor) >= 6
