"""Group posts into 10 planets.

`lexical` is the default: TF-IDF and k-means, no model download.
`bertopic` uses all-MiniLM-L6-v2 when that extra stack is installed.
Topic -1 (below min_cluster_size, or rank 11+) is excluded from the denominator.
"""

from __future__ import annotations

from pipeline.cluster_math import cluster_kmeans, salient_terms, vectorize


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
    # Six faces need six posts, so a planet is never smaller than that.
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
    buckets: dict[int, list[int]] = {}
    for index, label in enumerate(raw_labels):
        buckets.setdefault(int(label), []).append(index)

    survivors = []
    for label, members in buckets.items():
        if label < 0 or len(members) < min_cluster_size:
            continue
        survivors.append((label, members))
    survivors.sort(key=lambda item: (-len(item[1]), item[0]))
    if len(survivors) < keep:
        raise RuntimeError(
            f"Need {keep} clusters of at least {min_cluster_size} posts, found {len(survivors)}. "
            "Lower min_cluster_size or raise sample_size."
        )

    kept = survivors[:keep]
    remap = {label: new_id for new_id, (label, _members) in enumerate(kept)}
    assignments = [remap.get(label, -1) for label in raw_labels]
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
