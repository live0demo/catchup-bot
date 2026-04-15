"""/ask — free-form Q&A backed by the configured LLM."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.config import settings
from app.services import llm

router = Router(name="ask")
log = logging.getLogger(__name__)


@router.message(Command("ask"))
async def ask(msg: Message, command: CommandObject) -> None:
    question = (command.args or "").strip()
    if not question:
        await msg.answer(
            "Usage: <code>/ask &lt;your question&gt;</code>\n"
            "Example: <code>/ask viết email xin nghỉ phép 2 ngày bằng tiếng Việt</code>"
        )
        return

    if not settings.llm_enabled:
        await msg.answer(
            "🤖 LLM is not configured.\n"
            "The bot owner must set <code>LLM_API_KEY</code> "
            "(see README — Groq / Gemini / OpenRouter all have free tiers)."
        )
        return

    if len(question) > 4000:
        await msg.answer("❌ Question too long (max 4000 chars).")
        return

    placeholder = await msg.answer("🤔 thinking…")
    try:
        answer = await llm.ask(question)
    except Exception as e:  # noqa: BLE001
        log.exception("LLM /ask failed")
        await placeholder.edit_text(
            f"❌ LLM error: <code>{type(e).__name__}</code>\n"
            "Check your <code>LLM_API_KEY</code> / model name / quota."
        )
        return

    # Telegram message limit is 4096 chars; HTML tags inflate length a bit.
    answer = answer[:3900]
    try:
        await placeholder.edit_text(answer)
    except Exception:  # noqa: BLE001
        # If LLM returned malformed HTML, edit will fail; fall back to plain text.
        log.exception("Failed to edit with HTML; sending plain text")
        await placeholder.edit_text(answer, parse_mode=None)
