"""Tests for recurring reminder next-run computation."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.reminder_parser import compute_next_run

UTC = ZoneInfo("UTC")


def test_interval_seconds():
    after = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    nxt = compute_next_run("INTERVAL_SECONDS=7200", after, "UTC")
    assert nxt == datetime(2026, 4, 15, 12, 0, tzinfo=UTC)


def test_daily_today_in_future():
    after = datetime(2026, 4, 15, 8, 0, tzinfo=UTC)
    nxt = compute_next_run("FREQ=DAILY;BYHOUR=9;BYMINUTE=0", after, "UTC")
    assert nxt == datetime(2026, 4, 15, 9, 0, tzinfo=UTC)


def test_daily_today_in_past_rolls_to_tomorrow():
    after = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    nxt = compute_next_run("FREQ=DAILY;BYHOUR=9;BYMINUTE=0", after, "UTC")
    assert nxt == datetime(2026, 4, 16, 9, 0, tzinfo=UTC)


def test_weekly_picks_next_matching_weekday():
    # 2026-04-15 is Wednesday; next Monday is the 20th.
    after = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    nxt = compute_next_run("FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=0", after, "UTC")
    assert nxt == datetime(2026, 4, 20, 8, 0, tzinfo=UTC)


def test_weekly_today_already_past_rolls_a_week():
    # 2026-04-15 is Wednesday 10:00 UTC; weekly Wed 08:00 has passed → +7 days.
    after = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    nxt = compute_next_run("FREQ=WEEKLY;BYDAY=WE;BYHOUR=8;BYMINUTE=0", after, "UTC")
    assert nxt == datetime(2026, 4, 22, 8, 0, tzinfo=UTC)


def test_weekly_with_timezone():
    # Weekly Monday 08:00 Berlin == 06:00 UTC in CEST.
    after = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    nxt = compute_next_run("FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=0", after, "Europe/Berlin")
    assert nxt == datetime(2026, 4, 20, 6, 0, tzinfo=UTC)
