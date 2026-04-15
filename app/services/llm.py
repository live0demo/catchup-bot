"""Optional LLM-backed features (summaries + free-form Q&A).

Works with any OpenAI-compatible Chat Completions endpoint:
  - OpenAI:        https://api.openai.com/v1
  - Groq:          https://api.groq.com/openai/v1
  - OpenRouter:    https://openrouter.ai/api/v1
  - Google Gemini: https://generativelanguage.googleapis.com/v1beta/openai
  - Mistral:       https://api.mistral.ai/v1

Configured via LLM_API_KEY / LLM_BASE_URL / LLM_MODEL env vars.
Falls back to the local extractive summarizer on any failure.
"""
from __future__ import annotations

import logging
from typing import Literal

import httpx

from app.config import settings
from app.services.summarizer import CachedMessage, local_summarize

log = logging.getLogger(__name__)

Style = Literal["short", "medium", "detailed"]


_SUMMARY_PROMPT = (
    "You summarize a chat catch-up for a busy reader. "
    "Output sections in this exact order if applicable: "
    "Main topics; Decisions; Action items; Open questions. "
    "Use concise bullet points. Keep speaker attribution where it adds value. "
    "Style: {style}. "
    "Reply in HTML using only <b>, <i>, <code>; no other tags. "
    "{language_hint}"
)

_ASK_PROMPT = (
    "You are a concise, helpful assistant inside a Telegram chat. "
    "Reply in the same language as the user's question. "
    "Keep answers under 3500 characters. "
    "Format with HTML using only <b>, <i>, <code>, <pre>; no other tags. "
    "{language_hint}"
)


def _language_hint() -> str:
    lang = (settings.summary_language or "").strip()
    if not lang or lang.lower() == "auto":
        return "If the user/transcript language is clear, reply in that same language."
    return f"Reply in {lang}."


async def summarize(messages: list[CachedMessage], style: Style = "medium") -> str:
    if not settings.llm_enabled:
        return local_summarize(messages, style)
    try:
        return await _llm_summarize(messages, style)
    except Exception:  # noqa: BLE001
        log.exception("LLM summarization failed; falling back to local")
        return local_summarize(messages, style)


async def ask(question: str) -> str:
    """Free-form Q&A. Caller must check settings.llm_enabled first."""
    return await _chat_completion(
        [
            {"role": "system", "content": _ASK_PROMPT.format(language_hint=_language_hint())},
            {"role": "user", "content": question},
        ]
    )


async def _llm_summarize(messages: list[CachedMessage], style: Style) -> str:
    transcript_lines = [f"{m.user_name}: {m.text}" for m in messages if m.text]
    if not transcript_lines:
        return local_summarize(messages, style)
    transcript = "\n".join(transcript_lines)[:14000]

    return await _chat_completion(
        [
            {
                "role": "system",
                "content": _SUMMARY_PROMPT.format(
                    style=style, language_hint=_language_hint()
                ),
            },
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ]
    )


async def _chat_completion(messages: list[dict]) -> str:
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()
