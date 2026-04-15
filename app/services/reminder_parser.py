"""Natural-language reminder parser.

Supports a small but useful set of patterns:

  in 5 minutes <text>
  in 2 hours <text>
  tomorrow [at] 9am <text>
  today [at] 21:00 <text>
  monday [at] 8:00 <text>             (next occurrence of that weekday)
  on 2026-04-20 09:00 <text>
  every monday [at] 8:00 <text>       (recurring)
  every day [at] 9:00 <text>          (recurring)
  every 2 hours <text>                (recurring; emits an interval rrule)

Returns a ParsedReminder. Raises ParseError on unparseable input.

Ambiguity strategy: when the time of day cannot be inferred, default to 09:00
in the user's timezone and set `ambiguous=True` so the handler can confirm.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.utils.timefmt import safe_zone, utcnow


class ParseError(ValueError):
    pass


@dataclass
class ParsedReminder:
    text: str
    next_run_utc: datetime
    rrule: str | None = None  # our small subset; see scheduler.py for triggers
    ambiguous: bool = False
    explanation: str = ""


_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_WEEKDAY_RRULE = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}

_UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400,
    "week": 7 * 86400, "weeks": 7 * 86400,
}


_TIME_RE = re.compile(
    r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE
)


def _parse_time(token: str) -> tuple[int, int] | None:
    m = _TIME_RE.search(token)
    if not m:
        return None
    h = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "am":
        if h == 12:
            h = 0
    elif ampm == "pm":
        if h < 12:
            h += 12
    if not (0 <= h < 24 and 0 <= minute < 60):
        return None
    return h, minute


def _strip_time(text: str) -> str:
    return _TIME_RE.sub("", text, count=1).strip()


def _strip_leading_me(text: str) -> str:
    return re.sub(r"^\s*me\b[\s,:-]*", "", text, flags=re.IGNORECASE)


def parse(raw: str, tz_name: str, *, now: datetime | None = None) -> ParsedReminder:
    if not raw or not raw.strip():
        raise ParseError("Empty reminder.")

    text = _strip_leading_me(raw.strip())
    tz = safe_zone(tz_name)
    now_utc = now or utcnow()
    now_local = now_utc.astimezone(tz)

    lower = text.lower()

    # ---- recurring: every <weekday> [at] HH:MM ----
    m = re.match(
        r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"mon|tue|tues|wed|thu|thurs|fri|sat|sun)\s+(.*)",
        lower,
    )
    if m:
        wd = _WEEKDAYS[m.group(1)]
        rest_lower = m.group(2)
        rest_orig = text[m.end(1):].strip()
        t = _parse_time(rest_lower)
        h, minute = t if t else (9, 0)
        ambiguous = t is None
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        next_run = _next_weekday_at(now_local, wd, h, minute)
        rrule = f"FREQ=WEEKLY;BYDAY={_WEEKDAY_RRULE[wd]};BYHOUR={h};BYMINUTE={minute}"
        return ParsedReminder(
            text=body,
            next_run_utc=next_run.astimezone(tz).astimezone(now_utc.tzinfo),
            rrule=rrule,
            ambiguous=ambiguous,
            explanation=f"Every {m.group(1).capitalize()} at {h:02d}:{minute:02d} {tz_name}",
        )

    # ---- recurring: every day [at] HH:MM ----
    m = re.match(r"every\s+day\s+(.*)", lower)
    if m:
        rest_lower = m.group(1)
        rest_orig = text[m.end(0) - len(m.group(1)):].strip()
        t = _parse_time(rest_lower)
        h, minute = t if t else (9, 0)
        ambiguous = t is None
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        next_run_local = now_local.replace(hour=h, minute=minute, second=0, microsecond=0)
        if next_run_local <= now_local:
            next_run_local += timedelta(days=1)
        rrule = f"FREQ=DAILY;BYHOUR={h};BYMINUTE={minute}"
        return ParsedReminder(
            text=body,
            next_run_utc=next_run_local.astimezone(now_utc.tzinfo),
            rrule=rrule,
            ambiguous=ambiguous,
            explanation=f"Every day at {h:02d}:{minute:02d} {tz_name}",
        )

    # ---- recurring: every N <unit> ----
    m = re.match(r"every\s+(\d+)\s+(\w+)\s+(.*)", lower)
    if m and m.group(2) in _UNIT_SECONDS:
        n = int(m.group(1))
        unit = m.group(2)
        seconds = n * _UNIT_SECONDS[unit]
        if seconds < 60:
            raise ParseError("Recurring reminders must be at least 1 minute apart.")
        body = text[m.end(2):].strip(" ,:-") or "Reminder"
        next_run = now_utc + timedelta(seconds=seconds)
        rrule = f"INTERVAL_SECONDS={seconds}"
        return ParsedReminder(
            text=body,
            next_run_utc=next_run,
            rrule=rrule,
            explanation=f"Every {n} {unit}",
        )

    # ---- one-shot: in N <unit> ----
    m = re.match(r"in\s+(\d+)\s+(\w+)\s+(.*)", lower)
    if m and m.group(2) in _UNIT_SECONDS:
        n = int(m.group(1))
        unit = m.group(2)
        seconds = n * _UNIT_SECONDS[unit]
        body = text[m.end(2):].strip(" ,:-") or "Reminder"
        return ParsedReminder(
            text=body,
            next_run_utc=now_utc + timedelta(seconds=seconds),
            explanation=f"In {n} {unit}",
        )

    # ---- one-shot: tomorrow [at HH:MM] ----
    m = re.match(r"tomorrow\s*(.*)", lower)
    if m:
        rest_lower = m.group(1)
        rest_orig = text[len("tomorrow"):].strip()
        t = _parse_time(rest_lower)
        h, minute = t if t else (9, 0)
        ambiguous = t is None
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        target_local = (now_local + timedelta(days=1)).replace(
            hour=h, minute=minute, second=0, microsecond=0
        )
        return ParsedReminder(
            text=body,
            next_run_utc=target_local.astimezone(now_utc.tzinfo),
            ambiguous=ambiguous,
            explanation=f"Tomorrow at {h:02d}:{minute:02d} {tz_name}",
        )

    # ---- one-shot: today HH:MM ----
    m = re.match(r"today\s+(.*)", lower)
    if m:
        rest_lower = m.group(1)
        rest_orig = text[len("today"):].strip()
        t = _parse_time(rest_lower)
        if t is None:
            raise ParseError("`today` requires a time, e.g. `today 18:00 call mom`.")
        h, minute = t
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        target_local = now_local.replace(hour=h, minute=minute, second=0, microsecond=0)
        if target_local <= now_local:
            raise ParseError("That time has already passed today.")
        return ParsedReminder(
            text=body,
            next_run_utc=target_local.astimezone(now_utc.tzinfo),
            explanation=f"Today at {h:02d}:{minute:02d} {tz_name}",
        )

    # ---- one-shot: <weekday> [at HH:MM] ----
    m = re.match(
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"mon|tue|tues|wed|thu|thurs|fri|sat|sun)\s+(.*)",
        lower,
    )
    if m:
        wd = _WEEKDAYS[m.group(1)]
        rest_lower = m.group(2)
        rest_orig = text[m.end(1):].strip()
        t = _parse_time(rest_lower)
        h, minute = t if t else (9, 0)
        ambiguous = t is None
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        target_local = _next_weekday_at(now_local, wd, h, minute)
        return ParsedReminder(
            text=body,
            next_run_utc=target_local.astimezone(now_utc.tzinfo),
            ambiguous=ambiguous,
            explanation=f"{m.group(1).capitalize()} at {h:02d}:{minute:02d} {tz_name}",
        )

    # ---- one-shot: on YYYY-MM-DD [HH:MM] ----
    m = re.match(r"on\s+(\d{4}-\d{2}-\d{2})\s*(.*)", lower)
    if m:
        date_str = m.group(1)
        rest_lower = m.group(2)
        rest_orig = text[m.end(1):].strip()
        t = _parse_time(rest_lower)
        h, minute = t if t else (9, 0)
        ambiguous = t is None
        body = _strip_time(rest_orig).strip(" ,:-") or "Reminder"
        try:
            y, mth, d = (int(x) for x in date_str.split("-"))
            target_local = datetime(y, mth, d, h, minute, tzinfo=tz)
        except ValueError as e:
            raise ParseError(f"Invalid date: {date_str}") from e
        if target_local <= now_local:
            raise ParseError("That date/time has already passed.")
        return ParsedReminder(
            text=body,
            next_run_utc=target_local.astimezone(now_utc.tzinfo),
            ambiguous=ambiguous,
            explanation=f"On {date_str} at {h:02d}:{minute:02d} {tz_name}",
        )

    raise ParseError(
        "I couldn't understand the time. Try: `in 30 minutes ...`, "
        "`tomorrow 9am ...`, `monday 8:00 ...`, `every monday 8:00 ...`."
    )


def _next_weekday_at(now_local: datetime, weekday: int, hour: int, minute: int) -> datetime:
    target = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - now_local.weekday()) % 7
    target += timedelta(days=days_ahead)
    if target <= now_local:
        target += timedelta(days=7)
    return target


def compute_next_run(rrule: str, after_utc: datetime, tz_name: str) -> datetime | None:
    """Given our small rrule subset and a UTC moment, return the next firing in UTC."""
    tz = safe_zone(tz_name)
    if rrule.startswith("INTERVAL_SECONDS="):
        seconds = int(rrule.split("=", 1)[1])
        return after_utc + timedelta(seconds=seconds)

    parts = dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)
    freq = parts.get("FREQ")
    hour = int(parts.get("BYHOUR", "9"))
    minute = int(parts.get("BYMINUTE", "0"))

    after_local = after_utc.astimezone(tz)

    if freq == "DAILY":
        candidate = after_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(after_utc.tzinfo)

    if freq == "WEEKLY":
        byday = parts.get("BYDAY", "MO")
        wd_map = {v: k for k, v in _WEEKDAY_RRULE.items()}
        weekday = wd_map.get(byday, 0)
        candidate = _next_weekday_at(after_local, weekday, hour, minute)
        return candidate.astimezone(after_utc.tzinfo)

    return None
