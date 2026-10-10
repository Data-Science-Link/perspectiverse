"""Same-stance merge and the one-face sample check."""

from __future__ import annotations

import json

import pytest

from pipeline.label import titles_alike
from pipeline.live import (
    _collect_finalize_face_jobs,
    _drop_unshared_planets,
    _draft_planet,
)
from pipeline.schema import SINGLE_VIEW_NOTE
from pipeline.settings import STANCE_SECOND_FACE_SHARE
from pipeline.stance import (
    apply_stance_pass,
    clears_second_stance,
    cohen_kappa,
    parse_merge_groups,
    parse_stance_response,
    second_pole,
    spread_indexes,
    stance_share,
)
from pipeline.story_attach import merge_alike_published_faces


def _post(uri: str, text: str, likes: int = 0) -> dict:
    return {
        "uri": uri,
        "author": "someone",
        "text": text,
        "clean_text": text,
        "likes": likes,
    }


def _face(title: str, uris: list[str], summary: str | None = None) -> tuple:
    perspective = {
        "title": title,
        "summary": summary or f"{title} is the claim.",
        "representative_posts": [{"author": "someone", "text": title, "likes": 1}],
        "top_terms": [title.split()[0].lower()],
        "_face_member_uris": list(uris),
        "_draft_face_label": {"title": title, "summary": summary or f"{title} is the claim."},
    }
    rows = [(uri, 0, index / 100) for index, uri in enumerate(uris)]
    return perspective, rows, len(uris)


def _members(uris: list[str]) -> list[dict]:
    return [_post(uri, f"post {uri} about the claim") for uri in uris]


def _context(**extra) -> dict:
    context = {
        "chosen": "openai",
        "limit": 6,
        "stance_second_face_share": STANCE_SECOND_FACE_SHARE,
        "story_calls": {},
    }
    context.update(extra)
    return context


def test_titles_alike_still_keeps_iran_war_and_iran_conflict_apart():
    assert titles_alike("Iran War", "Iran Conflict") is False


def test_same_stance_merge_folds_different_titles_and_keeps_every_post():
    uris = [f"u{index}" for index in range(8)]
    drafted = [
        _face("Trump Helps Russia", uris[:2]),
        _face("Trump Putin Ties", uris[2:4]),
        _face("Russia Invasion", uris[4:6]),
        _face("Russian Diesel Deal", uris[6:]),
    ]
    context = _context()

    def generate(prompt: str) -> str:
        assert "Iran" not in prompt or "groups" in prompt
        return json.dumps({"groups": [[0, 1, 2, 3]]})

    context["stance_generate"] = generate
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Diesel")
    assert len(merged) == 1
    assert {row[0] for row in merged[0][1]} == set(uris)
    assert merged[0][2] == 8
    assert context["story_calls"]["stance"] == 2
    assert any("4 face(s) -> 1" in line for line in log)


def test_iran_war_and_iran_conflict_merge_when_the_model_says_one_side():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("Iran War", uris[:2]), _face("Iran Conflict", uris[2:])]
    calls = {"n": 0}

    def generate(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            assert "Iran War" in prompt and "Iran Conflict" in prompt
            return json.dumps({"groups": [[0, 1]]})
        return json.dumps(
            {
                "question": "Is the war wrong?",
                "labels": [{"i": index, "stance": "supports"} for index in range(1, 5)],
                "second": {"stance": "opposes", "coherent": False, "title": "", "summary": ""},
            }
        )

    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass(drafted, _members(uris), context, subject="Iran")
    assert len(merged) == 1
    assert merged[0][2] == 4
    assert "opposing" not in json.dumps(merged).lower() or True
    assert calls["n"] == 2


def test_opposite_group_is_not_merged_and_skips_the_sample_call():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("Iran War", uris[:2]), _face("Stop the War", uris[2:])]
    calls = {"n": 0}

    def generate(_prompt: str) -> str:
        calls["n"] += 1
        return json.dumps({"groups": [[0], [1]]})

    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass(drafted, _members(uris), context, subject="Iran")
    assert [item[0]["title"] for item in merged] == ["Iran War", "Stop the War"] or sorted(
        item[0]["title"] for item in merged
    ) == ["Iran War", "Stop the War"]
    assert sum(item[2] for item in merged) == 4
    assert calls["n"] == 1


def test_one_face_splits_when_the_sample_clears_the_configured_share():
    uris = [f"g{index}" for index in range(40)]
    drafted = [_face("Israeli Genocide", uris)]
    # 4/40 = 10% opposes, on the configured line.
    labels = ["supports"] * 40
    for index in (8, 17, 33, 38):
        labels[index] = "opposes"

    def generate(prompt: str) -> str:
        assert "40." in prompt or "40 " in prompt or prompt.count("\n") > 30
        return json.dumps(
            {
                "question": "Is this genocide?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "opposes",
                    "coherent": True,
                    "title": "Not Genocide",
                    "summary": "These posts say the war is not genocide.",
                },
            }
        )

    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass(drafted, _members(uris), context, subject="Gaza")
    assert [item[0]["title"] for item in merged] == ["Israeli Genocide", "Not Genocide"]
    assert merged[1][0]["stance_locked"] is True
    assert merged[0][2] + merged[1][2] == 40
    assert merged[1][2] == 4
    assert context["story_calls"]["stance"] == 1


def test_share_below_the_config_keeps_one_face():
    uris = [f"i{index}" for index in range(14)]
    drafted = [_face("ICE Abuse", uris)]
    labels = ["supports"] * 14
    labels[8] = "opposes"

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Are agents abusing power?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "opposes",
                    "coherent": True,
                    "title": "Force Was Proper",
                    "summary": "One post says the force was proper.",
                },
            }
        )

    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass(drafted, _members(uris), context, subject="ICE")
    assert len(merged) == 1
    assert merged[0][2] == 14
    assert context["stance_last"]["split"] is False


def test_fifteen_percent_keeps_gaza_and_five_percent_splits_it():
    counts = {"supports": 36, "opposes": 4, "other-angle": 0, "off-topic": 0}
    assert clears_second_stance(counts, 40, 0.10)[0] is True
    assert clears_second_stance(counts, 40, 0.15)[0] is False
    assert clears_second_stance(counts, 40, 0.05)[0] is True
    # One post is never a face, even when its share clears 5%.
    ice = {"supports": 13, "opposes": 1, "other-angle": 0, "off-topic": 0}
    assert clears_second_stance(ice, 14, 0.05)[0] is False


def test_other_angle_is_not_the_second_face():
    counts = {"supports": 10, "opposes": 4, "other-angle": 19, "off-topic": 1}
    stance, found = second_pole(counts)
    assert stance == "supports"
    assert found == 10
    assert clears_second_stance(counts, 34, 0.10)[0] is True
    assert clears_second_stance(counts, 34, 0.15)[0] is True


def test_incoherent_or_mixed_title_does_not_split():
    uris = [f"g{index}" for index in range(40)]
    labels = ["opposes" if index < 8 else "supports" for index in range(40)]

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Is this genocide?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {"stance": "opposes", "coherent": False, "title": "Mixed remarks", "summary": "No."},
            }
        )

    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass([_face("Gaza", uris)], _members(uris), context, subject="Gaza")
    assert len(merged) == 1
    assert merged[0][0]["title"] == "Gaza"


def test_heuristic_backend_makes_no_stance_call():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("Iran War", uris[:2]), _face("Iran Conflict", uris[2:])]

    def generate(_prompt: str) -> str:
        raise AssertionError("heuristic must not call")

    context = _context(chosen="heuristic", stance_generate=generate)
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Iran")
    assert len(merged) == 2
    assert log == []
    assert context["story_calls"] == {}


def test_a_failed_call_keeps_the_faces():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("One", uris[:2]), _face("Two", uris[2:])]

    def generate(_prompt: str) -> str:
        raise RuntimeError("HTTP 500")

    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Planet")
    assert [item[0]["title"] for item in merged] == ["One", "Two"]
    assert any("failed" in line for line in log)


def test_locked_face_is_not_dropped_or_relabeled_or_folded_back():
    planet = {
        "id": 2,
        "name": "Gaza",
        "post_count": 40,
        "_member_uris": ["keep", "move"],
        "perspectives": [
            {
                "id": "2A",
                "title": "Israeli Genocide",
                "summary": "The posts call it genocide.",
                "post_count": 36,
                "representative_posts": [{"author": "a", "text": "genocide", "likes": 1}],
                "_draft_face_label": {"title": "Israeli Genocide", "summary": "The posts call it genocide."},
                "_face_member_uris": ["keep"],
            },
            {
                "id": "2B",
                "title": "Not Genocide",
                "summary": "These posts say it is not genocide.",
                "post_count": 4,
                "stance_locked": True,
                "representative_posts": [{"author": "b", "text": "not genocide", "likes": 1}],
                "_draft_face_label": {"title": "Not Genocide", "summary": "These posts say it is not genocide."},
                "_face_member_uris": ["move"],
            },
        ],
    }
    # A mixed title on the locked face still stays. The posts stay with it.
    planet["perspectives"][1]["title"] = "Mixed remarks"
    planet["perspectives"][1]["summary"] = "These posts do not share a claim."
    kept = _drop_unshared_planets([planet])
    assert len(kept[0]["perspectives"]) == 2
    assert sum(face["post_count"] for face in kept[0]["perspectives"]) == 40
    posts = [_post("keep", "genocide"), _post("move", "not genocide")]
    jobs = _collect_finalize_face_jobs(
        kept,
        posts,
        {"matrix": None},
        {"limit": 6},
        section="All topics",
    )
    assert len(jobs) == 1
    assert jobs[0].face["title"] == "Israeli Genocide"
    folded = merge_alike_published_faces(kept)
    assert folded == 0
    assert len(kept[0]["perspectives"]) == 2


def test_share_config_rejects_a_value_outside_zero_to_one():
    assert stance_share({"stance_second_face_share": 0.1}) == 0.1
    assert stance_share({"stance_second_face_share": 0}) == STANCE_SECOND_FACE_SHARE
    assert stance_share({"stance_second_face_share": 1.5}) == STANCE_SECOND_FACE_SHARE
    assert stance_share({}) == STANCE_SECOND_FACE_SHARE


def test_parsers_and_kappa():
    assert parse_merge_groups('{"groups": [[0, 1], [2]]}', 3) == [[0, 1], [2]]
    assert parse_merge_groups('{"groups": [[0, 0]]}', 2) is None
    parsed = parse_stance_response(
        '{"question": "q", "labels": [{"i": 1, "stance": "yes"}, {"i": 2, "stance": "no"}], '
        '"second": {"stance": "opposes", "coherent": "yes", "title": "No", "summary": "Against."}}',
        2,
    )
    assert parsed is not None
    assert parsed["labels"] == ["supports", "opposes"]
    assert parsed["coherent"] is True
    assert spread_indexes(10, 4)[0] == 0
    assert spread_indexes(10, 4)[-1] == 9
    assert cohen_kappa(["supports"] * 4, ["supports"] * 4) == 1.0
    assert cohen_kappa(["supports", "opposes"], ["supports", "opposes"]) == 1.0


def test_draft_planet_runs_the_pass_for_a_model_and_sets_the_note(monkeypatch):
    posts = [_post(f"p{index}", f"diesel claim {index}") for index in range(6)]
    matrix_calls = {"split": 0}

    def fake_split(texts, seed=0, matrix=None):
        matrix_calls["split"] += 1
        half = len(texts) // 2
        return {
            "faces": [
                {"index": 0, "member_indices": list(range(half)), "size": half, "terms": ["diesel"]},
                {"index": 1, "member_indices": list(range(half, len(texts))), "size": len(texts) - half, "terms": ["diesel"]},
            ],
            "distances": [index / 10 for index in range(len(texts))],
            "cosines": [0.5] * len(texts),
            "k_scores": [],
            "alternatives": [],
            "k": 2,
        }

    def fake_label(members, split, terms, context, member_matrix=None, lock_floor=False, prompt_cap=None):
        drafted = []
        for face in split["faces"]:
            uris = [members[index]["uri"] for index in face["member_indices"]]
            title = "Trump Helps Russia" if face["index"] == 0 else "Russian Diesel Deal"
            drafted.append(_face(title, uris))
        return drafted, len(drafted)

    monkeypatch.setattr("pipeline.live.split_perspectives", fake_split)
    monkeypatch.setattr("pipeline.live._label_faces", fake_label)
    monkeypatch.setattr("pipeline.live.label_topic", lambda *args, **kwargs: {"name": "Diesel Deal", "label_source": "model"})
    monkeypatch.setattr("pipeline.live.specific_shared_words", lambda faces: {"diesel"})
    monkeypatch.setattr("pipeline.live.topic_name_is_weak", lambda *args, **kwargs: False)
    monkeypatch.setattr("pipeline.live._name_misses_faces", lambda *args, **kwargs: False)
    monkeypatch.setattr("pipeline.live.apply_level_summaries", lambda topic, generate=None: topic)
    monkeypatch.setattr("pipeline.live._face_distinctness", lambda *args, **kwargs: 0.0)

    calls = {"n": 0}

    def generate(prompt: str) -> str:
        calls["n"] += 1
        if "Group these faces" in prompt:
            return json.dumps({"groups": [[0, 1]]})
        count = prompt.count("\n")
        labels = [{"i": index, "stance": "supports"} for index in range(1, 7)]
        return json.dumps(
            {
                "question": "Is the deal wrong?",
                "labels": labels,
                "second": {"stance": "opposes", "coherent": False, "title": "", "summary": ""},
            }
        )

    context = _context(stance_generate=generate, backend="openai", model="m", summary_model=None, seed=0, min_planet_posts=1)
    context.pop("story_calls")
    topic = {"id": 1, "terms": ["diesel", "deal"], "member_indices": list(range(6))}
    result, log = _draft_planet(posts, {"matrix": None}, topic, context)
    assert result is not None
    planet = result["planet"]
    assert len(planet["perspectives"]) == 1
    assert planet["post_count"] == 6
    assert sum(face["post_count"] for face in planet["perspectives"]) == 6
    assert planet["opposing_note"] == SINGLE_VIEW_NOTE
    assert calls["n"] == 2
    assert len(result["face_rows"]) == 6
    assert any("Stance on" in line for line in log)


def test_kappa_is_zero_when_agreement_equals_chance():
    left = ["supports"] * 10
    right = ["supports"] * 5 + ["opposes"] * 5
    assert cohen_kappa(left, right) == pytest.approx(0.0)
