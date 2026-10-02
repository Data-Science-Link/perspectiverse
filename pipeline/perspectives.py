"""Split one planet into two to six faces.

The live path picks a face count from the conversation instead of always
forcing a cube. Weak faces are not invented: k is chosen between 2 and 6.
Representative posts are ordered by likes, then by distance to the face
centroid in TF-IDF space. A lopsided topic is valid: volumes are renormalized
to 100.
"""

from __future__ import annotations

from pipeline.cluster_math import cluster_inertia, cluster_kmeans, distances_to_centers, salient_terms, vectorize
from pipeline.schema import MAX_FACES, MIN_FACES

MIN_FACE_SHARE = 0.12
# Another face has to explain at least this much of the remaining scatter.
_FACE_GAIN = 0.12


def choose_n_faces(
    texts: list[str],
    *,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
) -> int:
    """Pick a face count in [min_faces, max_faces] from how the posts separate."""
    count = len(texts)
    if count < min_faces:
        raise ValueError(f"Need at least {min_faces} posts to cut faces, found {count}")
    upper = min(max_faces, count)
    matrix = vectorize(texts)
    # The cube needs two faces. Further cuts have to be a real split.
    best_k = min_faces
    labels, _centers = cluster_kmeans(matrix, min_faces, seed=seed)
    prev = cluster_inertia(matrix, labels)
    for k in range(min_faces + 1, upper + 1):
        if prev <= 1e-4:
            break
        trial, _centers = cluster_kmeans(matrix, k, seed=seed)
        sizes = [int(sum(1 for label in trial if int(label) == index)) for index in range(k)]
        if min(sizes) / count < MIN_FACE_SHARE:
            break
        inertia = cluster_inertia(matrix, trial)
        if (prev - inertia) / prev < _FACE_GAIN:
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
) -> dict:
    """Cluster `texts` into `n_faces` non-empty groups, or choose a count."""
    if n_faces is None:
        n_faces = choose_n_faces(texts, seed=seed, min_faces=min_faces, max_faces=max_faces)
    if len(texts) < n_faces:
        raise ValueError(f"Need at least {n_faces} posts to cut {n_faces} faces, found {len(texts)}")
    matrix = vectorize(texts)
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
