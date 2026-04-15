"""Reminder scheduler. APScheduler AsyncIOScheduler running in the bot's event loop.

We schedule each reminder as a one-shot job at its next_run_at. After firing,
we (a) record an idempotent ReminderDelivery row, (b) send the message,
(c) for recurring reminders, compute the next_run and re-schedule.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from app.config import settings
from app.db import session_scope
from app.models import MessageCache, Reminder, ReminderDelivery
from app.services.reminder_parser import compute_next_run

log = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.sched = AsyncIOScheduler(timezone="UTC")

    # ---------- lifecycle ----------

    def start(self) -> None:
        self.sched.start()
        # House-keeping: cleanup old cached messages once an hour.
        self.sched.add_job(
            self._cleanup_messages,
            "interval",
            hours=1,
            id="cleanup_messages",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        log.info("Scheduler started")

    def shutdown(self) -> None:
        try:
            self.sched.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass

    # ---------- public API ----------

    def load_persisted_reminders(self) -> None:
        with session_scope() as s:
            rows = s.execute(select(Reminder).where(Reminder.is_active.is_(True))).scalars().all()
            now = datetime.now(timezone.utc)
            for r in rows:
                next_run = r.next_run_at
                if next_run is None:
                    continue
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                if next_run <= now:
                    # Missed firing while bot was down: schedule immediately.
                    next_run = now + timedelta(seconds=5)
                self._schedule_single(r.id, next_run)
        log.info("Loaded persisted reminders")

    def schedule_reminder(self, reminder_id: int, when_utc: datetime) -> None:
        if when_utc.tzinfo is None:
            when_utc = when_utc.replace(tzinfo=timezone.utc)
        self._schedule_single(reminder_id, when_utc)

    def cancel_reminder(self, reminder_id: int) -> None:
        job_id = self._job_id(reminder_id)
        try:
            self.sched.remove_job(job_id)
        except Exception:  # noqa: BLE001
            pass

    # ---------- internals ----------

    def _job_id(self, reminder_id: int) -> str:
        return f"reminder:{reminder_id}"

    def _schedule_single(self, reminder_id: int, when_utc: datetime) -> None:
        self.sched.add_job(
            self._fire,
            trigger=DateTrigger(run_date=when_utc),
            id=self._job_id(reminder_id),
            args=[reminder_id, when_utc],
            replace_existing=True,
            misfire_grace_time=300,
        )

    async def _fire(self, reminder_id: int, fire_time: datetime) -> None:
        # Snapshot reminder + idempotent delivery insert in a single tx.
        try:
            with session_scope() as s:
                r = s.get(Reminder, reminder_id)
                if r is None or not r.is_active:
                    return
                # Idempotency: skip if we already delivered for this fire_time.
                existing = s.execute(
                    select(ReminderDelivery).where(
                        ReminderDelivery.reminder_id == reminder_id,
                        ReminderDelivery.fire_time == fire_time,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    log.info("Reminder %s at %s already delivered; skipping", reminder_id, fire_time)
                    return
                s.add(ReminderDelivery(reminder_id=reminder_id, fire_time=fire_time))

                payload = {
                    "chat_id": r.chat_id,
                    "text": r.text,
                    "rrule": r.rrule,
                    "tz": r.timezone,
                }
        except Exception:  # noqa: BLE001
            log.exception("Reminder fire prep failed for id=%s", reminder_id)
            return

        text = f"⏰ <b>Reminder</b>\n{_html_escape(payload['text'])}"
        try:
            await self.bot.send_message(payload["chat_id"], text)
        except Exception:  # noqa: BLE001
            log.exception("Failed to deliver reminder %s", reminder_id)
            # We still keep the delivery row so we don't loop.

        # Reschedule recurring.
        if payload["rrule"]:
            try:
                next_run = compute_next_run(
                    payload["rrule"], datetime.now(timezone.utc), payload["tz"]
                )
                if next_run is not None:
                    with session_scope() as s2:
                        r2 = s2.get(Reminder, reminder_id)
                        if r2 is not None and r2.is_active:
                            r2.next_run_at = next_run
                    self._schedule_single(reminder_id, next_run)
            except Exception:  # noqa: BLE001
                log.exception("Failed to reschedule recurring reminder %s", reminder_id)
        else:
            # One-shot done: deactivate.
            with session_scope() as s3:
                r3 = s3.get(Reminder, reminder_id)
                if r3 is not None:
                    r3.is_active = False

    async def _cleanup_messages(self) -> None:
        # APScheduler runs this in our loop; SQLite ops are fast.
        try:
            with session_scope() as s:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=settings.message_retention_days
                )
                deleted = s.query(MessageCache).filter(
                    MessageCache.created_at < cutoff
                ).delete()
            if deleted:
                log.info("Cleanup: removed %d old cached messages", deleted)
        except Exception:  # noqa: BLE001
            log.exception("Cleanup job failed")


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Avoid 'unused import' lint complaint (asyncio is used implicitly by APScheduler).
_ = asyncio
