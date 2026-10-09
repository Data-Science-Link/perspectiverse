"""Same-story attach, fold, face restore, and post-relabel title merge."""

import numpy as np

from pipeline.schema import SINGLE_VIEW_NOTE
from pipeline.story_attach import (
    attach_same_story,
    attachment_stems,
    merge_alike_published_faces,
    return_same_story_posts,
)
from pipeline.topics import cluster_texts


def _unit(*coords: float) -> np.ndarray:
    vec = np.zeros(8, dtype=np.float64)
    for index, value in enumerate(coords):
        vec[index] = value
    return vec / np.linalg.norm(vec)


def _repeat(text: str, count: int, vector: np.ndarray) -> tuple[list[str], np.ndarray]:
    return [text] * count, np.vstack([vector] * count)


def test_ukraine_noise_attaches_and_hockey_does_not():
    parent, parent_vec = _repeat("Ukraine Russia Kyiv drone strike on the bridge", 20, _unit(1, 0))
    near = "Kyiv drone strike hit Ukraine and Russia again"
    far = "The hockey playoff goal stunned the crowd in overtime"
    texts = parent + [near, far]
    matrix = np.vstack([parent_vec, _unit(0.50, 0.866), _unit(0, 1)])
    labels = [0] * 20 + [-1, -1]
    updated, stats = attach_same_story(matrix, texts, labels, fold=False)
    assert stats["attached"] == 1
    assert updated[20] == 0
    assert updated[21] == -1


def test_zionism_post_does_not_attach_to_a_gaza_planet():
    parent, parent_vec = _repeat("Gaza Israel Hamas Palestine fighting", 20, _unit(1, 0))
    zionism = "The Greens motion says Zionism is racism"
    texts = parent + [zionism]
    matrix = np.vstack([parent_vec, _unit(0.90, 0.436)])
    labels = [0] * 20 + [-1]
    updated, stats = attach_same_story(matrix, texts, labels, fold=False)
    assert stats["attached"] == 0
    assert updated[-1] == -1
    assert "zionism" not in attachment_stems(parent)


def test_author_cap_skip_stays_noise():
    parent, parent_vec = _repeat("Ukraine Russia Kyiv drone strike on the bridge", 20, _unit(1, 0))
    near = "Kyiv drone strike hit Ukraine and Russia again"
    texts = parent + [near]
    matrix = np.vstack([parent_vec, _unit(0.50, 0.866)])
    labels = [0] * 20 + [-1]
    updated, stats = attach_same_story(matrix, texts, labels, skip={20}, fold=False)
    assert stats["attached"] == 0
    assert updated[20] == -1


def test_kyiv_sibling_folds_and_genocide_ball_does_not():
    parent, parent_vec = _repeat("Ukraine Russia invasion of Kyiv", 22, _unit(1, 0, 0))
    kyiv, kyiv_vec = _repeat("Kyiv bridge strikes by Russian drones in Ukraine", 6, _unit(0.70, 0.714, 0))
    genocide = ["The holocaust and genocide memorial remembered the victims"] * 7
    genocide.append("Ukraine genocide")
    genocide_vec = np.vstack([_unit(0.72, 0.694, 0)] * 8)
    texts = parent + kyiv + genocide
    matrix = np.vstack([parent_vec, kyiv_vec, genocide_vec])
    labels = [0] * 22 + [1] * 6 + [2] * 8
    updated, stats = attach_same_story(matrix, texts, labels, noise=False)
    assert stats["folded_planets"] == 1
    assert stats["folded_posts"] == 6
    assert set(updated[:28]) == {0}
    assert set(updated[28:]) == {2}


def test_putin_planet_does_not_fold_into_ukraine():
    parent, parent_vec = _repeat("Ukraine Russia invasion of Kyiv", 22, _unit(1, 0))
    sibling, sibling_vec = _repeat("Trump met Putin to talk tariffs", 8, _unit(0.70, 0.714))
    texts = parent + sibling
    matrix = np.vstack([parent_vec, sibling_vec])
    labels = [0] * 22 + [1] * 8
    updated, stats = attach_same_story(matrix, texts, labels, noise=False)
    assert stats["folded_planets"] == 0
    assert set(updated[22:]) == {1}


def test_chain_does_not_follow_the_middle_planet():
    """C is close to B, and B folds into A. C does not follow B into A."""
    parent, parent_vec = _repeat("Ukraine Russia invasion of Kyiv", 30, _unit(1, 0, 0))
    middle, middle_vec = _repeat("Kyiv bridge strikes by Russian drones in Ukraine", 22, _unit(0.70, 0.714, 0))
    # Cosine to the middle planet is about 0.70. Cosine to the parent is 0.30.
    child_vec = _unit(0.30, 0.686, 0.663)
    child, child_rows = _repeat("Kyiv bridge strikes by Russian drones in Ukraine", 8, child_vec)
    texts = parent + middle + child
    matrix = np.vstack([parent_vec, middle_vec, child_rows])
    labels = [0] * 30 + [1] * 22 + [2] * 8
    updated, stats = attach_same_story(matrix, texts, labels, noise=False)
    assert stats["folded_planets"] == 1
    assert set(updated[:52]) == {0}
    assert set(updated[52:]) == {2}


def test_ambiguous_parents_leave_the_post_alone():
    left, left_vec = _repeat("Ukraine Russia invasion of Kyiv", 20, _unit(1, 0, 0))
    right, right_vec = _repeat("Ukraine Russia invasion of Kyiv", 20, _unit(0.98, 0.199, 0))
    post = "Kyiv drone strike hit Ukraine and Russia again"
    # Almost equally close to both parents.
    post_vec = _unit(0.995, 0.100, 0)
    texts = left + right + [post]
    matrix = np.vstack([left_vec, right_vec, post_vec])
    labels = [0] * 20 + [1] * 20 + [-1]
    updated, stats = attach_same_story(matrix, texts, labels, fold=False)
    assert stats["attached"] == 0
    assert updated[-1] == -1


def test_ice_acronym_is_an_attachment_stem():
    parent, parent_vec = _repeat("ICE deportation raid at the workplace", 20, _unit(1, 0))
    near = "ICE deportation raid continued overnight"
    other = "The ice age museum opened downtown"
    texts = parent + [near, other]
    matrix = np.vstack([parent_vec, _unit(0.60, 0.800), _unit(0.60, 0.800)])
    labels = [0] * 20 + [-1, -1]
    stems = attachment_stems(parent)
    assert "ice" in stems
    updated, stats = attach_same_story(matrix, texts, labels, fold=False)
    assert stats["attached"] == 1
    assert updated[20] == 0
    assert updated[21] == -1


def test_equal_synthetic_groups_do_not_fold(capsys):
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
    assert clustered["same_story"]["folded_planets"] == 0
    assert clustered["same_story"]["attached"] == 0
    assert capsys.readouterr().out == ""


def _member(uri: str, text: str) -> dict:
    return {"uri": uri, "clean_text": text, "text": text}


def _draft(title: str, uris: list[str], size: int | None = None) -> tuple[dict, list, int]:
    perspective = {
        "title": title,
        "summary": "These posts do not share a claim." if title == "Mixed remarks" else "A claim.",
        "_face_member_uris": list(uris),
    }
    rows = [(uri, 0, 0.1) for uri in uris]
    return perspective, rows, size if size is not None else len(uris)


def test_face_restore_returns_kyiv_and_not_zionism():
    members = [
        _member("u1", "Ukraine Russia invasion of Kyiv"),
        _member("u2", "Ukraine Russia invasion of Kyiv"),
        _member("u5", "Ukraine Russia invasion of Kyiv"),
        _member("u3", "Kyiv drone strike hit Ukraine and Russia again"),
        _member("u4", "The Greens motion says Zionism is racism"),
    ]
    kept = [_draft("Russia Invasion", ["u1", "u2", "u5"])]
    dropped = [
        _draft("Mixed remarks", ["u3"]),
        _draft("Mixed remarks", ["u4"]),
    ]
    restored, count = return_same_story_posts(kept, dropped, members)
    assert count == 1
    uris = [uri for uri, _position, _distance in restored[0][1]]
    assert uris == ["u1", "u2", "u5", "u3"]
    assert restored[0][2] == 4


def _face(title: str, count: int, face: str, uris: list[str]) -> dict:
    return {
        "id": face,
        "title": title,
        "summary": "One claim.",
        "post_count": count,
        "volume_percent": 50.0,
        "representative_posts": [{"author": "a", "text": title, "likes": 1}],
        "_face_member_uris": uris,
    }


def test_identical_iran_war_faces_merge_after_relabel():
    topic = {
        "id": 1,
        "post_count": 48,
        "perspectives": [
            _face("Iran War", 42, "1A", ["a"]),
            _face("Iran War", 6, "1B", ["b"]),
        ],
    }
    folded = merge_alike_published_faces([topic])
    assert folded == 1
    assert len(topic["perspectives"]) == 1
    assert topic["perspectives"][0]["post_count"] == 48
    assert topic["perspectives"][0]["id"] == "1A"
    assert topic["post_count"] == 48
    assert topic["opposing_note"] == SINGLE_VIEW_NOTE
    assert set(topic["perspectives"][0]["_face_member_uris"]) == {"a", "b"}


def test_iran_war_and_iran_conflict_stay_separate():
    topic = {
        "id": 2,
        "post_count": 48,
        "perspectives": [
            _face("Iran War", 42, "2A", ["a"]),
            _face("US Iran Conflict", 6, "2B", ["b"]),
        ],
    }
    folded = merge_alike_published_faces([topic])
    assert folded == 0
    assert [face["title"] for face in topic["perspectives"]] == ["Iran War", "US Iran Conflict"]
