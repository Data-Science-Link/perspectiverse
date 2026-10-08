"""Unit tests for MMR prompt post sampling."""

from __future__ import annotations

import numpy as np

from pipeline.prompt_sample import (
    DEFAULT_DEDUPE_COSINE,
    DEFAULT_RELEVANCE_POOL_FRACTION,
    relevance_pool_indices,
    select_prompt_posts,
)


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
    vectors = np.eye(30)
    first = select_prompt_posts(posts, cosines, limit=12, vectors=vectors)
    second = select_prompt_posts(posts, cosines, limit=12, vectors=vectors)
    assert [p["text"] for p in first] == [p["text"] for p in second]


def test_select_prompt_posts_respects_cap_with_relevance_pool():
    posts = _posts(50)
    cosines = [0.4 + 0.01 * i for i in range(50)]
    vectors = np.eye(50)
    pool = relevance_pool_indices(cosines, fraction=DEFAULT_RELEVANCE_POOL_FRACTION)
    chosen = select_prompt_posts(posts, cosines, limit=40, vectors=vectors)
    assert len(chosen) == min(40, len(pool))


def test_fewer_than_cap_returns_whole_pool():
    posts = _posts(15)
    cosines = [0.9 - 0.01 * i for i in range(15)]
    vectors = np.eye(15)
    chosen = select_prompt_posts(posts, cosines, limit=40, vectors=vectors)
    pool = relevance_pool_indices(cosines, fraction=DEFAULT_RELEVANCE_POOL_FRACTION)
    assert len(chosen) == len(pool)
    assert len(chosen) < 40


def test_missing_likes_does_not_break_sampling():
    posts = [
        {"text": "alpha one", "clean_text": "alpha one", "author": "a"},
        {"text": "alpha two", "clean_text": "alpha two", "author": "b"},
        {"text": "beta three", "clean_text": "beta three", "author": "c"},
    ]
    cosines = [0.9, 0.88, 0.5]
    vectors = np.eye(3)
    chosen = select_prompt_posts(posts, cosines, limit=3, vectors=vectors)
    assert len(chosen) == 3


def test_identical_text_collapses_under_dedupe():
    text = "same claim repeated verbatim for every post"
    posts = [{"text": text, "clean_text": text, "likes": i, "author": f"u{i}"} for i in range(8)]
    cosines = [0.99 - 0.001 * i for i in range(8)]
    vectors = np.ones((8, 4))
    chosen = select_prompt_posts(posts, cosines, limit=8, vectors=vectors)
    assert len(chosen) == 1


def test_relevance_pool_restricts_candidates():
    posts = _posts(20)
    cosines = [0.95 - 0.02 * i for i in range(20)]
    vectors = np.eye(20)
    pool = set(relevance_pool_indices(cosines, fraction=0.7))
    chosen = select_prompt_posts(posts, cosines, limit=40, vectors=vectors)
    picked_indices = []
    for post in chosen:
        picked_indices.append(next(i for i, p in enumerate(posts) if p["text"] == post["text"]))
    assert all(index in pool for index in picked_indices)


def test_like_boost_prefers_higher_likes_at_equal_centrality():
    posts = [
        {"text": "alpha claim one", "clean_text": "alpha claim one", "likes": 1, "author": "a"},
        {"text": "alpha claim two", "clean_text": "alpha claim two", "likes": 200, "author": "b"},
        {"text": "beta different subject", "clean_text": "beta different subject", "likes": 0, "author": "c"},
    ]
    cosines = [0.9, 0.9, 0.5]
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    chosen = select_prompt_posts(posts, cosines, limit=2, vectors=vectors)
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


def test_mmr_prefers_distinct_post_inside_relevance_pool():
    """Near-duplicate central posts lose to a distinct post that still sits in the top-70% pool."""
    posts = [
        {"text": "gaza ceasefire now end the war", "clean_text": "gaza ceasefire now end the war", "likes": 10, "author": "a"},
        {"text": "gaza ceasefire now end the war!", "clean_text": "gaza ceasefire now end the war!", "likes": 9, "author": "b"},
        {"text": "gaza ceasefire now end the war!!", "clean_text": "gaza ceasefire now end the war!!", "likes": 8, "author": "c"},
        {"text": "aid corridors must open for gaza civilians", "clean_text": "aid corridors must open for gaza civilians", "likes": 2, "author": "d"},
        {"text": "un votes on gaza resolution thursday", "clean_text": "un votes on gaza resolution thursday", "likes": 1, "author": "e"},
    ]
    cosines = [0.99, 0.985, 0.98, 0.82, 0.8]
    vectors = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.99, 0.01, 0.0, 0.0],
            [0.98, 0.02, 0.0, 0.0],
            [0.2, 0.9, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    chosen = select_prompt_posts(posts, cosines, limit=3, vectors=vectors)
    texts = [p["text"] for p in chosen]
    assert texts[0] == posts[0]["text"]
    assert any("aid corridors" in text for text in texts[1:])


def test_planet_sample_is_not_oldest_prefix():
    members = []
    for index in range(30):
        members.append(
            {
                "uri": f"at://u/{index}",
                "author": "u",
                "text": f"planet topic wording variant {index} with unique tokens token{index}",
                "clean_text": f"planet topic wording variant {index} with unique tokens token{index}",
                "likes": index,
                "created_at": f"2026-01-{index + 1:02d}T00:00:00Z",
            }
        )
    vectors = np.eye(30)
    # Corpus order is oldest-first, but centrality favors newer posts.
    cosines = [0.5 + 0.02 * index for index in range(30)]
    oldest_prefix = [members[index] for index in range(20)]
    mmr_sample = select_prompt_posts(members, cosines, limit=20, vectors=vectors)
    oldest_uris = [m["uri"] for m in oldest_prefix]
    sample_uris = []
    for post in mmr_sample:
        sample_uris.append(next(m["uri"] for m in members if m["text"] == post["text"]))
    assert sample_uris != oldest_uris
    assert len(mmr_sample) == 20
    assert oldest_uris[0] == members[0]["uri"]
