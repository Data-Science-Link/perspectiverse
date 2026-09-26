"""Split one planet into exactly six faces.

Representative posts are ordered by likes, then by distance to the face centroid
in TF-IDF space. A lopsided topic is valid: volumes are renormalized to 100.
"""

from __future__ import annotations

from pipeline.cluster_math import cluster_kmeans, distances_to_centers, salient_terms, vectorize


def split_perspectives(texts: list[str], *, n_faces: int = 6, seed: int = 0) -> dict:
    """Cluster `texts` into `n_faces` non-empty groups."""
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
