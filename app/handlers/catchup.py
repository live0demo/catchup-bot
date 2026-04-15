"""/markread, /catchup{,_short,_detailed}, /autosummary."""
from __future__ import annotations

import logging
from typing import Literal

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.db import session_scope
from app.handlers.settings import upsert_chat_from_msg, upsert_user_from_msg
from app.services.checkpoint import (
    get_or_create_state,
    latest_message_id,
    messages_since_checkpoint,
)
from app.services.llm import summarize
from app.utils.timefmt import utcnow

router = Router(name="catchup")
log = logging.getLogger(__name__)

Style = Literal["short", "medium", "detailed"]


@router.message(Command("markread"))
async def markread(msg: Message) -> None:
    upsert_user_from_msg(msg)
    upsert_chat_from_msg(msg)

    with session_scope() as s:
        st = get_or_create_state(s, msg.from_user.id, msg.chat.id)
        latest = latest_message_id(s, msg.chat.id)
        st.last_checkpoint_message_id = latest if latest is not None else msg.message_id
        st.last_checkpoint_at = utcnow()

    note = (
        "Checkpoint set ✅\n"
        "I'll catch you up from here when you run /catchup."
    )
    if msg.chat.type in ("group", "supergroup"):
        note += "\n<i>Note: I only see messages I'm allowed to read (Privacy Mode setting).</i>"
    await msg.answer(note)


async def _do_catchup(msg: Message, style: Style) -> None:
    upsert_user_from_msg(msg)
    upsert_chat_from_msg(msg)

    with session_scope() as s:
        st = get_or_create_state(s, msg.from_user.id, msg.chat.id)
        items = messages_since_checkpoint(s, msg.chat.id, st.last_checkpoint_message_id)
        # Reading-only after this point; advance checkpoint so re-running gives nothing new.
        latest = latest_message_id(s, msg.chat.id)
        if latest is not None:
            st.last_checkpoint_message_id = latest
            st.last_checkpoint_at = utcnow()

    if not items:
        if msg.chat.type in ("group", "supergroup"):
            await msg.answer(
                "No new messages since your checkpoint. "
                "If you expected some, check that I have permission to read group messages "
                "(BotFather → Edit Bot → Group Privacy → <b>Disable</b>)."
            )
        else:
            await msg.answer("Nothing new since your last checkpoint.")
        return

    summary = await summarize(items, style=style)
    await msg.answer(summary)


@router.message(Command("catchup"))
async def catchup(msg: Message) -> None:
    await _do_catchup(msg, "medium")


@router.message(Command("catchup_short"))
async def catchup_short(msg: Message) -> None:
    await _do_catchup(msg, "short")


@router.message(Command("catchup_detailed"))
async def catchup_detailed(msg: Message) -> None:
    await _do_catchup(msg, "detailed")


@router.message(Command("autosummary"))
async def autosummary(msg: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip().lower()
    if arg not in {"on", "off"}:
        await msg.answer("Usage: <code>/autosummary on</code> or <code>/autosummary off</code>")
        return
    with session_scope() as s:
        st = get_or_create_state(s, msg.from_user.id, msg.chat.id)
        st.autosummary = arg == "on"
    if arg == "on":
        await msg.answer(
            "Autosummary preference saved ✅\n"
            "<i>MVP note:</i> autosummary is a stored preference. Trigger digests with "
            "/catchup whenever you want one — automatic delivery can be added without schema changes."
        )
    else:
        await msg.answer("Autosummary disabled.")
