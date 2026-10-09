"""Stance-style splits inside one planet, and the scores used to compare them.

Sentence embeddings put a whole topic in one neighborhood, so a silhouette
gate on those embeddings often finds no second face. These helpers still
return a 2-way split, and they score how different the faces ended up.
No network calls. Deterministic given the texts, the matrix, and ``seed``.
"""

from __future__ import annotations

import numpy as np

from pipeline.cluster_math import (
    cluster_kmeans,
    salient_terms,
    silhouette_cosine,
    tokenize,
    vectorize,
)

# Same floors the face splitter uses. Imported as literals so this module
# does not import pipeline.perspectives (that module imports us).
MIN_FACE_POSTS = 2
MIN_FACE_SHARE = 0.05
# A published planet, including a story split out of a glued candidate.
# Overridable via settings ``min_planet_posts`` and PERSPECTIVERSE_MIN_PLANET_POSTS.
MIN_PLANET_POSTS = 5


def l2_rows(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _label_ids(labels) -> list[int]:
    return sorted({int(item) for item in np.asarray(labels) if int(item) >= 0})


def face_sizes(labels) -> list[int]:
    ids = _label_ids(labels)
    array = np.asarray(labels)
    return [int(np.sum(array == label)) for label in ids]


def unit_centers(matrix: np.ndarray, labels) -> np.ndarray | None:
    values = l2_rows(matrix)
    array = np.asarray(labels)
    ids = _label_ids(array)
    if len(ids) < 1:
        return None
    centers = []
    for label in ids:
        members = values[array == label]
        if len(members) == 0:
            return None
        center = members.mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            return None
        centers.append(center / norm)
    return np.vstack(centers)


def max_centroid_cosine(matrix: np.ndarray, labels) -> float | None:
    """Highest cosine between two face centroids. None when there is one face."""
    centers = unit_centers(matrix, labels)
    if centers is None or len(centers) < 2:
        return None
    similarity = centers @ centers.T
    np.fill_diagonal(similarity, -1.0)
    return float(similarity.max())


def distinctness_score(matrix: np.ndarray, labels) -> float:
    """1 when face centroids are orthogonal or opposite, 0 when they match.

    One face scores 0. Values above 1 are clipped; a negative cosine is
    already as distinct as this score goes.
    """
    cosine = max_centroid_cosine(matrix, labels)
    if cosine is None:
        return 0.0
    return float(min(1.0, max(0.0, 1.0 - cosine)))


def size_balance(sizes: list[int]) -> float:
    """Smallest face divided by the largest. 1 means equal counts."""
    if not sizes or max(sizes) <= 0:
        return 0.0
    return float(min(sizes) / max(sizes))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def pairwise_jaccard(groups: list[list[str]]) -> float:
    """Mean pairwise Jaccard. 1 means every face carries the same tokens."""
    sets = [{token.lower() for token in group if token} for group in groups]
    if len(sets) < 2:
        return 0.0
    scores = [
        _jaccard(sets[left], sets[right])
        for left in range(len(sets))
        for right in range(left + 1, len(sets))
    ]
    return float(sum(scores) / len(scores))


def class_tfidf_terms(texts: list[str], labels, limit: int = 5) -> list[list[str]]:
    """Top class-based TF-IDF terms for each face, BERTopic's representation step.

    Each face is one document. Term frequency is L1-normalized inside the
    face. The idf is ``log(1 + n_faces / faces_containing_term)``.
    """
    array = np.asarray(labels)
    ids = _label_ids(array)
    docs = []
    for label in ids:
        members = [texts[index] for index, item in enumerate(array) if int(item) == label]
        counts: dict[str, int] = {}
        for text in members:
            for token in set(tokenize(text)):
                counts[token] = counts.get(token, 0) + 1
        docs.append(counts)
    if not docs:
        return []
    document_frequency: dict[str, int] = {}
    for counts in docs:
        for term in counts:
            document_frequency[term] = document_frequency.get(term, 0) + 1
    faces = len(docs)
    ranked: list[list[str]] = []
    for counts in docs:
        total = sum(counts.values()) or 1
        scored = []
        for term, seen in counts.items():
            weight = (seen / total) * np.log(1.0 + faces / document_frequency[term])
            scored.append((float(weight), term))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ranked.append([term for _weight, term in scored[:limit]])
    return ranked


def term_sets(texts: list[str], labels, limit: int = 5) -> list[list[str]]:
    """Pipeline salient terms per face. Falls back to one c-TF-IDF term."""
    array = np.asarray(labels)
    ids = _label_ids(array)
    ctfidf = class_tfidf_terms(texts, labels, limit=limit)
    found = []
    for position, label in enumerate(ids):
        members = [texts[index] for index, item in enumerate(array) if int(item) == label]
        terms = salient_terms(members, limit=limit)
        if not terms and position < len(ctfidf):
            terms = ctfidf[position][:1]
        found.append(terms)
    return found


def ensure_two_sides(labels: np.ndarray, scores: np.ndarray, floor: int) -> np.ndarray:
    """Move boundary points until both sides have ``floor`` posts, when possible."""
    labels = np.asarray(labels, dtype=int).copy()
    scores = np.asarray(scores, dtype=float)
    count = int(labels.shape[0])
    if count < 2:
        return labels
    needed = max(1, min(int(floor), count // 2))
    # Collapse any unexpected third label onto the nearer of 0 and 1.
    labels = np.where(labels <= 0, 0, 1)
    for _ in range(count):
        sizes = np.bincount(labels, minlength=2)
        if int(sizes.min()) >= needed and int(sizes[0]) > 0 and int(sizes[1]) > 0:
            return labels
        small = 0 if sizes[0] <= sizes[1] else 1
        large = 1 - small
        donors = np.flatnonzero(labels == large)
        if donors.size == 0:
            break
        # Class 1 is the high-score side. Give the small side its nearest donor.
        if small == 0:
            chosen = int(donors[np.argmin(scores[donors])])
        else:
            chosen = int(donors[np.argmax(scores[donors])])
        labels[chosen] = small
    return labels


def _side_scores(matrix: np.ndarray, labels, centers: np.ndarray) -> np.ndarray:
    """Positive when a row is closer to center 1 than center 0."""
    values = np.asarray(matrix, dtype=float)
    assigned = np.asarray(centers, dtype=float)
    if assigned.shape[0] < 2:
        return np.zeros(values.shape[0], dtype=float)
    zero = np.linalg.norm(values - assigned[0], axis=1)
    one = np.linalg.norm(values - assigned[1], axis=1)
    return zero - one


def residual_axis_split(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split on the first principal direction after removing the shared topic.

    Subtracting the planet mean takes out the direction every post shares.
    What is left is the strongest leftover contrast. Sign of that projection
    is the two faces.
    """
    values = l2_rows(matrix)
    centered = values - values.mean(axis=0, keepdims=True)
    if float(np.linalg.norm(centered)) < 1e-8:
        scores = np.linspace(-1.0, 1.0, values.shape[0])
        labels = np.zeros(values.shape[0], dtype=int)
        labels[values.shape[0] // 2 :] = 1
        return labels, scores
    _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
    axis = vt[0]
    scores = centered @ axis
    # Point the axis so the first row is non-negative. That makes the cut stable.
    if scores[int(np.argmax(np.abs(scores)))] < 0:
        scores = -scores
    labels = (scores >= 0).astype(int)
    if labels.min() == labels.max():
        labels = np.zeros(values.shape[0], dtype=int)
        labels[int(np.argmax(scores)) if scores.max() != scores.min() else values.shape[0] // 2] = 1
    return labels, scores


def ward_labels(matrix: np.ndarray, k: int) -> np.ndarray:
    """Agglomerative clustering with Ward's minimum-variance link.

    Distance is squared Euclidean. The Lance-Williams update for that
    distance is exact, so the cut does not depend on a k-means restart.
    """
    values = np.asarray(matrix, dtype=float)
    count = int(values.shape[0])
    if k < 1 or k > count:
        raise ValueError(f"Ward needs 1..{count} clusters, got {k}")
    if k == count:
        return np.arange(count, dtype=int)
    squared = np.einsum("ij,ij->i", values, values)
    distance = squared[:, None] + squared[None, :] - 2.0 * (values @ values.T)
    np.maximum(distance, 0.0, out=distance)
    np.fill_diagonal(distance, np.inf)
    members: list[list[int]] = [[index] for index in range(count)]
    sizes = np.ones(count, dtype=float)
    active = np.ones(count, dtype=bool)
    remaining = count
    while remaining > k:
        view = np.where(active[:, None] & active[None, :], distance, np.inf)
        flat = int(np.argmin(view))
        left, right = divmod(flat, count)
        if left > right:
            left, right = right, left
        if not np.isfinite(view[left, right]):
            break
        left_size = float(sizes[left])
        right_size = float(sizes[right])
        gap = float(distance[left, right])
        targets = np.flatnonzero(active)
        targets = targets[(targets != left) & (targets != right)]
        if targets.size:
            target_size = sizes[targets]
            updated = (
                (left_size + target_size) * distance[left, targets]
                + (right_size + target_size) * distance[right, targets]
                - target_size * gap
            ) / (left_size + right_size + target_size)
            updated = np.maximum(updated, 0.0)
            distance[left, targets] = updated
            distance[targets, left] = updated
        distance[right, :] = np.inf
        distance[:, right] = np.inf
        distance[left, left] = np.inf
        sizes[left] = left_size + right_size
        active[right] = False
        members[left].extend(members[right])
        members[right] = []
        remaining -= 1
    labels = np.empty(count, dtype=int)
    for new_id, index in enumerate(np.flatnonzero(active)):
        labels[members[int(index)]] = new_id
    return labels


def spectral_labels(matrix: np.ndarray, k: int, seed: int = 0) -> np.ndarray:
    """Ng, Jordan, and Weiss spectral clustering on cosine affinity."""
    values = l2_rows(matrix)
    count = int(values.shape[0])
    if k < 2 or k > count:
        raise ValueError(f"Spectral clustering needs 2..{count} clusters, got {k}")
    affinity = values @ values.T
    np.maximum(affinity, 0.0, out=affinity)
    np.fill_diagonal(affinity, 0.0)
    degrees = affinity.sum(axis=1)
    if float(degrees.sum()) <= 1e-8:
        fallback, _centers = cluster_kmeans(values, k, seed=seed)
        return np.asarray(fallback, dtype=int)
    degrees = np.maximum(degrees, 1e-12)
    scale = 1.0 / np.sqrt(degrees)
    normalized = affinity * scale[:, None] * scale[None, :]
    _values, vectors = np.linalg.eigh(normalized)
    rows = vectors[:, -k:]
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    labels, _centers = cluster_kmeans(rows / norms, k, seed=seed)
    return np.asarray(labels, dtype=int)


def _components(count: int, edges: list[tuple[float, int, int]], threshold: float, min_size: int) -> np.ndarray:
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for weight, left, right in edges:
        if weight <= threshold:
            union(left, right)
    groups: dict[int, list[int]] = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)
    labels = np.full(count, -1, dtype=int)
    next_id = 0
    for members in groups.values():
        if len(members) < min_size:
            continue
        for index in members:
            labels[index] = next_id
        next_id += 1
    return labels


def _assign_noise(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    values = l2_rows(matrix)
    labels = np.asarray(labels, dtype=int).copy()
    ids = _label_ids(labels)
    if not ids:
        return labels
    centers = []
    for label in ids:
        center = values[labels == label].mean(axis=0)
        norm = float(np.linalg.norm(center))
        centers.append(center / norm if norm else center)
    stacked = np.vstack(centers)
    noise = np.flatnonzero(labels < 0)
    if noise.size:
        choice = (values[noise] @ stacked.T).argmax(axis=1)
        labels[noise] = np.asarray(ids, dtype=int)[choice]
    return labels


def mutual_reachability_labels(matrix: np.ndarray, min_cluster_size: int = 4) -> np.ndarray | None:
    """Single-linkage cut on mutual reachability, the HDBSCAN hierarchy.

    This is the density tree from Campello, Moulavi, and Sander, cut at the
    quantile whose non-noise components separate best. It is not their full
    excess-of-mass extractor. Returns None when fewer than two clusters survive.
    """
    values = l2_rows(matrix)
    count = int(values.shape[0])
    if count < 4:
        return None
    floor = max(2, min(int(min_cluster_size), count // 2))
    distance = 1.0 - (values @ values.T)
    np.clip(distance, 0.0, None, out=distance)
    np.fill_diagonal(distance, np.inf)
    neighbors = min(floor, count - 1)
    core = np.partition(distance, neighbors - 1, axis=1)[:, neighbors - 1]
    reach = np.maximum(distance, np.maximum(core[:, None], core[None, :]))
    np.fill_diagonal(reach, 0.0)
    selected = np.zeros(count, dtype=bool)
    selected[0] = True
    parent = np.zeros(count, dtype=int)
    weight = reach[0].copy()
    edges: list[tuple[float, int, int]] = []
    for _ in range(count - 1):
        weight[selected] = np.inf
        nxt = int(np.argmin(weight))
        if not np.isfinite(weight[nxt]):
            break
        edges.append((float(weight[nxt]), int(parent[nxt]), nxt))
        selected[nxt] = True
        better = (~selected) & (reach[nxt] < weight)
        parent[better] = nxt
        weight[better] = reach[nxt][better]
    if not edges:
        return None
    weights = np.array([item[0] for item in edges], dtype=float)
    best = None
    for quantile in (0.5, 0.7, 0.8, 0.9, 0.95):
        threshold = float(np.quantile(weights, quantile))
        raw = _components(count, edges, threshold, floor)
        clusters = _label_ids(raw)
        if len(clusters) < 2:
            continue
        assigned = _assign_noise(values, raw)
        score = silhouette_cosine(values, assigned)
        key = (round(score, 4), -len(clusters))
        if best is None or key > best[0]:
            best = (key, assigned)
    if best is None:
        return None
    return best[1]


# A post has to sit this close to its group's center, or it is not a member.
# Same line the old member peel used. Unrelated MiniLM posts sit near 0.1.
_BALL_MEMBER = 0.50
# Two centers at least this similar are one subject that the grid split apart.
_BALL_MERGE = 0.72
# A group whose posts only barely clear the peel is a mood, not a subject.
_BALL_MEAN = 0.60
# Full cohesive clustering through this size. Above it, centers come from a
# sample of this many posts and everyone else joins a center only when they
# sit inside that ball. A 100K window does not build an n×k distance matrix.
_EXACT_BALL_LIMIT = 12_000


def _peel_members(unit: np.ndarray, labels: np.ndarray, minimum: float) -> None:
    """Drop members farther than `minimum` cosine from their own center. In place."""
    for label in _label_ids(labels):
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        center = unit[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            labels[members] = -1
            continue
        cosine = unit[members] @ (center / norm)
        labels[members[cosine < minimum]] = -1


def _drop_loose_balls(unit: np.ndarray, labels: np.ndarray, minimum: float) -> None:
    """Drop a group whose members are not close to its center, on average."""
    for label in _label_ids(labels):
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        center = unit[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            labels[members] = -1
            continue
        if float((unit[members] @ (center / norm)).mean()) < minimum:
            labels[members] = -1


def _merge_same_subject(unit: np.ndarray, labels: np.ndarray, minimum: float) -> np.ndarray:
    """Fold centers that are one subject. Dissimilar centers stay apart."""
    labels = np.asarray(labels, dtype=int).copy()
    ids = _label_ids(labels)
    centers: list[np.ndarray] = []
    keep: list[int] = []
    for label in ids:
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        center = unit[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            labels[members] = -1
            continue
        centers.append(center / norm)
        keep.append(label)
    if len(keep) < 2:
        return labels
    stacked = np.vstack(centers)
    similarity = stacked @ stacked.T
    parent = list(range(len(keep)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    left, right = np.where(np.triu(similarity, 1) >= minimum)
    for pair in np.argsort(-similarity[left, right]):
        root_left, root_right = find(int(left[pair])), find(int(right[pair]))
        if root_left != root_right:
            parent[root_right] = root_left
    remap = {label: keep[find(index)] for index, label in enumerate(keep)}
    merged = np.full(labels.shape[0], -1, dtype=int)
    for index, label in enumerate(labels):
        if int(label) >= 0:
            merged[index] = remap.get(int(label), -1)
    return merged


def _keep_large(labels: np.ndarray, floor: int) -> np.ndarray:
    """Renumber groups of at least `floor` posts. Smaller groups become -1."""
    labels = np.asarray(labels, dtype=int)
    kept = np.full(labels.shape[0], -1, dtype=int)
    next_id = 0
    for label in _label_ids(labels):
        members = np.flatnonzero(labels == label)
        if members.size < floor:
            continue
        kept[members] = next_id
        next_id += 1
    return kept


def _cohesive_balls(unit: np.ndarray, floor: int, *, seed: int) -> np.ndarray:
    """Fine grid, then only the dense balls survive.

    The grid is about one seed per `floor` posts so two neighboring crowds are
    not glued together before they can be told apart. That seed count is not
    the group count. A cell that is not dense is dropped. Cells of one subject
    are merged. What remains is however many balls the distances support.
    """
    count = int(unit.shape[0])
    grid = min(count, max(floor, count // floor))
    if grid < 2:
        labels = np.zeros(count, dtype=int)
    else:
        labels, _centers = cluster_kmeans(unit, grid, seed=seed)
        labels = np.asarray(labels, dtype=int).copy()
    _peel_members(unit, labels, _BALL_MEMBER)
    labels = _merge_same_subject(unit, labels, _BALL_MERGE)
    _peel_members(unit, labels, _BALL_MEMBER)
    _drop_loose_balls(unit, labels, _BALL_MEAN)
    return _keep_large(labels, floor)


def _density_from_sample(unit: np.ndarray, floor: int, *, seed: int, sample_size: int) -> np.ndarray:
    """Centers from a sample. Other posts join a center only from inside its ball.

    This is the path above `_EXACT_BALL_LIMIT`. The sample is large enough to
    contain the crowds (12,000 at the default). A post outside the sample does
    not create a new group, and it does not join a center it is far from.
    """
    count = int(unit.shape[0])
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(count, size=min(count, int(sample_size)), replace=False))
    sampled = _cohesive_balls(unit[chosen], floor, seed=seed)
    ids = _label_ids(sampled)
    labels = np.full(count, -1, dtype=int)
    if not ids:
        return labels
    centers = []
    for label in ids:
        members = chosen[sampled == label]
        center = unit[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        centers.append(center / norm if norm else center)
    stacked = np.vstack(centers)
    id_array = np.asarray(ids, dtype=int)
    for start in range(0, count, 2048):
        end = min(start + 2048, count)
        sims = unit[start:end] @ stacked.T
        best = sims.argmax(axis=1)
        score = sims[np.arange(end - start), best]
        take = score >= _BALL_MEMBER
        labels[start:end][take] = id_array[best[take]]
    _peel_members(unit, labels, _BALL_MEMBER)
    _drop_loose_balls(unit, labels, _BALL_MEAN)
    return _keep_large(labels, floor)


def density_labels(
    matrix: np.ndarray,
    min_cluster_size: int = 8,
    *,
    seed: int = 0,
    exact_limit: int = _EXACT_BALL_LIMIT,
) -> np.ndarray:
    """Dense balls in the embedding. Isolated posts stay -1.

    Single-linkage on mutual reachability (the HDBSCAN distance) was measured
    on a 10K week and does not separate it: nearest-neighbor distances inside
    a topic and between topics are almost the same, so the graph becomes one
    chain. A topic in this embedding is a ball of posts near one center.

    Nothing here sets the group count to ``n / floor``. The floor is only the
    smallest ball we will call a group. Above ``exact_limit`` posts, centers
    are fit on a sample and the rest of the posts join a center only when they
    fall inside its ball.
    """
    values = l2_rows(np.asarray(matrix, dtype=np.float32))
    count = int(values.shape[0])
    floor = max(2, int(min_cluster_size))
    if count < floor:
        return np.full(count, -1, dtype=int)
    if count > int(exact_limit):
        return _density_from_sample(values, floor, seed=seed, sample_size=int(exact_limit))
    return _cohesive_balls(values, floor, seed=seed)


def _floor_for(count: int, min_posts: int) -> int:
    if count < 2:
        return 0
    return 1 if count < 2 * min_posts else min_posts


def _candidate_key(matrix: np.ndarray, texts: list[str], labels: np.ndarray) -> tuple:
    """Tightest split first. A far pair of outliers inflates centroid gap and loses."""
    distinct = distinctness_score(matrix, labels)
    overlap = pairwise_jaccard(term_sets(texts, labels))
    silhouette = silhouette_cosine(matrix, labels)
    return (round(silhouette, 3), round(distinct, 3), round(1.0 - overlap, 3))


def force_two_labels(
    texts: list[str],
    matrix: np.ndarray,
    *,
    seed: int = 0,
    min_posts: int = MIN_FACE_POSTS,
) -> tuple[np.ndarray, str]:
    """Always return two labels. The tightest cut wins.

    Candidates are the residual axis, 2-means on the embeddings, Ward's first
    cut, and 2-means on TF-IDF. Cosine silhouette picks the cut. Distinctness
    breaks a tie, then term separation. A two-post outlier can sit far from
    the crowd and look distinct while the planet is still one pile.
    """
    values = np.asarray(matrix, dtype=float)
    count = int(values.shape[0])
    if count < 2:
        raise ValueError(f"Need at least 2 posts to force two faces, found {count}")
    share_floor = int(np.ceil(MIN_FACE_SHARE * count - 1e-9))
    floor = min(count // 2, max(_floor_for(count, min_posts), share_floor))
    candidates: list[tuple[str, np.ndarray]] = []

    residual_labels, residual_scores = residual_axis_split(values)
    candidates.append(("residual_axis", ensure_two_sides(residual_labels, residual_scores, floor)))

    kmeans_labels, centers = cluster_kmeans(values, 2, seed=seed)
    kmeans_labels = np.asarray(kmeans_labels, dtype=int)
    candidates.append(
        ("embedding_kmeans2", ensure_two_sides(kmeans_labels, _side_scores(values, kmeans_labels, centers), floor))
    )

    ward = ward_labels(values, 2)
    ward_scores = _side_scores(values, ward, _raw_centers(values, ward))
    candidates.append(("ward2", ensure_two_sides(ward, ward_scores, floor)))

    try:
        lexical = vectorize(texts)
        lexical_labels, lexical_centers = cluster_kmeans(lexical, 2, seed=seed)
        lexical_labels = np.asarray(lexical_labels, dtype=int)
        candidates.append(
            (
                "ctfidf_kmeans2",
                ensure_two_sides(
                    lexical_labels,
                    _side_scores(lexical, lexical_labels, lexical_centers),
                    floor,
                ),
            )
        )
    except ValueError:
        pass

    best_name = candidates[0][0]
    best_labels = candidates[0][1]
    best_key = None
    for name, labels in candidates:
        if len(_label_ids(labels)) < 2:
            continue
        key = _candidate_key(values, texts, labels)
        if best_key is None or key > best_key:
            best_key = key
            best_name = name
            best_labels = labels
    return best_labels, best_name


def _raw_centers(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    ids = _label_ids(labels)
    centers = []
    for label in ids:
        members = matrix[np.asarray(labels) == label]
        centers.append(members.mean(axis=0) if len(members) else np.zeros(matrix.shape[1]))
    return np.vstack(centers)


def _passes_size(labels: np.ndarray, count: int, min_posts: int) -> bool:
    sizes = face_sizes(labels)
    if len(sizes) < 2:
        return False
    floor = max(min_posts, MIN_FACE_SHARE * count)
    return min(sizes) >= floor


def best_k_labels(
    matrix: np.ndarray,
    splitter,
    *,
    seed: int = 0,
    min_k: int = 2,
    max_k: int = 6,
    min_posts: int = MIN_FACE_POSTS,
) -> tuple[np.ndarray, int]:
    """Highest cosine silhouette in ``min_k..max_k`` that keeps every face large enough.

    A near tie keeps the smaller k. If no k passes, the 2-cluster cut is
    rebalanced so both sides still exist.
    """
    values = np.asarray(matrix, dtype=float)
    count = int(values.shape[0])
    upper = min(max_k, max(count // max(min_posts, 1), 2), count)
    upper = max(upper, 2)
    best = None
    for k in range(min_k, min(upper, count) + 1):
        labels = np.asarray(splitter(values, k, seed), dtype=int)
        if not _passes_size(labels, count, min_posts):
            continue
        score = silhouette_cosine(values, labels)
        key = (round(float(score), 3), -k)
        if best is None or key > best[0]:
            best = (key, labels, k)
    if best is not None:
        return best[1], best[2]
    labels = np.asarray(splitter(values, 2, seed), dtype=int)
    scores = _side_scores(values, labels, _raw_centers(values, labels))
    labels = ensure_two_sides(labels, scores, _floor_for(count, min_posts))
    return labels, 2


def _pack(name: str, texts: list[str], matrix: np.ndarray, labels: np.ndarray | None, *, dropped: bool, forced: bool, llm_calls: int = 0, note: str = "") -> dict:
    if labels is None or dropped:
        return {
            "approach": name,
            "dropped": True,
            "labels": [],
            "k": 0,
            "distinctness": 0.0,
            "silhouette": None,
            "max_centroid_cosine": None,
            "term_overlap": None,
            "ctfidf_overlap": None,
            "balance": None,
            "sizes": [],
            "terms": [],
            "forced": forced,
            "llm_calls": llm_calls,
            "note": note,
        }
    array = np.asarray(labels, dtype=int)
    sizes = face_sizes(array)
    terms = term_sets(texts, array)
    ctfidf = class_tfidf_terms(texts, array)
    cosine = max_centroid_cosine(matrix, array)
    return {
        "approach": name,
        "dropped": False,
        "labels": [int(item) for item in array],
        "k": len(sizes),
        "distinctness": round(distinctness_score(matrix, array), 3),
        "silhouette": round(float(silhouette_cosine(matrix, array)), 3),
        "max_centroid_cosine": None if cosine is None else round(float(cosine), 3),
        "term_overlap": round(pairwise_jaccard(terms), 3),
        "ctfidf_overlap": round(pairwise_jaccard(ctfidf), 3),
        "balance": round(size_balance(sizes), 3),
        "sizes": sizes,
        "terms": terms,
        "forced": forced,
        "llm_calls": llm_calls,
        "note": note,
    }


def group_baseline(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    """Current production gate: silhouette k-means, drop when nothing passes."""
    from pipeline.perspectives import score_face_counts

    rows = score_face_counts(texts, seed=seed, matrix=matrix)
    valid = [row for row in rows if row["valid"]]
    valid.sort(key=lambda row: (-round(float(row["silhouette"]), 3), int(row["k"])))
    if not valid:
        reason = "; ".join(f"k={row['k']}: {row['reason']}" for row in rows) or "too few posts"
        return _pack("baseline", texts, matrix, None, dropped=True, forced=False, note=reason)
    chosen = valid[0]
    return _pack("baseline", texts, matrix, chosen["labels"], dropped=False, forced=False)


def group_ward(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    labels, _k = best_k_labels(matrix, lambda values, k, _seed: ward_labels(values, k), seed=seed)
    return _pack("ward", texts, matrix, labels, dropped=False, forced=False)


def group_spectral(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    labels, _k = best_k_labels(
        matrix,
        lambda values, k, used_seed: spectral_labels(values, k, seed=used_seed),
        seed=seed,
    )
    return _pack("spectral", texts, matrix, labels, dropped=False, forced=False)


def group_hdbscan_forced(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    count = int(np.asarray(matrix).shape[0])
    found = mutual_reachability_labels(matrix, min_cluster_size=max(MIN_FACE_POSTS, int(MIN_FACE_SHARE * count)))
    if found is None or len(_label_ids(found)) < 2:
        labels, method = force_two_labels(texts, matrix, seed=seed)
        packed = _pack("hdbscan_forced2", texts, matrix, labels, dropped=False, forced=True, note=method)
        return packed
    # Cap at 6 faces: fold the smallest extras into the nearest large face.
    packed_labels = _cap_faces(matrix, found, 6)
    return _pack("hdbscan_forced2", texts, matrix, packed_labels, dropped=False, forced=False)


def _cap_faces(matrix: np.ndarray, labels: np.ndarray, limit: int) -> np.ndarray:
    labels = np.asarray(labels, dtype=int).copy()
    while len(_label_ids(labels)) > limit:
        ids = _label_ids(labels)
        sizes = {label: int(np.sum(labels == label)) for label in ids}
        small = min(ids, key=lambda label: (sizes[label], label))
        centers = unit_centers(matrix, labels)
        if centers is None:
            break
        position = {label: index for index, label in enumerate(ids)}
        others = [label for label in ids if label != small]
        small_center = centers[position[small]]
        target = max(others, key=lambda label: float(small_center @ centers[position[label]]))
        labels[labels == small] = target
    ids = _label_ids(labels)
    remap = {label: index for index, label in enumerate(ids)}
    return np.asarray([remap[int(item)] for item in labels], dtype=int)


def group_ctfidf(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    """k-means on TF-IDF, then c-TF-IDF terms. The embedding matrix is only for scores."""
    try:
        lexical = vectorize(texts)
    except ValueError as exc:
        labels, method = force_two_labels(texts, matrix, seed=seed)
        return _pack("ctfidf", texts, matrix, labels, dropped=False, forced=True, note=f"{method}; {exc}")
    labels, _k = best_k_labels(lexical, lambda values, k, used_seed: cluster_kmeans(values, k, seed=used_seed)[0], seed=seed)
    return _pack("ctfidf", texts, matrix, labels, dropped=False, forced=False)


def group_residual(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    del seed
    labels, scores = residual_axis_split(matrix)
    labels = ensure_two_sides(labels, scores, _floor_for(int(np.asarray(matrix).shape[0]), MIN_FACE_POSTS))
    return _pack("residual_axis", texts, matrix, labels, dropped=False, forced=False)


def group_keep_floor(texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    """Shipped rule: the silhouette split when it passes, otherwise one face.

    A forced second face is not published. ``distinctness`` is 0 on that
    single face. ``force_two_labels`` remains available for the comparison
    approaches.
    """
    baseline = group_baseline(texts, matrix, seed=seed)
    if not baseline["dropped"]:
        baseline["approach"] = "keep_floor"
        return baseline
    labels = np.zeros(len(texts), dtype=int)
    packed = _pack(
        "keep_floor",
        texts,
        matrix,
        labels,
        dropped=False,
        forced=False,
        note="no distinct second view",
    )
    return packed


APPROACHES = (
    "baseline",
    "ward",
    "spectral",
    "hdbscan_forced2",
    "ctfidf",
    "residual_axis",
    "keep_floor",
)

_RUNNERS = {
    "baseline": group_baseline,
    "ward": group_ward,
    "spectral": group_spectral,
    "hdbscan_forced2": group_hdbscan_forced,
    "ctfidf": group_ctfidf,
    "residual_axis": group_residual,
    "keep_floor": group_keep_floor,
}


def run_approach(name: str, texts: list[str], matrix: np.ndarray, *, seed: int = 0) -> dict:
    runner = _RUNNERS.get(name)
    if runner is None:
        raise ValueError(f"Unknown grouping approach {name}")
    return runner(texts, matrix, seed=seed)


def assign_to_descriptions(matrix: np.ndarray, description_matrix: np.ndarray) -> np.ndarray:
    """Give each post the description whose embedding is nearest in cosine."""
    posts = l2_rows(matrix)
    descriptions = l2_rows(description_matrix)
    return np.asarray((posts @ descriptions.T).argmax(axis=1), dtype=int)
