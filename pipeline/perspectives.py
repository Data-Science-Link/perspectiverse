"""Split one planet into two to six faces.

The live path picks a face count from the conversation. A second face is kept
when it is a different wording, not a paraphrase of the same sentence. A
uniform pile stays one face. Representative posts are the closest rows to that face's embedding.
Likes break a tie. A lopsided topic is valid: volumes are
renormalized to 100.
"""

from __future__ import annotations

from pipeline.cluster_math import (
    cluster_inertia,
    cluster_kmeans,
    cosines_to_centers,
    distances_to_centers,
    salient_terms,
    vectorize,
)
from pipeline.schema import MAX_FACES, MIN_FACES

# Six equal faces are about a sixth of the planet. A short tail is not a view,
# but a first unbalanced cut must not hide a cleaner split at a higher k.
MIN_FACE_SHARE = 0.15
# MiniLM leaves two stances of one subject close together. A cut that explains
# a few percent of the scatter is a real second view; TF-IDF paraphrases fail
# the share test before this bar matters.
_FACE_GAIN = 0.035
# Planet merge treats 0.72 as the same subject. Two stances of that subject
# usually land between 0.75 and 0.88, so the face line has to sit higher.
# Closer than this and the cut is one stance written two ways.
_FACE_COSINE = 0.90


def _as_matrix(texts: list[str], matrix):
    if matrix is not None:
        return matrix
    return vectorize(texts)


def _centroids_are_far(matrix, labels) -> bool:
    """True when every pair of face centroids is a real split, not a paraphrase."""
    import numpy as np

    labels = np.asarray(labels)
    centers = []
    for label in sorted({int(item) for item in labels}):
        members = matrix[labels == label]
        if len(members) == 0:
            return False
        center = members.mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            return False
        centers.append(center / norm)
    for index, left in enumerate(centers):
        for right in centers[index + 1 :]:
            if float(left @ right) >= _FACE_COSINE:
                return False
    return True


def _face_sizes(labels, k: int) -> list[int]:
    return [int(sum(1 for label in labels if int(label) == index)) for index in range(k)]


def choose_n_faces(
    texts: list[str],
    *,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> int:
    """Pick a face count from how the posts separate.

    Two to six faces when the posts form distinct groups. One face stays only
    when every cut is a paraphrase or an empty slice of a uniform pile.
    """
    count = len(texts) if matrix is None else int(matrix.shape[0])
    if count < max(min_faces, 1):
        raise ValueError(f"Need at least {max(min_faces, 1)} posts to cut faces, found {count}")
    upper = min(max_faces, count)
    values = _as_matrix(texts, matrix)
    if count < 2 or upper < 2:
        return 1
    labels, _centers = cluster_kmeans(values, 1, seed=seed)
    base = cluster_inertia(values, labels)
    if base <= 1e-4:
        return 1
    best_k = 1
    prev = base
    for k in range(2, upper + 1):
        trial, _centers = cluster_kmeans(values, k, seed=seed)
        sizes = _face_sizes(trial, k)
        if min(sizes) < 2 or min(sizes) / count < MIN_FACE_SHARE:
            continue
        if not _centroids_are_far(values, trial):
            continue
        inertia = cluster_inertia(values, trial)
        if prev <= 1e-4 or (prev - inertia) / prev < _FACE_GAIN:
            continue
        best_k = k
        prev = inertia
    if best_k == 1 and count >= 4:
        # A far minority is still its own perspective. Stopping at one bar of
        # 100% hid that view whenever the first cut was smaller than a fifth.
        trial, _centers = cluster_kmeans(values, 2, seed=seed)
        sizes = _face_sizes(trial, 2)
        inertia = cluster_inertia(values, trial)
        gain = (base - inertia) / base if base > 1e-4 else 0.0
        if min(sizes) >= 1 and _centroids_are_far(values, trial) and gain >= _FACE_GAIN:
            return 2
    return best_k


def split_perspectives(
    texts: list[str],
    *,
    n_faces: int | None = None,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> dict:
    """Cluster `texts` into `n_faces` non-empty groups, or choose a count."""
    values = _as_matrix(texts, matrix)
    if n_faces is None:
        n_faces = choose_n_faces(
            texts,
            seed=seed,
            min_faces=min_faces,
            max_faces=max_faces,
            matrix=values,
        )
    if len(texts) < n_faces:
        raise ValueError(f"Need at least {n_faces} posts to cut {n_faces} faces, found {len(texts)}")
    matrix = values
    labels, centers = cluster_kmeans(matrix, n_faces, seed=seed)
    distances = distances_to_centers(matrix, labels, centers)
    cosines = cosines_to_centers(matrix, labels, centers)
    faces = []
    for face_index in range(n_faces):
        members = [index for index, label in enumerate(labels) if int(label) == face_index]
        member_texts = [texts[index] for index in members]
        faces.append(
            {
                "index": face_index,
                "member_indices": members,
                "size": len(members),
                "terms": salient_terms(member_texts, limit=3),
            }
        )
    return {
        "assignments": [int(label) for label in labels],
        "distances": distances,
        "cosines": cosines,
        "faces": faces,
    }


def select_representatives(
    posts: list[dict],
    distances: list[float],
    limit: int = 36,
    matches: list[float] | None = None,
) -> list[dict]:
    """Closest embedding first. Likes break a tie.

    ``matches`` are cosines to the face centroid from the matrix already used
    to cluster. ``limit`` matches ``EXAMPLE_POST_CAP`` in pipeline.settings.
    """
    scores = list(matches) if matches is not None and len(matches) == len(posts) else None

    def sort_key(index: int) -> tuple:
        likes = int(posts[index].get("likes") or 0)
        if scores is not None:
            return (-float(scores[index]), -likes, index)
        return (float(distances[index]), -likes, index)

    chosen = []
    for index in sorted(range(len(posts)), key=sort_key)[:limit]:
        post = posts[index]
        record = {
            "author": post.get("author") or "unknown",
            "text": post.get("clean_text") or post.get("text") or "",
            "likes": int(post.get("likes") or 0),
        }
        if scores is not None:
            record["match"] = round(float(scores[index]), 3)
        chosen.append(record)
    return chosen
