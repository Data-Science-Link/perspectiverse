"""Deterministic TF-IDF and k-means used by the lexical backend and face split.

No sentence-transformer download. Input order plus `seed` fixes the result.
"""

from __future__ import annotations

import re

import numpy as np

TOKEN_RE = re.compile(r"[a-z]{3,}")
STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "have",
        "about",
        "discussion",
        "debate",
        "policy",
        "public",
        "people",
        "today",
        "just",
        "they",
        "them",
        "their",
        "what",
        "when",
        "where",
        "which",
        "would",
        "could",
        "should",
        "there",
        "here",
        "into",
        "your",
        "youre",
        "been",
        "being",
        "were",
        "was",
        "are",
        "not",
        "but",
        "its",
        "our",
        "out",
        "note",
        "you",
        "more",
        "because",
        "like",
        "how",
        "who",
        "don",
        "dont",
        "had",
        "has",
        "have",
        "two",
        "can",
        "get",
        "got",
        "she",
        "his",
        "her",
        "him",
        "one",
        "must",
        "between",
        "good",
        "know",
        "now",
        "then",
        "than",
        "also",
        "some",
        "any",
        "all",
        "will",
        "really",
        "very",
        "even",
        "still",
        "back",
        "over",
        "after",
        "before",
        "why",
        "yes",
        "yeah",
        "nah",
        "lol",
        "https",
        "http",
        "www",
        "com",
    }
)


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


def vectorize(texts: list[str]) -> np.ndarray:
    """L2-normalized TF-IDF. Vocabulary is the most common remaining terms."""
    docs = [tokenize(text) for text in texts]
    document_frequency: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    ranked = sorted(document_frequency, key=lambda term: (-document_frequency[term], term))
    vocab = ranked[:400]
    if not vocab:
        raise ValueError("No usable tokens to cluster")
    index = {term: position for position, term in enumerate(vocab)}
    matrix = np.zeros((len(docs), len(vocab)), dtype=float)
    count = len(docs)
    idf = np.array(
        [np.log((1 + count) / (1 + document_frequency[term])) + 1 for term in vocab],
        dtype=float,
    )
    for row, doc in enumerate(docs):
        counts: dict[str, int] = {}
        for token in doc:
            if token in index:
                counts[token] = counts.get(token, 0) + 1
        total = sum(counts.values())
        if total == 0:
            continue
        for token, seen in counts.items():
            matrix[row, index[token]] = (seen / total) * idf[index[token]]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def salient_terms(texts: list[str], limit: int = 3) -> list[str]:
    """Terms that show up in enough posts in this bucket to name it."""
    counts: dict[str, int] = {}
    for text in texts:
        for token in set(tokenize(text)):
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts, key=lambda term: (-counts[term], term))
    if not texts:
        return []
    threshold = max(2, int(len(texts) * 0.3))
    strong = [term for term in ranked if counts[term] >= threshold]
    chosen = strong[:limit] or ranked[:1]
    floor = min(limit, 4)
    if len(texts) >= 2 and len(chosen) < floor:
        for term in ranked:
            if term in chosen:
                continue
            chosen.append(term)
            if len(chosen) >= floor:
                break
    return chosen[:limit]


def _sq_distances(matrix: np.ndarray, centers: np.ndarray, row_norms: np.ndarray | None = None) -> np.ndarray:
    """Squared Euclidean distance from every row to every center, as an n x k matrix.

    Uses |x|^2 - 2 x.c + |c|^2 so memory is n x k, not n x k x d. The old
    broadcast built an n x k x d tensor (about 3.4 GB at 7,447 claims and
    k=201) and was most of the non-LLM runtime (issue #53).
    """
    if row_norms is None:
        row_norms = np.einsum("ij,ij->i", matrix, matrix)
    center_norms = np.einsum("ij,ij->i", centers, centers)
    distance = row_norms[:, None] - 2.0 * (matrix @ centers.T) + center_norms[None, :]
    np.maximum(distance, 0.0, out=distance)
    return distance


def _farthest_first(matrix: np.ndarray, k: int, start: int) -> list[int]:
    count = matrix.shape[0]
    k = min(k, count)
    chosen = [start % count]
    nearest = np.full(count, np.inf)
    for _ in range(1, k):
        delta = matrix - matrix[chosen[-1]]
        distance = np.einsum("ij,ij->i", delta, delta)
        nearest = np.minimum(nearest, distance)
        for index in chosen:
            nearest[index] = -1.0
        chosen.append(int(np.argmax(nearest)))
    return chosen


def _lloyd(matrix: np.ndarray, seeds: list[int], iters: int) -> tuple[np.ndarray, np.ndarray]:
    centers = matrix[seeds].astype(float, copy=True)
    labels = np.zeros(matrix.shape[0], dtype=int)
    row_norms = np.einsum("ij,ij->i", matrix, matrix)
    k = centers.shape[0]
    for _ in range(iters):
        labels = _sq_distances(matrix, centers, row_norms).argmin(axis=1)
        sums = np.zeros_like(centers)
        np.add.at(sums, labels, matrix)
        counts = np.bincount(labels, minlength=k)
        filled = counts > 0
        # An empty cluster keeps its previous center, as before.
        centers[filled] = sums[filled] / counts[filled, None]
    return labels, centers


def _fill_empty(matrix: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = labels.copy()
    centers = centers.copy()
    k = centers.shape[0]
    for _ in range(k):
        counts = np.bincount(labels, minlength=k)
        empty = [index for index in range(k) if counts[index] == 0]
        if not empty:
            break
        donors = counts > 1
        if not np.any(donors):
            break
        delta = matrix - centers[labels]
        distance = np.einsum("ij,ij->i", delta, delta)
        distance = np.where(donors[labels], distance, -1.0)
        best_point = int(np.argmax(distance))
        if distance[best_point] < 0:
            break
        labels[best_point] = empty[0]
        for index in range(k):
            mask = labels == index
            if np.any(mask):
                centers[index] = matrix[mask].mean(axis=0)
    return labels, centers


def cluster_kmeans(matrix: np.ndarray, k: int, seed: int = 0, iters: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """Return labels and centers. Every cluster has at least one row when n >= k."""
    count = matrix.shape[0]
    if count < k:
        raise ValueError(f"Need at least {k} rows to form {k} clusters, found {count}")
    seeds = _farthest_first(matrix, k, seed % count)
    labels, centers = _lloyd(matrix, seeds, iters)
    return _fill_empty(matrix, labels, centers)


def silhouette_cosine(matrix: np.ndarray, labels, max_rows: int = 1500) -> float:
    """Mean silhouette with cosine distance. Higher means tighter, better-separated groups.

    O(n^2) in the rows, so a large group is scored on an evenly spaced sample
    of at most ``max_rows`` rows (deterministic). Singletons score 0.
    """
    labels = np.asarray(labels, dtype=int)
    values = np.asarray(matrix, dtype=float)
    count = int(labels.shape[0])
    ids = sorted({int(item) for item in labels})
    if count < 2 or len(ids) < 2:
        return 0.0
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = values / norms
    rows = np.arange(count)
    if count > max_rows:
        rows = np.linspace(0, count - 1, max_rows).round().astype(int)
    onehot = np.zeros((count, len(ids)), dtype=float)
    position = {label: index for index, label in enumerate(ids)}
    onehot[np.arange(count), [position[int(label)] for label in labels]] = 1.0
    sizes = onehot.sum(axis=0)
    distance = 1.0 - unit[rows] @ unit.T
    np.maximum(distance, 0.0, out=distance)
    distance[np.arange(rows.shape[0]), rows] = 0.0
    totals = distance @ onehot
    own = np.array([position[int(label)] for label in labels[rows]])
    own_size = sizes[own]
    alone = own_size <= 1
    a = np.where(alone, 0.0, totals[np.arange(rows.shape[0]), own] / np.maximum(own_size - 1, 1))
    means = totals / sizes[None, :]
    means[np.arange(rows.shape[0]), own] = np.inf
    b = means.min(axis=1)
    denom = np.maximum(np.maximum(a, b), 1e-12)
    scores = np.where(alone, 0.0, (b - a) / denom)
    return float(scores.mean())


def grow_clusters_to_min(
    matrix: np.ndarray,
    labels: np.ndarray,
    selected: set[int],
    min_size: int,
) -> np.ndarray:
    """Move leftover or surplus rows so every selected cluster has min_size members.

    Leftover rows (labels not in `selected`) are taken first. Surplus rows come
    from selected clusters that already sit above `min_size`. Prefer the row
    closest to the short cluster's centroid so the grown planet stays coherent.
    """
    labels = np.asarray(labels, dtype=int).copy()
    chosen = set(selected)
    if not chosen:
        return labels

    def count(label: int) -> int:
        return int(np.sum(labels == label))

    def centroid(label: int) -> np.ndarray:
        mask = labels == label
        if not np.any(mask):
            return np.zeros(matrix.shape[1], dtype=float)
        return matrix[mask].mean(axis=0)

    for _ in range(matrix.shape[0] * 2):
        short = [label for label in chosen if count(label) < min_size]
        if not short:
            return labels
        target = min(short, key=lambda label: (count(label), label))
        target_center = centroid(target)
        best_row = None
        best_key = None
        for row in range(matrix.shape[0]):
            label = int(labels[row])
            if label == target:
                continue
            if label in chosen:
                if count(label) <= min_size:
                    continue
                priority = 1
            else:
                priority = 0
            delta = matrix[row] - target_center
            key = (priority, float(np.dot(delta, delta)), row)
            if best_key is None or key < best_key:
                best_key = key
                best_row = row
        if best_row is None:
            break
        labels[best_row] = target
    return labels


def cluster_inertia(matrix: np.ndarray, labels: np.ndarray) -> float:
    """Mean squared distance to each row's own centroid. Lower is tighter."""
    labels = np.asarray(labels, dtype=int)
    count = int(labels.shape[0])
    if count == 0:
        return 0.0
    total = 0.0
    for label in sorted({int(item) for item in labels}):
        mask = labels == label
        center = matrix[mask].mean(axis=0)
        delta = matrix[mask] - center
        total += float(np.einsum("ij,ij->", delta, delta))
    return total / count


def distances_to_centers(matrix: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> list[float]:
    values: list[float] = []
    for row, label in enumerate(labels):
        delta = matrix[row] - centers[int(label)]
        values.append(float(np.dot(delta, delta)))
    return values


def cosines_to_centers(matrix: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> list[float]:
    """Cosine of each row to its cluster center. Reuses the matrix already clustered."""
    labels = np.asarray(labels, dtype=int)
    assigned = centers[labels]
    numer = np.einsum("ij,ij->i", matrix, assigned)
    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(assigned, axis=1)
    denom = np.where(denom == 0, 1.0, denom)
    return [float(value) for value in numer / denom]
