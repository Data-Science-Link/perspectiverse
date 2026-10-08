"""Unit tests for MMR prompt post sampling."""

from __future__ import annotations

import numpy as np

from pipeline.prompt_sample import DEFAULT_DEDUPE_COSINE, select_prompt_posts


def _posts(n: int, *, likes: int = 0, text_prefix: str = "topic") -> list[dict]:
    return [
        {
            "author": f"u{i}",
            "text": f"{text_prefix} angle {i} with distinct wording number {i}.",
            "clean_text": f"{text_prefix} angle {i} with distinct wording number {i}.",
            "likes": likes + (i % 3),
        }
        for i in range(n)
    ]


def test_select_prompt_posts_is_deterministic():
    posts = _posts(30)
    cosines = [0.5 + 0.01 * i for i in range(30)]
    first = select_prompt_posts(posts, cosines, limit=12)
    second = select_prompt_posts(posts, cosines, limit=12)
    assert [p["text"] for p in first] == [p["text"] for p in second]


def test_select_prompt_posts_respects_cap():
    posts = _posts(50)
    cosines = [0.4] * 50
    vectors = np.eye(50)
    chosen = select_prompt_posts(posts, cosines, limit=40, vectors=vectors)
    assert len(chosen) == 40


def test_like_boost_prefers_higher_likes_at_equal_centrality():
    posts = [
        {"text": "alpha claim one", "clean_text": "alpha claim one", "likes": 1, "author": "a"},
        {"text": "alpha claim two", "clean_text": "alpha claim two", "likes": 200, "author": "b"},
        {"text": "beta different subject", "clean_text": "beta different subject", "likes": 0, "author": "c"},
    ]
    cosines = [0.9, 0.9, 0.5]
    chosen = select_prompt_posts(posts, cosines, limit=2)
    texts = [p["text"] for p in chosen]
    assert texts[0] == "alpha claim two"


def test_dedupe_skips_near_duplicate_embeddings():
    posts = [
        {"text": "war update from the front lines today", "clean_text": "war update from the front lines today", "likes": 5, "author": "a"},
        {"text": "war update from the front lines today!", "clean_text": "war update from the front lines today!", "likes": 3, "author": "b"},
        {"text": "diplomacy talks resume in geneva", "clean_text": "diplomacy talks resume in geneva", "likes": 1, "author": "c"},
    ]
    cosines = [0.95, 0.94, 0.7]
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    chosen = select_prompt_posts(
        posts,
        cosines,
        limit=3,
        dedupe_cosine=DEFAULT_DEDUPE_COSINE,
        vectors=vectors,
    )
    assert len(chosen) == 2
    assert any("diplomacy" in p["text"] for p in chosen)


def test_mmr_prefers_diversity_over_redundant_central_posts():
    posts = _posts(8, text_prefix="same framing repeated")
    cosines = [0.99, 0.98, 0.97, 0.96, 0.85, 0.84, 0.83, 0.82]
    # Orthogonal rows force MMR to spread across indices instead of four near-ties.
    vectors = np.eye(8)
    chosen = select_prompt_posts(posts, cosines, limit=4, vectors=vectors)
    indices = {int(p["text"].split()[-1].rstrip(".")) for p in chosen}
    assert len(indices) == 4
    assert max(indices) >= 3


def test_vectors_matrix_optional():
    posts = _posts(6)
    vectors = np.eye(6)
    cosines = [0.5] * 6
    chosen = select_prompt_posts(posts, cosines, limit=3, vectors=vectors)
    assert len(chosen) == 3
