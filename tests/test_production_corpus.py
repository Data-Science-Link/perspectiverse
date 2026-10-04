"""Cluster the production R2 corpus and check the snapshot the site would publish.

The daily job keeps that corpus in a private bucket. This test downloads a
copy, reclusters it, and writes a temp data.json. It never uploads.

Skipped unless ``PERSPECTIVERSE_RUN_PRODUCTION=1`` and R2 credentials are
set, so a normal CI run does not download the corpus or call the labeler.
Set ``PERSPECTIVERSE_PRODUCTION_OUTPUT`` to also save the snapshot for review.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from pipeline.schema import validate_payload

FILLER = (
    "that is the position in the posts about",
    "is the claim these posts repeat",
    "the posts gathered here are making that case",
    "these posts are making that case",
)


def _configured() -> bool:
    if os.environ.get("PERSPECTIVERSE_RUN_PRODUCTION") != "1":
        return False
    needed = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT")
    return all(os.environ.get(name, "").strip() for name in needed)


pytestmark = pytest.mark.skipif(
    not _configured(),
    reason="set PERSPECTIVERSE_RUN_PRODUCTION=1 with R2 credentials to cluster the production corpus",
)


def _repeated_word(title: str) -> bool:
    words = [word.strip(".,;:!?\"'").lower() for word in str(title or "").split()]
    words = [word for word in words if word]
    return any(left == right for left, right in zip(words, words[1:]))


def test_production_corpus_builds_a_snapshot(tmp_path: Path) -> None:
    from pipeline.live import run_live
    from pipeline.r2 import load_r2_config, restore_corpus

    config = load_r2_config()
    if config is None:
        pytest.skip("R2 is not configured")

    database = tmp_path / "live_corpus.db"
    status = restore_corpus(database, config=config)
    assert status == "downloaded"
    connection = sqlite3.connect(database)
    try:
        stored = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        claims = connection.execute("SELECT COUNT(*) FROM posts WHERE is_claim = 1").fetchone()[0]
    finally:
        connection.close()
    assert stored >= 1000
    assert claims >= 500

    destination = tmp_path / "data.json"
    written = run_live(output=destination, db_path=database, relabel=True)
    payload = json.loads(Path(written).read_text(encoding="utf-8"))
    validate_payload(payload)

    mirror = os.environ.get("PERSPECTIVERSE_PRODUCTION_OUTPUT", "").strip()
    if mirror:
        target = Path(mirror)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    assert payload["mode"] == "live"
    assert payload["total_posts"] >= 500
    topics = payload["topics"]
    assert topics, "production clustering published no planets"
    counts = [int(topic["post_count"]) for topic in topics]
    assert len(set(counts)) > 1, "every planet was given the same post count"
    assert all(count > 0 and count != payload["total_posts"] for count in counts)
    assert sum(counts) <= payload["total_posts"]
    multi = 0
    for topic in topics:
        faces = topic["perspectives"]
        assert 1 <= len(faces) <= 6
        if len(faces) > 1:
            multi += 1
        face_counts = [int(face["post_count"]) for face in faces]
        assert sum(face_counts) == int(topic["post_count"])
        blob = " ".join(
            [
                str(topic.get("name") or ""),
                str(topic.get("brief") or ""),
                str(topic.get("detail") or ""),
                *(str(face.get("title") or "") for face in faces),
                *(str(face.get("brief") or "") for face in faces),
            ]
        ).lower()
        for phrase in FILLER:
            assert phrase not in blob
        assert not _repeated_word(str(topic.get("name") or ""))
        for face in faces:
            title = str(face.get("title") or "")
            assert title and not title.endswith("?")
            assert not _repeated_word(title)
            posts = face.get("representative_posts") or []
            assert len(posts) >= 2
            matches = [post.get("match") for post in posts]
            assert all(match is not None for match in matches)
            assert matches == sorted(matches, reverse=True)
    assert multi >= 1, "no planet separated into more than one perspective"
