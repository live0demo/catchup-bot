"""Helpers for the checkpoint-based catch-up model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MessageCache, UserChatState
from app.services.summarizer import CachedMessage


def get_or_create_state(s: Session, user_id: int, chat_id: int) -> UserChatState:
    st = s.execute(
        select(UserChatState).where(
            UserChatState.user_id == user_id, UserChatState.chat_id == chat_id
        )
    ).scalar_one_or_none()
    if st is None:
        st = UserChatState(user_id=user_id, chat_id=chat_id)
        s.add(st)
        s.flush()
    return st


def latest_message_id(s: Session, chat_id: int) -> int | None:
    return s.execute(
        select(MessageCache.message_id)
        .where(MessageCache.chat_id == chat_id)
        .order_by(MessageCache.message_id.desc())
        .limit(1)
    ).scalar_one_or_none()


def messages_since_checkpoint(
    s: Session, chat_id: int, checkpoint_msg_id: int | None, limit: int = 500
) -> list[CachedMessage]:
    q = select(MessageCache).where(MessageCache.chat_id == chat_id)
    if checkpoint_msg_id is not None:
        q = q.where(MessageCache.message_id > checkpoint_msg_id)
    q = q.order_by(MessageCache.message_id.asc()).limit(limit)
    rows = s.execute(q).scalars().all()
    return [CachedMessage(user_name=r.user_name or "?", text=r.text) for r in rows]


def filter_since(messages: list[CachedMessage], checkpoint_index: int) -> list[CachedMessage]:
    """Pure helper used by tests: return messages strictly after the checkpoint index."""
    if checkpoint_index < 0:
        return list(messages)
    return messages[checkpoint_index + 1 :]


def cleanup_old_messages(s: Session, retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    res = s.query(MessageCache).filter(MessageCache.created_at < cutoff).delete()
    return int(res or 0)
