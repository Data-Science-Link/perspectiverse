import json
from pathlib import Path

from pipeline.perspectives import select_representatives, split_perspectives
from pipeline.schema import to_percents
from pipeline.topics import cluster_texts
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


def test_each_topic_splits_into_six_faces():
    posts = [post for post in build_tiny_posts() if "zzzznoise" not in post["text"] and post["text"].startswith("climate")]
    split = split_perspectives([post["text"] for post in posts], seed=0)
    assert len(split["faces"]) == 6
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
    split = split_perspectives([post["text"] for post in posts], seed=0)
    found = {term for face in split["faces"] for term in face["terms"]}
    assert set(FACES).issubset(found)
