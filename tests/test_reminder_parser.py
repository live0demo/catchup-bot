"""Tests for the natural-language reminder parser."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.reminder_parser import ParseError, parse


# Fixed reference time: Wednesday 2026-04-15 10:00 UTC.
NOW_UTC = datetime(2026, 4, 15, 10, 0, tzinfo=ZoneInfo("UTC"))


def test_in_minutes():
    p = parse("in 30 minutes water plants", "UTC", now=NOW_UTC)
    assert p.text == "water plants"
    assert p.rrule is None
    delta = (p.next_run_utc - NOW_UTC).total_seconds()
    assert delta == 30 * 60


def test_in_hours_strips_me():
    p = parse("me in 2 hours check server", "UTC", now=NOW_UTC)
    assert p.text == "check server"
    assert (p.next_run_utc - NOW_UTC).total_seconds() == 2 * 3600


def test_tomorrow_with_time():
    p = parse("tomorrow 9am submit report", "UTC", now=NOW_UTC)
    assert p.text == "submit report"
    assert p.next_run_utc == datetime(2026, 4, 16, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert not p.ambiguous


def test_tomorrow_no_time_is_ambiguous():
    p = parse("tomorrow buy bread", "UTC", now=NOW_UTC)
    assert p.ambiguous is True
    # default time 09:00
    assert p.next_run_utc.hour == 9
    assert p.next_run_utc.minute == 0


def test_today_requires_time():
    with pytest.raises(ParseError):
        parse("today buy bread", "UTC", now=NOW_UTC)


def test_today_in_future():
    p = parse("today 18:00 call mom", "UTC", now=NOW_UTC)
    assert p.next_run_utc == datetime(2026, 4, 15, 18, 0, tzinfo=ZoneInfo("UTC"))


def test_today_in_past_rejected():
    with pytest.raises(ParseError):
        parse("today 06:00 call mom", "UTC", now=NOW_UTC)


def test_weekday_one_shot():
    # NOW is Wednesday; Monday is in 5 days.
    p = parse("monday 8:00 team sync", "UTC", now=NOW_UTC)
    assert p.text == "team sync"
    assert p.next_run_utc == datetime(2026, 4, 20, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_weekday_recurring():
    p = parse("every monday 8:00 team sync", "UTC", now=NOW_UTC)
    assert p.text == "team sync"
    assert p.rrule == "FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=0"


def test_every_day():
    p = parse("every day 9:00 take vitamins", "UTC", now=NOW_UTC)
    assert p.rrule == "FREQ=DAILY;BYHOUR=9;BYMINUTE=0"
    # Today 09:00 is in the past, so next firing is tomorrow 09:00.
    assert p.next_run_utc == datetime(2026, 4, 16, 9, 0, tzinfo=ZoneInfo("UTC"))


def test_every_n_hours_interval():
    p = parse("every 2 hours stand up", "UTC", now=NOW_UTC)
    assert p.rrule == "INTERVAL_SECONDS=7200"
    assert p.next_run_utc == datetime(2026, 4, 15, 12, 0, tzinfo=ZoneInfo("UTC"))


def test_iso_date():
    p = parse("on 2026-04-20 09:30 doctor", "UTC", now=NOW_UTC)
    assert p.text == "doctor"
    assert p.next_run_utc == datetime(2026, 4, 20, 9, 30, tzinfo=ZoneInfo("UTC"))


def test_unparseable():
    with pytest.raises(ParseError):
        parse("yo do something", "UTC", now=NOW_UTC)


def test_timezone_applied():
    p = parse("tomorrow 9am do stuff", "Europe/Berlin", now=NOW_UTC)
    # 9am Berlin on 2026-04-16 == 07:00 UTC (Berlin is UTC+2 in April; CEST).
    assert p.next_run_utc == datetime(2026, 4, 16, 7, 0, tzinfo=ZoneInfo("UTC"))
