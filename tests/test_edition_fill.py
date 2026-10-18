"""Edition fill loop stop reasons and logging (#213)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pipeline.edition_fill import (
    STOP_MAX_ROUNDS,
    STOP_NO_PROGRESS,
    STOP_REACHED_TARGET,
    STOP_SPEND,
    STOP_WALL_TIME,
    STOP_WINDOW_EXHAUSTED,
    run_edition_fill_loop,
    trim_to_target,
)

_KEPT = (
    "City rents keep rising and the council vote next week will decide whether "
    "tenants get any real protection or another delay."
)


def _post(index: int) -> dict:
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    return {
        "uri": f"at://fixture/{index}",
        "author": "author",
        "text": f"{_KEPT} Post {index}.",
        "clean_text": f"{_KEPT} Post {index}.",
        "likes": 1,
        "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_claim": None,
        "section": "",
    }


def _settings():
    return {"window_hours": 168, "seed": 0, "free_ingest_per_day": 50}


def test_trim_to_target_uses_retire_ordering():
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    posts = [_post(index) for index in range(5)]
    for index, post in enumerate(posts):
        post["created_at"] = (
            moment.replace(hour=index).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    cleaned = list(posts)
    trimmed, kept = trim_to_target(
        cleaned,
        posts,
        target=3,
        window_hours=168,
        now=moment,
    )
    assert len(kept) == 3
    assert {post["uri"] for post in kept} == {
        "at://fixture/2",
        "at://fixture/3",
        "at://fixture/4",
    }
    assert len(trimmed) == 3


def test_stop_reached_target(monkeypatch):
    target = 5
    corpus = [_post(index) for index in range(8)]

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        return corpus[: max(target, 1)], False

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=target)
    assert result.stop_reason == STOP_REACHED_TARGET
    assert len(result.planet_posts) == target
    assert result.rounds[-1].edition_quality_count == target


def test_stop_spend(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: ([], False),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_SPEND
    assert result.planet_posts == []


def test_stop_wall_time(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.live.fill_past_safe_margin", lambda _now: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: ([], False),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_WALL_TIME


def test_stop_max_rounds(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "2")
    calls = {"n": 0}

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        calls["n"] += 1
        return [_post(calls["n"])], False

    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.live.fill_past_safe_margin", lambda _now: False)
    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_MAX_ROUNDS
    assert calls["n"] == 2


def test_stop_window_exhausted(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.live.fill_past_safe_margin", lambda _now: False)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: ([], True),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_WINDOW_EXHAUSTED


def test_stop_no_progress(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "10")
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.live.fill_past_safe_margin", lambda _now: False)
    same = [_post(1)]

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        return list(same), False

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=100_000)
    assert result.stop_reason == STOP_NO_PROGRESS
    assert len(result.rounds) >= 2


def test_pipeline_dict_includes_stop_reason(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: ([], False),
    )
    result = run_edition_fill_loop([], _settings(), None, target=50)
    payload = result.pipeline_dict()
    assert payload["edition_fill_stop_reason"] == STOP_SPEND
    assert "edition_fill_rounds" in payload
