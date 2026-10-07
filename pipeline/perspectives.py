"""Split one planet into two to six faces.

The live path tries every face count from two to six inside the planet's own
embedding space and keeps the count whose faces fit best (mean cosine
silhouette). A count only competes when every face is a real group: at least
``MIN_FACE_POSTS`` posts and ``MIN_FACE_SHARE`` of the planet, no two face
centroids closer than ``_FACE_COSINE`` (a paraphrase is not a second view),
and every face at least as tight as the planet it came from. Faces do not
have to be balanced; a small, tight minority is a face.

When no count from two to six passes, the planet has no honest second
perspective and ``choose_n_faces`` returns ``None``. The caller drops that
planet instead of padding it (issues #41, #53). Representative posts are the
closest rows to that face's embedding. Likes break a tie.
"""

from __future__ import annotations

from pipeline.cluster_math import (
    cluster_inertia,
    cluster_kmeans,
    cosines_to_centers,
    distances_to_centers,
    salient_terms,
    silhouette_cosine,
    vectorize,
)
from pipeline.schema import MAX_FACES, MIN_FACES

# A face this small is noise, not a perspective. Set low enough that a tight
# minority of ~5 % is kept rather than merged into the majority face (#41).
MIN_FACE_SHARE = 0.05
# One post is a remark, not a group of people holding a view.
MIN_FACE_POSTS = 2
# Planet merge treats 0.72 as the same subject. Two stances of that subject
# usually land between 0.75 and 0.88, so the face line has to sit higher.
# Closer than this and the cut is one stance written two ways.
_FACE_COSINE = 0.90
# Deterministic k-means restarts per face count. The lowest inertia wins.
_FACE_RESTARTS = 3


def _as_matrix(texts: list[str], matrix):
    if matrix is not None:
        return matrix
    return vectorize(texts)


def _unit_centers(matrix, labels, k: int):
    """Normalized face centroids, or None when a face is empty or degenerate."""
    import numpy as np

    labels = np.asarray(labels)
    centers = []
    for label in range(k):
        members = matrix[labels == label]
        if len(members) == 0:
            return None
        center = members.mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            return None
        centers.append(center / norm)
    return np.vstack(centers)


def _centroids_are_far(matrix, labels) -> bool:
    """True when every pair of face centroids is a real split, not a paraphrase."""
    import numpy as np

    labels = np.asarray(labels)
    k = len({int(item) for item in labels})
    remap = {old: new for new, old in enumerate(sorted({int(item) for item in labels}))}
    centers = _unit_centers(matrix, np.array([remap[int(item)] for item in labels]), k)
    if centers is None:
        return False
    similarity = centers @ centers.T
    np.fill_diagonal(similarity, -1.0)
    return bool(similarity.max() < _FACE_COSINE) if k > 1 else True


def _cohesion(matrix, labels, k: int) -> list[float]:
    """Mean cosine of each face's members to that face's centroid."""
    import numpy as np

    labels = np.asarray(labels)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    unit = matrix / norms[:, None]
    centers = _unit_centers(matrix, labels, k)
    if centers is None:
        return [0.0] * k
    return [float((unit[labels == label] @ centers[label]).mean()) for label in range(k)]


def _face_sizes(labels, k: int) -> list[int]:
    return [int(sum(1 for label in labels if int(label) == index)) for index in range(k)]


def _best_kmeans(values, k: int, seed: int):
    """Deterministic restarts of k-means; keep the lowest inertia."""
    count = int(values.shape[0])
    best = None
    for attempt in range(_FACE_RESTARTS):
        start = seed + attempt * max(count // _FACE_RESTARTS, 1)
        labels, centers = cluster_kmeans(values, k, seed=start)
        inertia = cluster_inertia(values, labels)
        if best is None or inertia < best[0] - 1e-12:
            best = (inertia, labels, centers)
    return best[1], best[2]


def score_face_counts(
    texts: list[str],
    *,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> list[dict]:
    """Every face count tried, with the gate results and the fit score.

    Each row: k, labels, centers, sizes, silhouette, max_centroid_cosine,
    min_cohesion, planet_cohesion, valid, reason.
    """
    import numpy as np

    values = _as_matrix(texts, matrix)
    count = int(values.shape[0])
    lower = max(int(min_faces), 2)
    upper = min(int(max_faces), count)
    rows: list[dict] = []
    if count < lower * MIN_FACE_POSTS:
        return rows
    planet = _cohesion(values, np.zeros(count, dtype=int), 1)[0]
    if cluster_inertia(values, np.zeros(count, dtype=int)) <= 1e-4:
        return rows
    floor = max(MIN_FACE_POSTS, MIN_FACE_SHARE * count)
    for k in range(lower, upper + 1):
        labels, centers = _best_kmeans(values, k, seed)
        sizes = _face_sizes(labels, k)
        row = {
            "k": k,
            "labels": labels,
            "centers": centers,
            "sizes": sizes,
            "silhouette": None,
            "max_centroid_cosine": None,
            "min_cohesion": None,
            "planet_cohesion": planet,
            "valid": False,
            "reason": "",
        }
        rows.append(row)
        if min(sizes) < floor:
            row["reason"] = f"face of {min(sizes)} posts is under {floor:g}"
            continue
        unit = _unit_centers(values, labels, k)
        if unit is None:
            row["reason"] = "empty face"
            continue
        similarity = unit @ unit.T
        np.fill_diagonal(similarity, -1.0)
        row["max_centroid_cosine"] = float(similarity.max())
        if row["max_centroid_cosine"] >= _FACE_COSINE:
            row["reason"] = "two faces are paraphrases"
            continue
        cohesion = _cohesion(values, labels, k)
        row["min_cohesion"] = min(cohesion)
        if row["min_cohesion"] + 1e-9 < planet:
            row["reason"] = "a face is looser than the planet"
            continue
        row["silhouette"] = silhouette_cosine(values, labels)
        if row["silhouette"] <= 0.0:
            row["reason"] = "faces do not separate"
            continue
        row["valid"] = True
    return rows


def _ranked_valid(rows: list[dict]) -> list[dict]:
    """Valid counts, best silhouette first; the smaller count wins a near tie."""
    valid = [row for row in rows if row["valid"]]
    return sorted(valid, key=lambda row: (-round(float(row["silhouette"]), 3), int(row["k"])))


def _pick(rows: list[dict]) -> dict | None:
    ranked = _ranked_valid(rows)
    return ranked[0] if ranked else None


def choose_n_faces(
    texts: list[str],
    *,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> int | None:
    """Pick 2..6 faces by fit, or None when the planet cannot support two real faces."""
    count = len(texts) if matrix is None else int(matrix.shape[0])
    if count < max(min_faces, 1):
        raise ValueError(f"Need at least {max(min_faces, 1)} posts to cut faces, found {count}")
    chosen = _pick(
        score_face_counts(texts, seed=seed, min_faces=min_faces, max_faces=max_faces, matrix=matrix)
    )
    return None if chosen is None else int(chosen["k"])


def split_perspectives(
    texts: list[str],
    *,
    n_faces: int | None = None,
    seed: int = 0,
    min_faces: int = MIN_FACES,
    max_faces: int = MAX_FACES,
    matrix=None,
) -> dict:
    """Cluster ``texts`` into faces.

    With ``n_faces`` the count is forced. Otherwise the best count in 2..6 is
    chosen; when none passes, ``faces`` is empty and ``reason`` says why, so
    the caller can drop the planet.
    """
    values = _as_matrix(texts, matrix)
    chosen_row = None
    rows: list[dict] = []
    if n_faces is None:
        rows = score_face_counts(
            texts, seed=seed, min_faces=min_faces, max_faces=max_faces, matrix=values
        )
        chosen_row = _pick(rows)
        if chosen_row is None:
            reasons = "; ".join(f"k={row['k']}: {row['reason']}" for row in rows) or "too few posts"
            return {
                "assignments": [],
                "distances": [],
                "cosines": [],
                "faces": [],
                "k_scores": _summaries(rows),
                "reason": f"no 2-6 face split passes ({reasons})",
                "alternatives": [],
            }
        n_faces = int(chosen_row["k"])
    if len(texts) < n_faces:
        raise ValueError(f"Need at least {n_faces} posts to cut {n_faces} faces, found {len(texts)}")
    if chosen_row is not None:
        labels, centers = chosen_row["labels"], chosen_row["centers"]
    else:
        labels, centers = cluster_kmeans(values, n_faces, seed=seed)
    result = _faces_from(texts, values, labels, centers, n_faces)
    result["k_scores"] = _summaries(rows)
    result["reason"] = ""
    # Other passing counts, best fit first, for a caller whose labels collapse.
    result["alternatives"] = [
        _faces_from(texts, values, row["labels"], row["centers"], int(row["k"]))
        for row in _ranked_valid(rows)
        if chosen_row is not None and row is not chosen_row
    ]
    return result


def _faces_from(texts: list[str], values, labels, centers, n_faces: int) -> dict:
    distances = distances_to_centers(values, labels, centers)
    cosines = cosines_to_centers(values, labels, centers)
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
        "k": n_faces,
        "assignments": [int(label) for label in labels],
        "distances": distances,
        "cosines": cosines,
        "faces": faces,
    }


def _summaries(rows: list[dict]) -> list[dict]:
    """Loggable k-selection scores without the arrays."""
    return [
        {
            "k": row["k"],
            "sizes": row["sizes"],
            "silhouette": None if row["silhouette"] is None else round(float(row["silhouette"]), 3),
            "valid": row["valid"],
            "reason": row["reason"],
        }
        for row in rows
    ]


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
