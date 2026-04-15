"""Tests for the local extractive summarizer."""
from __future__ import annotations

from app.services.summarizer import CachedMessage, local_summarize


def _msgs():
    return [
        CachedMessage("Alice", "Should we ship the new dashboard on Friday?"),
        CachedMessage("Bob", "Yes — let's go with the chart library we discussed."),
        CachedMessage("Carol", "Decision: we will use ApexCharts for v1."),
        CachedMessage("Bob", "I will write the migration script by tomorrow."),
        CachedMessage("Alice", "Who owns the QA pass?"),
        CachedMessage("Carol", "TODO: Bob to set up CI for the new package."),
    ]


def test_empty_input():
    out = local_summarize([], style="medium")
    assert "No new messages" in out


def test_medium_summary_has_sections():
    out = local_summarize(_msgs(), style="medium")
    assert "Catch-up" in out
    assert "Main topics" in out
    assert "Decisions" in out
    assert "Action items" in out
    assert "Open questions" in out


def test_short_summary_is_shorter_than_detailed():
    msgs = _msgs()
    short = local_summarize(msgs, style="short")
    detailed = local_summarize(msgs, style="detailed")
    assert len(short) < len(detailed)
    # Detailed includes the chronological digest.
    assert "Chronological digest" in detailed
    assert "Chronological digest" not in short


def test_html_is_escaped():
    out = local_summarize(
        [CachedMessage("Eve", "I <3 reading <script> tags & ampersands?")],
        style="detailed",
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp;" in out


def test_actions_detected():
    msgs = [
        CachedMessage("Bob", "I will write the migration script by tomorrow."),
        CachedMessage("Carol", "Random unrelated chatter goes here."),
    ]
    out = local_summarize(msgs, style="medium")
    assert "Action items" in out
    assert "migration script" in out
