"""Timezone-aware datetime helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def safe_zone(name: str | None, default: str = "UTC") -> ZoneInfo:
    try:
        return ZoneInfo(name or default)
    except ZoneInfoNotFoundError:
        return ZoneInfo(default)


def to_utc(dt: datetime, tz_name: str) -> datetime:
    """Treat naive dt as being in tz_name; return UTC-aware datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=safe_zone(tz_name))
    return dt.astimezone(timezone.utc)


def fmt_local(dt: datetime, tz_name: str) -> str:
    return dt.astimezone(safe_zone(tz_name)).strftime("%Y-%m-%d %H:%M %Z")
