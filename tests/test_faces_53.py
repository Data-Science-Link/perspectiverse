"""Regression tests for issue #53: no published planet outside 2-6 faces.

The 2026-10-07 daily run died on ``Topic 2 should have 2-6 perspectives,
found 1`` after face labels collapsed a split (a face with no shared claim,
or two faces with the same title). These tests pin the honest behavior: pick
2..6 faces by fit, keep small tight minorities, and drop a planet that cannot
keep two distinct faces instead of padding it or failing the snapshot.
"""

from __future__ import annotations

import numpy as np
import pytest

from pipeline import live
from pipeline.assemble import assemble_payload
from pipeline.cluster_math import (
    _farthest_first,
    _lloyd,
    cluster_kmeans,
    silhouette_cosine,
)
from pipeline.perspectives import (
    MIN_FACE_POSTS,
    MIN_FACE_SHARE,
    choose_n_faces,
    score_face_counts,
    split_perspectives,
)
from pipeline.schema import MAX_FACES, MIN_FACES


def _blobs(sizes, *, dim=24, spread=0.08, seed=0, base=None):
    """Unit vectors in tight groups around random directions (one subject, several stances)."""
    rng = np.random.default_rng(seed)
    root = rng.normal(size=dim) if base is None else base
    rows = []
    for size in sizes:
        direction = root + rng.normal(size=dim) * 0.9
        direction /= np.linalg.norm(direction)
        group = direction + rng.normal(size=(size, dim)) * spread
        rows.append(group / np.linalg.norm(group, axis=1, keepdims=True))
    return np.vstack(rows)


@pytest.mark.parametrize("k", [2, 3, 4, 5, 6])
def test_k_selection_finds_the_true_count(k):
    sizes = [30 - 3 * index for index in range(k)]
    matrix = _blobs(sizes, seed=k)
    texts = ["post"] * matrix.shape[0]
    assert choose_n_faces(texts, seed=0, matrix=matrix) == k


def test_k_selection_keeps_a_small_tight_minority():
    """No 50/50 forcing: a 5% minority that is tight and far stays its own face (#41)."""
    matrix = _blobs([76, 4], seed=3)
    split = split_perspectives(["post"] * 80, seed=0, matrix=matrix)
    sizes = sorted(face["size"] for face in split["faces"])
    assert sizes == [4, 76]
    assert min(sizes) / 80 >= MIN_FACE_SHARE


@pytest.mark.parametrize("seed", range(25))
def test_k_selection_never_leaves_two_to_six(seed):
    rng = np.random.default_rng(seed)
    count = int(rng.integers(2, 160))
    matrix = rng.normal(size=(count, 16))
    if seed % 3 == 0:
        matrix = _blobs([max(count // 3, 1)] * 3, dim=16, seed=seed)
    k = choose_n_faces(["post"] * matrix.shape[0], seed=seed, matrix=matrix)
    assert k is None or MIN_FACES <= k <= MAX_FACES
    split = split_perspectives(["post"] * matrix.shape[0], seed=seed, matrix=matrix)
    if k is None:
        assert split["faces"] == []
    else:
        assert len(split["faces"]) == k
        assert all(face["size"] >= MIN_FACE_POSTS for face in split["faces"])
    for alternative in split.get("alternatives") or []:
        assert MIN_FACES <= len(alternative["faces"]) <= MAX_FACES


def test_every_scored_count_reports_its_gates():
    matrix = _blobs([20, 20], seed=1)
    rows = score_face_counts(["post"] * 40, seed=0, matrix=matrix)
    assert [row["k"] for row in rows] == [2, 3, 4, 5, 6]
    best = max((row for row in rows if row["valid"]), key=lambda row: row["silhouette"])
    assert best["k"] == 2
    for row in rows:
        assert row["valid"] or row["reason"]


def test_fast_lloyd_matches_the_broadcast_version():
    """The n x k distance form gives the same clustering as the old n x k x d broadcast."""
    rng = np.random.default_rng(7)
    matrix = rng.normal(size=(300, 12))
    seeds = _farthest_first(matrix, 9, 0)
    labels, centers = _lloyd(matrix, seeds, 12)
    reference = matrix[seeds].copy()
    for _ in range(12):
        delta = matrix[:, None, :] - reference[None, :, :]
        expected = np.einsum("ijk,ijk->ij", delta, delta).argmin(axis=1)
        for index in range(reference.shape[0]):
            if np.any(expected == index):
                reference[index] = matrix[expected == index].mean(axis=0)
    assert (labels == expected).all()
    assert np.allclose(centers, reference)
    filled, _ = cluster_kmeans(matrix, 9)
    assert {int(item) for item in filled} == set(range(9))


def test_silhouette_matches_definition():
    matrix = _blobs([10, 12], seed=2)
    labels = np.array([0] * 10 + [1] * 12)
    distance = 1 - matrix @ matrix.T
    scores = []
    for row in range(22):
        own = labels == labels[row]
        a = distance[row, own].sum() / (own.sum() - 1)
        b = distance[row, ~own].mean()
        scores.append((b - a) / max(a, b))
    assert silhouette_cosine(matrix, labels) == pytest.approx(float(np.mean(scores)))


# --- the 1-face path through _build_topics ---------------------------------


def _planet_posts(prefix, sizes, seed):
    matrix = _blobs(sizes, seed=seed)
    posts = []
    for face, size in enumerate(sizes):
        for copy in range(size):
            posts.append(
                {
                    "uri": f"at://{prefix}/{face}/{copy}",
                    "author": f"{prefix}.{face}.{copy}",
                    "clean_text": f"{prefix} {prefix} stance{face} claim{face} words{face} {copy}",
                    "text": f"{prefix} {prefix} stance{face} claim{face} words{face} {copy}",
                    "likes": copy,
                }
            )
    return posts, matrix


def _clustered(groups):
    posts, blocks, topics = [], [], []
    for index, (group_posts, matrix) in enumerate(groups):
        start = len(posts)
        posts.extend(group_posts)
        blocks.append(matrix)
        topics.append(
            {
                "id": index,
                "size": len(group_posts),
                "member_indices": list(range(start, len(posts))),
                "terms": [group_posts[0]["clean_text"].split()[0]],
            }
        )
    return posts, {"topics": topics, "matrix": np.vstack(blocks), "assignments": [], "noise_count": 0}


SETTINGS = {"label_backend": "heuristic", "representative_posts": 6, "seed": 0}


def _fake_labels(monkeypatch, titles_for):
    """Faces get titles from ``titles_for(prefix, face_text)``; grounding checks pass."""

    def label_perspective(posts, terms, backend="auto", model=None):
        text = str(posts[0].get("text") or "")
        prefix = text.split()[0]
        title = titles_for(prefix, text)
        return {"title": title, "summary": f"{title} is the claim here.", "label_source": "heuristic"}

    monkeypatch.setattr(live, "label_perspective", label_perspective)
    monkeypatch.setattr(live, "_title_covers_posts", lambda title, posts: True)
    monkeypatch.setattr(live, "_claim_words_overlap", lambda left, right: True)
    monkeypatch.setattr(live, "_posts_share_a_subject", lambda posts: True)
    monkeypatch.setattr(live, "specific_shared_words", lambda faces: {"shared"})


def test_planet_whose_faces_collapse_is_dropped_not_published(monkeypatch):
    """The 2026-10-07 failure: labels merge every face into one. Drop the planet."""
    good = _planet_posts("ukraine", [30, 12], seed=11)
    collapsing = _planet_posts("medicare", [30, 12], seed=12)

    def titles_for(prefix, text):
        if prefix == "medicare":
            return "Medicare Payment"  # every face gets the same stance title
        return "Russia Aggression" if "stance0" in text else "Trump Ukraine Deal"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([good, collapsing])
    topics, membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert [len(topic["perspectives"]) for topic in topics] == [2]
    assert {uri.split("/")[2] for uri, _topic in membership} == {"ukraine"}
    assert {topic_id for _uri, topic_id, _face, _distance in face_rows} == {1}
    payload = assemble_payload(topics, mode="live", source="fixture", total_posts=len(posts))
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in payload["topics"])


def test_mixed_remarks_face_leaves_one_face_and_drops_the_planet(monkeypatch):
    collapsing = _planet_posts("medicare", [30, 12], seed=12)

    def titles_for(prefix, text):
        return "Medicare Payment" if "stance0" in text else "Mixed remarks"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([collapsing])
    topics, membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert topics == [] and membership == [] and face_rows == []


def test_collapsed_split_retries_the_next_best_count(monkeypatch):
    """Two labeled faces merge at the best k; the next passing k keeps two distinct faces."""
    three = _planet_posts("canada", [30, 12, 10], seed=21)

    def titles_for(prefix, text):
        return "Alberta Separation" if "stance2" in text else "US Canada Tensions"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([three])
    split = split_perspectives(
        [post["clean_text"] for post in posts], seed=0, matrix=clustered["matrix"]
    )
    topics, _membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert len(topics) == 1
    faces = topics[0]["perspectives"]
    assert 2 <= len(faces) <= 6
    assert len({face["title"] for face in faces}) == len(faces)
    assert sum(face["post_count"] for face in faces) == len(posts)
    assert abs(sum(face["volume_percent"] for face in faces) - 100) < 0.15
    # Merged membership rows point at the published face positions.
    assert {position for _uri, _topic, position, _distance in face_rows} == set(range(len(faces)))
    assert split["faces"]


def test_one_bad_planet_does_not_block_the_rest(monkeypatch):
    good = _planet_posts("ukraine", [30, 12], seed=11)
    bad = _planet_posts("broken", [30, 12], seed=13)

    def titles_for(prefix, text):
        if prefix == "broken":
            raise RuntimeError("label backend exploded")
        return "Russia Aggression" if "stance0" in text else "Trump Ukraine Deal"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([bad, good])
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert [topic["id"] for topic in topics] == [1]
    assert len(topics[0]["perspectives"]) == 2


def test_collapsed_best_k_retries_the_next_count(monkeypatch):
    """The best k merges to one face; the next passing k is used, and the planet stays at 2+."""
    three = _planet_posts("canada", [30, 12, 10], seed=21)
    calls = []
    original = live._label_faces

    def collapse_first(members, split, terms, context):
        drafted, labeled = original(members, split, terms, context)
        calls.append(split.get("k"))
        if len(calls) == 1:
            return drafted[:1], labeled
        return drafted, labeled

    def titles_for(prefix, text):
        if "stance2" in text:
            return "Alberta Separation"
        if "stance1" in text:
            return "Trade Tariffs"
        return "US Canada Tensions"

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_label_faces", collapse_first)
    posts, clustered = _clustered([three])
    topics, _membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert calls[0] != calls[1]
    assert len(calls) == 2
    assert len(topics) == 1
    assert MIN_FACES <= len(topics[0]["perspectives"]) <= MAX_FACES
    assert {position for _uri, _topic, position, _distance in face_rows} == set(
        range(len(topics[0]["perspectives"]))
    )


def test_build_topics_stops_once_keep_planets_survive(monkeypatch):
    groups = [_planet_posts(f"topic{index}", [30, 12], seed=30 + index) for index in range(5)]
    drafted = []
    original = live._draft_planet

    def counting(posts, clustered, topic, context):
        drafted.append(topic["id"])
        return original(posts, clustered, topic, context)

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    posts, clustered = _clustered(groups)
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2)
    assert len(topics) == 2
    assert drafted == [0, 1]


def test_parallel_workers_do_not_label_past_keep(monkeypatch):
    """A full wave is only the planets still needed, even when several run at once."""
    groups = [_planet_posts(f"topic{index}", [30, 12], seed=30 + index) for index in range(5)]
    drafted = []
    face_calls = []
    original = live._draft_planet

    def counting(posts, clustered, topic, context):
        drafted.append(topic["id"])
        return original(posts, clustered, topic, context)

    def titles_for(prefix, text):
        face_calls.append(prefix)
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    posts, clustered = _clustered(groups)
    context = live._label_context(SETTINGS)
    context["workers"] = 8
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2, context=context)
    assert drafted == [0, 1]
    assert [topic["id"] for topic in topics] == [1, 2]
    assert len(face_calls) == 4
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in topics)


def test_parallel_workers_keep_rank_order_when_the_first_planet_is_slower(monkeypatch):
    import threading

    groups = [_planet_posts(f"topic{index}", [30, 12], seed=40 + index) for index in range(2)]
    started_second = threading.Event()
    overlap = []
    original = live._draft_planet

    def counting(posts, clustered, topic, context):
        if topic["id"] == 0:
            overlap.append(started_second.wait(2))
        elif topic["id"] == 1:
            started_second.set()
        return original(posts, clustered, topic, context)

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    posts, clustered = _clustered(groups)
    context = live._label_context(SETTINGS)
    context["workers"] = 4
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2, context=context)
    assert overlap == [True]
    assert [topic["name"].split()[0] for topic in topics] == ["topic0", "topic1"]


def test_parallel_workers_fill_keep_after_a_failure_without_the_whole_pool(monkeypatch):
    groups = [_planet_posts(f"topic{index}", [30, 12], seed=50 + index) for index in range(5)]
    drafted = []
    original = live._draft_planet

    def counting(posts, clustered, topic, context):
        drafted.append(topic["id"])
        if topic["id"] == 0:
            raise RuntimeError("label backend exploded")
        return original(posts, clustered, topic, context)

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    posts, clustered = _clustered(groups)
    context = live._label_context(SETTINGS)
    context["workers"] = 8
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2, context=context)
    assert drafted == [0, 1, 2]
    assert [topic["name"].split()[0] for topic in topics] == ["topic1", "topic2"]


def test_label_workers_zero_is_one_at_a_time(monkeypatch):
    monkeypatch.setattr(live, "_resolve_backend", lambda backend: "openai")
    monkeypatch.setattr(live, "_generator_for", lambda chosen, model: (lambda prompt: "{}"))
    settings = {
        "label_backend": "openai",
        "openai_model": "m",
        "representative_posts": 6,
        "seed": 0,
        "label_workers": 0,
    }
    assert live._label_context(settings)["workers"] == 1


def test_unshared_face_cannot_leave_fewer_than_two_faces():
    one_left = {
        "id": 2,
        "name": "Solo",
        "perspectives": [
            {"id": "2A", "title": "Real Claim", "summary": "A real claim here.", "post_count": 8, "volume_percent": 80},
            {
                "id": "2B",
                "title": "Mixed remarks",
                "summary": "These posts do not share a claim.",
                "post_count": 2,
                "volume_percent": 20,
            },
        ],
    }
    assert live._drop_unshared_planets([one_left]) == []


def test_dropping_one_unshared_face_keeps_two_and_realigns_rows():
    planet = {
        "id": 4,
        "name": "Court",
        "post_count": 20,
        "perspectives": [
            {"id": "4A", "title": "Roe Settled", "summary": "Roe is settled law.", "post_count": 10, "volume_percent": 50},
            {
                "id": "4B",
                "title": "Mixed remarks",
                "summary": "These posts do not share a claim.",
                "post_count": 6,
                "volume_percent": 30,
            },
            {"id": "4C", "title": "Dobbs Ruling", "summary": "Dobbs changed the rule.", "post_count": 4, "volume_percent": 20},
        ],
    }
    kept = live._drop_unshared_planets([planet])
    assert len(kept) == 1
    faces = kept[0]["perspectives"]
    assert [face["title"] for face in faces] == ["Roe Settled", "Dobbs Ruling"]
    assert abs(sum(face["volume_percent"] for face in faces) - 100) < 0.15
    assert kept[0]["post_count"] == 14
    rows = live._align_face_rows(
        kept,
        [("at://a", 4, 0, 0.1), ("at://b", 4, 1, 0.2), ("at://c", 4, 2, 0.3)],
    )
    assert [(uri, index) for uri, _topic, index, _distance in rows] == [("at://a", 0), ("at://c", 1)]
    assert [face["id"] for face in faces] == ["4A", "4B"]


def test_publishable_guard_drops_a_one_face_planet():
    one = {"name": "Alone", "perspectives": [{"title": "Only"}]}
    two = {"name": "Pair", "perspectives": [{"title": "A"}, {"title": "B"}]}
    seven = {"name": "Crowd", "perspectives": [{"title": str(index)} for index in range(7)]}
    assert live._publishable_planets([one, two, seven]) == [two]


def test_a_failing_section_is_skipped(monkeypatch):
    good = _planet_posts("ukraine", [30, 12], seed=11)
    other = _planet_posts("medicare", [30, 12], seed=12)
    posts, clustered = _clustered([good, other])
    for post in posts:
        post["section"] = "World" if post["uri"].startswith("at://ukraine") else "Health"

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)
    def cluster_texts(texts, **kwargs):
        if texts[0].startswith("medicare"):
            raise ValueError("section exploded")
        # The section's posts are one planet; reuse the sliced embeddings.
        return {
            "topics": [{"id": 0, "size": len(texts), "member_indices": list(range(len(texts))), "terms": ["ukraine"]}],
            "matrix": kwargs["embed"](texts),
            "assignments": [0] * len(texts),
            "noise_count": 0,
        }

    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    settings = {
        **SETTINGS,
        "min_cluster_size": 8,
        "cluster_backend": "embedding",
        "embedding_model": "unused",
    }
    sections = live._cluster_sections(posts, clustered["matrix"], settings, 10, 8)
    assert list(sections) == ["World"]
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in sections["World"])


def test_section_budget_runs_the_largest_section_then_stops(monkeypatch):
    """Largest section first. Once the deadline has passed, the rest are skipped."""
    world = _planet_posts("ukraine", [30, 12], seed=11)
    health = _planet_posts("medicare", [20, 12], seed=12)
    posts, clustered = _clustered([world, health])
    for post in posts:
        post["section"] = "World" if post["uri"].startswith("at://ukraine") else "Health"

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    _fake_labels(monkeypatch, titles_for)

    def cluster_texts(texts, **kwargs):
        return {
            "topics": [
                {"id": 0, "size": len(texts), "member_indices": list(range(len(texts))), "terms": ["topic"]}
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [0] * len(texts),
            "noise_count": 0,
        }

    ticks = iter([0.0, 1_000.0])
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    settings = {**SETTINGS, "min_cluster_size": 8, "cluster_backend": "embedding", "embedding_model": "unused"}
    sections = live._cluster_sections(posts, clustered["matrix"], settings, 10, 8, deadline=10.0)
    assert list(sections) == ["World"]
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in sections["World"])


def test_section_budget_skips_remaining_sections(monkeypatch):
    good = _planet_posts("ukraine", [30, 12], seed=11)
    posts, clustered = _clustered([good])
    for post in posts:
        post["section"] = "World"
    settings = {**SETTINGS, "min_cluster_size": 8, "cluster_backend": "embedding", "embedding_model": "unused"}
    sections = live._cluster_sections(posts, clustered["matrix"], settings, 10, 8, deadline=0.0)
    assert sections == {}
