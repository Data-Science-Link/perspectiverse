"""Metric and split tests for perspective grouping. No model download."""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.grouping import (
    assign_to_descriptions,
    class_tfidf_terms,
    distinctness_score,
    force_two_labels,
    group_keep_floor,
    max_centroid_cosine,
    mutual_reachability_labels,
    pairwise_jaccard,
    residual_axis_split,
    run_approach,
    size_balance,
    spectral_labels,
    ward_labels,
)
from pipeline.schema import _check_face_distinctness


def _blobs(sizes, *, dim=16, spread=0.04, seed=0, separation=0.9):
    rng = np.random.default_rng(seed)
    rows = []
    for index, size in enumerate(sizes):
        direction = rng.normal(size=dim)
        direction /= np.linalg.norm(direction)
        # Push later groups away from the first so the cut is real.
        if index:
            direction = direction * separation + rng.normal(size=dim)
            direction /= np.linalg.norm(direction)
        group = direction + rng.normal(size=(size, dim)) * spread
        rows.append(group / np.linalg.norm(group, axis=1, keepdims=True))
    return np.vstack(rows)


def test_distinctness_is_zero_for_one_cloud_and_high_for_two():
    same = np.ones((12, 4))
    assert distinctness_score(same, np.zeros(12, dtype=int)) == 0.0
    assert max_centroid_cosine(same, np.zeros(12, dtype=int)) is None
    left = np.zeros((8, 2))
    left[:, 0] = 1
    right = np.zeros((8, 2))
    right[:, 1] = 1
    labels = np.array([0] * 8 + [1] * 8)
    matrix = np.vstack([left, right])
    assert max_centroid_cosine(matrix, labels) == pytest.approx(0.0, abs=1e-6)
    assert distinctness_score(matrix, labels) == pytest.approx(1.0, abs=1e-6)


def test_size_balance_and_term_overlap():
    assert size_balance([10, 10]) == 1
    assert size_balance([1, 4]) == 0.25
    assert size_balance([]) == 0
    assert pairwise_jaccard([["rent", "wage"], ["rent", "wage"]]) == 1
    assert pairwise_jaccard([["rent"], ["vaccine"]]) == 0
    assert pairwise_jaccard([["rent"]]) == 0


def test_class_tfidf_names_the_separating_term():
    texts = ["rent rent housing costs"] * 6 + ["vaccine vaccine clinic dose"] * 6
    labels = [0] * 6 + [1] * 6
    terms = class_tfidf_terms(texts, labels, limit=3)
    assert "rent" in terms[0]
    assert "vaccine" in terms[1]
    assert pairwise_jaccard(terms) == 0


def test_ward_and_spectral_recover_two_blobs():
    matrix = _blobs([20, 15], seed=2)
    ward = ward_labels(matrix, 2)
    spectral = spectral_labels(matrix, 2, seed=0)
    for labels in (ward, spectral):
        assert set(np.unique(labels)) == {0, 1}
        assert distinctness_score(matrix, labels) > 0.3
        sizes = np.bincount(labels)
        assert sizes.min() >= 10


def test_residual_axis_splits_a_centered_contrast():
    matrix = _blobs([18, 14], seed=4, separation=1.4)
    labels, _scores = residual_axis_split(matrix)
    assert len(set(labels.tolist())) == 2
    assert distinctness_score(matrix, labels) > 0.2


def test_hdbscan_style_finds_two_dense_groups_or_the_caller_forces():
    matrix = _blobs([24, 18], seed=5, spread=0.02, separation=1.6)
    labels = mutual_reachability_labels(matrix, min_cluster_size=4)
    assert labels is not None
    assert len(set(int(item) for item in labels)) >= 2


def test_force_two_never_drops_and_is_deterministic():
    matrix = _blobs([22, 9], seed=6)
    texts = [f"alpha policy rent {index}" for index in range(22)]
    texts += [f"omega policy vaccine {index}" for index in range(9)]
    first, method = force_two_labels(texts, matrix, seed=1)
    second, method_again = force_two_labels(texts, matrix, seed=1)
    assert method == method_again
    assert np.array_equal(first, second)
    assert set(np.unique(first)) == {0, 1}
    assert min(np.bincount(first)) >= 2
    packed = group_keep_floor(texts, matrix, seed=1)
    assert packed["dropped"] is False
    assert packed["k"] >= 2


def test_uniform_cloud_is_kept_with_a_low_score():
    matrix = np.ones((20, 6))
    texts = [f"rent rent rent housing costs {index}" for index in range(20)]
    packed = run_approach("baseline", texts, matrix, seed=0)
    assert packed["dropped"] is True
    kept = run_approach("keep_floor", texts, matrix, seed=0)
    assert kept["dropped"] is False
    assert kept["k"] == 2
    assert kept["forced"] is True
    assert kept["distinctness"] <= 0.05
    assert kept["llm_calls"] == 0


def test_assign_to_descriptions_follows_the_nearer_stance():
    posts = np.array([[1.0, 0.0], [1.0, 0.05], [0.0, 1.0], [0.05, 1.0]])
    descriptions = np.array([[1.0, 0.0], [0.0, 1.0]])
    labels = assign_to_descriptions(posts, descriptions)
    assert labels.tolist() == [0, 0, 1, 1]


def test_schema_accepts_an_optional_distinctness_score():
    _check_face_distinctness({"name": "Rent"}, "Topic 1")
    _check_face_distinctness({"face_distinctness": 0}, "Topic 1")
    _check_face_distinctness({"face_distinctness": 1.0}, "Topic 1")
    _check_face_distinctness({"face_distinctness": None}, "Topic 1")
    with pytest.raises(ValueError):
        _check_face_distinctness({"face_distinctness": 1.2}, "Topic 1")
    with pytest.raises(ValueError):
        _check_face_distinctness({"face_distinctness": True}, "Topic 1")
    with pytest.raises(ValueError):
        _check_face_distinctness({"face_distinctness": "low"}, "Topic 1")


def test_every_local_approach_returns_the_metric_keys():
    matrix = _blobs([16, 12, 8], seed=8)
    texts = [f"stance{index // 12} claim words {index}" for index in range(36)]
    for name in ("baseline", "ward", "spectral", "hdbscan_forced2", "ctfidf", "residual_axis", "keep_floor"):
        packed = run_approach(name, texts, matrix, seed=0)
        assert packed["approach"] == name
        assert packed["llm_calls"] == 0
        assert packed["dropped"] is False or name == "baseline"
        if not packed["dropped"]:
            assert packed["k"] >= 2
            assert abs(sum(packed["sizes"]) - len(texts)) == 0
            assert 0.0 <= packed["distinctness"] <= 1.0
            assert 0.0 <= packed["balance"] <= 1.0


def test_catalog_walk_splits_fill_the_ceiling_and_drops_do_not():
    from pipeline.eval.grouping_eval import catalog_walk

    records = [
        {
            "kind": "split",
            "detection_faces": 4,
            "skipped": 1,
            "label_calls": {"faces": 8, "names": 2, "briefs": 0},
            "planet_objs": [{"name": "Diesel"}, {"name": "Measles"}],
        },
        {
            "kind": "keep",
            "detection_faces": 2,
            "label_calls": {"faces": 2, "names": 1, "briefs": 0},
            "planet_objs": [{"name": "Spare"}],
        },
    ]
    before = catalog_walk(records, 2, split_stories=False)
    after = catalog_walk(records, 2, split_stories=True)
    assert before["kept"] == 1
    assert before["dropped"] == 1
    assert before["split_candidates"] == 0
    assert [planet["name"] for planet in before["planets"]] == ["Spare"]
    assert before["label_calls"] == {"faces": 6, "names": 1, "briefs": 0, "finalize_faces": 0}
    assert after["kept"] == 2
    assert after["dropped"] == 0
    assert after["split_candidates"] == 1
    assert after["candidates_drafted"] == 1
    assert [planet["name"] for planet in after["planets"]] == ["Diesel", "Measles"]
    assert after["gross_split_calls"]["faces"] == 4
    assert after["gross_split_calls"]["names"] == 2
    assert after["label_calls"]["faces"] == 8
