"""Free ingest is the production path. No paid calls in these tests."""

from datetime import datetime, timedelta, timezone

import pytest

from pipeline.free_ingest import (
    FREE_INGEST_DAYS,
    WIDE_QUERIES,
    day_windows,
    free_ingest_enabled,
    ingest_free,
    paced_fetch,
    section_copies,
    stamp_candidate_sections,
)
from pipeline.jev import classify_planet_section, reset_jev_state
from pipeline.settings import load_settings


def test_free_ingest_defaults_off(tmp_path, monkeypatch):
    """A config that omits the key stays on the old path.

    Production does not omit it: ``pipeline.example.yaml`` sets it true, and
    the workflow sets ``PERSPECTIVERSE_FREE_INGEST`` to ``1`` or ``0``.
    """
    monkeypatch.delenv("PERSPECTIVERSE_FREE_INGEST", raising=False)
    path = tmp_path / "pipeline.yaml"
    path.write_text("sample_size: 20\n", encoding="utf-8")
    settings = load_settings(path)
    assert settings["free_ingest"] is False
    assert free_ingest_enabled(settings) is False


def test_example_config_is_on_and_zero_forces_the_old_path(monkeypatch):
    from pipeline.settings import EXAMPLE_PATH

    monkeypatch.delenv("PERSPECTIVERSE_FREE_INGEST", raising=False)
    assert load_settings(EXAMPLE_PATH)["free_ingest"] is True
    assert free_ingest_enabled(load_settings(EXAMPLE_PATH)) is True
    monkeypatch.setenv("PERSPECTIVERSE_FREE_INGEST", "0")
    assert load_settings(EXAMPLE_PATH)["free_ingest"] is False
    monkeypatch.setenv("PERSPECTIVERSE_FREE_INGEST", "false")
    assert load_settings(EXAMPLE_PATH)["free_ingest"] is False


def test_free_ingest_env_turns_it_on(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_FREE_INGEST", "1")
    path = tmp_path / "pipeline.yaml"
    path.write_text("free_ingest: false\n", encoding="utf-8")
    settings = load_settings(path)
    assert settings["free_ingest"] is True


def test_day_windows_stay_inside_seven_days():
    moment = datetime(2026, 10, 17, 15, tzinfo=timezone.utc)
    windows = day_windows(moment, FREE_INGEST_DAYS)
    assert len(windows) == 7
    assert windows[0][0] == datetime(2026, 10, 17, tzinfo=timezone.utc)
    assert windows[-1][0] == datetime(2026, 10, 11, tzinfo=timezone.utc)
    assert windows[0][1] - windows[-1][0] == __import__("datetime").timedelta(days=7)


def test_wide_queries_cover_more_than_the_neutral_six():
    assert WIDE_QUERIES[:6] == ("the", "and", "to", "of", "in", "for")
    assert len(WIDE_QUERIES) > 6


def test_ingest_free_stores_non_claims_and_drops_spam(monkeypatch):
    moment = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
    aside = {
        "uri": "at://aside",
        "author": "ada",
        "text": "I forgot to buy antihistamines and now I am restless.",
        "likes": 1,
        "created_at": "2026-10-17T01:00:00Z",
    }
    remark = {
        "uri": "at://remark",
        "author": "bea",
        "text": "The city should build public housing near the train station this year.",
        "likes": 2,
        "created_at": "2026-10-16T01:00:00Z",
    }
    spam = {
        "uri": "at://spam",
        "author": "bot",
        "text": "Now playing on KB Radio: Fantasy! Tune in now: https://radio.example/listen",
        "likes": 0,
        "created_at": "2026-10-17T02:00:00Z",
    }

    def fake_extract(**kwargs):
        assert kwargs["since"] is not None and kwargs["until"] is not None
        assert kwargs["pages"] == 40
        assert kwargs["subsample"] is False
        if kwargs["queries"] == ["the"] and kwargs["since"].date().isoformat() == "2026-10-17":
            return [aside, spam]
        if kwargs["queries"] == ["the"] and kwargs["since"].date().isoformat() == "2026-10-16":
            return [remark]
        return []

    kept = ingest_free(
        [],
        {"window_hours": 168, "seed": 0, "free_ingest_per_day": 5},
        ["the"],
        target=100,
        now=moment,
        extract=fake_extract,
        days=2,
    )
    uris = {post["uri"] for post in kept}
    assert uris == {"at://aside", "at://remark"}
    assert all(post["is_claim"] is None for post in kept)


def test_fetch_buckets_reconcile_to_fetched():
    from pipeline.chitchat_guard import get_chitchat_log, reset_chitchat_log

    moment = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
    shared = (
        "The city should build public housing near the train station this year "
        "because rents keep climbing for working families."
    )
    existing = [
        {
            "uri": "at://stored",
            "author": "ada",
            "text": shared,
            "likes": 1,
            "created_at": "2026-10-17T01:00:00Z",
        }
    ]

    def fake_extract(**kwargs):
        return [
            {
                "uri": "at://copy-text",
                "author": "bob",
                "text": shared,
                "likes": 1,
                "created_at": "2026-10-17T03:00:00Z",
            },
            {
                "uri": "at://fresh-one",
                "author": "cara",
                "text": "The school board should publish the safety audit before the bond vote next month.",
                "likes": 1,
                "created_at": "2026-10-17T04:00:00Z",
            },
            {
                "uri": "at://fresh-two",
                "author": "dan",
                "text": "The port expansion needs an independent review of environmental impacts this year.",
                "likes": 1,
                "created_at": "2026-10-17T05:00:00Z",
            },
        ]

    reset_chitchat_log()
    ingest_free(
        existing,
        {"window_hours": 168, "seed": 0, "free_ingest_per_day": 1},
        ["the"],
        target=100,
        now=moment,
        extract=fake_extract,
        days=1,
    )
    log = get_chitchat_log()
    assert log.buckets_reconcile()
    assert log.fetched == log.accounted_total()
    assert log.near_duplicate_blocked >= 1
    assert log.new_stored == 1
    assert log.over_daily_cap >= 1
    assert log.fetched == 3


def test_paced_fetch_backs_off_on_403(monkeypatch):
    calls = {"n": 0}

    def flaky(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("HTTP 403 from api.bsky.app")
        return {"posts": [], "cursor": None}

    monkeypatch.setattr("pipeline.free_ingest._default_fetch", flaky)
    monkeypatch.setattr("pipeline.free_ingest.time.sleep", lambda _seconds: None)
    assert paced_fetch("the", None, 10) == {"posts": [], "cursor": None}
    assert calls["n"] == 2


def test_stamp_is_one_call_per_candidate_planet():
    posts = [
        {"text": "rent is too high in the city", "clean_text": "rent is too high in the city"},
        {"text": "the senate vote is next week", "clean_text": "the senate vote is next week"},
        {"text": "the quarterback threw two picks", "clean_text": "the quarterback threw two picks"},
    ]
    clustered = {
        "topics": [
            {"terms": ["rent"], "member_indices": [0, 1]},
            {"terms": ["game"], "member_indices": [2]},
        ]
    }
    seen = []

    def classify(summary, arguments):
        seen.append((summary, arguments))
        return "Sports" if "quarterback" in arguments else "Politics"

    calls = stamp_candidate_sections(posts, clustered, classify)
    assert calls == 2
    assert len(seen) == 2
    assert posts[0]["section"] == "Politics"
    assert posts[2]["section"] == "Sports"


def test_section_copies_do_not_rename_the_global_planet():
    topics = [{"id": 1, "category": "Health", "perspectives": [{"id": "1a"}]}]
    grouped = section_copies(topics)
    grouped["Health"][0]["id"] = "Health-1"
    assert topics[0]["id"] == 1


def test_classify_planet_section_skips_the_network_without_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    reset_jev_state()

    def boom(_body):
        raise AssertionError("Jev was called")

    monkeypatch.setattr("pipeline.jev._post_systemone", boom)
    assert classify_planet_section("housing", "rent is too high") is None


def test_classify_planet_section_is_one_request(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-used")
    reset_jev_state()
    calls = []

    def fake(body):
        calls.append(body)
        return {
            "model": "jev-test",
            "answers": {"section": {"type": "choice", "choice": "Politics", "confidence": 0.9}},
        }

    monkeypatch.setattr("pipeline.jev._post_systemone", fake)
    assert classify_planet_section("election", "the senate should vote") == "Politics"
    assert len(calls) == 1
    assert "section" in calls[0]["questions"]
    assert "spam" not in calls[0]["questions"]


def test_run_live_free_ingest_does_not_call_per_post_jev(monkeypatch, tmp_path):
    from pipeline.live import run_live
    from tests.corpus import build_tiny_posts

    posts = build_tiny_posts()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for post in posts:
        post["created_at"] = now
        post["clean_text"] = post["text"]
        post["is_claim"] = None
    aside = {
        "uri": "at://fixture/aside",
        "author": "aside.person",
        "text": "I just want a quiet evening and a long walk after dinner tonight.",
        "clean_text": "I just want a quiet evening and a long walk after dinner tonight.",
        "likes": 1,
        "created_at": now,
        "is_claim": None,
    }
    posts.append(aside)

    def fake_ingest(*_args, **_kwargs):
        return list(posts)

    def boom_jev(*_args, **_kwargs):
        raise AssertionError("per-post Jev must not run when free ingest is on")

    monkeypatch.setattr("pipeline.live.ingest_free", fake_ingest)
    monkeypatch.setattr("pipeline.live.apply_jev", boom_jev)
    monkeypatch.setattr("pipeline.live.classify_planet_section", lambda _summary, _arguments: "Politics")
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "\n".join(
            [
                "free_ingest: true",
                "min_cluster_size: 8",
                "cluster_backend: lexical",
                "label_backend: heuristic",
                "sample_size: 200",
                "window_hours: 168",
                "representative_posts: 12",
                "seed: 0",
                "catalog_size: 10",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "data.json"
    run_live(output=output, config=config, db_path=tmp_path / "live.db")
    import json
    import sqlite3

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "live"
    connection = sqlite3.connect(tmp_path / "live.db")
    rows = connection.execute("SELECT uri, is_claim FROM posts").fetchall()
    connection.close()
    stored = {uri: claim for uri, claim in rows}
    assert "at://fixture/aside" in stored
    assert stored["at://fixture/aside"] is None
    assert any(topic.get("category") == "Politics" for topic in payload["topics"])
    stages = json.loads((tmp_path / "free_ingest_stages.json").read_text(encoding="utf-8"))
    assert stages["jev_planet_label_calls"] >= 1
    assert "cluster" in stages["wall_seconds"]
    assert "label" in stages["wall_seconds"]


def test_preview_summary_counts_days_planets_and_jev_dollars(tmp_path):
    import json
    import sqlite3

    from pipeline.free_ingest_preview import build_summary, write_preview

    data = {
        "topics": [{"category": "Politics"}, {"category": "Health"}],
        "sections": {"Politics": [{"category": "Politics"}]},
    }
    (tmp_path / "data.json").write_text(json.dumps(data), encoding="utf-8")
    db = tmp_path / "live.db"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE posts (created_at TEXT)")
    connection.executemany(
        "INSERT INTO posts (created_at) VALUES (?)",
        [("2026-10-16T01:00:00Z",), ("2026-10-16T02:00:00Z",), ("2026-10-17T03:00:00Z",), ("",)],
    )
    connection.commit()
    connection.close()
    cost = {
        "rows": [
            {"service": "typesafe-jev", "calls": 4, "cost_usd": "0.0300"},
            {"service": "deepinfra", "calls": 9, "cost_usd": "0.2000"},
        ]
    }
    stages = {"wall_seconds": {"ingest": 1.25, "cluster": 3}, "jev_planet_label_calls": 4}
    summary = build_summary(
        data=data,
        posts_by_day={"2026-10-16": 2, "2026-10-17": 1, "unknown": 1},
        cost=cost,
        stages=stages,
    )
    assert summary["posts_per_utc_day"]["2026-10-16"] == 2
    assert summary["post_count"] == 4
    assert summary["planet_count"] == 3
    assert summary["jev_planet_label_calls"] == 4
    assert summary["jev_planet_label_usd"] == "0.03"
    assert summary["wall_seconds"] == {"ingest": 1.25, "cluster": 3.0}
    assert "deepinfra" not in json.dumps(summary)

    out = tmp_path / "preview"
    (tmp_path / "cost.json").write_text(json.dumps(cost), encoding="utf-8")
    (tmp_path / "stages.json").write_text(json.dumps(stages), encoding="utf-8")
    write_preview(
        out,
        data_path=tmp_path / "data.json",
        db_path=db,
        cost_path=tmp_path / "cost.json",
        stages_path=tmp_path / "stages.json",
    )
    written = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert written["posts_per_utc_day"] == {"2026-10-16": 2, "2026-10-17": 1, "unknown": 1}
    assert json.loads((out / "data.json").read_text(encoding="utf-8"))["topics"]


def test_preview_ledger_records_spend_without_publishing_the_edition(monkeypatch, tmp_path):
    from pipeline import spend_cap

    seen = {}

    def fake(repo, run_file, *, push, commit_message, log_prefix, attempts=4):
        seen["repo"] = repo
        seen["run_file"] = run_file
        seen["push"] = push
        seen["message"] = commit_message
        seen["prefix"] = log_prefix
        return 0

    monkeypatch.setattr(spend_cap, "_commit_ledger_with_push_retry", fake)
    cost = tmp_path / "cost_run.json"
    assert spend_cap.record_preview_ledger(tmp_path, push=True, cost_run=cost) == 0
    assert seen["push"] is True
    assert seen["run_file"] == cost
    assert "edition not published" in seen["message"]
    assert "data.json" not in seen["message"]


_KEPT_TEXT = "The city should build public housing near the train station this year."


def _planet():
    return {
        "id": 1,
        "name": "Public housing",
        "category": "Politics",
        "total_volume_percent": 100.0,
        "brief": "The city should build public housing near the station.",
        "detail": "Posts argue the city should build public housing near the train station this year.",
        "perspectives": [
            {
                "id": "1a",
                "title": "Build the housing",
                "summary": "The city should build public housing near the train station.",
                "volume_percent": 100.0,
                "representative_posts": [
                    {"author": "ada", "text": _KEPT_TEXT, "likes": 1},
                ],
            }
        ],
    }


def _seed_posts(db, count, *, scored: bool, old_uri: str):
    from pipeline.store import connect, replace_posts

    moment = datetime.now(timezone.utc)
    recent = (moment - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (moment - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = [
        {
            "uri": f"at://seed/{index}",
            "author": f"user{index % 40}",
            "text": _KEPT_TEXT,
            "clean_text": _KEPT_TEXT,
            "likes": 1,
            "created_at": recent,
            "section": "Politics" if scored else "",
            "section_confidence": 0.9 if scored else None,
            "spam_score": 0.1 if scored else None,
            "is_claim": True if scored else None,
        }
        for index in range(count)
    ]
    posts.append(
        {
            "uri": old_uri,
            "author": "old",
            "text": _KEPT_TEXT,
            "clean_text": _KEPT_TEXT,
            "likes": 1,
            "created_at": old,
            "section": "Politics" if scored else "",
            "section_confidence": 0.9 if scored else None,
            "spam_score": 0.1 if scored else None,
            "is_claim": True if scored else None,
        }
    )
    connection = connect(db)
    replace_posts(connection, posts)
    connection.close()


def _run_schedule_like(monkeypatch, tmp_path, *, env):
    """Run ``run_live`` the way the workflow's live step loads settings."""
    from pipeline.live import run_live
    from pipeline.spend_cap import reset_day_state

    reset_day_state()
    monkeypatch.setenv("PERSPECTIVERSE_FREE_INGEST", env)
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_COST_LEDGER", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    handed = []
    planet_calls = []
    topups = []

    def apply_jev(posts, **_kwargs):
        handed.append(list(posts))
        return list(posts)

    def topup(*_args, **_kwargs):
        topups.append(1)
        raise AssertionError("old-path top-up ran")

    def classify(_summary, _arguments):
        planet_calls.append(1)
        return "Politics"

    def per_post(*_args, **_kwargs):
        raise AssertionError("per-post Jev request")

    monkeypatch.setattr("pipeline.live.apply_jev", apply_jev)
    monkeypatch.setattr("pipeline.live._topup_claims", topup)
    monkeypatch.setattr("pipeline.live.classify_planet_section", classify)
    monkeypatch.setattr("pipeline.jev._classify_post", per_post)
    monkeypatch.setattr("pipeline.jev._classify_batched", per_post)
    monkeypatch.setattr("pipeline.jev._post_systemone", per_post)
    monkeypatch.setattr(
        "pipeline.live.cluster_texts",
        lambda texts, **_kwargs: {
            "topics": [{"terms": ["city"], "member_indices": [0], "size": 1}],
            "noise_count": 0,
            "matrix": None,
        },
    )

    def build(*_args, **_kwargs):
        return [_planet()], [], []

    monkeypatch.setattr("pipeline.live._build_topics", build)
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "\n".join(
            [
                "free_ingest: false",
                "window_hours: 168",
                "seed: 0",
                "catalog_size: 10",
                "min_cluster_size: 5",
                "cluster_backend: lexical",
                "label_backend: heuristic",
                "representative_posts: 12",
            ]
        ),
        encoding="utf-8",
    )
    run_live(output=tmp_path / "data.json", config=config, db_path=tmp_path / "live.db")
    return handed, planet_calls, topups


@pytest.mark.parametrize(
    ("count", "scored", "expect_fetch"),
    [
        (8_500, True, True),
        (100_000, False, False),
    ],
)
def test_default_schedule_path_makes_zero_per_post_jev_calls(
    monkeypatch, tmp_path, count, scored, expect_fetch
):
    """The schedule env must not reach ``apply_jev`` on stored or fetched posts.

    8,500 scored rows are the Oct 17 corpus shape: the old path would still
    fetch the gap to 100K and score that morning batch before any top-up.
    100,000 unscored rows are a free-ingest publish: the old path would score
    them in that same ``apply_jev`` and hit the $1 stop.
    """
    import sqlite3

    old_uri = "at://seed/too-old"
    _seed_posts(tmp_path / "live.db", count, scored=scored, old_uri=old_uri)
    fetched = {"n": 0}

    def fake_extract(**_kwargs):
        fetched["n"] += 1
        if fetched["n"] == 1:
            return [
                {
                    "uri": "at://fetched/new",
                    "author": "new",
                    "text": (
                        "The port authority should publish the dredging study "
                        "before the bond vote next month."
                    ),
                    "likes": 1,
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            ]
        return []

    monkeypatch.setattr("pipeline.free_ingest.extract_posts", fake_extract)
    handed, planet_calls, topups = _run_schedule_like(monkeypatch, tmp_path, env="1")
    assert handed == []
    assert topups == []
    assert planet_calls == [1]
    assert (fetched["n"] > 0) is expect_fetch
    connection = sqlite3.connect(tmp_path / "live.db")
    rows = {
        uri: claim
        for uri, claim in connection.execute("SELECT uri, is_claim FROM posts")
    }
    connection.close()
    assert old_uri not in rows
    assert "at://seed/0" in rows
    assert rows["at://seed/0"] is None
    if expect_fetch:
        assert "at://fetched/new" in rows
        assert rows["at://fetched/new"] is None
        assert len(rows) == count + 1
    else:
        assert "at://fetched/new" not in rows
        assert len(rows) == count


def test_legacy_env_still_reaches_apply_jev_on_stored_posts(monkeypatch, tmp_path):
    """``PERSPECTIVERSE_FREE_INGEST=0`` is the explicit old path, not the default.

    The morning fetch is mocked. ``_collect_posts`` skips that fetch only when
    a stored post is dated today and today is already in the ledger. The seed
    is two hours old, so after UTC midnight the skip misses, a real Bluesky
    response sets ``refreshed``, and the legacy ``_topup_claims`` runs because
    the corpus is under the target. That gate is the same code as on
    ``74e24c5``. An empty mock keeps the fetch from deciding the result.
    """
    from pipeline.store import connect, record_fetched_days

    def fake_extract(**_kwargs):
        return []

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    _seed_posts(tmp_path / "live.db", 3, scored=True, old_uri="at://seed/too-old")
    moment = datetime.now(timezone.utc)
    connection = connect(tmp_path / "live.db")
    record_fetched_days(
        connection,
        [moment.date().isoformat()],
        fetched_at=moment.isoformat(),
        kept=3,
    )
    connection.close()
    handed, planet_calls, topups = _run_schedule_like(monkeypatch, tmp_path, env="0")
    assert len(handed) == 1
    assert len(handed[0]) >= 3
    assert all(post.get("is_claim") is True for post in handed[0])
    assert planet_calls == []
    assert topups == []


def test_free_path_day_cost_is_planet_labels_not_stored_posts():
    """755 planet calls stay under $1. Scoring 100K stored posts does not."""
    import json
    from decimal import Decimal
    from pathlib import Path

    from pipeline.costs import JEV_USD_PER_MILLION_INPUT_TOKENS

    evidence = json.loads(Path("docs/evidence/issue-192/speed_test.json").read_text(encoding="utf-8"))
    planets = int(evidence["planet_build"]["candidate_planets"])
    per_call = Decimal(str(evidence["planet_build"]["usd_per_call"]))
    measured = Decimal(planets) * per_call
    # 490 input tokens is the logged planet-section projection (DECISIONS 2026-10-08).
    token_usd = Decimal(planets * 490) * JEV_USD_PER_MILLION_INPUT_TOKENS / Decimal(1_000_000)
    labels = Decimal("0.13")
    assert planets == 755
    assert measured == Decimal("0.020989")
    assert token_usd < Decimal("0.02")
    assert measured + labels < Decimal("1")
    assert Decimal(100_000) * per_call > Decimal("2.70")
    assert evidence["search"]["elapsed_seconds"] < 3600
    assert evidence["planet_build"]["seconds"] < 3600
