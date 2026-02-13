"""Tests for Phase 7: Production Infrastructure.

Tests for health check server, structured logging, and config additions.
"""

import asyncio
import json
import logging
from datetime import datetime
from unittest.mock import patch

import pytest

from bot.health import start_health_server, stop_health_server
from bot.logging_config import JSONFormatter, setup_logging
from config import BOT_VERSION


# ---------------------------------------------------------------------------
# Health Check Server
# ---------------------------------------------------------------------------
class TestHealthCheckServer:
    """Tests for the lightweight asyncio health check HTTP server."""

    @pytest.fixture(autouse=True)
    async def _cleanup_server(self):
        """Ensure the health check server is stopped after each test."""
        yield
        await stop_health_server()

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self):
        """GET /health should return 200 with JSON body."""
        await start_health_server(port=18080, run_mode="polling")
        reader, writer = await asyncio.open_connection("127.0.0.1", 18080)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        writer.close()
        response_str = response.decode()
        assert "200 OK" in response_str
        # Parse the JSON body (after the empty line separating headers from body)
        body = response_str.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["status"] == "ok"
        assert data["version"] == BOT_VERSION
        assert data["mode"] == "polling"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_webhook_mode(self):
        """Health check should report webhook mode when configured."""
        await start_health_server(port=18081, run_mode="webhook")
        reader, writer = await asyncio.open_connection("127.0.0.1", 18081)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        writer.close()
        body = response.decode().split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["mode"] == "webhook"

    @pytest.mark.asyncio
    async def test_unknown_path_returns_404(self):
        """Non-/health paths should return 404."""
        await start_health_server(port=18082, run_mode="polling")
        reader, writer = await asyncio.open_connection("127.0.0.1", 18082)
        writer.write(b"GET /unknown HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        writer.close()
        assert "404 Not Found" in response.decode()

    @pytest.mark.asyncio
    async def test_stop_server_idempotent(self):
        """Stopping a non-running server should not raise."""
        await stop_health_server()  # should be a no-op

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        """Server should start and stop cleanly."""
        await start_health_server(port=18083, run_mode="polling")
        # Verify it's listening
        reader, writer = await asyncio.open_connection("127.0.0.1", 18083)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        writer.close()
        assert "200 OK" in response.decode()
        # Stop
        await stop_health_server()
        # Verify it's no longer listening
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", 18083)


# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
class TestJSONFormatter:
    """Tests for the JSON log formatter."""

    def test_basic_json_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_json_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_json_format_with_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User action",
            args=(),
            exc_info=None,
        )
        record.user_id = 12345  # type: ignore[attr-defined]
        record.zone = "Bugis"  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["user_id"] == 12345
        assert data["zone"] == "Bugis"

    def test_json_timestamp_is_utc(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts.tzinfo is not None  # should be timezone-aware

    def test_json_output_is_single_line(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="multi\nline\nmessage",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        # json.dumps produces single-line output by default (newlines escaped)
        assert "\n" not in output


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_setup_text_format(self):
        setup_logging(log_format="text")
        root = logging.getLogger()
        assert len(root.handlers) > 0
        handler = root.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)

    def test_setup_json_format(self):
        setup_logging(log_format="json")
        root = logging.getLogger()
        assert len(root.handlers) > 0
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_suppresses_noisy_loggers(self):
        setup_logging(log_format="text")
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING

    def test_setup_removes_duplicate_handlers(self):
        """Calling setup_logging twice should not duplicate handlers."""
        setup_logging(log_format="text")
        count1 = len(logging.getLogger().handlers)
        setup_logging(log_format="text")
        count2 = len(logging.getLogger().handlers)
        assert count1 == count2


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class TestPhase7Config:
    """Tests for Phase 7 configuration variables."""

    def test_bot_version_format(self):
        assert isinstance(BOT_VERSION, str)
        parts = BOT_VERSION.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_default_log_format(self):
        from config import LOG_FORMAT

        assert LOG_FORMAT in ("text", "json")

    def test_default_health_check_enabled(self):
        from config import HEALTH_CHECK_ENABLED

        assert isinstance(HEALTH_CHECK_ENABLED, bool)

    def test_default_port_is_int(self):
        from config import PORT

        assert isinstance(PORT, int)
        assert PORT > 0

    def test_sentry_dsn_default_none(self):
        from config import SENTRY_DSN

        # In test environment, SENTRY_DSN should not be set
        assert SENTRY_DSN is None

    def test_webhook_url_default_none(self):
        from config import WEBHOOK_URL

        # In test environment, WEBHOOK_URL should not be set
        assert WEBHOOK_URL is None


# ---------------------------------------------------------------------------
# Sentry initialization
# ---------------------------------------------------------------------------
class TestSentryInit:
    """Tests for Sentry error tracking initialization."""

    def test_sentry_init_skipped_when_no_dsn(self):
        """_init_sentry should be a no-op when SENTRY_DSN is not set."""
        from bot.main import _init_sentry

        # Should not raise
        with patch("bot.main.SENTRY_DSN", None):
            _init_sentry()

    def test_sentry_init_warns_when_sdk_missing(self):
        """_init_sentry should warn (not crash) if sentry-sdk is not installed."""
        from bot.main import _init_sentry

        with (
            patch("bot.main.SENTRY_DSN", "https://fake@sentry.io/0"),
            patch.dict("sys.modules", {"sentry_sdk": None}),
            patch("bot.main.logger") as mock_logger,
        ):
            _init_sentry()
            mock_logger.warning.assert_called_once()
