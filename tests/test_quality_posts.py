"""Quality posts are the only rows inserted. No paid calls."""

from datetime import datetime, timedelta, timezone

from pipeline.corpus_persist import persist_paid_corpus
from pipeline.jev import apply_jev, known_scored_uris, reset_jev_state
from pipeline.costs import reset_meter
from pipeline.free_ingest import prepare_post, refresh_carried_posts
from pipeline.store import (
    connect,
    drop_non_quality_posts,
    load_posts,
    replace_posts,
    save_jev_verdicts,
    should_drop_stored_post,
    write_quality_posts,
)


def _post(uri: str, *, claim: bool | None, spam: float | None = None, text: str | None = None) -> dict:
    body = text or f"The city should fund public housing because rents jumped again {uri}."
    post = {
        "uri": uri,
        "author": "ada",
        "text": body,
        "clean_text": body,
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
    }
    if claim is not None:
        post["is_claim"] = claim
        post["section"] = "Politics"
    if spam is not None:
        post["spam_score"] = spam
    return post


def _uris(connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT uri FROM posts")}


def test_write_quality_posts_skips_spam_and_non_claims(tmp_path):
    connection = connect(tmp_path / "corpus.db")
    write_quality_posts(
        connection,
        [
            _post("at://claim", claim=True, spam=0.1),
            _post("at://aside", claim=False, spam=0.1),
            _post("at://spam", claim=True, spam=0.95),
            _post("at://unscored", claim=None),
        ],
    )
    assert _uris(connection) == {"at://claim"}
    connection.close()


def test_cleanup_keeps_cached_non_claims_drops_spam_and_filters(tmp_path):
    connection = connect(tmp_path / "corpus.db")
    replace_posts(
        connection,
        [
            _post("at://claim", claim=True, spam=0.1),
            _post("at://cached-aside", claim=False, spam=0.2),
            _post("at://uncached-aside", claim=False, spam=0.2),
            _post("at://cached-spam", claim=True, spam=0.9),
            _post("at://thanks", claim=True, spam=0.1, text="Thanks!!"),
        ],
    )
    save_jev_verdicts(
        connection,
        [
            ("at://cached-aside", 0.2, 0.1, "Other", "jev-latest", "2026-10-16", "aa", "jev-latest:test"),
            ("at://cached-spam", 0.9, 0.8, "Politics", "jev-latest", "2026-10-16", "bb", "jev-latest:test"),
        ],
    )
    assert should_drop_stored_post(_post("at://cached-aside", claim=False, spam=0.2)) is False
    dropped = drop_non_quality_posts(connection)
    assert dropped == 2
    assert _uris(connection) == {"at://claim", "at://cached-aside", "at://uncached-aside"}
    cached = {row[0] for row in connection.execute("SELECT uri FROM jev_verdicts")}
    assert {"at://cached-aside", "at://cached-spam"} <= cached
    assert drop_non_quality_posts(connection) == 0
    write_quality_posts(connection, [_post("at://later", claim=True, spam=0.1)])
    assert _uris(connection) == {"at://later", "at://uncached-aside"}
    connection.close()


def test_rejected_jev_uris_are_cached_and_not_inserted(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_jev_state()
    reset_meter()
    calls = {"n": 0}

    def fake_read(url, **kwargs):
        del url, kwargs
        calls["n"] += 1
        return {
            "model": "jev-latest",
            "answers": {
                "spam": {"type": "noul", "noul": 0.1},
                "claim": {"type": "noul", "noul": 0.2},
            },
            "usage": {"input_tokens": 100, "output_tokens": 0},
        }

    monkeypatch.setattr("pipeline.jev.read_json", fake_read)
    connection = connect(tmp_path / "corpus.db")
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)
    aside = {
        "uri": "at://aside",
        "author": "ada",
        "text": "The city should fund public housing because rents jumped again this week.",
        "clean_text": "The city should fund public housing because rents jumped again this week.",
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
    }
    scored = apply_jev([aside], connection=connection, now=now, update_input=True)
    assert calls["n"] == 1
    assert scored[0]["is_claim"] is False
    write_quality_posts(connection, scored)
    assert _uris(connection) == set()
    assert "at://aside" in known_scored_uris(connection, now=now)
    apply_jev([aside], connection=connection, now=now)
    assert calls["n"] == 1
    reset_meter()
    connection.close()


def test_halt_persist_does_not_insert_non_claims(tmp_path):
    connection = connect(tmp_path / "corpus.db")
    database = tmp_path / "corpus.db"
    persist_paid_corpus(
        connection,
        [
            _post("at://claim", claim=True, spam=0.1),
            _post("at://aside", claim=False, spam=0.1),
        ],
        db_path=database,
    )
    assert load_posts(connection)[0]["uri"] == "at://claim"
    assert _uris(connection) == {"at://claim"}
    connection.close()


def test_carried_rows_predating_filters_use_clean_text_and_drop_chitchat():
    moment = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
    cutoff = moment - timedelta(hours=168)
    legacy = {
        "uri": "at://legacy-thanks",
        "author": "ada",
        "text": "",
        "clean_text": "Thanks!!",
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
        "is_claim": True,
        "spam_score": 0.1,
    }
    kept, stats = refresh_carried_posts([legacy], cutoff)
    assert kept == []
    assert stats["carried_seen"] == 1
    assert stats["carried_chitchat"] == 1
    assert stats["carried_kept"] == 0
    prepared = prepare_post(legacy)
    assert prepared["text"] == "Thanks!!"


def test_carried_rows_predating_filters_drop_even_with_legacy_claim_bit():
    moment = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
    cutoff = moment - timedelta(hours=168)
    legacy = {
        "uri": "at://legacy-gm",
        "author": "ada",
        "text": "",
        "clean_text": "gm",
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
        "is_claim": True,
        "spam_score": 0.1,
    }
    kept, stats = refresh_carried_posts([legacy], cutoff)
    assert kept == []
    assert stats["carried_chitchat"] == 1
