#!/usr/bin/env python3
"""Read-only production census after langid language filter."""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.chitchat_guard import edition_posts_for_clustering, ingest_block_reason
from pipeline.cleaning import clean_text
from pipeline.eval.grouping_eval import embed_texts
from pipeline.label import heuristic_topic_label
from pipeline.language import edition_filter_reason, looks_english, post_raw_text
from pipeline.store import (
    _jev_verdict_is_spam,
    _stored_spam_or_guard,
    connect,
    load_jev_verdicts,
    load_posts,
    should_drop_stored_post,
)
from pipeline.topics import CANDIDATE_POOL, cluster_texts

URL_PLANET_RE = re.compile(
    r"\b(?:youtu(?:\.be)?|youtube|bsky|twitch|kick)\b|app\s+profile",
    re.IGNORECASE,
)


def main() -> None:
    random.seed(2518)
    db = Path("/tmp/production_live_corpus.db")
    conn = connect(db)
    posts = load_posts(conn)
    verdicts = load_jev_verdicts(conn, [str(p.get("uri") or "") for p in posts])
    conn.close()

    by_delete: dict[str, list[dict]] = {
        "link_only": [],
        "language": [],
        "jev_cached_spam": [],
        "other_filter": [],
    }
    for post in posts:
        uri = str(post.get("uri") or "")
        row = verdicts.get(uri)
        if not should_drop_stored_post(post, row):
            continue
        reason = ingest_block_reason(post)
        if reason == "link_only":
            by_delete["link_only"].append(post)
        elif reason == "language":
            by_delete["language"].append(post)
        elif row is not None and _jev_verdict_is_spam(row) and not _stored_spam_or_guard(post):
            by_delete["jev_cached_spam"].append(post)
        else:
            by_delete["other_filter"].append(post)

    stored_after_cleanup = len(posts) - sum(len(v) for v in by_delete.values())

    lang_sample = random.sample(
        by_delete["language"],
        min(50, len(by_delete["language"])),
    )
    lang_fp = [p for p in lang_sample if looks_english(post_raw_text(p))]

    kept_new, lang_skip, link_skip, chit_skip = edition_posts_for_clustering(posts)
    texts_new = [
        clean_text(str(p.get("text") or p.get("clean_text") or "")) for p in kept_new
    ]
    cache = Path("/tmp/embed_corpus_langid.npy")
    matrix = embed_texts(texts_new, cache)
    clustered = cluster_texts(
        texts_new,
        min_cluster_size=5,
        cluster_backend="embedding",
        seed=0,
        catalog_size=CANDIDATE_POOL,
        embed=lambda _b, rows=matrix: rows,
        authors=[str(p.get("author") or "unknown") for p in kept_new],
    )
    planets: list[dict] = []
    for topic in clustered.get("topics") or []:
        idx = [int(i) for i in (topic.get("member_indices") or [])]
        members = [kept_new[i] for i in idx if 0 <= i < len(kept_new)]
        name = heuristic_topic_label(list(topic.get("terms") or []), members)["name"]
        planets.append({"name": name, "size": int(topic.get("size") or len(idx))})
    planets.sort(key=lambda r: (-r["size"], r["name"]))

    flagged = []
    for planet in planets:
        name = planet["name"]
        note = []
        if URL_PLANET_RE.search(name):
            note.append("url_title")
        if name.strip().lower() in {"que", "youtu", "bsky app profile"}:
            note.append("review_flag")
        if note:
            flagged.append({**planet, "flags": note})

    out = {
        "stored_deletions": {k: len(v) for k, v in by_delete.items()},
        "stored_deletion_samples": {
            k: [post_raw_text(p)[:240] for p in random.sample(v, min(10, len(v)))]
            for k, v in by_delete.items()
            if v
        },
        "stored_rows_after_cleanup": stored_after_cleanup,
        "toward_100k_note": (
            "Free ingest counts only posts that pass keep_edition_quality (ingest_block_reason "
            "None). drop_non_quality_posts removes cached Jev spam and filter blocks from the "
            "stored table, so deleted rows do not count toward the 100K fill."
        ),
        "language_sample_n": len(lang_sample),
        "language_sample_english_fp": len(lang_fp),
        "language_sample_fp_texts": [post_raw_text(p)[:240] for p in lang_fp],
        "clustering_kept": len(kept_new),
        "cluster_skips": {
            "language": lang_skip,
            "link_only": link_skip,
            "chitchat": chit_skip,
        },
        "planets_top40": planets[:40],
        "planets_flagged": flagged,
        "planets_all_count": len(planets),
    }
    path = Path("/tmp/census_langid.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
