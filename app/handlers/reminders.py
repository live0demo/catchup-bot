"""/remind, /list_reminders, /delete_reminder + ambiguity confirmation."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.db import session_scope
from app.handlers.settings import get_user_tz, upsert_chat_from_msg, upsert_user_from_msg
from app.models import Reminder
from app.scheduler.scheduler import ReminderScheduler
from app.services.reminder_parser import ParseError, parse
from app.utils.timefmt import fmt_local

router = Router(name="reminders")
log = logging.getLogger(__name__)


class _SchedulerRef:
    """Tiny holder so handlers can reach the scheduler without import gymnastics."""

    def __init__(self) -> None:
        self._sched: Optional[ReminderScheduler] = None

    def set(self, sched: ReminderScheduler) -> None:
        self._sched = sched

    def get(self) -> ReminderScheduler:
        if self._sched is None:
            raise RuntimeError("Scheduler not initialised")
        return self._sched


scheduler_ref = _SchedulerRef()


@router.message(Command("remind"))
async def remind(msg: Message, command: CommandObject) -> None:
    upsert_user_from_msg(msg)
    upsert_chat_from_msg(msg)

    raw = (command.args or "").strip()
    if not raw:
        await msg.answer(
            "Usage:\n"
            "<code>/remind in 30 minutes water plants</code>\n"
            "<code>/remind tomorrow 9am submit report</code>\n"
            "<code>/remind every monday 8:00 team sync</code>"
        )
        return

    tz_name = get_user_tz(msg.from_user.id)
    try:
        parsed = parse(raw, tz_name)
    except ParseError as e:
        await msg.answer(f"❌ {e}")
        return

    with session_scope() as s:
        r = Reminder(
            user_id=msg.from_user.id,
            chat_id=msg.chat.id,
            text=parsed.text,
            next_run_at=parsed.next_run_utc,
            rrule=parsed.rrule,
            timezone=tz_name,
            is_active=True,
        )
        s.add(r)
        s.flush()
        rid = r.id
        next_run = r.next_run_at

    when_str = fmt_local(next_run, tz_name)

    if parsed.ambiguous:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Confirm", callback_data=f"r:ok:{rid}"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data=f"r:no:{rid}"),
                ]
            ]
        )
        await msg.answer(
            f"That looked ambiguous — I assumed <b>{when_str}</b>"
            + (f" (<i>{parsed.explanation}</i>)" if parsed.explanation else "")
            + f"\nReminder text: <i>{_html_escape(parsed.text)}</i>\n\nConfirm?",
            reply_markup=kb,
        )
        return

    scheduler_ref.get().schedule_reminder(rid, parsed.next_run_utc)
    await msg.answer(
        f"⏰ Saved (#{rid})\n"
        f"<b>When</b>: {when_str}"
        f"{' (recurring)' if parsed.rrule else ''}\n"
        f"<b>What</b>: {_html_escape(parsed.text)}"
    )


@router.callback_query(F.data.startswith("r:"))
async def reminder_confirm(cb: CallbackQuery) -> None:
    try:
        _, action, rid_str = cb.data.split(":")
        rid = int(rid_str)
    except (ValueError, AttributeError):
        await cb.answer("Bad payload")
        return

    with session_scope() as s:
        r = s.get(Reminder, rid)
        if r is None:
            await cb.answer("Not found")
            return
        if action == "ok":
            r.is_active = True
            scheduler_ref.get().schedule_reminder(rid, r.next_run_at)
            await cb.message.edit_text(
                cb.message.html_text + "\n\n✅ <b>Confirmed.</b>"
            )
            await cb.answer("Confirmed")
        else:
            r.is_active = False
            await cb.message.edit_text(
                cb.message.html_text + "\n\n❌ <b>Cancelled.</b>"
            )
            await cb.answer("Cancelled")


@router.message(Command("list_reminders"))
async def list_reminders(msg: Message) -> None:
    tz_name = get_user_tz(msg.from_user.id)
    with session_scope() as s:
        rows = s.execute(
            select(Reminder)
            .where(Reminder.user_id == msg.from_user.id, Reminder.is_active.is_(True))
            .order_by(Reminder.next_run_at.asc())
        ).scalars().all()
        items = [
            (r.id, r.text, r.next_run_at, r.rrule, r.chat_id) for r in rows
        ]

    if not items:
        await msg.answer("You have no active reminders. Set one with /remind.")
        return

    lines = ["<b>Your reminders</b>"]
    for rid, text, when, rrule, chat_id in items:
        when_str = fmt_local(when, tz_name) if when else "—"
        scope = "here" if chat_id == msg.chat.id else f"chat {chat_id}"
        recurring = " 🔁" if rrule else ""
        lines.append(
            f"#{rid}{recurring} — <b>{when_str}</b> ({scope})\n  {_html_escape(text)}"
        )
    lines.append("\nDelete with <code>/delete_reminder &lt;id&gt;</code>.")
    await msg.answer("\n".join(lines))


@router.message(Command("delete_reminder"))
async def delete_reminder(msg: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    try:
        rid = int(arg)
    except ValueError:
        await msg.answer("Usage: <code>/delete_reminder 42</code>")
        return

    with session_scope() as s:
        r = s.get(Reminder, rid)
        if r is None or r.user_id != msg.from_user.id:
            await msg.answer("Reminder not found.")
            return
        r.is_active = False
    scheduler_ref.get().cancel_reminder(rid)
    await msg.answer(f"Deleted reminder #{rid}.")


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
