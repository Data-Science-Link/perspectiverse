"""Split one planet into two to six faces.

The live path tries every face count from two to six inside the planet's own
embedding space and keeps the count whose faces fit best (mean cosine
silhouette). A count only competes when every face is a real group: at least
``MIN_FACE_POSTS`` posts and ``MIN_FACE_SHARE`` of the planet, no paraphrase
pair, and every face at least as tight as the planet it came from. A
paraphrase pair is two face centroids at or above ``_PARAPHRASE_COSINE``
whose posts do not take opposite sides. Faces do not have to be balanced; a
small, tight minority is a face.

When no count from two to six passes, the planet is one face and every post
stays on it. ``choose_n_faces`` returns ``None``. ``split_perspectives`` does
not force a second face. Representative posts are the closest rows to that
face's embedding. Likes break a tie.
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
from pipeline.grouping import distinctness_score, force_two_labels
from pipeline.schema import MAX_FACES, MIN_FACES

# A face this small is noise, not a perspective. Set low enough that a tight
# minority of ~5 % is kept rather than merged into the majority face (#41).
MIN_FACE_SHARE = 0.05
# One post is a remark, not a group of people holding a view.
MIN_FACE_POSTS = 2
# Planet merge treats 0.72 as the same subject. Centroids from 0.80 up are one
# stance written two ways unless the posts actually disagree. The old hard
# ceiling (_FACE_COSINE, 0.90) accepted that 0.80–0.89 band with no
# disagreement check, which is how paraphrase faces shipped (The Show at
# 0.849). Issue #286.
_FACE_COSINE = 0.90
_PARAPHRASE_COSINE = 0.80
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


def _posts_disagree(left_posts: list[dict], right_posts: list[dict]) -> bool:
    """True when the free stance lexicon says these posts take opposite sides.

    Titles are empty on purpose. The split has not been labeled, and this
    check must not wait for a title, a fold, or a model call.
    """
    from pipeline.stance import local_faces_disagree

    return local_faces_disagree({}, {}, left_posts, right_posts)


def _posts_for_label(texts: list[str], labels, label: int) -> list[dict]:
    return [{"text": texts[index]} for index, item in enumerate(labels) if int(item) == label]


def _refused_given_centers(texts: list[str], labels, unit) -> list[tuple[int, int, float]]:
    """Face pairs at or above the paraphrase line whose posts do not disagree.

    ``labels`` and ``unit`` are already numbered 0..k-1.
    """
    import numpy as np

    labels = np.asarray(labels)
    refused: list[tuple[int, int, float]] = []
    k = int(unit.shape[0])
    for left in range(k):
        for right in range(left + 1, k):
            cosine = float(unit[left] @ unit[right])
            if cosine < _PARAPHRASE_COSINE:
                continue
            if _posts_disagree(_posts_for_label(texts, labels, left), _posts_for_label(texts, labels, right)):
                continue
            refused.append((left, right, cosine))
    return refused


def refused_paraphrase_pairs(texts: list[str], labels, matrix) -> list[tuple[int, int, float]]:
    """Pairs this split must not publish, as ``(left_label, right_label, cosine)``.

    A pair of face centroids at or above ``_PARAPHRASE_COSINE`` is one stance
    written two ways, unless the posts take opposite sides. Below that line
    the geometric gates still decide. The lexicon is the free #268 check. It
    does not call a model.
    """
    import numpy as np

    labels = np.asarray(labels)
    values = np.asarray(matrix)
    if len(texts) != int(values.shape[0]) or len(texts) != int(labels.shape[0]):
        raise ValueError("texts, labels, and matrix rows must describe the same posts")
    present = sorted({int(item) for item in labels})
    if len(present) < 2:
        return []
    remap = {old: new for new, old in enumerate(present)}
    mapped = np.array([remap[int(item)] for item in labels])
    unit = _unit_centers(values, mapped, len(present))
    if unit is None:
        return [(present[0], present[1], 1.0)]
    return [
        (present[left], present[right], cosine)
        for left, right, cosine in _refused_given_centers(texts, mapped, unit)
    ]


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
        refused = _refused_given_centers(texts, labels, unit)
        if refused:
            cosine = max(item[2] for item in refused)
            row["reason"] = f"two faces are paraphrases ({cosine:.3f}; posts do not disagree)"
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
    chosen. When none passes, the planet is one perspective (``single_view``)
    and ``forced`` is false. A second face is created only when the distance
    gates already used here say the views are distinct. ``distinctness`` is 0
    when there is one face or the centroids match, and 1 when they are orthogonal.
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
            import numpy as np

            count = int(values.shape[0])
            if count < 1:
                return {
                    "assignments": [],
                    "distances": [],
                    "cosines": [],
                    "faces": [],
                    "k_scores": _summaries(rows),
                    "reason": f"no distinct second view ({reasons})",
                    "alternatives": [],
                    "forced": False,
                    "distinctness": 0.0,
                    "method": "",
                    "single_view": True,
                }
            # No k in 2..6 cleared the distance gates. Publish the planet as
            # one perspective instead of padding a second face.
            single = np.zeros(count, dtype=int)
            centers = _mean_centers(values, single, 1)
            result = _faces_from(texts, values, single, centers, 1)
            result["k_scores"] = _summaries(rows)
            result["reason"] = f"no distinct second view ({reasons})"
            result["alternatives"] = []
            result["forced"] = False
            result["distinctness"] = 0.0
            result["method"] = "single_view"
            result["single_view"] = True
            return result
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
    result["forced"] = False
    result["distinctness"] = round(distinctness_score(values, labels), 3)
    result["method"] = "silhouette_kmeans"
    # Other passing counts, best fit first, for a caller whose labels collapse.
    result["alternatives"] = [
        _faces_from(texts, values, row["labels"], row["centers"], int(row["k"]))
        for row in _ranked_valid(rows)
        if chosen_row is not None and row is not chosen_row
    ]
    return result


def _mean_centers(matrix, labels, k: int):
    import numpy as np

    labels = np.asarray(labels)
    centers = np.zeros((k, matrix.shape[1]), dtype=float)
    for label in range(k):
        members = matrix[labels == label]
        if len(members):
            centers[label] = members.mean(axis=0)
    return centers


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
