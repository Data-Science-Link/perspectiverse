"""Density grouping: the data decides the group count. Noise stays noise."""

import numpy as np

from pipeline.grouping import density_labels
from pipeline.topics import cluster_texts


def _blob(center, count, spread, rng):
    return center + rng.normal(scale=spread, size=(count, center.shape[0]))


def test_two_dense_blobs_and_noise_stay_separate():
    rng = np.random.default_rng(0)
    left = _blob(np.eye(16)[0], 30, 0.01, rng)
    right = _blob(np.eye(16)[1], 24, 0.01, rng)
    # Isolated posts: each sits on its own axis, far from both blobs and from
    # each other. A point that lands inside a blob is a member, not noise.
    noise = np.eye(16)[2:14]
    matrix = np.vstack([left, right, noise])
    labels = density_labels(matrix, min_cluster_size=8, seed=0)
    groups = {int(label) for label in labels if int(label) >= 0}
    assert len(groups) == 2
    assert int(np.sum(labels < 0)) == 12
    left_labels = set(int(item) for item in labels[:30])
    right_labels = set(int(item) for item in labels[30:54])
    assert len(left_labels) == 1
    assert len(right_labels) == 1
    assert left_labels != right_labels


def test_one_dense_cloud_is_one_group():
    rng = np.random.default_rng(1)
    matrix = _blob(np.array([0.2, 0.7, 0.1, 0.0]), 40, 0.02, rng)
    labels = density_labels(matrix, min_cluster_size=8, seed=1)
    assert set(int(item) for item in labels) == {0}


def test_group_count_is_not_n_over_floor():
    """Three tight groups must not be sliced into n // 8 cells."""
    rng = np.random.default_rng(2)
    parts = [
        _blob(np.eye(6)[index], 20, 0.01, rng)
        for index in range(3)
    ]
    matrix = np.vstack(parts)
    labels = density_labels(matrix, min_cluster_size=8, seed=2)
    assert len({int(item) for item in labels if int(item) >= 0}) == 3


def test_sample_path_still_finds_the_blobs():
    """Above the exact limit, centers are fit on a sample and the rest join the ball."""
    rng = np.random.default_rng(3)
    left = _blob(np.eye(8)[0], 80, 0.01, rng)
    right = _blob(np.eye(8)[1], 70, 0.01, rng)
    matrix = np.vstack([left, right])
    labels = density_labels(matrix, min_cluster_size=8, seed=3, exact_limit=40)
    groups = {int(item) for item in labels if int(item) >= 0}
    assert groups == {0, 1}
    assert len({int(item) for item in labels[:80]}) == 1
    assert len({int(item) for item in labels[80:]}) == 1


def test_embedding_cluster_ranks_every_natural_group():
    def embed(texts):
        rows = []
        for text in texts:
            axis = int(text.split()[1])
            row = np.zeros(16)
            row[axis] = 1.0
            rows.append(row)
        return np.asarray(rows, dtype=float)

    texts = [f"topic {topic} words {copy}" for topic in range(6) for copy in range(10)]
    clustered = cluster_texts(
        texts,
        min_cluster_size=8,
        cluster_backend="embedding",
        seed=0,
        catalog_size=10_000,
        embed=embed,
        authors=[f"voice-{index}" for index in range(len(texts))],
    )
    assert len(clustered["topics"]) == 6
    assert clustered["noise_count"] == 0
