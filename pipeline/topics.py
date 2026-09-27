"""Group posts into 10 planets.

`lexical` is the default: TF-IDF and k-means, no model download.
`bertopic` uses all-MiniLM-L6-v2 when that extra stack is installed.
Topic -1 (below min_cluster_size, or rank 11+) is excluded from the denominator.
When k-means leaves fewer than 10 planets above the size floor, leftover and
surplus posts are reassigned so a live sample still publishes 10 cubes.
"""

from __future__ import annotations

from pipeline.cluster_math import cluster_kmeans, grow_clusters_to_min, salient_terms, vectorize


def cluster_texts(
    texts: list[str],
    *,
    min_cluster_size: int = 8,
    cluster_backend: str = "lexical",
    embedding_model: str = "all-MiniLM-L6-v2",
    seed: int = 0,
) -> dict:
    """Return 10 kept topics and per-post assignments (-1 is noise)."""
    if cluster_backend == "bertopic":
        raw_labels, term_lookup = _bertopic_labels(texts, min_cluster_size, embedding_model)
    elif cluster_backend == "lexical":
        raw_labels, term_lookup = _lexical_labels(texts, min_cluster_size, seed)
    else:
        raise ValueError(f"Unknown cluster_backend {cluster_backend}")
    # Keep enough posts that a planet can still grow two to six faces.
    return _keep_top(texts, raw_labels, term_lookup, max(min_cluster_size, 6))


def _lexical_labels(texts: list[str], min_cluster_size: int, seed: int) -> tuple[list[int], dict[int, list[str]]]:
    del min_cluster_size  # applied when the top 10 are selected
    matrix = vectorize(texts)
    k = min(11, matrix.shape[0])
    labels, _centers = cluster_kmeans(matrix, k, seed=seed)
    return [int(label) for label in labels], {}


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
    keep: int = 10,
) -> dict:
    labels = [int(label) for label in raw_labels]
    if len(texts) < keep * min_cluster_size:
        raise RuntimeError(
            f"Need {keep} clusters of at least {min_cluster_size} posts, found {len(texts)} posts. "
            "Raise sample_size."
        )

    labels = _ensure_cluster_count(texts, labels, keep, min_cluster_size)
    ranked = _ranked_clusters(labels)
    if len(ranked) < keep:
        raise RuntimeError(
            f"Need {keep} clusters of at least {min_cluster_size} posts, found {len(ranked)}. "
            "Lower min_cluster_size or raise sample_size."
        )

    survivors = [(label, members) for label, members in ranked if len(members) >= min_cluster_size]
    if len(survivors) >= keep:
        kept = survivors[:keep]
    else:
        selected = {label for label, _members in ranked[:keep]}
        grown = grow_clusters_to_min(vectorize(texts), labels, selected, min_cluster_size)
        labels = [int(label) for label in grown]
        kept = []
        for label, members in _ranked_clusters(labels):
            if label not in selected:
                continue
            if len(members) < min_cluster_size:
                raise RuntimeError(
                    f"Need {keep} clusters of at least {min_cluster_size} posts, "
                    f"found {len(kept)} after rebalance. Lower min_cluster_size or raise sample_size."
                )
            kept.append((label, members))
        kept.sort(key=lambda item: (-len(item[1]), item[0]))
        if len(kept) < keep:
            raise RuntimeError(
                f"Need {keep} clusters of at least {min_cluster_size} posts, found {len(kept)}. "
                "Lower min_cluster_size or raise sample_size."
            )

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


def _ensure_cluster_count(texts: list[str], labels: list[int], keep: int, min_cluster_size: int) -> list[int]:
    """Split the largest planets until k-means/BERTopic produced `keep` groups."""
    labels = list(labels)
    next_label = max(labels) + 1 if labels else 0
    for _ in range(keep):
        ranked = _ranked_clusters(labels)
        if len(ranked) >= keep:
            return labels
        candidates = [(label, members) for label, members in ranked if len(members) >= 2 * min_cluster_size]
        if not candidates:
            return labels
        label, members = candidates[0]
        member_texts = [texts[index] for index in members]
        local_labels, _centers = cluster_kmeans(vectorize(member_texts), 2, seed=0)
        for local, index in zip(local_labels, members):
            labels[index] = label if int(local) == 0 else next_label
        next_label += 1
    return labels
