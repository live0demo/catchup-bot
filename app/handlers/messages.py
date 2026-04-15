"""Cache non-command group messages so /catchup has something to summarize."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.handlers.settings import upsert_chat_from_msg
from app.models import MessageCache

router = Router(name="messages")
log = logging.getLogger(__name__)


def _is_command(text: str | None) -> bool:
    return bool(text) and text.lstrip().startswith("/")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def cache_group_message(msg: Message) -> None:
    text = msg.text or msg.caption
    if not text or _is_command(text):
        return

    upsert_chat_from_msg(msg)

    user_name = (
        msg.from_user.full_name
        if msg.from_user and msg.from_user.full_name
        else (msg.from_user.username if msg.from_user else None)
    )

    try:
        with session_scope() as s:
            s.add(
                MessageCache(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    user_id=msg.from_user.id if msg.from_user else None,
                    user_name=user_name,
                    text=text,
                )
            )
    except IntegrityError:
        # Duplicate (chat_id, message_id): ignore.
        pass
    except Exception:  # noqa: BLE001
        log.exception("Failed to cache message")
