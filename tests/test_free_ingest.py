"""Free ingest stays off unless the setting is on. No paid calls."""

from datetime import datetime, timezone

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
    monkeypatch.delenv("PERSPECTIVERSE_FREE_INGEST", raising=False)
    path = tmp_path / "pipeline.yaml"
    path.write_text("sample_size: 20\n", encoding="utf-8")
    settings = load_settings(path)
    assert settings["free_ingest"] is False
    assert free_ingest_enabled(settings) is False


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
