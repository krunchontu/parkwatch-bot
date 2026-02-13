"""Unit tests for pure functions in bot.main.

Tests: haversine_meters, get_reporter_badge, get_accuracy_indicator,
       sanitize_description, build_alert_message, generate_sighting_id.
"""

from datetime import datetime, timezone

from bot.main import (
    ZONE_COORDS,
    ZONES,
    build_alert_message,
    generate_sighting_id,
    get_accuracy_indicator,
    get_reporter_badge,
    haversine_meters,
    sanitize_description,
)


# ---------------------------------------------------------------------------
# haversine_meters
# ---------------------------------------------------------------------------
class TestHaversineMeters:
    """Tests for the Haversine distance function."""

    def test_same_point_returns_zero(self):
        assert haversine_meters(1.3521, 103.8198, 1.3521, 103.8198) == 0.0

    def test_known_distance_tanjong_pagar_to_bugis(self):
        """Tanjong Pagar to Bugis is roughly 2.7-2.8 km."""
        tp = ZONE_COORDS["Tanjong Pagar"]
        bg = ZONE_COORDS["Bugis"]
        dist = haversine_meters(tp[0], tp[1], bg[0], bg[1])
        assert 2500 < dist < 3200

    def test_short_distance_within_duplicate_radius(self):
        """Two points 100m apart should be under 200m threshold."""
        # ~100m north of Tanjong Pagar
        lat1, lng1 = 1.2764, 103.8460
        lat2, lng2 = 1.2773, 103.8460  # roughly 100m north
        dist = haversine_meters(lat1, lng1, lat2, lng2)
        assert dist < 200

    def test_symmetry(self):
        """Distance A→B should equal distance B→A."""
        a = (1.3521, 103.8198)
        b = (1.2764, 103.8460)
        assert haversine_meters(*a, *b) == haversine_meters(*b, *a)

    def test_large_distance_cross_island(self):
        """Woodlands to Tanjong Pagar is ~17-19 km (north to south)."""
        wl = ZONE_COORDS["Woodlands"]
        tp = ZONE_COORDS["Tanjong Pagar"]
        dist = haversine_meters(wl[0], wl[1], tp[0], tp[1])
        assert 15_000 < dist < 20_000

    def test_always_positive(self):
        dist = haversine_meters(1.0, 100.0, 2.0, 101.0)
        assert dist > 0


# ---------------------------------------------------------------------------
# get_reporter_badge
# ---------------------------------------------------------------------------
class TestGetReporterBadge:
    """Tests for badge assignment based on report count."""

    def test_new_badge_zero_reports(self):
        assert get_reporter_badge(0) == "🆕 New"

    def test_new_badge_two_reports(self):
        assert get_reporter_badge(2) == "🆕 New"

    def test_regular_badge_boundary(self):
        assert get_reporter_badge(3) == "⭐ Regular"

    def test_regular_badge_ten_reports(self):
        assert get_reporter_badge(10) == "⭐ Regular"

    def test_trusted_badge_boundary(self):
        assert get_reporter_badge(11) == "⭐⭐ Trusted"

    def test_trusted_badge_fifty_reports(self):
        assert get_reporter_badge(50) == "⭐⭐ Trusted"

    def test_veteran_badge_boundary(self):
        assert get_reporter_badge(51) == "🏆 Veteran"

    def test_veteran_badge_high_count(self):
        assert get_reporter_badge(999) == "🏆 Veteran"


# ---------------------------------------------------------------------------
# get_accuracy_indicator
# ---------------------------------------------------------------------------
class TestGetAccuracyIndicator:
    """Tests for accuracy indicator based on score and feedback count."""

    def test_not_enough_data_returns_empty(self):
        assert get_accuracy_indicator(1.0, 0) == ""
        assert get_accuracy_indicator(1.0, 1) == ""
        assert get_accuracy_indicator(1.0, 2) == ""

    def test_threshold_three_ratings_shows_indicator(self):
        assert get_accuracy_indicator(1.0, 3) == "✅"

    def test_high_accuracy(self):
        assert get_accuracy_indicator(0.9, 10) == "✅"
        assert get_accuracy_indicator(0.8, 5) == "✅"

    def test_mixed_accuracy(self):
        assert get_accuracy_indicator(0.79, 5) == "⚠️"
        assert get_accuracy_indicator(0.5, 10) == "⚠️"

    def test_low_accuracy(self):
        assert get_accuracy_indicator(0.49, 5) == "❌"
        assert get_accuracy_indicator(0.0, 10) == "❌"

    def test_boundary_80_percent(self):
        """Exactly 0.8 should be high accuracy."""
        assert get_accuracy_indicator(0.8, 5) == "✅"

    def test_boundary_50_percent(self):
        """Exactly 0.5 should be mixed accuracy."""
        assert get_accuracy_indicator(0.5, 5) == "⚠️"


# ---------------------------------------------------------------------------
# sanitize_description
# ---------------------------------------------------------------------------
class TestSanitizeDescription:
    """Tests for input sanitization."""

    def test_none_input(self):
        assert sanitize_description(None) is None

    def test_empty_string(self):
        assert sanitize_description("") is None

    def test_whitespace_only(self):
        assert sanitize_description("   ") is None

    def test_normal_text_unchanged(self):
        assert sanitize_description("outside Maxwell Food Centre") == "outside Maxwell Food Centre"

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_description("  hello  ") == "hello"

    def test_collapses_multiple_whitespace(self):
        assert sanitize_description("Block   123    carpark") == "Block 123 carpark"

    def test_strips_html_tags(self):
        assert sanitize_description("<b>bold</b> text") == "bold text"
        assert sanitize_description("<script>alert('xss')</script>") == "alert('xss')"

    def test_removes_control_characters(self):
        assert sanitize_description("hello\x00world") == "helloworld"
        assert sanitize_description("hello\x01world") == "helloworld"

    def test_truncates_to_100_characters(self):
        long_text = "x" * 150
        result = sanitize_description(long_text)
        assert len(result) == 100

    def test_combined_sanitization(self):
        """HTML + whitespace + control chars all at once."""
        text = "  <b>Hello</b>   \x00world   "
        assert sanitize_description(text) == "Hello world"

    def test_result_empty_after_cleanup(self):
        """Tags-only input should return None after stripping."""
        assert sanitize_description("<br><hr>") is None


# ---------------------------------------------------------------------------
# build_alert_message
# ---------------------------------------------------------------------------
class TestBuildAlertMessage:
    """Tests for alert message construction."""

    def _make_sighting(self, **overrides):
        base = {
            "zone": "Tanjong Pagar",
            "reported_at": datetime(2026, 2, 13, 6, 30, 0, tzinfo=timezone.utc),
            "description": "outside Maxwell Food Centre",
            "lat": 1.276432,
            "lng": 103.846021,
        }
        base.update(overrides)
        return base

    def test_basic_alert_with_all_fields(self):
        msg = build_alert_message(
            self._make_sighting(),
            pos=0,
            neg=0,
            badge="⭐ Regular",
            accuracy_indicator="✅",
        )
        assert "WARDEN ALERT — Tanjong Pagar" in msg
        assert "outside Maxwell Food Centre" in msg
        assert "1.276432" in msg
        assert "⭐ Regular ✅" in msg
        assert "Was this accurate?" in msg

    def test_alert_without_description(self):
        msg = build_alert_message(
            self._make_sighting(description=None),
            pos=0,
            neg=0,
            badge="🆕 New",
            accuracy_indicator="",
        )
        assert "📝 Location:" not in msg
        assert "🆕 New" in msg

    def test_alert_without_gps(self):
        msg = build_alert_message(
            self._make_sighting(lat=None, lng=None),
            pos=0,
            neg=0,
            badge="⭐ Regular",
            accuracy_indicator="",
        )
        assert "🌐 GPS:" not in msg

    def test_alert_with_feedback(self):
        msg = build_alert_message(
            self._make_sighting(),
            pos=5,
            neg=1,
            badge="⭐ Regular",
            accuracy_indicator="✅",
            feedback_received=True,
        )
        assert "📊 Feedback: 👍 5 / 👎 1" in msg
        assert "Thanks for your feedback!" in msg
        assert "Was this accurate?" not in msg

    def test_alert_without_feedback(self):
        msg = build_alert_message(
            self._make_sighting(),
            pos=0,
            neg=0,
            badge="⭐ Regular",
            accuracy_indicator="✅",
        )
        assert "Was this accurate?" in msg
        assert "📊 Feedback:" not in msg

    def test_sgt_time_display(self):
        """UTC 06:30 should display as 02:30 PM SGT (UTC+8)."""
        msg = build_alert_message(
            self._make_sighting(),
            pos=0,
            neg=0,
            badge="⭐ Regular",
            accuracy_indicator="",
        )
        assert "02:30 PM SGT" in msg

    def test_naive_datetime_treated_as_utc(self):
        """A naive datetime should be treated as UTC for display."""
        sighting = self._make_sighting(
            reported_at=datetime(2026, 2, 13, 6, 30, 0)  # naive
        )
        msg = build_alert_message(
            sighting,
            pos=0,
            neg=0,
            badge="⭐ Regular",
            accuracy_indicator="",
        )
        assert "02:30 PM SGT" in msg

    def test_no_accuracy_indicator(self):
        """Reporter line should not have trailing space when no indicator."""
        msg = build_alert_message(
            self._make_sighting(),
            pos=0,
            neg=0,
            badge="🆕 New",
            accuracy_indicator="",
        )
        assert "👤 Reporter: 🆕 New\n" in msg


# ---------------------------------------------------------------------------
# generate_sighting_id
# ---------------------------------------------------------------------------
class TestGenerateSightingId:
    """Tests for UUID4 sighting ID generation."""

    def test_returns_string(self):
        assert isinstance(generate_sighting_id(), str)

    def test_uuid4_format(self):
        """UUID4 has format xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx."""
        sid = generate_sighting_id()
        parts = sid.split("-")
        assert len(parts) == 5
        assert len(sid) == 36
        assert parts[2][0] == "4"  # version 4

    def test_unique_ids(self):
        ids = {generate_sighting_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# Zone data integrity
# ---------------------------------------------------------------------------
class TestZoneData:
    """Verify zone data consistency."""

    def test_zone_count(self):
        """Should have 80 zones total across all regions."""
        total = sum(len(region["zones"]) for region in ZONES.values())
        assert total == 80

    def test_region_count(self):
        assert len(ZONES) == 6

    def test_all_zones_have_coordinates(self):
        """Every zone in ZONES should have an entry in ZONE_COORDS."""
        for region in ZONES.values():
            for zone in region["zones"]:
                assert zone in ZONE_COORDS, f"Missing coordinates for zone: {zone}"

    def test_zone_coords_count_matches(self):
        assert len(ZONE_COORDS) == 80

    def test_coordinates_in_singapore(self):
        """All coordinates should be within Singapore bounding box."""
        for zone, (lat, lng) in ZONE_COORDS.items():
            assert 1.15 < lat < 1.48, f"{zone} latitude {lat} outside Singapore"
            assert 103.60 < lng < 104.10, f"{zone} longitude {lng} outside Singapore"
