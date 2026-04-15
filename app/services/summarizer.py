"""Local extractive summarizer + small abstraction so an LLM can plug in."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal

Style = Literal["short", "medium", "detailed"]


@dataclass
class CachedMessage:
    user_name: str
    text: str


_QUESTION_RE = re.compile(r"\?\s*$")
_ACTION_RE = re.compile(
    r"\b(todo|to-do|action|let's|lets|we (?:should|need|must)|please|"
    r"i'll|i will|deadline|by (?:tomorrow|today|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|\d{1,2}(?:am|pm|:\d{2}))|due|assign(?:ed)? to)\b",
    re.IGNORECASE,
)
_DECISION_RE = re.compile(
    r"\b(decided|decision|agreed|we (?:will|are going to)|approved|reject(?:ed)?|"
    r"go(?:ing)? with|chose|picked|final(?:ize|ised|ized)?)\b",
    re.IGNORECASE,
)
_STOPWORDS = set(
    "the a an and or but of for to in on at by with from as is are was were be been "
    "being have has had do does did this that these those it its i you he she we they "
    "them my your our their his her not no yes if then so than too very can could "
    "would should will just about into over under up down out off only also".split()
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _word_freqs(messages: Iterable[CachedMessage]) -> Counter:
    counts: Counter = Counter()
    for m in messages:
        for w in re.findall(r"[a-zA-Z][a-zA-Z\-']{2,}", m.text.lower()):
            if w in _STOPWORDS:
                continue
            counts[w] += 1
    return counts


def _top_themes(freqs: Counter, k: int = 6) -> list[str]:
    return [w for w, _ in freqs.most_common(k)]


def local_summarize(messages: list[CachedMessage], style: Style = "medium") -> str:
    """Heuristic extractive summary. Always returns a non-empty, readable string."""
    msgs = [
        CachedMessage(user_name=m.user_name or "?", text=_normalize(m.text))
        for m in messages
        if _normalize(m.text or "")
    ]
    if not msgs:
        return "_No new messages since your last checkpoint._"

    questions: list[str] = []
    actions: list[str] = []
    decisions: list[str] = []
    digest_lines: list[str] = []

    for m in msgs:
        line = f"<b>{_html_escape(m.user_name)}</b>: {_html_escape(m.text)}"
        digest_lines.append(line)
        if _QUESTION_RE.search(m.text):
            questions.append(f"• {_html_escape(m.text)} — <i>{_html_escape(m.user_name)}</i>")
        if _ACTION_RE.search(m.text):
            actions.append(f"• {_html_escape(m.text)} — <i>{_html_escape(m.user_name)}</i>")
        if _DECISION_RE.search(m.text):
            decisions.append(f"• {_html_escape(m.text)} — <i>{_html_escape(m.user_name)}</i>")

    themes = _top_themes(_word_freqs(msgs))
    total = len(msgs)
    speakers = sorted({m.user_name for m in msgs})

    header = (
        f"📝 <b>Catch-up</b> — {total} message(s) "
        f"from {len(speakers)} speaker(s) "
        f"({', '.join(_html_escape(s) for s in speakers[:5])}"
        f"{', ...' if len(speakers) > 5 else ''})"
    )

    sections: list[str] = [header]

    if themes:
        sections.append("<b>Main topics</b>: " + ", ".join(_html_escape(t) for t in themes))

    if decisions:
        sections.append("<b>Decisions</b>\n" + "\n".join(_dedupe(decisions)[:8]))
    if actions:
        sections.append("<b>Action items</b>\n" + "\n".join(_dedupe(actions)[:10]))
    if questions:
        sections.append("<b>Open questions</b>\n" + "\n".join(_dedupe(questions)[:10]))

    if style == "short":
        # Header + topics + top action/decision/question only.
        short = sections[:2]
        for extra in sections[2:]:
            first_line = extra.split("\n", 1)
            if len(first_line) == 2:
                short.append(first_line[0] + "\n" + first_line[1].split("\n")[0])
        return "\n\n".join(short)

    if style == "detailed":
        digest = "<b>Chronological digest</b>\n" + "\n".join(
            f"{i+1}. {ln}" for i, ln in enumerate(digest_lines[:60])
        )
        sections.append(digest)
        if len(digest_lines) > 60:
            sections.append(f"<i>… {len(digest_lines) - 60} more message(s) trimmed.</i>")

    return "\n\n".join(sections)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
