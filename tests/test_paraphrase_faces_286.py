"""Fixture pairs the stance lexicon misread on high-cosine faces (#286).

The posts are the published representative texts from the 2026-10-20 snapshot
(at most 36 per face). The matrix is synthetic and only places the two faces
at cosine 0.85, above the paraphrase line. The gate may refuse that split
only when both faces hold the same pole and that pole is not aimed at
disjoint named actors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "286"


def _load(pair_id: str) -> dict:
    return json.loads((FIXTURES / f"{pair_id}.json").read_text(encoding="utf-8"))


def _posts(texts: list[str]) -> list[dict]:
    return [{"text": text} for text in texts]


def _at_cosine(posts_a: list[str], posts_b: list[str], cosine: float = 0.85):
    import numpy as np

    left = np.array([1.0, 0.0])
    right = np.array([cosine, (1 - cosine**2) ** 0.5])
    texts = list(posts_a) + list(posts_b)
    matrix = np.vstack([left] * len(posts_a) + [right] * len(posts_b))
    labels = [0] * len(posts_a) + [1] * len(posts_b)
    return texts, labels, matrix


def _refused(data: dict) -> list[tuple[int, int]]:
    from pipeline.perspectives import refused_paraphrase_pairs

    texts, labels, matrix = _at_cosine(data["posts_a"], data["posts_b"])
    refused = refused_paraphrase_pairs(texts, labels, matrix)
    return [(left, right) for left, right, _cosine in refused]


def test_attributed_endorse_is_not_the_speakers_side():
    from pipeline.stance import _cue_pole

    assert _cue_pole("Trump is supporting Putin") == 0
    assert _cue_pole("TFG is now prosecuting the iran war and directly supporting Putin") == 0
    assert _cue_pole("we support the policy") == 1
    assert _cue_pole('He said "Israel condemns violence" and left.') == 0
    assert _cue_pole("Putin has been empowered with the resources to kill countless Ukrainians") == -1
    assert _cue_pole("I am not defending Putin") == -1
    assert _cue_pole("I say this policy is stupid and wrong") == -1


def test_same_actor_is_one_stance_and_a_different_actor_is_not():
    from pipeline.perspectives import choose_n_faces

    same = ["israel is committing genocide"] * 12
    texts, _labels, matrix = _at_cosine(same, same)
    assert choose_n_faces(texts, seed=0, matrix=matrix) is None
    texts, _labels, matrix = _at_cosine(
        ["israel is committing genocide"] * 12,
        ["hamas killed civilians"] * 12,
    )
    assert choose_n_faces(texts, seed=0, matrix=matrix) == 2


def test_u001_accusatory_supporting_does_not_merge():
    """Trump Helps Russia condemns. Trump Supports Putin does not endorse.

    Accusatory "supporting Putin" is Trump's act, not the speaker taking
    Putin's side. Two leftover endorse cues ("worth", "our support") are not
    enough posts to give that face a pole. No pole is not agreement, so the
    split stays.
    """
    from pipeline.stance import _posts_pole, posts_share_stance

    data = _load("u001")
    left, right = _posts(data["posts_a"]), _posts(data["posts_b"])
    assert _posts_pole(left) == -1
    assert _posts_pole(right) == 0
    assert posts_share_stance(left, right) is False
    assert _refused(data) == []


def test_u002_mixed_advocacy_posts_do_not_share_one_pole():
    """Trans Hate and Trans Rights both read as advocacy to a person.

    The posts do not give the lexicon one shared side. Trans Hate is 3
    condemn and 3 endorse out of 36. Trans Rights is 4 condemn and 2 endorse
    out of 36, under the share that holds a pole. Endorse cues that are
    quoted or attributed ("i don't support trans people", "they just want
    you to vote in their favor") are not the speaker's side. Condemn cues
    such as "genocide", "harm", and "trans hate" are. Neither face holds a
    pole, so there is no positive evidence they are the same stance. The
    split stays. The gate does not merge them to match a human reading of
    advocacy.
    """
    from pipeline.stance import _cue_pole, _posts_pole, posts_share_stance

    data = _load("u002")
    left, right = _posts(data["posts_a"]), _posts(data["posts_b"])
    left_signs = [_cue_pole(post["text"]) for post in left]
    right_signs = [_cue_pole(post["text"]) for post in right]
    assert sum(sign < 0 for sign in left_signs) == 3
    assert sum(sign > 0 for sign in left_signs) == 3
    assert sum(sign < 0 for sign in right_signs) == 4
    assert sum(sign > 0 for sign in right_signs) == 2
    assert _posts_pole(left) == 0
    assert _posts_pole(right) == 0
    assert posts_share_stance(left, right) is False
    assert _refused(data) == []


def test_u003_influence_has_no_pole_so_the_split_stays():
    """Israel Condemned holds a condemn pole. Israel Influence does not.

    Four endorse posts and two condemn posts out of 36 do not hold a side.
    A face with no pole is not evidence the two agree.
    """
    from pipeline.stance import _posts_pole, posts_share_stance

    data = _load("u003")
    left, right = _posts(data["posts_a"]), _posts(data["posts_b"])
    assert _posts_pole(left) == -1
    assert _posts_pole(right) == 0
    assert posts_share_stance(left, right) is False
    assert _refused(data) == []


def test_u005_same_sign_on_different_actors_is_not_the_same_stance():
    """Both faces condemn, and they condemn different actors.

    Israel Condemned attaches the condemn cues to Israel. Israel Defends
    attaches them to Hamas ("Hamas ... killed", against two posts that clear
    the pole). Quoted "Israel condemns violence" is not the speaker. The
    same sign on disjoint named actors is not positive evidence of one
    stance, so the split stays.
    """
    from pipeline.stance import _pole_actors, _posts_pole, posts_share_stance

    data = _load("u005")
    left, right = _posts(data["posts_a"]), _posts(data["posts_b"])
    assert _posts_pole(left) == -1
    assert _posts_pole(right) == -1
    assert _pole_actors(left, -1) == {"israel"}
    assert _pole_actors(right, -1) == {"hamas"}
    assert posts_share_stance(left, right) is False
    assert _refused(data) == []


def test_u005_choose_n_faces_keeps_both_faces():
    from pipeline.perspectives import choose_n_faces

    data = _load("u005")
    texts, _labels, matrix = _at_cosine(data["posts_a"], data["posts_b"])
    assert choose_n_faces(texts, seed=0, matrix=matrix) == 2


@pytest.mark.parametrize("pair_id", ["u001", "u002", "u003", "u005"])
def test_fixture_pair_is_kept(pair_id: str):
    from pipeline.perspectives import choose_n_faces

    data = _load(pair_id)
    texts, _labels, matrix = _at_cosine(data["posts_a"], data["posts_b"])
    assert choose_n_faces(texts, seed=0, matrix=matrix) == 2
    assert _refused(data) == []
