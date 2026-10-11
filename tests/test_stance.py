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
from pipeline.schema import (
    SINGLE_VIEW_NOTE,
    STANCE_CHECK_FAILED,
    STANCE_CHECK_INCOHERENT,
    _check_stance_check,
    apply_opposing_note,
)
from pipeline.settings import STANCE_SECOND_FACE_SHARE
from pipeline.stance import (
    apply_stance_pass,
    clears_second_stance,
    cohen_kappa,
    explain_stance_failure,
    parse_merge_groups,
    parse_stance_response,
    report_stance_check_failures,
    report_stance_check_incoherent,
    reset_stance_check_failures,
    stance_check_incoherent,
    sample_limit,
    sample_rows,
    second_pole,
    spread_indexes,
    stance_check_failures,
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
        if "\"groups\"" in prompt or "groups" in prompt and "labels" not in prompt:
            return json.dumps({"groups": [[0, 1, 2, 3]]})
        return json.dumps(
            {
                "question": "Is the deal wrong?",
                "labels": [{"i": index, "stance": "supports"} for index in range(1, 9)],
                "second": {"stance": "opposes", "coherent": False, "title": "", "summary": ""},
            }
        )

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


@pytest.mark.parametrize(
    ("coherent", "title"),
    [
        (False, "Not Genocide"),
        (False, "Mixed remarks"),
        (False, ""),
        (True, "Mixed remarks"),
        (True, ""),
    ],
)
def test_above_threshold_without_one_claim_keeps_pre_pass_faces(coherent, title):
    uris = [f"g{index}" for index in range(40)]
    labels = ["opposes" if index < 8 else "supports" for index in range(40)]

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Is this genocide?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {"stance": "opposes", "coherent": coherent, "title": title, "summary": "No."},
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass([_face("Gaza", uris)], _members(uris), context, subject="Gaza")
    assert [item[0]["title"] for item in merged] == ["Gaza"]
    assert context.get("stance_check_incoherent") is True
    assert context.get("stance_check_failed") is not True
    assert context["stance_last"]["blocked"] is True
    assert context["stance_last"]["split"] is False
    assert "Second side not coherent" in " ".join(log)
    assert "Pre-pass faces kept (1)" in " ".join(log)
    assert stance_check_incoherent() == 1
    assert stance_check_failures() == 0
    topic = {"perspectives": [{"title": "Gaza"}], "stance_check": STANCE_CHECK_INCOHERENT, "opposing_note": SINGLE_VIEW_NOTE}
    apply_opposing_note(topic)
    assert "opposing_note" not in topic
    _check_stance_check({"stance_check": STANCE_CHECK_INCOHERENT}, "planet")
    with pytest.raises(ValueError, match="opposing_note"):
        _check_stance_check({"stance_check": STANCE_CHECK_INCOHERENT, "opposing_note": SINGLE_VIEW_NOTE}, "planet")


def test_incoherent_second_side_undoes_a_same_stance_merge():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("Iran War", uris[:2]), _face("Trump Invites Attack", uris[2:])]
    labels = ["supports", "supports", "opposes", "opposes"]

    def generate(prompt: str) -> str:
        if "Group these faces" in prompt:
            return json.dumps({"groups": [[0, 1]]})
        return json.dumps(
            {
                "question": "Is there a war?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {"stance": "opposes", "coherent": False, "title": "No War", "summary": "Against."},
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Trump Iran War")
    assert [item[0]["title"] for item in merged] == ["Iran War", "Trump Invites Attack"]
    assert context.get("stance_check_incoherent") is True
    assert context.get("stance_check_failed") is not True
    assert "Pre-pass faces kept (2)" in " ".join(log)
    assert stance_check_incoherent() == 1
    assert report_stance_check_incoherent() == 1


def test_a_below_threshold_side_stays_one_face_even_when_incoherent():
    uris = [f"i{index}" for index in range(14)]
    labels = ["supports"] * 14
    labels[8] = "opposes"

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Are agents abusing power?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {"stance": "opposes", "coherent": False, "title": "", "summary": ""},
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass([_face("ICE Abuse", uris)], _members(uris), context, subject="ICE")
    assert len(merged) == 1
    assert context.get("stance_check_incoherent") is not True
    assert context["stance_last"]["blocked"] is False
    assert stance_check_incoherent() == 0
    assert any("1 face(s) -> 1" in line for line in log)


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


# No Men, 11 Oct 2026, temperature 0. Valid JSON, three labels of a 40-post sample.
NO_MEN_PARTIAL = (
    '{"question": "Should men be allowed in women\'s sports?", '
    '"labels": [{"i": 1, "stance": "opposes"}, {"i": 3, "stance": "opposes"}, '
    '{"i": 14, "stance": "supports"}], '
    '"second": {"stance": "opposes", "coherent": true, "title": "No Men", '
    '"summary": "Most posts argue that men should not be allowed in women\'s sports, '
    'citing concerns about fairness, safety, and women\'s rights."}}'
)


def test_no_men_partial_labels_are_a_schema_mismatch():
    assert parse_stance_response(NO_MEN_PARTIAL, 40) is None
    assert (
        explain_stance_failure(NO_MEN_PARTIAL, None, kind="sample", count=40)
        == "schema mismatch: labels cover 3 of 40"
    )


def test_a_partial_reply_retries_once_and_then_keeps_the_faces():
    uris = [f"n{index}" for index in range(40)]
    drafted = [_face("Women's Rights", uris)]
    calls = {"n": 0, "seeds": []}

    def generate(prompt: str, seed: int | None = None) -> str:
        calls["n"] += 1
        calls["seeds"].append(seed)
        return NO_MEN_PARTIAL

    context = _context(stance_generate=generate)
    before = stance_check_failures()
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="No Men")
    assert [item[0]["title"] for item in merged] == ["Women's Rights"]
    assert calls["n"] == 2
    assert calls["seeds"] == [0, 1]
    assert context.get("stance_check_failed") is True
    assert "labels cover 3 of 40" in " ".join(log)
    assert "Pre-pass faces kept (1)" in " ".join(log)
    assert stance_check_failures() == before + 1


def test_a_failed_sample_after_a_merge_restores_the_pre_pass_faces():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("Iran War", uris[:2]), _face("Trump Invites Attack", uris[2:])]

    def generate(prompt: str, seed: int | None = None) -> str:
        del seed
        if "Group these faces" in prompt:
            return json.dumps({"groups": [[0, 1]]})
        raise RuntimeError("HTTP 500")

    context = _context(stance_generate=generate)
    before = stance_check_failures()
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Trump Iran War")
    assert [item[0]["title"] for item in merged] == ["Iran War", "Trump Invites Attack"]
    assert context.get("stance_check_failed") is True
    assert "Pre-pass faces kept (2)" in " ".join(log)
    assert "HTTP error" in " ".join(log)
    assert stance_check_failures() == before + 1


def test_a_failed_call_keeps_the_faces():
    uris = ["a", "b", "c", "d"]
    drafted = [_face("One", uris[:2]), _face("Two", uris[2:])]

    def generate(_prompt: str) -> str:
        raise RuntimeError("HTTP 500")

    context = _context(stance_generate=generate)
    before = stance_check_failures()
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Planet")
    assert [item[0]["title"] for item in merged] == ["One", "Two"]
    assert any("failed" in line for line in log)
    assert context.get("stance_check_failed") is True
    assert stance_check_failures() == before + 1


def test_folding_a_failed_check_does_not_add_the_opposing_note():
    topic = {
        "id": 1,
        "name": "Gaza",
        "stance_check": STANCE_CHECK_FAILED,
        "perspectives": [
            {
                "id": "1A",
                "title": "Israeli Genocide",
                "summary": "The posts call the war genocide.",
                "post_count": 4,
                "representative_posts": [{"author": "a", "text": "This is genocide.", "likes": 1}],
            },
            {
                "id": "1B",
                "title": "Israeli Genocide",
                "summary": "The posts call the war genocide.",
                "post_count": 2,
                "representative_posts": [{"author": "b", "text": "This is genocide too.", "likes": 1}],
            },
        ],
    }
    assert merge_alike_published_faces([topic]) == 1
    assert len(topic["perspectives"]) == 1
    assert "opposing_note" not in topic
    assert topic["stance_check"] == STANCE_CHECK_FAILED


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


def test_sample_grows_to_100_once_the_planet_reaches_100_posts():
    assert sample_limit(14) == 40
    assert sample_limit(99) == 40
    assert sample_limit(100) == 100
    assert sample_limit(210) == 100
    small = sample_rows([(f"s{index}", 0, index) for index in range(34)])
    assert len(small) == 34
    mid = sample_rows([(f"m{index}", 0, index) for index in range(83)])
    assert len(mid) == 40
    assert mid[0][0] == "m0"
    assert mid[-1][0] == "m82"
    large = sample_rows([(f"g{index}", 0, index) for index in range(210)])
    assert len(large) == 100
    assert large[0][0] == "g0"
    assert large[-1][0] == "g209"
    shifted = sample_rows([(f"m{index}", 0, index) for index in range(83)], seed=1)
    repeated = sample_rows([(f"m{index}", 0, index) for index in range(83)], seed=1)
    assert [row[0] for row in shifted] == [row[0] for row in repeated]
    assert [row[0] for row in shifted] != [row[0] for row in mid]
    assert len(shifted) == 40
    whole = [(f"t{index}", 0, index) for index in range(9)]
    assert [row[0] for row in sample_rows(whole, seed=1)] == [row[0] for row in sample_rows(whole, seed=3)]


def test_share_config_rejects_a_value_outside_zero_to_one():
    assert STANCE_SECOND_FACE_SHARE == 0.10
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


def test_a_short_sample_is_not_a_failed_stance_check():
    uris = ["only"]
    drafted = [_face("Tiny", uris)]

    def generate(_prompt: str) -> str:
        raise AssertionError("a one-post planet is not sent")

    context = _context(stance_generate=generate)
    before = stance_check_failures()
    merged, log = apply_stance_pass(drafted, _members(uris), context, subject="Tiny")
    assert len(merged) == 1
    assert context.get("stance_check_failed") is not True
    assert stance_check_failures() == before
    assert any("fewer than" in line for line in log)


@pytest.mark.parametrize("kind", ["timeout", "http", "unparseable"])
def test_failed_stance_check_skips_the_opposing_note_and_counts(monkeypatch, kind, capsys):
    posts = [_post(f"p{index}", f"gaza claim {index}") for index in range(6)]

    def fake_split(texts, seed=0, matrix=None):
        return {
            "faces": [
                {"index": 0, "member_indices": list(range(len(texts))), "size": len(texts), "terms": ["gaza"]},
            ],
            "distances": [index / 10 for index in range(len(texts))],
            "cosines": [0.5] * len(texts),
            "k_scores": [],
            "alternatives": [],
            "k": 1,
        }

    def fake_label(members, split, terms, context, member_matrix=None, lock_floor=False, prompt_cap=None):
        uris = [members[index]["uri"] for index in split["faces"][0]["member_indices"]]
        return [_face("Israeli Genocide", uris)], 1

    def generate(_prompt: str) -> str:
        if kind == "timeout":
            raise TimeoutError("timed out")
        if kind == "http":
            raise RuntimeError("HTTP 500")
        return "not json"

    monkeypatch.setattr("pipeline.live.split_perspectives", fake_split)
    monkeypatch.setattr("pipeline.live._label_faces", fake_label)
    monkeypatch.setattr("pipeline.live.label_topic", lambda *args, **kwargs: {"name": "Gaza", "label_source": "model"})
    monkeypatch.setattr("pipeline.live.specific_shared_words", lambda faces: {"gaza"})
    monkeypatch.setattr("pipeline.live.topic_name_is_weak", lambda *args, **kwargs: False)
    monkeypatch.setattr("pipeline.live._name_misses_faces", lambda *args, **kwargs: False)
    monkeypatch.setattr("pipeline.live.apply_level_summaries", lambda topic, generate=None: topic)
    monkeypatch.setattr("pipeline.live._face_distinctness", lambda *args, **kwargs: 0.0)

    reset_stance_check_failures()
    context = _context(stance_generate=generate, backend="openai", model="m", summary_model=None, seed=0, min_planet_posts=1)
    context.pop("story_calls")
    topic = {"id": 1, "terms": ["gaza"], "member_indices": list(range(6))}
    result, log = _draft_planet(posts, {"matrix": None}, topic, context)
    assert result is not None
    planet = result["planet"]
    assert len(planet["perspectives"]) == 1
    assert planet["post_count"] == 6
    assert planet["perspectives"][0]["title"] == "Israeli Genocide"
    assert "opposing_note" not in planet
    assert SINGLE_VIEW_NOTE not in json.dumps(planet)
    assert planet["stance_check"] == STANCE_CHECK_FAILED
    assert stance_check_failures() == 1
    assert any("the call failed" in line for line in log)
    kept = _drop_unshared_planets([planet])
    assert kept[0]["stance_check"] == STANCE_CHECK_FAILED
    assert "opposing_note" not in kept[0]
    folded = merge_alike_published_faces(kept)
    assert folded == 0
    assert "opposing_note" not in kept[0]
    assert report_stance_check_failures() == 1
    assert "Stance check failed: 1 planet(s)" in capsys.readouterr().err


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
        labels = [{"i": index, "stance": "opposes" if index <= 2 else "supports"} for index in range(1, 7)]
        return json.dumps(
            {
                "question": "Is the deal wrong?",
                "labels": labels,
                "second": {"stance": "opposes", "coherent": False, "title": "", "summary": ""},
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate, backend="openai", model="m", summary_model=None, seed=0, min_planet_posts=1)
    context.pop("story_calls")
    topic = {"id": 1, "terms": ["diesel", "deal"], "member_indices": list(range(6))}
    result, log = _draft_planet(posts, {"matrix": None}, topic, context)
    assert result is not None
    planet = result["planet"]
    assert [face["title"] for face in planet["perspectives"]] == ["Trump Helps Russia", "Russian Diesel Deal"]
    assert planet["post_count"] == 6
    assert sum(face["post_count"] for face in planet["perspectives"]) == 6
    assert "opposing_note" not in planet
    assert SINGLE_VIEW_NOTE not in json.dumps(planet)
    assert planet["stance_check"] == STANCE_CHECK_INCOHERENT
    assert calls["n"] == 2
    assert len(result["face_rows"]) == 6
    assert any("Second side not coherent" in line for line in log)
    assert any("Pre-pass faces kept (2)" in line for line in log)
    assert stance_check_incoherent() == 1
    assert stance_check_failures() == 0


def test_the_first_stance_call_uses_the_pipeline_seed():
    uris = [f"n{index}" for index in range(6)]
    calls = {"seeds": []}

    def generate(prompt: str, seed: int | None = None) -> str:
        calls["seeds"].append(seed)
        return NO_MEN_PARTIAL

    context = _context(stance_generate=generate, seed=7)
    apply_stance_pass([_face("Women's Rights", uris)], _members(uris), context, subject="No Men")
    assert calls["seeds"] == [7, 8]


def test_kappa_is_zero_when_agreement_equals_chance():
    left = ["supports"] * 10
    right = ["supports"] * 5 + ["opposes"] * 5
    assert cohen_kappa(left, right) == pytest.approx(0.0)
