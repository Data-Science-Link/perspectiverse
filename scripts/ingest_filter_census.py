#!/usr/bin/env python3
"""Measure ingest filters and local clustering on a saved live_corpus.db.

No network, no paid calls, no R2 writes. Uses fastembed and heuristic labels.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.chitchat_guard import edition_posts_for_clustering, ingest_block_reason
from pipeline.cleaning import clean_text
from pipeline.eval.grouping_eval import embed_texts
from pipeline.label import heuristic_topic_label
from pipeline.store import connect, load_posts
from pipeline.topics import CANDIDATE_POOL, cluster_texts

_URL_PLANET_RE = re.compile(
    r"\b(?:youtu(?:\.be)?|youtube|bsky|twitch|kick)\b|app\s+profile",
    re.IGNORECASE,
)


def _load_main_language_module():
    """Import partition logic from main for a before/after comparison."""
    source = subprocess.check_output(
        ["git", "show", "main:pipeline/language.py"],
        cwd=ROOT,
        text=True,
    )
    path = Path("/tmp/language_main_snapshot.py")
    path.write_text(source, encoding="utf-8")
    import importlib.util

    spec = importlib.util.spec_from_file_location("language_main_snapshot", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def drop_counts(posts: list[dict], *, use_main: bool) -> tuple[dict[str, int], dict[str, list[str]]]:
    if use_main:
        lang_mod = _load_main_language_module()
        _kept, language, links = lang_mod.partition_posts(posts)
        return {"link_only": links, "language": language}, {}
    by_reason: dict[str, list[str]] = {"link_only": [], "language": []}
    for post in posts:
        reason = ingest_block_reason(post)
        if reason in by_reason:
            text = str(post.get("text") or post.get("clean_text") or "")[:220]
            by_reason[reason].append(text)
    counts = {key: len(values) for key, values in by_reason.items()}
    samples = {
        key: random.sample(values, min(50, len(values))) if values else []
        for key, values in by_reason.items()
    }
    return counts, samples


def cluster_planets(
    posts: list[dict],
    *,
    seed: int,
    strip_hosts: bool,
    cache: Path,
) -> list[dict]:
    if strip_hosts:
        texts = [
            clean_text(str(post.get("text") or post.get("clean_text") or ""))
            for post in posts
        ]
    else:
        texts = [str(post.get("clean_text") or post.get("text") or "") for post in posts]
    matrix = embed_texts(texts, cache)
    clustered = cluster_texts(
        texts,
        min_cluster_size=5,
        cluster_backend="embedding",
        seed=seed,
        catalog_size=CANDIDATE_POOL,
        embed=lambda _batch, rows=matrix: rows,
        authors=[str(post.get("author") or "unknown") for post in posts],
    )
    candidates = []
    for topic in clustered.get("topics") or []:
        indices = [int(i) for i in (topic.get("member_indices") or [])]
        members = [posts[i] for i in indices if 0 <= i < len(posts)]
        label = heuristic_topic_label(list(topic.get("terms") or []), members)
        candidates.append(
            {
                "name": str(label.get("name") or ""),
                "size": int(topic.get("size") or len(indices)),
                "terms": list(topic.get("terms") or [])[:8],
            }
        )
    candidates.sort(key=lambda row: (-row["size"], row["name"]))
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    connection = connect(args.db)
    try:
        posts = load_posts(connection)
    finally:
        connection.close()
    print(f"Loaded {len(posts)} posts from {args.db}")
    before_counts, _ = drop_counts(posts, use_main=True)
    after_counts, samples = drop_counts(posts, use_main=False)
    print("Ingest drop counts (main filters):", before_counts)
    print("Ingest drop counts (new filters):", after_counts)
    for reason, texts in samples.items():
        print(f"  sample {reason}:")
        for text in texts[:3]:
            print(f"    - {text}")

    kept_main_mod = _load_main_language_module()
    kept_old, lang_old, link_old = kept_main_mod.partition_posts(posts)
    kept_new, lang_new, link_new, chit_new = edition_posts_for_clustering(posts)
    print(
        f"Clustering input: old kept={len(kept_old)} "
        f"(lang={lang_old} links={link_old}); "
        f"new kept={len(kept_new)} (lang={lang_new} links={link_new} chit={chit_new})"
    )

    random.seed(args.seed)
    print("Clustering BEFORE (old partition, no host strip in embed text)...")
    t0 = time.perf_counter()
    before_planets = cluster_planets(
        kept_old,
        seed=args.seed,
        strip_hosts=False,
        cache=Path("/tmp/embed_corpus_before.npy"),
    )
    before_secs = time.perf_counter() - t0
    print(f"  {len(before_planets)} candidate planets in {before_secs:.1f}s")
    print("Clustering AFTER (new partition, host strip in embed text)...")
    t0 = time.perf_counter()
    after_planets = cluster_planets(
        kept_new,
        seed=args.seed,
        strip_hosts=True,
        cache=Path("/tmp/embed_corpus_after.npy"),
    )
    after_secs = time.perf_counter() - t0
    print(f"  {len(after_planets)} candidate planets in {after_secs:.1f}s")

    def url_hits(rows: list[dict]) -> list[dict]:
        return [row for row in rows if _URL_PLANET_RE.search(row["name"])]

    before_url = url_hits(before_planets)
    after_url = url_hits(after_planets)
    print(f"URL-titled planets BEFORE: {len(before_url)}")
    for row in before_url[:15]:
        print(f"  {row['size']:4d}  {row['name']}")
    print(f"URL-titled planets AFTER: {len(after_url)}")
    for row in after_url[:15]:
        print(f"  {row['size']:4d}  {row['name']}")

    payload = {
        "posts": len(posts),
        "before_ingest_drops": before_counts,
        "after_ingest_drops": after_counts,
        "after_samples": samples,
        "clustering_kept_old": len(kept_old),
        "clustering_kept_new": len(kept_new),
        "before_planets_top50": before_planets[:50],
        "after_planets_top50": after_planets[:50],
        "before_url_planets": before_url,
        "after_url_planets": after_url,
    }
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.json_out}")


if __name__ == "__main__":
    main()
