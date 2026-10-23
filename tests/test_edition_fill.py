"""Edition fill loop stop reasons and logging (#213)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pipeline.edition_fill import (
    STOP_EDITION_GAP,
    STOP_MAX_ROUNDS,
    STOP_NO_PROGRESS,
    STOP_REACHED_TARGET,
    STOP_SPEND,
    STOP_WALL_TIME,
    STOP_WINDOW_EXHAUSTED,
    edition_fill_past_safe_margin,
    run_edition_fill_loop,
    trim_to_target,
)

_KEPT = (
    "City rents keep rising and the council vote next week will decide whether "
    "tenants get any real protection or another delay."
)


def _post(index: int, *, moment: datetime | None = None) -> dict:
    when = moment or datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    return {
        "uri": f"at://fixture/{index}",
        "author": "author",
        "text": f"{_KEPT} Post {index}.",
        "clean_text": f"{_KEPT} Post {index}.",
        "likes": 1,
        "created_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_claim": None,
        "section": "",
    }


def _settings():
    return {"window_hours": 168, "seed": 0, "free_ingest_per_day": 50}


def _ingest_result(posts, exhausted=False, near_dup=0):
    return list(posts), exhausted, near_dup


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
        clock=lambda: moment,
    )
    assert len(kept) == 3
    assert {post["uri"] for post in kept} == {
        "at://fixture/2",
        "at://fixture/3",
        "at://fixture/4",
    }
    assert len(trimmed) == 3


def test_trim_keeps_link_only_in_stored_corpus_when_ingest_switch_off(monkeypatch):
    monkeypatch.setenv("DROP_LINK_AND_LANGUAGE_AT_INGEST", "0")
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    edition = [_post(index, moment=moment) for index in range(6)]
    link_only = {
        "uri": "at://fixture/link",
        "author": "author",
        "text": "https://example.com/report",
        "clean_text": "https://example.com/report",
        "likes": 1,
        "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_claim": None,
        "section": "",
    }
    cleaned = edition + [link_only]
    aligned, edition_kept = trim_to_target(
        cleaned,
        edition,
        target=4,
        window_hours=168,
        clock=lambda: moment,
    )
    assert len(edition_kept) == 4
    assert "at://fixture/link" in {post["uri"] for post in aligned}


def test_stop_reached_target(monkeypatch):
    target = 5
    corpus = [_post(index) for index in range(8)]

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        return _ingest_result(corpus[: max(target, 1)])

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    # Pin the clock to the fixture posts' date; on the real clock they leave the
    # 168-hour window on 2026-10-24 12:00 UTC and the loop never reaches target.
    result = run_edition_fill_loop(
        [], _settings(), None, target=target, now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    )
    assert result.stop_reason == STOP_REACHED_TARGET
    assert len(result.planet_posts) == target
    assert result.rounds[-1].edition_quality_count == target


def test_stop_spend(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result([]),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_SPEND
    assert result.planet_posts == []


def test_stop_wall_time(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result([]),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_WALL_TIME


def test_stop_wall_time_mid_loop_with_advancing_clock(monkeypatch):
    base = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)
    state = {"now": base}
    monkeypatch.setenv("PERSPECTIVERSE_JOB_STARTED_AT", base.isoformat())
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)

    def clock() -> datetime:
        return state["now"]

    calls = {"n": 0}

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        calls["n"] += 1
        state["now"] = base + timedelta(minutes=261)
        return _ingest_result([_post(calls["n"])])

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=100, clock=clock)
    assert result.stop_reason == STOP_WALL_TIME
    assert calls["n"] == 1
    assert edition_fill_past_safe_margin(clock)


def test_stop_max_rounds(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "2")
    calls = {"n": 0}

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        calls["n"] += 1
        return _ingest_result([_post(calls["n"])])

    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: False)
    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_MAX_ROUNDS
    assert calls["n"] == 2


def test_stop_window_exhausted(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: False)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result([], exhausted=True),
    )
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.stop_reason == STOP_WINDOW_EXHAUSTED


def test_stop_no_progress(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "10")
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: False)
    same = [_post(1)]

    def fake_ingest(existing, settings, queries, *, target, now=None, reset_log=True, **kwargs):
        return _ingest_result(list(same))

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", fake_ingest)
    result = run_edition_fill_loop([], _settings(), None, target=100_000)
    assert result.stop_reason == STOP_NO_PROGRESS
    assert len(result.rounds) >= 2


def test_trim_undershoot_does_not_report_reached(monkeypatch):
    """Re-measure after trim: old posts can leave the edition short of target."""
    target = 5
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    fresh = [_post(index, moment=moment) for index in range(7)]
    measures = {"n": 0}

    def fake_measure(cleaned, **kwargs):
        measures["n"] += 1
        meta = {
            "before_language_filter": len(fresh),
            "skipped_non_english": 0,
            "skipped_link_only": 0,
            "skipped_chitchat_cluster_pass": 0,
        }
        if measures["n"] <= 2:
            return list(fresh), meta
        return fresh[:3], meta

    monkeypatch.setattr("pipeline.edition_fill.measure_edition", fake_measure)
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: False)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result(fresh),
    )
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "1")
    result = run_edition_fill_loop([], _settings(), None, target=target, clock=lambda: moment)
    assert result.stop_reason == STOP_MAX_ROUNDS
    assert len(result.planet_posts) < target


def test_pipeline_dict_includes_stop_reason(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: True)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result([]),
    )
    result = run_edition_fill_loop([], _settings(), None, target=50)
    payload = result.pipeline_dict()
    assert payload["edition_fill_stop_reason"] == STOP_SPEND
    assert "edition_fill_rounds" in payload


def test_switch_off_no_ingest_when_link_only_fill_clustering_gap(monkeypatch):
    """80 edition + 20 link-only stored: main does not fetch (shortfall 0)."""
    monkeypatch.setenv("DROP_LINK_AND_LANGUAGE_AT_INGEST", "0")
    moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    edition = [_post(index, moment=moment) for index in range(80)]
    link_only = [
        {
            "uri": f"at://fixture/link/{index}",
            "author": "author",
            "text": "https://example.com/report",
            "clean_text": "https://example.com/report",
            "likes": 1,
            "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "is_claim": None,
            "section": "",
        }
        for index in range(20)
    ]
    corpus = edition + link_only
    ingest_calls: list[int] = []

    def track_ingest(*_args, **_kwargs):
        ingest_calls.append(1)
        return _ingest_result(corpus)

    monkeypatch.setattr("pipeline.edition_fill.ingest_free", track_ingest)
    result = run_edition_fill_loop(corpus, _settings(), None, target=100, clock=lambda: moment)
    assert ingest_calls == []
    assert len(result.planet_posts) == 80
    assert result.stop_reason == STOP_EDITION_GAP
    assert result.stop_reason != STOP_REACHED_TARGET


def test_near_duplicate_count_on_round_line(monkeypatch):
    monkeypatch.setattr("pipeline.edition_fill.at_spend_stop", lambda: False)
    monkeypatch.setattr("pipeline.edition_fill.edition_fill_past_safe_margin", lambda _clock: False)
    monkeypatch.setattr(
        "pipeline.edition_fill.ingest_free",
        lambda *args, **kwargs: _ingest_result([_post(1)], near_dup=7),
    )
    monkeypatch.setenv("PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS", "1")
    result = run_edition_fill_loop([], _settings(), None, target=100)
    assert result.rounds[0].near_duplicate_dropped == 7
