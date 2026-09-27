import json
from pathlib import Path

import pytest

from pipeline.perspectives import choose_n_faces, select_representatives, split_perspectives
from pipeline.schema import to_percents
from pipeline.topics import _keep_top, cluster_texts
from tests.corpus import FACES, TOPICS, build_tiny_posts


def test_lexical_cluster_drops_noise_and_keeps_ten():
    posts = build_tiny_posts()
    clustered = cluster_texts(
        [post["text"] for post in posts],
        min_cluster_size=8,
        cluster_backend="lexical",
        seed=0,
    )
    assert len(clustered["topics"]) == 10
    assert clustered["noise_count"] == 2
    for post, assignment in zip(posts, clustered["assignments"]):
        if "zzzznoise" in post["text"]:
            assert assignment == -1
        else:
            assert assignment >= 0
    volumes = to_percents([topic["size"] for topic in clustered["topics"]])
    assert abs(sum(volumes) - 100.0) < 0.05
    names = {" ".join(topic["terms"]) for topic in clustered["topics"]}
    assert names == set(TOPICS)


def test_each_topic_splits_into_two_to_six_faces():
    posts = [post for post in build_tiny_posts() if "zzzznoise" not in post["text"] and post["text"].startswith("climate")]
    split = split_perspectives([post["text"] for post in posts], seed=0)
    assert 2 <= len(split["faces"]) <= 6
    assert all(face["size"] >= 1 for face in split["faces"])
    volumes = to_percents([face["size"] for face in split["faces"]])
    assert abs(sum(volumes) - 100.0) < 0.05
    # One dominant face must still be a valid cube: inflate the first bucket.
    lopsided = to_percents([40, 2, 2, 2, 2, 2])
    assert abs(sum(lopsided) - 100.0) < 0.05
    assert max(lopsided) > 70


def test_representatives_prefer_likes_then_centroid():
    posts = [
        {"author": "low", "text": "a", "clean_text": "low likes", "likes": 1},
        {"author": "high", "text": "b", "clean_text": "high likes", "likes": 9},
        {"author": "tie-far", "text": "c", "clean_text": "tied far", "likes": 9},
    ]
    chosen = select_representatives(posts, [0.2, 0.4, 0.1], limit=2)
    assert [post["author"] for post in chosen] == ["tie-far", "high"]
    assert "likes" in chosen[0]


def test_checked_in_fixture_matches_builder():
    path = Path(__file__).parent / "fixtures" / "tiny_posts.json"
    assert json.loads(path.read_text(encoding="utf-8")) == build_tiny_posts()


def test_face_terms_cover_the_six_labels():
    posts = [post for post in build_tiny_posts() if post["text"].startswith("football")]
    split = split_perspectives([post["text"] for post in posts], n_faces=6, seed=0)
    found = {term for face in split["faces"] for term in face["terms"]}
    assert set(FACES).issubset(found)


def test_choose_n_faces_collapses_a_binary_topic():
    texts = [f"alpha alpha alpha cluster {index}" for index in range(12)]
    texts += [f"omega omega omega cluster {index}" for index in range(12)]
    assert choose_n_faces(texts, seed=0) == 2


def test_lexical_cluster_rebalances_an_uneven_live_sample():
    texts = []
    for topic in TOPICS[:9]:
        for copy in range(12):
            texts.append(f"{topic} {topic} {topic} {topic} discussion {copy}")
    for word in ("zzzzalpha", "zzzzbravo"):
        for copy in range(4):
            texts.append(f"{word} {word} {word} outlier {copy}")
    clustered = cluster_texts(texts, min_cluster_size=2, cluster_backend="lexical", seed=0)
    assert len(clustered["topics"]) == 10
    assert all(topic["size"] >= 6 for topic in clustered["topics"])


def test_keep_top_rebalances_short_clusters_into_ten_planets():
    texts = []
    labels = []
    for topic in range(9):
        word = f"topic{topic:02d}word"
        for copy in range(8):
            texts.append(f"{word} {word} {word} extra context {copy}")
            labels.append(topic)
    for topic, word in ((9, "leftoveralpha"), (10, "leftoverbravo")):
        for copy in range(4):
            texts.append(f"{word} {word} {word} extra context {copy}")
            labels.append(topic)

    clustered = _keep_top(texts, labels, {}, min_cluster_size=6, keep=10)
    assert len(clustered["topics"]) == 10
    assert all(topic["size"] >= 6 for topic in clustered["topics"])
    assert clustered["noise_count"] == 2
    assert sum(1 for assignment in clustered["assignments"] if assignment >= 0) == 78


def test_keep_top_rejects_too_few_posts():
    texts = ["alpha beta gamma extra"] * 50
    labels = [index % 11 for index in range(50)]
    with pytest.raises(RuntimeError, match="found 50 posts"):
        _keep_top(texts, labels, {}, min_cluster_size=6, keep=10)
