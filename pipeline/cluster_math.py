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
    return chosen


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
    centers = matrix[seeds].copy()
    labels = np.zeros(matrix.shape[0], dtype=int)
    for _ in range(iters):
        delta = matrix[:, None, :] - centers[None, :, :]
        distance = np.einsum("ijk,ijk->ij", delta, delta)
        labels = distance.argmin(axis=1)
        for index in range(centers.shape[0]):
            mask = labels == index
            if np.any(mask):
                centers[index] = matrix[mask].mean(axis=0)
    return labels, centers


def _fill_empty(matrix: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = labels.copy()
    centers = centers.copy()
    for _ in range(centers.shape[0]):
        empty = [index for index in range(centers.shape[0]) if not np.any(labels == index)]
        if not empty:
            break
        counts = [(index, int(np.sum(labels == index))) for index in range(centers.shape[0])]
        donors = [index for index, count in counts if count > 1]
        if not donors:
            break
        best_point = None
        best_distance = -1.0
        for row in range(matrix.shape[0]):
            label = int(labels[row])
            if label not in donors:
                continue
            delta = matrix[row] - centers[label]
            distance = float(np.dot(delta, delta))
            if distance > best_distance:
                best_distance = distance
                best_point = row
        if best_point is None:
            break
        labels[best_point] = empty[0]
        for index in range(centers.shape[0]):
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


def distances_to_centers(matrix: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> list[float]:
    values: list[float] = []
    for row, label in enumerate(labels):
        delta = matrix[row] - centers[int(label)]
        values.append(float(np.dot(delta, delta)))
    return values
