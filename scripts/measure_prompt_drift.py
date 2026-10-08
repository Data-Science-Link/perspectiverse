#!/usr/bin/env python3
"""Measure prompt-sample drift on the tracked seed corpus (live_corpus.db)."""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from pipeline.embed import embed_minilm
from pipeline.prompt_sample import (
    DEFAULT_RELEVANCE_POOL_FRACTION,
    cosines_to_matrix_centroid,
    relevance_pool_indices,
    select_prompt_posts,
)
from pipeline.store import LIVE_CORPUS_DB, connect, load_posts


def _face_groups(connection) -> list[tuple[int, int, list[int]]]:
    rows = connection.execute(
        "SELECT uri, topic_id, face_index FROM perspectives ORDER BY topic_id, face_index"
    ).fetchall()
    by_key: dict[tuple[int, int], list[int]] = defaultdict(list)
    uri_to_index: dict[str, int] = {}
    posts = load_posts(connection)
    for index, post in enumerate(posts):
        uri_to_index[str(post["uri"])] = index
    for uri, topic_id, face_index in rows:
        index = uri_to_index.get(str(uri))
        if index is not None:
            by_key[(int(topic_id), int(face_index))].append(index)
    ranked = sorted(by_key.items(), key=lambda item: -len(item[1]))
    return [(key[0], key[1], indices) for key, indices in ranked]


def _stats(
    posts: list[dict],
    cosines: list[float],
    chosen: list[dict],
    pool: set[int],
) -> dict:
    matches = [float(post.get("match") or 0.0) for post in chosen]
    picked = []
    for post in chosen:
        snippet = str(post.get("text") or "")
        picked.append(
            next(
                i
                for i, row in enumerate(posts)
                if snippet in {str(row.get("text") or ""), str(row.get("clean_text") or "")}
            )
        )
    outside = sum(1 for index in picked if index not in pool)
    return {
        "count": len(chosen),
        "min_match": round(min(matches), 3) if matches else None,
        "median_match": round(float(statistics.median(matches)), 3) if matches else None,
        "outside_pool": outside,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    db = root / "pipeline" / "data" / "live_corpus.db"
    if not db.exists():
        db = LIVE_CORPUS_DB
    connection = connect(db)
    posts = load_posts(connection)
    texts = [str(post["clean_text"] or post["text"] or "") for post in posts]
    matrix = embed_minilm(texts)
    faces = _face_groups(connection)[:3]
    print("Drift on three largest seed-corpus faces (cap 40, top-70% pool after fix):\n")
    print(f"{'face':>12}  {'mode':>8}  {'n':>3}  {'min':>6}  {'median':>7}  {'outside70%':>10}")
    print("-" * 60)
    for topic_id, face_index, indices in faces:
        face_posts = [posts[index] for index in indices]
        face_vectors = matrix[indices]
        cosines = cosines_to_matrix_centroid(face_vectors)
        pool = set(relevance_pool_indices(cosines, fraction=DEFAULT_RELEVANCE_POOL_FRACTION))
        before = select_prompt_posts(
            face_posts,
            cosines,
            limit=40,
            vectors=None,
            relevance_pool_fraction=1.0,
        )
        after = select_prompt_posts(face_posts, cosines, limit=40, vectors=face_vectors)
        before_stats = _stats(face_posts, cosines, before, pool)
        after_stats = _stats(face_posts, cosines, after, pool)
        label = f"t{topic_id}f{face_index}"
        print(
            f"{label:>12}  {'before':>8}  {before_stats['count']:>3}  "
            f"{before_stats['min_match']:>6}  {before_stats['median_match']:>7}  {before_stats['outside_pool']:>10}"
        )
        print(
            f"{'':>12}  {'after':>8}  {after_stats['count']:>3}  "
            f"{after_stats['min_match']:>6}  {after_stats['median_match']:>7}  {after_stats['outside_pool']:>10}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
