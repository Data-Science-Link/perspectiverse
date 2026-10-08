"""Deterministic diverse post sampling for labeling prompts.

Maximal marginal relevance over embedding cosines, with a small like-count
boost and near-duplicate suppression. Used for face and planet naming prompts
so the model sees central *and* varied posts, not the twelve tightest repeats.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from pipeline.cluster_math import vectorize

# Skip a candidate when it is this cosine-close to an already chosen post.
DEFAULT_DEDUPE_COSINE = 0.92
# Trade relevance (to centroid) vs diversity in MMR.
DEFAULT_LAMBDA = 0.65
# log1p(likes) is scaled by this before adding to relevance.
LIKE_BOOST_SCALE = 0.04
# MMR runs only on the strongest fraction of centroid cosines (issue #86 review).
DEFAULT_RELEVANCE_POOL_FRACTION = 0.7


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def _relevance_scores(cosines: Sequence[float], posts: Sequence[dict]) -> np.ndarray:
    base = np.asarray([float(c) for c in cosines], dtype=float)
    likes = np.asarray([math.log1p(max(0, int(post.get("likes") or 0))) for post in posts], dtype=float)
    if likes.size:
        likes = likes / max(float(likes.max()), 1.0)
    return base + LIKE_BOOST_SCALE * likes


def _pairwise_cosines(matrix: np.ndarray) -> np.ndarray:
    normalized = _normalize_rows(np.asarray(matrix, dtype=float))
    return normalized @ normalized.T


def relevance_pool_indices(
    cosines: Sequence[float],
    *,
    fraction: float = DEFAULT_RELEVANCE_POOL_FRACTION,
) -> list[int]:
    """Indices of the top ``fraction`` of members by centroid cosine."""
    count = len(cosines)
    if count == 0:
        return []
    pool_size = int(math.ceil(count * float(fraction)))
    pool_size = max(1, min(pool_size, count))
    ranked = sorted(range(count), key=lambda index: (-float(cosines[index]), index))
    return sorted(ranked[:pool_size])


def cosines_to_matrix_centroid(matrix: np.ndarray) -> list[float]:
    """Cosine of each row to the mean of normalized rows."""
    values = np.asarray(matrix, dtype=float)
    if values.size == 0:
        return []
    normalized = _normalize_rows(values)
    center = normalized.mean(axis=0)
    norm = np.linalg.norm(center) or 1.0
    center = center / norm
    return [float(row @ center) for row in normalized]


def select_prompt_posts(
    posts: list[dict],
    cosines: Sequence[float] | None,
    *,
    limit: int = 40,
    vectors: np.ndarray | None = None,
    lambda_mmr: float = DEFAULT_LAMBDA,
    dedupe_cosine: float = DEFAULT_DEDUPE_COSINE,
    relevance_pool_fraction: float = DEFAULT_RELEVANCE_POOL_FRACTION,
) -> list[dict]:
    """Return up to ``limit`` posts: centroid-relevant, diverse, deduped.

    Deterministic for fixed ``posts``, ``cosines``, and parameters.
    Tie-breaks use ascending member index.
    """
    if not posts or limit <= 0:
        return []
    cap = min(int(limit), len(posts))

    texts = [str(post.get("clean_text") or post.get("text") or "") for post in posts]
    if vectors is None:
        try:
            vectors = vectorize(texts)
        except ValueError:
            vectors = None

    if cosines is None or len(cosines) != len(posts):
        if vectors is not None:
            center = _normalize_rows(vectors).mean(axis=0)
            norm = np.linalg.norm(center) or 1.0
            center = center / norm
            cosines = [float(row @ center) for row in _normalize_rows(vectors)]
        else:
            cosines = [0.0] * len(posts)

    pool = relevance_pool_indices(cosines, fraction=relevance_pool_fraction)
    if not pool:
        return []
    cap = min(cap, len(pool))

    pool_posts = [posts[index] for index in pool]
    pool_cosines = [float(cosines[index]) for index in pool]
    pool_vectors = np.asarray(vectors, dtype=float)[pool] if vectors is not None else None

    relevance = _relevance_scores(pool_cosines, pool_posts)
    sim = (
        _pairwise_cosines(pool_vectors)
        if pool_vectors is not None
        else np.zeros((len(pool), len(pool)))
    )

    lam = float(lambda_mmr)
    chosen: list[int] = []
    candidates = list(range(len(pool)))

    # Seed the set with the strongest relevance (stable index tie-break).
    first = max(candidates, key=lambda index: (relevance[index], -index))
    chosen.append(first)
    candidates.remove(first)

    while len(chosen) < cap and candidates:
        best_index = None
        best_score = -1e9
        for index in candidates:
            if chosen and sim.size:
                if any(float(sim[index, picked]) >= dedupe_cosine for picked in chosen):
                    continue
            if chosen:
                diversity = max(float(sim[index, picked]) for picked in chosen)
            else:
                diversity = 0.0
            score = lam * float(relevance[index]) - (1.0 - lam) * diversity
            if score > best_score or (score == best_score and (best_index is None or index < best_index)):
                best_score = score
                best_index = index
        if best_index is None:
            break
        chosen.append(best_index)
        candidates.remove(best_index)

    return [_record(pool_posts[index], pool[index], cosines) for index in chosen]


def _record(post: dict, index: int, cosines: Sequence[float] | None) -> dict:
    record = {
        "author": post.get("author") or "unknown",
        "text": post.get("clean_text") or post.get("text") or "",
        "likes": int(post.get("likes") or 0),
    }
    if cosines is not None and index < len(cosines):
        record["match"] = round(float(cosines[index]), 3)
    return record


def planet_member_cosines(matrix: np.ndarray | None, member_indices: list[int]) -> list[float]:
    """Cosine of each member row to the planet centroid."""
    if matrix is None or not member_indices:
        return []
    values = np.asarray(matrix, dtype=float)[member_indices]
    if values.size == 0:
        return []
    normalized = _normalize_rows(values)
    center = normalized.mean(axis=0)
    norm = np.linalg.norm(center) or 1.0
    center = center / norm
    return [float(row @ center) for row in normalized]
