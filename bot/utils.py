"""Pure utility functions for ParkWatch SG."""

import math
import re
import uuid
from datetime import timedelta, timezone

# Singapore Time (UTC+8)
SGT = timezone(timedelta(hours=8))


def haversine_meters(lat1, lng1, lat2, lng2):
    """Haversine formula — returns distance in meters between two GPS points."""
    earth_radius = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_reporter_badge(report_count):
    """Return badge based on number of reports."""
    if report_count >= 51:
        return "\U0001f3c6 Veteran"
    elif report_count >= 11:
        return "\u2b50\u2b50 Trusted"
    elif report_count >= 3:
        return "\u2b50 Regular"
    else:
        return "\U0001f195 New"


def get_accuracy_indicator(accuracy_score, total_feedback):
    """Return accuracy indicator based on score."""
    if total_feedback < 3:
        return ""  # Not enough data
    if accuracy_score >= 0.8:
        return "\u2705"  # Highly accurate
    elif accuracy_score >= 0.5:
        return "\u26a0\ufe0f"  # Mixed accuracy
    else:
        return "\u274c"  # Low accuracy - possible spammer


def generate_sighting_id():
    """Generate unique sighting ID using UUID4 (collision-proof)."""
    return str(uuid.uuid4())


def sanitize_description(text):
    """Sanitize user-provided description text.

    Strips whitespace, removes control characters, strips HTML tags,
    collapses whitespace, and truncates to 100 characters.
    Returns None if the result is empty.
    """
    if not text:
        return None
    text = text.strip()
    # Remove control characters (U+0000-U+001F) except newline and tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple whitespace into single space
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    text = text[:100]
    return text if text else None
