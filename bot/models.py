"""Typed data models for ParkWatch SG.

TypedDict definitions for rows returned by the Database layer, providing
runtime documentation and static type-checking via mypy.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class UserRow(TypedDict):
    telegram_id: int
    username: str | None
    first_name: str | None
    created_at: datetime
    report_count: int
    warnings: int
    flagged: bool


class UserStatsRow(TypedDict):
    report_count: int


class SubscriptionRow(TypedDict):
    id: int
    telegram_id: int
    zone_name: str
    created_at: datetime


class SightingRow(TypedDict):
    id: str
    zone: str
    description: str | None
    reporter_id: int
    reporter_name: str
    reporter_badge: str
    lat: float | None
    lng: float | None
    reported_at: datetime
    feedback_positive: int
    feedback_negative: int


class FeedbackRow(TypedDict):
    id: int
    user_id: int
    sighting_id: str
    vote: str
    created_at: datetime


class AdminActionRow(TypedDict):
    id: int
    admin_id: int
    action: str
    target: str | None
    detail: str | None
    created_at: datetime


class BannedUserRow(TypedDict):
    telegram_id: int
    banned_by: int
    reason: str | None
    banned_at: datetime


class ConfigOverrideRow(TypedDict):
    key: str
    value: str
    updated_by: int
    updated_at: datetime


class GlobalStatsRow(TypedDict):
    total_users: int
    active_reporters_7d: int
    active_feedback_givers_7d: int
    total_sightings: int
    sightings_24h: int
    active_subscriptions: int
    unique_subscribers: int
    feedback_positive: int
    feedback_negative: int


class ZoneDetailRow(TypedDict):
    zone: str
    total_sightings: int
    sightings_24h: int
    subscribers: int
