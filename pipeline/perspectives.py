"""Split one planet into one to six faces.

The live path picks a face count from the conversation. A second face is kept
only when it is large and is a different stance, not a paraphrase. One stance
stays one face. Representative posts are ordered by likes, then by distance
to the face centroid. A lopsided topic is valid: volumes are renormalized to 100.
"""

from __future__ import annotations

from pipeline.cluster_math import cluster_inertia, cluster_kmeans, distances_to_centers, salient_terms, vectorize
from pipeline.schema import MAX_FACES, MIN_FACES

# A second face has to be about a fifth of the planet. A short tail is not a view.
MIN_FACE_SHARE = 0.20
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


def choose_n_faces(
    texts: list[str],
    *,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> int:
    """Pick a face count from how the posts separate. One face is allowed."""
    count = len(texts) if matrix is None else int(matrix.shape[0])
    if count < max(min_faces, 1):
        raise ValueError(f"Need at least {max(min_faces, 1)} posts to cut faces, found {count}")
    upper = min(max_faces, count)
    values = _as_matrix(texts, matrix)
    if count < 2 or upper < 2:
        return 1
    best_k = 1
    labels, _centers = cluster_kmeans(values, 1, seed=seed)
    prev = cluster_inertia(values, labels)
    for k in range(2, upper + 1):
        if prev <= 1e-4:
            break
        trial, _centers = cluster_kmeans(values, k, seed=seed)
        sizes = [int(sum(1 for label in trial if int(label) == index)) for index in range(k)]
        if min(sizes) / count < MIN_FACE_SHARE:
            break
        if not _centroids_are_far(values, trial):
            break
        inertia = cluster_inertia(values, trial)
        if prev <= 1e-4 or (prev - inertia) / prev < _FACE_GAIN:
            break
        best_k = k
        prev = inertia
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
        "faces": faces,
    }


def select_representatives(posts: list[dict], distances: list[float], limit: int = 12) -> list[dict]:
    """Highest likes first. Equal likes break toward the centroid."""
    order = sorted(
        range(len(posts)),
        key=lambda index: (-int(posts[index].get("likes") or 0), distances[index], index),
    )
    chosen = []
    for index in order[:limit]:
        post = posts[index]
        chosen.append(
            {
                "author": post.get("author") or "unknown",
                "text": post.get("clean_text") or post.get("text") or "",
                "likes": int(post.get("likes") or 0),
            }
        )
    return chosen
