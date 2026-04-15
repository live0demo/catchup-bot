"""Optional LLM-backed summarizer. Falls back to local on any failure."""
from __future__ import annotations

import logging
from typing import Literal

import httpx

from app.config import settings
from app.services.summarizer import CachedMessage, local_summarize

log = logging.getLogger(__name__)

Style = Literal["short", "medium", "detailed"]


_PROMPT = (
    "You summarize a chat catch-up for a busy reader. "
    "Output sections in this exact order if applicable: "
    "Main topics; Decisions; Action items; Open questions. "
    "Use concise bullet points. Keep speaker attribution where it adds value. "
    "Style: {style}. "
    "Reply in HTML using only <b>, <i>, <code>; no other tags."
)


async def summarize(messages: list[CachedMessage], style: Style = "medium") -> str:
    if not settings.llm_enabled:
        return local_summarize(messages, style)
    try:
        return await _llm_summarize(messages, style)
    except Exception:  # noqa: BLE001
        log.exception("LLM summarization failed; falling back to local")
        return local_summarize(messages, style)


async def _llm_summarize(messages: list[CachedMessage], style: Style) -> str:
    transcript_lines = [f"{m.user_name}: {m.text}" for m in messages if m.text]
    if not transcript_lines:
        return local_summarize(messages, style)
    transcript = "\n".join(transcript_lines)[:14000]

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _PROMPT.format(style=style)},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()
