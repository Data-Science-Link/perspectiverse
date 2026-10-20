"""Quality posts are the only rows inserted. No paid calls."""

from datetime import datetime, timedelta, timezone

from pipeline.corpus_persist import persist_paid_corpus
from pipeline.jev import apply_jev, known_scored_uris, reset_jev_state
from pipeline.costs import reset_meter
from pipeline.chitchat_guard import (
    edition_posts_for_clustering,
    ingest_block_reason,
    planet_chitchat_reason,
)
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
from pipeline.stored_purge import (
    PURGE_STORED_REASONS_ENV,
    purge_stored_reasons_list,
    should_purge_stored_for_ingest_reason,
    stored_purge_key_for_ingest_reason,
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


def test_stored_link_and_language_purge_switch(tmp_path, monkeypatch):
    link_post = {
        "uri": "at://stored-bare-link",
        "author": "ada",
        "text": "youtu.be/VAWjsVoDpm0",
        "clean_text": "#musicsky",
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
        "is_claim": True,
    }
    lang_post = {
        "uri": "at://stored-pt",
        "author": "ada",
        "text": "O governo do Brasil anunciou novas medidas econômicas hoje",
        "clean_text": "O governo do Brasil anunciou novas medidas econômicas hoje",
        "likes": 1,
        "created_at": "2026-10-16T12:00:00Z",
        "is_claim": True,
    }
    keep_post = _post("at://claim", claim=True, spam=0.1)
    connection = connect(tmp_path / "corpus.db")
    replace_posts(connection, [keep_post, link_post, lang_post])

    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
    assert purge_stored_reasons_list() == frozenset()
    assert should_purge_stored_for_ingest_reason("link_only") is False
    assert ingest_block_reason(link_post) == "link_only"
    assert ingest_block_reason(lang_post) == "language"
    assert should_drop_stored_post(link_post) is False
    assert should_drop_stored_post(lang_post) is False
    assert drop_non_quality_posts(connection) == 0
    assert _uris(connection) == {"at://claim", "at://stored-bare-link", "at://stored-pt"}
    kept, language, links, chitchat = edition_posts_for_clustering(load_posts(connection))
    assert [post["uri"] for post in kept] == ["at://claim"]
    assert (language, links, chitchat) == (1, 1, 0)

    monkeypatch.setenv("PERSPECTIVERSE_PURGE_STORED_REASONS", "link_only,language")
    assert purge_stored_reasons_list() == frozenset({"link_only", "language"})
    assert should_drop_stored_post(link_post) is True
    assert should_drop_stored_post(lang_post) is True
    dropped = drop_non_quality_posts(connection)
    assert dropped == 2
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
    assert dropped == 1
    assert _uris(connection) == {
        "at://claim",
        "at://cached-aside",
        "at://uncached-aside",
        "at://thanks",
    }
    cached = {row[0] for row in connection.execute("SELECT uri FROM jev_verdicts")}
    assert {"at://cached-aside", "at://cached-spam"} <= cached
    assert drop_non_quality_posts(connection) == 0
    write_quality_posts(connection, [_post("at://later", claim=True, spam=0.1)])
    assert _uris(connection) == {"at://later", "at://uncached-aside"}
    connection.close()


def test_stored_chitchat_purge_is_opt_in(tmp_path, monkeypatch):
    thanks = _post("at://thanks", claim=True, spam=0.1, text="Thank you!!")
    block = ingest_block_reason(thanks)
    assert block.startswith("chitchat:")
    assert stored_purge_key_for_ingest_reason(block) == "chitchat"
    monkeypatch.delenv(PURGE_STORED_REASONS_ENV, raising=False)
    assert should_drop_stored_post(thanks) is False
    monkeypatch.setenv(PURGE_STORED_REASONS_ENV, "chitchat")
    assert should_drop_stored_post(thanks) is True
    planet = [{"text": "Thank you!!"}] * 16
    assert planet_chitchat_reason(planet, [], name="Thank")


def test_cleanup_drops_cached_spam_when_row_has_no_scores(tmp_path):
    connection = connect(tmp_path / "corpus.db")
    replace_posts(
        connection,
        [
            {
                "uri": "at://cached-spam",
                "author": "ada",
                "text": "The city should fund public housing because rents jumped again this week.",
                "clean_text": "The city should fund public housing because rents jumped again this week.",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            }
        ]
    )
    save_jev_verdicts(
        connection,
        [
            ("at://cached-spam", 0.9, 0.8, "Politics", "jev-latest", "2026-10-16", "bb", "jev-latest:test"),
        ],
    )
    dropped = drop_non_quality_posts(connection)
    assert dropped == 1
    assert _uris(connection) == set()
    connection.close()


def test_kept_non_claim_counts_cached_verdict_without_row_label(tmp_path, capsys):
    connection = connect(tmp_path / "corpus.db")
    replace_posts(
        connection,
        [
            {
                "uri": "at://cached-aside",
                "author": "ada",
                "text": "The city should fund public housing because rents jumped again this week.",
                "clean_text": "The city should fund public housing because rents jumped again this week.",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            _post("at://thanks", claim=None, text="Thanks!!"),
        ],
    )
    save_jev_verdicts(
        connection,
        [
            ("at://cached-aside", 0.2, 0.1, "Other", "jev-latest", "2026-10-16", "aa", "jev-latest:test"),
        ],
    )
    dropped = drop_non_quality_posts(connection)
    assert dropped == 0
    assert _uris(connection) == {"at://cached-aside", "at://thanks"}
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


def test_workflow_drop_non_quality_end_to_end(tmp_path, capsys):
    """Same path as ``python -m pipeline.store drop-non-quality <db>`` in the workflow."""
    from pipeline.store import main

    db = tmp_path / "live_corpus.db"
    connection = connect(db)
    policy = (
        "The city council should vote on the housing bond before the winter budget deadline."
    )
    dutch = "Het is niet een goed plan want de regering heeft geen meerderheid in het parlement."
    replace_posts(
        connection,
        [
            {
                "uri": "at://thanks",
                "author": "ada",
                "text": "Thank you so much!",
                "clean_text": "Thank you so much!",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://link-only",
                "author": "ada",
                "text": "https://example.com/only",
                "clean_text": "https://example.com/only",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://non-english",
                "author": "ada",
                "text": dutch,
                "clean_text": dutch,
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://cached-spam",
                "author": "ada",
                "text": policy,
                "clean_text": policy,
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://cached-aside",
                "author": "ada",
                "text": policy,
                "clean_text": policy,
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            _post("at://claim", claim=True, spam=0.1, text=policy),
        ],
    )
    save_jev_verdicts(
        connection,
        [
            ("at://cached-spam", 0.9, 0.8, "Politics", "jev-latest", "2026-10-16", "bb", "jev-latest:test"),
            ("at://cached-aside", 0.2, 0.1, "Other", "jev-latest", "2026-10-16", "aa", "jev-latest:test"),
        ],
    )
    connection.close()

    assert main(["drop-non-quality", str(db)]) == 0
    captured = capsys.readouterr().out
    assert (
        "Stored corpus cleanup: spam=1, filtered=0 "
        "(chit-chat, link-only, language, or free spam guard), "
        "kept_non_claim=1; 5 row(s) remain."
    ) in captured
    assert captured.strip().splitlines()[-1] == "1"

    connection = connect(db)
    assert _uris(connection) == {
        "at://claim",
        "at://cached-aside",
        "at://thanks",
        "at://link-only",
        "at://non-english",
    }
    verdicts = {row[0] for row in connection.execute("SELECT uri FROM jev_verdicts")}
    assert verdicts == {"at://cached-spam", "at://cached-aside"}
    connection.close()


def test_workflow_drop_non_quality_purges_when_reasons_listed(tmp_path, capsys, monkeypatch):
    from pipeline.store import main

    monkeypatch.setenv(PURGE_STORED_REASONS_ENV, "chitchat,link_only,language")
    db = tmp_path / "live_corpus.db"
    connection = connect(db)
    dutch = "Het is niet een goed plan want de regering heeft geen meerderheid in het parlement."
    replace_posts(
        connection,
        [
            {
                "uri": "at://thanks",
                "author": "ada",
                "text": "Thank you so much!",
                "clean_text": "Thank you so much!",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://link-only",
                "author": "ada",
                "text": "https://example.com/only",
                "clean_text": "https://example.com/only",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            {
                "uri": "at://non-english",
                "author": "ada",
                "text": dutch,
                "clean_text": dutch,
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
            },
            _post("at://claim", claim=True, spam=0.1),
        ],
    )
    connection.close()
    assert main(["drop-non-quality", str(db)]) == 0
    captured = capsys.readouterr().out
    assert "filtered=3" in captured
    connection = connect(db)
    assert _uris(connection) == {"at://claim"}
    connection.close()


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
