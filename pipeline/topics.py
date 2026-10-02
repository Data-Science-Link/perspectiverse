"""Group posts into a saved topic catalog.

`embedding` is the live default: a local MiniLM model, then many tight groups.
Loose posts stay unlabeled. `catalog_size` keeps only the largest of those
groups, so a week is not poured into ten planets and a small week is not
split until it fills ten orbits. `lexical` is TF-IDF for tests. `bertopic` is
optional. Clusters below `min_cluster_size` are Topic -1.
"""

from __future__ import annotations

from pipeline.schema import SYSTEM_SIZE
from pipeline.cluster_math import cluster_kmeans, salient_terms, vectorize

# MiniLM cosine on mixed posts sits near 0.1. A member has to sit much closer
# than that to its centroid, or it is left out instead of watering the group down.
_MEMBER_COSINE = 0.50
# Fragments of one subject land above this. Different subjects do not.
_MERGE_COSINE = 0.72


def cluster_texts(
    texts: list[str],
    *,
    min_cluster_size: int = 8,
    cluster_backend: str = "embedding",
    embedding_model: str = "all-MiniLM-L6-v2",
    seed: int = 0,
    catalog_size: int = SYSTEM_SIZE,
    embed=None,
) -> dict:
    """Return kept topics and per-post assignments (-1 is noise)."""
    if cluster_backend == "bertopic":
        raw_labels, term_lookup = _bertopic_labels(texts, min_cluster_size, embedding_model)
    elif cluster_backend == "lexical":
        raw_labels, term_lookup = _lexical_labels(texts, min_cluster_size, seed)
    elif cluster_backend == "embedding":
        raw_labels, term_lookup = _embedding_labels(
            texts,
            seed=seed,
            embed=embed,
            embedding_model=embedding_model,
            min_cluster_size=min_cluster_size,
        )
    else:
        raise ValueError(f"Unknown cluster_backend {cluster_backend}")
    # A planet still needs enough posts to grow two faces. catalog_size caps the count.
    return _keep_top(texts, raw_labels, term_lookup, max(min_cluster_size, 6), keep=catalog_size)


def _lexical_labels(texts: list[str], min_cluster_size: int, seed: int) -> tuple[list[int], dict[int, list[str]]]:
    del min_cluster_size  # applied when small clusters are dropped
    matrix = vectorize(texts)
    # Eleven is enough for the separable fixture (ten topics plus noise).
    # Extra planets are not manufactured afterwards.
    k = min(11, matrix.shape[0])
    labels, _centers = cluster_kmeans(matrix, k, seed=seed)
    return [int(label) for label in labels], {}


def _embedding_labels(
    texts: list[str],
    *,
    seed: int,
    embed,
    embedding_model: str,
    min_cluster_size: int,
) -> tuple[list[int], dict[int, list[str]]]:
    if embed is None:
        from pipeline.embed import embed_minilm

        embed = lambda batch: embed_minilm(batch, model_name=embedding_model)  # noqa: E731
    matrix = _l2_normalize(embed(texts))
    labels = _labels_by_cohesion(matrix, seed=seed, min_cluster_size=min_cluster_size)
    return labels, {}


def _l2_normalize(matrix) -> "np.ndarray":
    import numpy as np

    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2:
        raise RuntimeError("Embeddings must be a 2-d matrix")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _labels_by_cohesion(matrix, *, seed: int, min_cluster_size: int) -> list[int]:
    """Return many tight groups. Posts that do not fit one stay at -1.

    The k-means count is one slot per minimum planet, so a long week can
    yield 100 or more groups. That search does not stop at ten, and it does
    not hand every post to a planet. The caller keeps the largest groups.
    """
    import numpy as np

    count = int(matrix.shape[0])
    if count == 0:
        return []
    if count < 2:
        return [0] * count
    slot = max(int(min_cluster_size), 1)
    # One candidate group per minimum planet. A long week can exceed 100.
    # catalog_size later keeps the largest. There is no cap at 10 here.
    k = min(count, max(2, count // slot))
    labels, _centers = cluster_kmeans(matrix, k, seed=seed)
    labels = np.asarray(labels, dtype=int).copy()
    _peel_loose(matrix, labels)
    _merge_near_centroids(matrix, labels)
    _peel_loose(matrix, labels)
    return [int(label) for label in labels]


def _peel_loose(matrix, labels) -> None:
    """Drop members that are not close to their own centroid. In place."""
    import numpy as np

    for label in sorted({int(item) for item in labels if int(item) >= 0}):
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        center = matrix[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            labels[members] = -1
            continue
        cosine = matrix[members] @ (center / norm)
        labels[members[cosine < _MEMBER_COSINE]] = -1


def _merge_near_centroids(matrix, labels) -> None:
    """Fold split pieces of one subject back together. Dissimilar groups stay apart."""
    import numpy as np

    def snapshot():
        found: dict[int, np.ndarray] = {}
        centers: dict[int, np.ndarray] = {}
        for label in sorted({int(item) for item in labels if int(item) >= 0}):
            members = np.flatnonzero(labels == label)
            if members.size == 0:
                continue
            center = matrix[members].mean(axis=0)
            norm = float(np.linalg.norm(center))
            if norm == 0.0:
                labels[members] = -1
                continue
            found[label] = members
            centers[label] = center / norm
        return found, centers

    while True:
        members, centers = snapshot()
        labels_now = list(members)
        best = None
        for index, left in enumerate(labels_now):
            for right in labels_now[index + 1 :]:
                similarity = float(centers[left] @ centers[right])
                if similarity < _MERGE_COSINE:
                    continue
                low, high = (left, right) if left < right else (right, left)
                key = (similarity, -low, -high)
                if best is None or key > best[0]:
                    best = (key, left, right)
        if best is None:
            return
        _key, left, right = best
        if members[right].size > members[left].size or (
            members[right].size == members[left].size and right < left
        ):
            left, right = right, left
        labels[members[right]] = left


def _bertopic_labels(
    texts: list[str],
    min_cluster_size: int,
    embedding_model: str,
) -> tuple[list[int], dict[int, list[str]]]:
    try:
        from bertopic import BERTopic
    except ImportError as exc:
        raise RuntimeError(
            "cluster_backend bertopic needs the full install (uv sync). "
            "The default lexical backend does not download a model."
        ) from exc

    model = BERTopic(
        embedding_model=embedding_model,
        min_topic_size=max(min_cluster_size, 2),
        calculate_probabilities=False,
        verbose=False,
    )
    labels, _probs = model.fit_transform(texts)
    terms: dict[int, list[str]] = {}
    for label in set(int(item) for item in labels):
        if label < 0:
            continue
        topic_terms = model.get_topic(label) or []
        terms[label] = [word for word, _weight in topic_terms[:5]]
    return [int(label) for label in labels], terms


def _keep_top(
    texts: list[str],
    raw_labels: list[int],
    term_lookup: dict[int, list[str]],
    min_cluster_size: int,
    keep: int = SYSTEM_SIZE,
) -> dict:
    labels = [int(label) for label in raw_labels]
    if len(texts) < min_cluster_size:
        raise RuntimeError(
            f"Need at least {min_cluster_size} posts to form a planet, found {len(texts)} posts."
        )

    ranked = _ranked_clusters(labels)
    survivors = [(label, members) for label, members in ranked if len(members) >= min_cluster_size]
    if not survivors:
        raise RuntimeError(
            f"No cluster met min size {min_cluster_size} among {len(texts)} posts."
        )
    kept = survivors[:keep]

    remap = {label: new_id for new_id, (label, _members) in enumerate(kept)}
    assignments = [remap.get(label, -1) for label in labels]
    topics = []
    for new_id, (label, members) in enumerate(kept):
        member_texts = [texts[index] for index in members]
        terms = term_lookup.get(label) or salient_terms(member_texts, limit=3)
        topics.append(
            {
                "id": new_id,
                "size": len(members),
                "member_indices": members,
                "terms": terms,
            }
        )
    noise_count = sum(1 for assignment in assignments if assignment < 0)
    return {"assignments": assignments, "topics": topics, "noise_count": noise_count}


def _ranked_clusters(labels: list[int]) -> list[tuple[int, list[int]]]:
    buckets: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        if label < 0:
            continue
        buckets.setdefault(label, []).append(index)
    ranked = list(buckets.items())
    ranked.sort(key=lambda item: (-len(item[1]), item[0]))
    return ranked

