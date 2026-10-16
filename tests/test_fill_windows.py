"""Fill-only Bluesky date windows. No network and no paid calls."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pipeline.live import (
    FILL_EMPTY_WINDOWS_STOP,
    FILL_JOB_MARGIN_MINUTES,
    PIPELINE_JOB_LIMIT_MINUTES,
    _collect_posts,
    _fill_claims_by_day,
    fill_past_safe_margin,
)
from pipeline.schema import SYSTEM_SIZE
from pipeline.settings import DEFAULTS
from pipeline.spend_cap import SpendCapExceeded


NOW = datetime(2026, 10, 16, 18, tzinfo=timezone.utc)


def _settings():
    return {
        "window_hours": 168,
        "refresh_hours": 24,
        "seed": 0,
        "neutral_queries": ["the", "and"],
        "catalog_size": 10,
    }


def _post(when: datetime, uri: str) -> dict:
    day = when.strftime("%Y-%m-%d")
    return {
        "uri": uri,
        "author": "ada",
        "text": f"The city should fund public housing on {day} because rents jumped again.",
        "likes": 2,
        "created_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _mark_claims(posts, **_kwargs):
    for post in posts:
        post["is_claim"] = True
        post["section"] = "Politics"
    return posts


def test_workflow_records_the_job_clock_before_live():
    from pathlib import Path

    import yaml

    document = yaml.safe_load(Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8"))
    steps = document["jobs"]["pipeline"]["steps"]
    names = [step.get("name") for step in steps]
    clock_at = names.index("Record job start for the fill time margin")
    live_at = next(index for index, step in enumerate(steps) if step.get("id") == "live")
    assert clock_at < live_at
    assert "PERSPECTIVERSE_JOB_STARTED_AT" in steps[clock_at]["run"]
    assert document["jobs"]["pipeline"]["timeout-minutes"] == 360


def test_ten_planet_cap_is_unchanged():
    assert SYSTEM_SIZE == 10
    assert DEFAULTS["catalog_size"] == 10


def test_fill_walks_older_utc_days_until_the_claim_target(monkeypatch, capsys):
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    seen = []

    def fake_extract(**kwargs):
        assert kwargs["pages"] == 40
        assert kwargs["subsample"] is False
        assert "since" not in kwargs or kwargs["since"] is not None
        since = kwargs["since"]
        until = kwargs["until"]
        assert until - since == timedelta(days=1)
        seen.append(since)
        created = since + timedelta(hours=12)
        return [_post(created, f"at://day/{since.date().isoformat()}")]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", _mark_claims)
    monkeypatch.setattr("pipeline.live.guard_before_paid_call", lambda _kind: None)
    claims, corpus, span = _fill_claims_by_day(
        [],
        target=3,
        settings=_settings(),
        connection=None,
        corpus_posts=[],
        now=NOW,
        clock=lambda: NOW,
    )
    assert [item.date().isoformat() for item in seen] == ["2026-10-16", "2026-10-15", "2026-10-14"]
    assert seen[1] == seen[0] - timedelta(days=1)
    assert {post["uri"] for post in claims} == {
        "at://day/2026-10-16",
        "at://day/2026-10-15",
        "at://day/2026-10-14",
    }
    assert span == int((NOW - seen[-1]).total_seconds() // 3600) + 24
    logged = capsys.readouterr().out
    assert "Fill window 2026-10-16T00:00:00Z .. 2026-10-17T00:00:00Z: 1 posts" in logged
    assert "3 claims so far" in logged
    assert "spend $0.00 of $15.00" in logged
    assert "Fill date range 2026-10-14T00:00:00Z .. 2026-10-17T00:00:00Z: 3 window(s)" in logged
    assert "stop: claim target" in logged
    assert corpus is not None and len(corpus) == 3


def test_fill_stops_before_a_paid_call_once_the_cap_is_reached(monkeypatch, capsys):
    scored = []

    def fake_extract(**kwargs):
        since = kwargs["since"]
        return [_post(since + timedelta(hours=3), f"at://day/{since.date().isoformat()}")]

    def guard(_kind):
        if len(scored) >= 1:
            raise SpendCapExceeded("fill cap", spent_usd=Decimal("15.00"))

    def jev(posts, **kwargs):
        scored.append(posts[0]["uri"])
        return _mark_claims(posts, **kwargs)

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", jev)
    monkeypatch.setattr("pipeline.live.guard_before_paid_call", guard)
    corpus: list[dict] = []
    with pytest.raises(SpendCapExceeded):
        _fill_claims_by_day(
            [],
            target=10,
            settings=_settings(),
            connection=None,
            corpus_posts=corpus,
            now=NOW,
            clock=lambda: NOW,
        )
    assert scored == ["at://day/2026-10-16"]
    assert [post["uri"] for post in corpus] == ["at://day/2026-10-16"]
    logged = capsys.readouterr().out
    assert "Fill window 2026-10-15T00:00:00Z .. 2026-10-16T00:00:00Z: 1 posts" in logged
    assert "stop: fill spend cap" in logged


def test_in_flight_window_stays_on_the_corpus_when_jev_hits_the_cap(monkeypatch):
    def fake_extract(**kwargs):
        since = kwargs["since"]
        return [_post(since + timedelta(hours=3), f"at://day/{since.date().isoformat()}")]

    def jev(posts, **_kwargs):
        if posts[0]["uri"].endswith("2026-10-15"):
            raise SpendCapExceeded("crossed", spent_usd=Decimal("15.00"))
        return _mark_claims(posts)

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", jev)
    monkeypatch.setattr("pipeline.live.guard_before_paid_call", lambda _kind: None)
    corpus: list[dict] = []
    with pytest.raises(SpendCapExceeded):
        _fill_claims_by_day(
            [],
            target=10,
            settings=_settings(),
            connection=None,
            corpus_posts=corpus,
            now=NOW,
            clock=lambda: NOW,
        )
    assert [post["uri"] for post in corpus] == ["at://day/2026-10-16", "at://day/2026-10-15"]
    assert corpus[0]["is_claim"] is True


def test_fill_stops_when_the_job_margin_is_gone(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_extract(**_kwargs):
        calls["n"] += 1
        raise AssertionError("no search once the job margin is gone")

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    started = NOW - timedelta(minutes=PIPELINE_JOB_LIMIT_MINUTES - FILL_JOB_MARGIN_MINUTES)
    monkeypatch.setenv("PERSPECTIVERSE_JOB_STARTED_AT", started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert fill_past_safe_margin(NOW) is True
    claims, _corpus, span = _fill_claims_by_day(
        [{"uri": "at://kept", "is_claim": True, "text": "already here"}],
        target=100,
        settings=_settings(),
        connection=None,
        corpus_posts=[{"uri": "at://kept", "is_claim": True, "text": "already here"}],
        now=NOW,
        clock=lambda: NOW,
    )
    assert calls["n"] == 0
    assert span == 0
    assert [post["uri"] for post in claims] == ["at://kept"]
    assert "45 minutes or less left" in capsys.readouterr().out


def test_fill_stops_after_one_window_when_the_clock_crosses_the_margin(monkeypatch, capsys):
    def fake_extract(**kwargs):
        since = kwargs["since"]
        return [_post(since + timedelta(hours=4), f"at://day/{since.date().isoformat()}")]

    monkeypatch.setenv("PERSPECTIVERSE_JOB_STARTED_AT", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))
    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", _mark_claims)
    monkeypatch.setattr("pipeline.live.guard_before_paid_call", lambda _kind: None)
    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        if ticks["n"] == 1:
            return NOW
        return NOW + timedelta(minutes=PIPELINE_JOB_LIMIT_MINUTES)

    claims, _corpus, span = _fill_claims_by_day(
        [],
        target=50,
        settings=_settings(),
        connection=None,
        corpus_posts=[],
        now=NOW,
        clock=clock,
    )
    assert [post["uri"] for post in claims] == ["at://day/2026-10-16"]
    assert span > 0
    assert "job time margin" in capsys.readouterr().out


def test_fill_stops_after_empty_days(monkeypatch, capsys):
    calls = []

    def fake_extract(**kwargs):
        calls.append(kwargs["since"])
        return []

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    claims, _corpus, span = _fill_claims_by_day(
        [],
        target=5,
        settings=_settings(),
        connection=None,
        corpus_posts=[],
        now=NOW,
        clock=lambda: NOW,
    )
    assert claims == []
    assert span == 0
    assert len(calls) == FILL_EMPTY_WINDOWS_STOP
    assert calls[0].date().isoformat() == "2026-10-16"
    assert calls[-1] == calls[0] - timedelta(days=FILL_EMPTY_WINDOWS_STOP - 1)
    logged = capsys.readouterr().out
    assert f"{FILL_EMPTY_WINDOWS_STOP} date windows" in logged
    assert "returned no posts" in logged


def test_resumed_fill_walks_past_already_seen_days(monkeypatch, capsys):
    """A corpus covering 20 UTC days must not trip the 14-empty-day stop.

    Those windows return posts that are already in the corpus. Only a search
    that returns nothing counts as empty, so the walk reaches an older day.
    Today is already on the corpus, so that redundant search is skipped.
    """
    span_days = 20
    covered = [(NOW - timedelta(days=offset)).date() for offset in range(span_days)]
    corpus = [
        _post(datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc), f"at://seen/{day.isoformat()}")
        for day in covered
    ]
    claims_in = [dict(post, is_claim=True, section="Politics") for post in corpus]
    calls = []
    scored = []

    def fake_extract(**kwargs):
        since = kwargs["since"]
        calls.append(since.date())
        day = since.date()
        if day in set(covered):
            return [_post(since + timedelta(hours=12), f"at://seen/{day.isoformat()}")]
        return [_post(since + timedelta(hours=12), f"at://new/{day.isoformat()}")]

    def jev(posts, **kwargs):
        scored.extend(post["uri"] for post in posts)
        return _mark_claims(posts, **kwargs)

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", jev)
    monkeypatch.setattr("pipeline.live.guard_before_paid_call", lambda _kind: None)
    claims, updated, span = _fill_claims_by_day(
        claims_in,
        target=len(claims_in) + 1,
        settings=_settings(),
        connection=None,
        corpus_posts=list(corpus),
        now=NOW,
        clock=lambda: NOW,
    )
    older = covered[-1] - timedelta(days=1)
    assert NOW.date() not in calls
    assert len(calls) > FILL_EMPTY_WINDOWS_STOP
    assert older in calls
    assert calls[-1] == older
    assert scored == [f"at://new/{older.isoformat()}"]
    assert f"at://new/{older.isoformat()}" in {post["uri"] for post in claims}
    assert span > 0
    assert updated is not None
    assert f"at://new/{older.isoformat()}" in {post["uri"] for post in updated}
    logged = capsys.readouterr().out
    assert f"Fill skipped {NOW.date().isoformat()}" in logged
    assert "none new" in logged
    assert "empty days" not in logged
    assert "stop: claim target" in logged


def test_scheduled_collect_does_not_walk_date_windows(monkeypatch, tmp_path):
    from pipeline.store import connect

    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    connection = connect(tmp_path / "live.db")

    def fake_extract(**kwargs):
        assert "since" not in kwargs
        assert "until" not in kwargs
        assert kwargs.get("pages") is None
        return [
            {
                "uri": "at://today",
                "author": "ada",
                "text": "People were arguing about the rent increase on my block again today.",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            }
        ]

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    cleaned, _source, refreshed = _collect_posts(
        [],
        _settings(),
        None,
        None,
        10,
        connection,
        now=NOW,
    )
    connection.close()
    assert refreshed is True
    assert [post["uri"] for post in cleaned] == ["at://today"]
