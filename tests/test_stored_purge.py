"""Stored-row purge env keys (unset matches main spam-only on production snapshot)."""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.chitchat_guard import ingest_block_reason
from pipeline.store import (
    _stored_spam,
    connect,
    load_jev_verdicts,
    load_posts,
    should_drop_stored_post,
)
from pipeline.stored_purge import (
    purge_stored_reasons_list,
    should_purge_stored_for_ingest_reason,
    stored_purge_key_for_ingest_reason,
)

_PRODUCTION_DB = Path("/tmp/production_live_corpus.db")


def test_purge_keys_map_chitchat_subreasons():
    assert stored_purge_key_for_ingest_reason("chitchat:thanks") == "chitchat"
    assert stored_purge_key_for_ingest_reason("spam:duplicate") is None
    assert stored_purge_key_for_ingest_reason("link_only") == "link_only"


def test_unset_env_disables_listed_keys_only(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
    assert purge_stored_reasons_list() == frozenset()
    assert should_purge_stored_for_ingest_reason("chitchat:thanks") is False
    assert should_purge_stored_for_ingest_reason("link_only") is False
    assert should_purge_stored_for_ingest_reason("language") is False
    assert should_purge_stored_for_ingest_reason("weather_bot") is False
    assert should_purge_stored_for_ingest_reason("spam:duplicate") is True


def test_each_purge_key_enables_only_that_reason(monkeypatch):
    cases = [
        ("chitchat", "chitchat:thanks", {"text": "Thank you so much ❤️"}),
        ("link_only", "link_only", None),
        ("language", "language", None),
        ("weather_bot", "weather_bot", None),
    ]
    for key, reason, post in cases:
        monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
        monkeypatch.setenv("PERSPECTIVERSE_PURGE_STORED_REASONS", key)
        assert purge_stored_reasons_list() == frozenset({key})
        assert should_purge_stored_for_ingest_reason(reason) is True
        assert should_purge_stored_for_ingest_reason("link_only") is (key == "link_only")
        if post is not None:
            assert ingest_block_reason(post) == reason
            assert should_drop_stored_post(post) is True


def test_all_purge_keys_together(monkeypatch):
    monkeypatch.setenv(
        "PERSPECTIVERSE_PURGE_STORED_REASONS",
        "chitchat,link_only,language,weather_bot",
    )
    enabled = purge_stored_reasons_list()
    assert enabled == frozenset({"chitchat", "link_only", "language", "weather_bot"})
    for reason in ("chitchat:thanks", "link_only", "language", "weather_bot"):
        assert should_purge_stored_for_ingest_reason(reason) is True


def test_production_unset_matches_main_spam_only(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_PURGE_STORED_REASONS", raising=False)
    os.environ["PERSPECTIVERSE_ALLOW_PAID"] = "0"
    if not _PRODUCTION_DB.exists():
        return
    conn = connect(_PRODUCTION_DB)
    posts = load_posts(conn)
    verdicts = load_jev_verdicts(conn, [str(p.get("uri") or "") for p in posts])
    conn.close()
    spam_drops = 0
    filtered_drops = 0
    for post in posts:
        uri = str(post.get("uri") or "")
        row = verdicts.get(uri)
        if not should_drop_stored_post(post, row):
            continue
        if _stored_spam(post, row):
            spam_drops += 1
        else:
            filtered_drops += 1
    assert filtered_drops == 0
    assert spam_drops == 411
