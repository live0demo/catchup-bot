"""Cache non-command group messages so /catchup has something to summarize.

Also auto-advances each sender's checkpoint: if a user sends a message in a
group, they were obviously present, so we treat everything up to and
including their message as "read" for them. Lurkers (who never speak) still
need to use /markread manually — Telegram does not expose true read state.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.handlers.settings import upsert_chat_from_msg, upsert_user_from_msg
from app.models import MessageCache
from app.services.checkpoint import get_or_create_state
from app.utils.timefmt import utcnow

router = Router(name="messages")
log = logging.getLogger(__name__)


def _is_command(text: str | None) -> bool:
    return bool(text) and text.lstrip().startswith("/")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def cache_group_message(msg: Message) -> None:
    text = msg.text or msg.caption
    if not text or _is_command(text):
        return
    if msg.from_user is None or msg.from_user.is_bot:
        return  # ignore service messages and other bots

    upsert_chat_from_msg(msg)
    upsert_user_from_msg(msg)

    user_name = msg.from_user.full_name or msg.from_user.username

    try:
        with session_scope() as s:
            s.add(
                MessageCache(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    user_id=msg.from_user.id,
                    user_name=user_name,
                    text=text,
                )
            )
    except IntegrityError:
        # Duplicate (chat_id, message_id): ignore.
        pass
    except Exception:  # noqa: BLE001
        log.exception("Failed to cache message")
        return

    # Auto-advance the sender's catch-up checkpoint. Only move forward.
    try:
        with session_scope() as s:
            st = get_or_create_state(s, msg.from_user.id, msg.chat.id)
            current = st.last_checkpoint_message_id or 0
            if msg.message_id > current:
                st.last_checkpoint_message_id = msg.message_id
                st.last_checkpoint_at = utcnow()
    except Exception:  # noqa: BLE001
        log.exception("Failed to auto-advance checkpoint")
