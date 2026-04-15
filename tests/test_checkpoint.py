"""Tests for the pure checkpoint-filter helper.

The DB-backed version uses identical logic but exists in a SQLAlchemy session;
we test the pure helper to keep the unit test fast and independent.
"""
from __future__ import annotations

from app.services.checkpoint import filter_since
from app.services.summarizer import CachedMessage


MSGS = [CachedMessage("U", f"m{i}") for i in range(5)]


def test_no_checkpoint_returns_all():
    out = filter_since(MSGS, checkpoint_index=-1)
    assert [m.text for m in out] == [f"m{i}" for i in range(5)]


def test_checkpoint_at_start():
    # checkpoint at index 0 means "everything strictly after m0".
    out = filter_since(MSGS, checkpoint_index=0)
    assert [m.text for m in out] == ["m1", "m2", "m3", "m4"]


def test_checkpoint_at_end_returns_nothing():
    out = filter_since(MSGS, checkpoint_index=4)
    assert out == []


def test_checkpoint_past_end_returns_nothing():
    out = filter_since(MSGS, checkpoint_index=99)
    assert out == []


def test_middle_checkpoint():
    out = filter_since(MSGS, checkpoint_index=2)
    assert [m.text for m in out] == ["m3", "m4"]
