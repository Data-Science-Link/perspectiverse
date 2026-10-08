"""Regression tests for issue #53: no published planet outside 2-6 faces.

The 2026-10-07 daily run died on ``Topic 2 should have 2-6 perspectives,
found 1`` after face labels collapsed a split (a face with no shared claim,
or two faces with the same title). #53 dropped that planet. #76 keeps it:
pick 2..6 faces by fit, keep small tight minorities, and when the split
collapses, force two faces and record ``face_distinctness`` instead of
dropping the planet or failing the snapshot.
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
        assert len(split["faces"]) == 2
        assert split["forced"] is True
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

    def label_perspective(posts, terms, backend="auto", model=None, **kwargs):
        text = str(posts[0].get("text") or "")
        prefix = text.split()[0]
        title = titles_for(prefix, text)
        return {"title": title, "summary": f"{title} is the claim here.", "label_source": "heuristic"}

    monkeypatch.setattr(live, "label_perspective", label_perspective)
    monkeypatch.setattr(live, "_title_covers_posts", lambda title, posts: True)
    monkeypatch.setattr(live, "_claim_words_overlap", lambda left, right: True)
    monkeypatch.setattr(live, "_posts_share_a_subject", lambda posts: True)
    monkeypatch.setattr(live, "specific_shared_words", lambda faces: {"shared"})


def test_planet_whose_faces_collapse_is_kept_with_a_score(monkeypatch):
    """Labels that merge every face into one used to drop the planet. Keep it (#76)."""
    good = _planet_posts("ukraine", [30, 12], seed=11)
    collapsing = _planet_posts("medicare", [30, 12], seed=12)

    def titles_for(prefix, text):
        if prefix == "medicare":
            return "Medicare Payment"  # every face gets the same stance title
        return "Russia Aggression" if "stance0" in text else "Trump Ukraine Deal"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([good, collapsing])
    topics, membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert [len(topic["perspectives"]) for topic in topics] == [2, 2]
    assert {uri.split("/")[2] for uri, _topic in membership} == {"ukraine", "medicare"}
    assert {topic_id for _uri, topic_id, _face, _distance in face_rows} == {1, 2}
    medicare = next(topic for topic in topics if "Medicare" in topic["name"] or "medicare" in topic["name"].lower())
    assert medicare["face_distinctness"] > 0
    assert len({face["title"] for face in medicare["perspectives"]}) == 2
    payload = assemble_payload(topics, mode="live", source="fixture", total_posts=len(posts))
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in payload["topics"])
    assert all("face_distinctness" in topic for topic in payload["topics"])


def test_mixed_remarks_face_does_not_drop_the_planet(monkeypatch):
    collapsing = _planet_posts("medicare", [30, 12], seed=12)

    def titles_for(prefix, text):
        return "Medicare Payment" if "stance0" in text else "Mixed remarks"

    _fake_labels(monkeypatch, titles_for)
    posts, clustered = _clustered([collapsing])
    topics, membership, face_rows = live._build_topics(posts, clustered, SETTINGS, keep=10)
    assert len(topics) == 1
    assert len(topics[0]["perspectives"]) == 2
    assert membership and face_rows
    assert 0.0 <= topics[0]["face_distinctness"] <= 1.0


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
    kept = live._drop_unshared_planets([one_left])
    assert len(kept) == 1
    assert [face["title"] for face in kept[0]["perspectives"]] == ["Real Claim", "Mixed remarks"]


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

    clock = {"now": 0.0}
    original = live._draft_planet

    def draft(posts, clustered, topic, context):
        result = original(posts, clustered, topic, context)
        # The first planet spends the rest of the ceiling. Workers are 1 here,
        # so the smaller section has not been submitted yet.
        clock["now"] = 1_000.0
        return result

    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    monkeypatch.setattr(live, "_draft_planet", draft)
    monkeypatch.setattr("time.monotonic", lambda: clock["now"])
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


def _story_blob(word: str, size: int, seed: int):
    """One tight embedding group whose posts repeat a single subject word."""
    matrix = _blobs([size], seed=seed)
    posts = []
    for copy in range(size):
        extra = {"diesel": "stockpile refinery", "measles": "vaccine outbreak", "bitcoin": "wallet ledger"}.get(
            word, "remark detail"
        )
        text = f"{word} {word} {word} {extra} {copy}"
        posts.append(
            {
                "uri": f"at://{word}/{copy}",
                "author": f"{word}.{copy}",
                "clean_text": text,
                "text": text,
                "likes": copy,
            }
        )
    return posts, matrix


def _glued_candidate(stories):
    posts, blocks = [], []
    for group_posts, matrix in stories:
        posts.extend(group_posts)
        blocks.append(matrix)
    clustered = {
        "topics": [
            {
                "id": 0,
                "size": len(posts),
                "member_indices": list(range(len(posts))),
                "terms": ["glued"],
            }
        ],
        "matrix": np.vstack(blocks),
        "assignments": [],
        "noise_count": 0,
    }
    return posts, clustered


def test_glued_stories_split_instead_of_dropping(capsys):
    """A candidate whose faces share no subject word becomes one planet per story."""
    posts, clustered = _glued_candidate(
        [
            _story_blob("diesel", 24, seed=3),
            _story_blob("measles", 20, seed=11),
        ]
    )
    topics, membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=10)
    logged = capsys.readouterr().out
    assert "its faces are different stories." not in logged
    assert "Splitting" in logged
    assert len(topics) == 2
    names = " ".join(topic["name"].lower() for topic in topics)
    assert "diesel" in names
    assert "measles" in names
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in topics)
    authors = {uri.split("/")[2] for uri, _topic in membership}
    assert authors == {"diesel", "measles"}
    for topic in topics:
        words = {word for face in topic["perspectives"] for word in (face.get("top_terms") or [])}
        assert words
        # Each planet's faces are one story, so they share that story's word.
        blob = "diesel" if "diesel" in topic["name"].lower() else "measles"
        assert all(blob in str(face.get("title") or "").lower() or blob in str(face.get("summary") or "").lower() or blob in " ".join(face.get("top_terms") or []) for face in topic["perspectives"])


def test_different_stories_stay_published_through_the_later_guard(capsys):
    """The post-label guard does not drop a planet for being a different story.

    A glued candidate is split into planets. Once those planets exist, removing
    faces with no shared claim does not throw them away, and a planet that
    arrives with one face still is.
    """
    posts, clustered = _glued_candidate(
        [
            _story_blob("diesel", 24, seed=3),
            _story_blob("measles", 20, seed=11),
        ]
    )
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=10)
    logged = capsys.readouterr().out
    assert len(topics) == 2
    assert "Splitting" in logged
    assert not any(
        line.startswith("Dropping") and "different stories" in line for line in logged.splitlines()
    )
    kept = live._drop_unshared_planets(topics)
    assert [topic["name"] for topic in kept] == [topic["name"] for topic in topics]
    lone = {
        **topics[0],
        "name": "Lone",
        "perspectives": topics[0]["perspectives"][:1],
    }
    assert live._drop_unshared_planets([lone]) == []


def test_split_planets_stay_within_the_catalog(capsys):
    posts, clustered = _glued_candidate(
        [
            _story_blob("diesel", 24, seed=3),
            _story_blob("measles", 20, seed=11),
            _story_blob("bitcoin", 18, seed=19),
        ]
    )
    topics, membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2)
    logged = capsys.readouterr().out
    assert len(topics) == 2
    assert "the catalog already has 2 planets" in logged
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in topics)
    assert len({topic_id for _uri, topic_id in membership}) == 2


def test_single_post_story_is_skipped_with_a_reason(capsys):
    diesel_posts, diesel_matrix = _story_blob("diesel", 16, seed=4)
    lone = {
        "uri": "at://hurricane/0",
        "author": "hurricane.0",
        "clean_text": "hurricane hurricane landfall warning",
        "text": "hurricane hurricane landfall warning",
        "likes": 1,
    }
    # A 1-post face cannot come from the face splitter's floors, so build the
    # drafted rows the splitter would hand to the story cut.
    members = diesel_posts + [lone]
    drafted = [
        (
            {
                "title": "Diesel",
                "summary": "Diesel exports are the claim.",
                "representative_posts": [{"text": post["text"]} for post in diesel_posts[:3]],
            },
            [(post["uri"], 0, 0.1) for post in diesel_posts],
            len(diesel_posts),
        ),
        (
            {
                "title": "Hurricane",
                "summary": "A hurricane is the claim.",
                "representative_posts": [{"text": lone["text"]}],
            },
            [(lone["uri"], 1, 0.2)],
            1,
        ),
    ]
    topic = {"id": 0, "terms": ["glued"], "member_indices": list(range(len(members))), "size": len(members)}
    clustered = {"matrix": np.vstack([diesel_matrix, _blobs([1], seed=8)]), "topics": [topic]}
    handled, result, log = live._split_different_stories(
        members, clustered, topic, live._label_context(SETTINGS), members, drafted, []
    )
    assert handled is True
    assert any(line.startswith("INFO ") and "1 post" in line for line in log)
    assert not any("Folding" in line for line in log)
    assert result is not None
    assert result["floor_excluded"] == 1
    assert len(result["planets"]) == 1
    assert "diesel" in result["planets"][0]["planet"]["name"].lower()
    assert all("hurricane" not in uri for uri in result["planets"][0]["membership"])
    del capsys


def _spy_labelers(monkeypatch):
    """Record posts handed to the label, name, and rename calls."""
    seen = []

    def wrap(name):
        real = getattr(live, name)

        def spy(*args, **kwargs):
            posts = args[0] if args else []
            if isinstance(posts, list):
                blob = " ".join(
                    str(post.get("text") or post.get("clean_text") or "")
                    for post in posts
                    if isinstance(post, dict)
                )
                seen.append((name, blob))
            return real(*args, **kwargs)

        monkeypatch.setattr(live, name, spy)

    for name in ("label_perspective", "label_topic", "name_from_perspectives"):
        wrap(name)
    return seen


def _drafted_stories(stories):
    """Pre-labeled faces, one per story, as ``_split_different_stories`` receives them."""
    members = []
    drafted = []
    blocks = []
    for posts, matrix in stories:
        start = len(members)
        members.extend(posts)
        blocks.append(matrix)
        drafted.append(
            (
                {
                    "title": posts[0]["text"].split()[0].capitalize(),
                    "summary": f"{posts[0]['text'].split()[0]} is the claim.",
                    "representative_posts": [{"text": post["text"]} for post in posts[:3]],
                },
                [(post["uri"], len(drafted), 0.1) for post in posts],
                len(posts),
            )
        )
        del start
    topic = {"id": 0, "terms": ["glued"], "member_indices": list(range(len(members))), "size": len(members)}
    clustered = {"matrix": np.vstack(blocks), "topics": [topic]}
    return members, clustered, topic, drafted


def test_split_child_under_the_floor_is_excluded_without_label_calls(monkeypatch):
    seen = _spy_labelers(monkeypatch)
    members, clustered, topic, drafted = _drafted_stories(
        [
            _story_blob("diesel", 16, seed=4),
            _story_blob("measles", 3, seed=9),
        ]
    )
    context = live._label_context(SETTINGS)
    context["section"] = "Health"
    handled, result, log = live._split_different_stories(
        members, clustered, topic, context, members, drafted, []
    )
    assert handled is True
    assert result is not None
    assert len(result["planets"]) == 1
    assert "diesel" in result["planets"][0]["planet"]["name"].lower()
    assert result["floor_excluded"] == 1
    assert any(line.startswith("INFO Health:") and "3 posts" in line for line in log)
    assert seen
    assert all("measles" not in blob for _name, blob in seen)


def test_split_child_at_the_floor_is_kept(monkeypatch):
    seen = _spy_labelers(monkeypatch)
    members, clustered, topic, drafted = _drafted_stories(
        [
            _story_blob("diesel", 16, seed=4),
            _story_blob("measles", 5, seed=9),
        ]
    )
    handled, result, log = live._split_different_stories(
        members, clustered, topic, live._label_context(SETTINGS), members, drafted, []
    )
    assert handled is True
    assert result is not None
    assert len(result["planets"]) == 2
    names = " ".join(bundle["planet"]["name"].lower() for bundle in result["planets"])
    assert "diesel" in names
    assert "measles" in names
    assert result["floor_excluded"] == 0
    assert any("measles" in blob for _name, blob in seen)
    assert not any(line.startswith("INFO ") for line in log)


def test_min_planet_posts_override_excludes_a_child_the_default_keeps(monkeypatch):
    members, clustered, topic, drafted = _drafted_stories(
        [
            _story_blob("diesel", 16, seed=4),
            _story_blob("measles", 6, seed=9),
        ]
    )
    default_handled, default_result, _default_log = live._split_different_stories(
        members, clustered, topic, live._label_context(SETTINGS), members, drafted, []
    )
    assert default_handled is True
    assert len(default_result["planets"]) == 2

    seen = _spy_labelers(monkeypatch)
    overridden = live._label_context({**SETTINGS, "min_planet_posts": 8})
    overridden["section"] = "Health"
    handled, result, log = live._split_different_stories(
        members, clustered, topic, overridden, members, drafted, []
    )
    assert handled is True
    assert result is not None
    assert len(result["planets"]) == 1
    assert "measles" not in result["planets"][0]["planet"]["name"].lower()
    assert result["floor_excluded"] == 1
    assert any(line.startswith("INFO Health:") and "6 posts" in line for line in log)
    assert all("measles" not in blob for _name, blob in seen)


def test_planet_that_shrinks_below_the_floor_is_not_named(monkeypatch, capsys):
    """Face labels can leave fewer posts than the floor. Skip the name and do not publish."""

    def fake_faces(members, split, terms, context, lock_floor=False):
        del split, terms, context, lock_floor
        drafted = []
        cursor = 0
        for position, size in enumerate((2, 1)):
            chunk = members[cursor : cursor + size]
            cursor += size
            drafted.append(
                (
                    {
                        "title": "Diesel exports",
                        "summary": "Diesel exports are the claim.",
                        "representative_posts": [{"text": post["text"]} for post in chunk],
                    },
                    [(post["uri"], position, 0.1) for post in chunk],
                    size,
                )
            )
        return drafted, 2

    monkeypatch.setattr(live, "_label_faces", fake_faces)
    named = []

    def fake_name(*args, **kwargs):
        del args, kwargs
        named.append("name")
        return {"name": "Nope", "label_source": "heuristic"}

    monkeypatch.setattr(live, "label_topic", fake_name)
    posts, matrix = _story_blob("diesel", 12, seed=3)
    clustered = {
        "topics": [{"id": 0, "size": 12, "member_indices": list(range(12)), "terms": ["diesel"]}],
        "matrix": matrix,
        "assignments": [],
        "noise_count": 0,
    }
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=1)
    logged = capsys.readouterr().out
    assert topics == []
    assert named == []
    assert "INFO All topics:" in logged
    assert "3 posts" in logged


def test_whole_planet_under_the_floor_is_not_labeled_or_used_as_filler(monkeypatch, capsys):
    seen = _spy_labelers(monkeypatch)
    small_posts, small_matrix = _story_blob("measles", 4, seed=2)
    big_posts, big_matrix = _story_blob("diesel", 16, seed=6)
    posts = small_posts + big_posts
    clustered = {
        "topics": [
            {"id": 0, "size": 4, "member_indices": [0, 1, 2, 3], "terms": ["measles"]},
            {"id": 1, "size": 16, "member_indices": list(range(4, 20)), "terms": ["diesel"]},
        ],
        "matrix": np.vstack([small_matrix, big_matrix]),
        "assignments": [],
        "noise_count": 0,
    }
    topics, membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=1)
    logged = capsys.readouterr().out
    assert len(topics) == 1
    assert "diesel" in topics[0]["name"].lower()
    assert "INFO All topics:" in logged
    assert "4 posts" in logged
    assert "measles" in logged.lower()
    assert all("measles" not in blob for _name, blob in seen)
    assert {uri.split("/")[2] for uri, _topic in membership} == {"diesel"}
