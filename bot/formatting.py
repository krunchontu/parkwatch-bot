"""Shared formatting helpers for ParkWatch SG."""

from datetime import datetime, timezone

from .utils import SGT

DIVIDER = "\u2501" * 21


def format_sgt(dt: datetime, fmt: str = "%Y-%m-%d %I:%M %p SGT") -> str:
    """Convert a datetime to an SGT-formatted string.

    Handles both naive (assumed UTC) and aware datetimes.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SGT).strftime(fmt)


def format_sgt_short(dt: datetime) -> str:
    """Short SGT format: ``MM/DD HH:MM AM/PM``."""
    return format_sgt(dt, "%m/%d %I:%M %p")


def format_sgt_time(dt: datetime) -> str:
    """Time-only SGT format: ``HH:MM AM/PM SGT``."""
    return format_sgt(dt, "%I:%M %p SGT")
