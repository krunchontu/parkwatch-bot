"""Structured logging configuration for ParkWatch SG.

Supports two modes controlled by the LOG_FORMAT environment variable:
- "text" (default): Human-readable format for local development
- "json": Structured JSON format for log aggregation services (Datadog, ELK, CloudWatch, etc.)
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Output example:
    {"timestamp":"2026-02-13T14:30:00.123456+00:00","level":"INFO","logger":"bot.main","message":"Bot starting..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id  # type: ignore[attr-defined]
        if hasattr(record, "zone"):
            log_entry["zone"] = record.zone  # type: ignore[attr-defined]

        return json.dumps(log_entry, default=str)


def setup_logging(log_format: str = "text", level: int = logging.INFO) -> None:
    """Configure the root logger based on the desired format.

    Args:
        log_format: "text" for human-readable, "json" for structured JSON.
        level: Logging level (default: INFO).
    """
    root_logger = logging.getLogger()

    # Remove any existing handlers to avoid duplicate output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
