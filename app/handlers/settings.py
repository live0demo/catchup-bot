"""User settings: timezone."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from app.config import settings as app_settings
from app.db import session_scope
from app.models import User
from app.utils.timefmt import safe_zone

router = Router(name="settings")


def _ensure_user(s, msg: Message) -> User:
    u = s.get(User, msg.from_user.id)
    if u is None:
        u = User(
            id=msg.from_user.id,
            username=msg.from_user.username,
            full_name=msg.from_user.full_name,
            timezone=app_settings.default_timezone,
        )
        s.add(u)
        s.flush()
    return u


@router.message(Command("set_timezone"))
async def set_timezone(msg: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await msg.answer(
            "Usage: <code>/set_timezone Europe/Berlin</code>\n"
            "Use any IANA timezone name."
        )
        return
    tz = safe_zone(arg, default="UTC")
    if tz.key != arg:
        await msg.answer(f"Unknown timezone <code>{arg}</code>. Try e.g. <code>Europe/Berlin</code>.")
        return
    with session_scope() as s:
        u = _ensure_user(s, msg)
        u.timezone = arg
    await msg.answer(f"Timezone set to <code>{arg}</code>.")


# Re-export for use by other handlers without circular imports.
ensure_user = _ensure_user


def get_user_tz(user_id: int) -> str:
    with session_scope() as s:
        u = s.get(User, user_id)
        if u and u.timezone:
            return u.timezone
    return app_settings.default_timezone


def upsert_user_from_msg(msg: Message) -> None:
    with session_scope() as s:
        u = s.get(User, msg.from_user.id)
        if u is None:
            s.add(
                User(
                    id=msg.from_user.id,
                    username=msg.from_user.username,
                    full_name=msg.from_user.full_name,
                    timezone=app_settings.default_timezone,
                )
            )
        else:
            u.username = msg.from_user.username
            u.full_name = msg.from_user.full_name


def upsert_chat_from_msg(msg: Message) -> None:
    from app.models import Chat
    with session_scope() as s:
        c = s.get(Chat, msg.chat.id)
        if c is None:
            s.add(Chat(id=msg.chat.id, type=msg.chat.type, title=msg.chat.title))
        else:
            c.type = msg.chat.type
            c.title = msg.chat.title
