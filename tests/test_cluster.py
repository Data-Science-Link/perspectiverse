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
    assert 1 <= len(split["faces"]) <= 6
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


def test_choose_n_faces_does_not_slice_a_uniform_topic():
    texts = [f"rent rent rent housing housing costs discussion {index}" for index in range(24)]
    assert choose_n_faces(texts, seed=0) == 1


def test_lexical_cluster_does_not_mint_a_tenth_planet():
    texts = []
    for topic in TOPICS[:9]:
        for copy in range(12):
            texts.append(f"{topic} {topic} {topic} {topic} discussion {copy}")
    for word in ("zzzzalpha", "zzzzbravo"):
        for copy in range(4):
            texts.append(f"{word} {word} {word} outlier {copy}")
    clustered = cluster_texts(texts, min_cluster_size=2, cluster_backend="lexical", seed=0)
    assert len(clustered["topics"]) == 9
    assert all(topic["size"] >= 6 for topic in clustered["topics"])


def test_embedding_publishes_the_largest_tight_groups_and_leaves_the_rest():
    import numpy as np

    def embed(texts):
        rows = []
        for text in texts:
            if text.startswith("topic"):
                axis = int(text.split()[1])
                row = np.zeros(32)
                row[axis] = 1.0
            else:
                axis = 16 + int(text.split()[1])
                row = np.zeros(32)
                row[axis] = 1.0
            rows.append(row)
        return np.asarray(rows, dtype=float)

    texts = [f"topic {topic} words {copy}" for topic in range(12) for copy in range(10)]
    texts += [f"loose {index} words" for index in range(15)]
    clustered = cluster_texts(
        texts,
        min_cluster_size=8,
        cluster_backend="embedding",
        seed=0,
        catalog_size=10,
        embed=embed,
    )
    assert len(clustered["topics"]) == 10
    assert clustered["noise_count"] == 35
    for topic in clustered["topics"]:
        axes = {int(texts[index].split()[1]) for index in topic["member_indices"]}
        assert axes == {int(texts[topic["member_indices"][0]].split()[1])}
        assert all(texts[index].startswith("topic") for index in topic["member_indices"])


def test_embedding_does_not_publish_a_loose_cloud():
    import numpy as np

    def embed(texts):
        rows = []
        for index, _text in enumerate(texts):
            row = np.zeros(len(texts))
            row[index] = 1.0
            rows.append(row)
        return np.asarray(rows, dtype=float)

    texts = [f"unrelated post number {index} about nothing shared" for index in range(40)]
    with pytest.raises(RuntimeError, match="No cluster met min size"):
        cluster_texts(
            texts,
            min_cluster_size=8,
            cluster_backend="embedding",
            seed=0,
            catalog_size=10,
            embed=embed,
        )


def test_embedding_backend_keeps_three_separated_groups():
    import numpy as np

    def embed(texts):
        rows = []
        for text in texts:
            if "alpha" in text:
                rows.append([1.0, 0.0, 0.0])
            elif "beta" in text:
                rows.append([0.0, 1.0, 0.0])
            else:
                rows.append([0.0, 0.0, 1.0])
        return np.asarray(rows, dtype=float)

    texts = [f"alpha topic words {index}" for index in range(12)]
    texts += [f"beta topic words {index}" for index in range(12)]
    texts += [f"gamma topic words {index}" for index in range(12)]
    clustered = cluster_texts(
        texts,
        min_cluster_size=8,
        cluster_backend="embedding",
        seed=0,
        catalog_size=10,
        embed=embed,
    )
    assert len(clustered["topics"]) == 3
    assert clustered["noise_count"] == 0


def test_keep_top_does_not_split_large_clusters_to_fill_ten():
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
    assert len(clustered["topics"]) == 9
    assert all(topic["size"] >= 6 for topic in clustered["topics"])
    assert clustered["noise_count"] == 8
    assert sum(1 for assignment in clustered["assignments"] if assignment >= 0) == 72


def test_author_cap_keeps_three_posts_and_ranks_by_voices():
    texts = []
    authors = []
    labels = []
    for copy in range(8):
        texts.append(f"alpha alpha alpha shared topic {copy}")
        authors.append("solo")
        labels.append(0)
    for copy in range(6):
        texts.append(f"beta beta beta shared topic {copy}")
        authors.append(f"voice-{copy}")
        labels.append(1)
    from pipeline.topics import _cap_author_posts, _keep_top

    capped_labels = _cap_author_posts(labels, authors, 3)
    assert capped_labels.count(0) == 3
    assert capped_labels.count(1) == 6
    kept = _keep_top(texts, capped_labels, {}, min_cluster_size=2, keep=10, authors=authors)
    assert [topic["size"] for topic in kept["topics"]] == [6, 3]


def test_wide_group_is_dropped():
    import numpy as np

    from pipeline.topics import _drop_wide_groups

    matrix = np.asarray(
        [
            [1.0, 0.0],
            [0.6, 0.8],
            [0.0, 1.0],
        ],
        dtype=float,
    )
    labels = np.asarray([0, 0, 0])
    _drop_wide_groups(matrix, labels, minimum=0.9)
    assert set(int(item) for item in labels) == {-1}


def test_keep_top_rejects_too_few_posts():
    texts = ["alpha beta gamma extra"] * 50
    labels = [index % 11 for index in range(50)]
    with pytest.raises(RuntimeError, match="No cluster met min size"):
        _keep_top(texts, labels, {}, min_cluster_size=6, keep=10)
