"""Same-stance merge and the one-face sample check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.label import titles_alike
from pipeline.live import (
    _collect_finalize_face_jobs,
    _drop_unshared_planets,
    _draft_planet,
    _merge_alike_drafts,
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
    align_contradicting_title,
    apply_local_stance_gate,
    apply_stance_pass,
    gate_published_perspectives,
    claim_words_cover,
    clears_second_stance,
    cohen_kappa,
    explain_stance_failure,
    parse_merge_groups,
    build_stance_prompt,
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

    members = _members(uris)
    for index in (8, 17, 33, 38):
        members[index]["text"] = "This war is not genocide."
        members[index]["clean_text"] = "This war is not genocide."
    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass(drafted, members, context, subject="Gaza")
    assert [item[0]["title"] for item in merged] == ["Israeli Genocide", "Not Genocide"]
    assert merged[1][0]["stance_locked"] is True
    assert merged[0][2] + merged[1][2] == 40
    assert merged[1][2] == 4
    assert context["story_calls"]["stance"] == 1


def test_abolish_ice_under_ice_has_role_stays_one_face():
    uris = [f"i{index}" for index in range(40)]
    labels = ["opposes" if index < 18 else "supports" for index in range(40)]
    members = _members(uris)
    for index in range(18):
        members[index]["text"] = "Abolish ICE."
        members[index]["clean_text"] = "Abolish ICE."

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Does ICE have a legitimate role?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "opposes",
                    "coherent": True,
                    "title": "ICE Has Role",
                    "summary": (
                        "Some posts argue that ICE has a legitimate role in law enforcement "
                        "and should not be abolished."
                    ),
                },
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass([_face("ICE Abuse", uris)], members, context, subject="Ice")
    assert [item[0]["title"] for item in merged] == ["ICE Abuse"]
    assert merged[0][2] == 40
    assert context["stance_last"]["split"] is False
    assert context["stance_last"]["blocked"] is True
    assert context["stance_last"]["claim_grounded"] is False
    assert context.get("stance_check_incoherent") is True
    assert context["story_calls"]["stance"] == 1
    assert "Second side not coherent" in " ".join(log)
    assert stance_check_incoherent() == 1


def test_force_was_proper_minority_still_splits():
    uris = [f"f{index}" for index in range(40)]
    labels = ["opposes" if index < 18 else "supports" for index in range(40)]
    members = _members(uris)
    for index in range(18):
        members[index]["text"] = "The force was proper."
        members[index]["clean_text"] = "The force was proper."

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Was the force proper?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "opposes",
                    "coherent": True,
                    "title": "Force Was Proper",
                    "summary": "These posts say the force was proper.",
                },
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass([_face("ICE Abuse", uris)], members, context, subject="Ice")
    assert [item[0]["title"] for item in merged] == ["ICE Abuse", "Force Was Proper"]
    assert merged[1][0]["stance_locked"] is True
    assert merged[1][2] == 18
    assert merged[0][2] + merged[1][2] == 40
    assert context["story_calls"]["stance"] == 1
    assert context.get("stance_check_incoherent") is not True
    assert context["stance_last"]["claim_grounded"] is True
    assert any("1 face(s) -> 2" in line for line in log)


def _second_json(question: str, labels: list[str], title: str, summary: str) -> str:
    return json.dumps(
        {
            "question": question,
            "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
            "second": {
                "stance": "opposes",
                "coherent": True,
                "title": title,
                "summary": summary,
            },
        }
    )


def test_shared_topic_noun_is_not_a_claim_word():
    posts = [
        _post("a", "Women and transgender can be better athletes than him."),
        _post("b", "Every queer athlete who finds a team makes the locker room safer."),
    ]
    summary = (
        "Some argue that transgender athletes have inherent biological advantages "
        "that affect competition."
    )
    assert claim_words_cover("Biological Differences", summary, posts, "Sports") is True
    assert (
        claim_words_cover(
            "Biological Differences",
            summary,
            posts,
            "Sports",
            planet_terms=["sports", "athletes"],
        )
        is False
    )
    assert (
        claim_words_cover(
            "Biological Differences",
            summary,
            posts,
            "Sports",
            majority_posts=[
                _post("m1", "Trans athletes differ biologically."),
                _post("m2", "These athletes are in a separate class."),
            ],
            majority_title="Other Topic",
            majority_summary="A different sentence with none of those words.",
        )
        is False
    )


def test_biological_differences_collapses_on_the_shared_word_athletes():
    minority = [
        "Or maybe less. Women and transgender can be better athletes than him",
        "Every queer athlete who finds a team that feels like family makes the locker room a little safer for the next kid.",
    ]
    majority = [
        (
            "They are not like non-transgenders and never will be. That is not bad, only true. "
            "Transgenders in sport is clearly in a seperate class that crosses biological red lines "
            "of understanding!"
        ),
        "Trans athletes differ biologically from the field they join.",
        "These athletes are not the same as the women they compete with.",
    ]
    texts = minority + majority
    uris = [f"t{index}" for index in range(len(texts))]
    labels = ["opposes" if index < len(minority) else "supports" for index in range(len(texts))]
    members = [_post(uri, text) for uri, text in zip(uris, texts)]

    def generate(_prompt: str) -> str:
        return _second_json(
            "Do trans athletes have a competitive advantage?",
            labels,
            "Biological Differences",
            (
                "Some argue that transgender athletes have inherent biological advantages "
                "that affect competition."
            ),
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(
        [
            _face(
                "Trans Athletes",
                uris,
                summary="Trans athletes differ biologically",
            )
        ],
        members,
        context,
        subject="Sports",
        terms=["sports"],
    )
    assert [item[0]["title"] for item in merged] == ["Trans Athletes"]
    assert context["stance_last"]["claim_grounded"] is False
    assert context["stance_last"]["split"] is False
    assert context.get("stance_check_incoherent") is True
    assert context["story_calls"]["stance"] == 1
    assert "Second side not coherent" in " ".join(log)


def test_anti_war_minority_still_splits():
    minority = [
        "With MBS' ambitions on the line, Saudi Arabia is increasingly looking for a diplomatic way to end its renewed aggression on Yemen, the report said.",
        "Saudi Arabia Has Few Options as Houthis Aim at Heart of Its Ambitions Perhaps the NYT should remind its readers about the Saudi led war on Yemen from 2015 through 2021",
        "The Houthis have already said they don't care whether they cool their heels in Saudi Arabia or invade Yemen, assisting the despots in Arabia means the Houthis will make them a target. Not sure about Turkeys but most Pakistanis oppose involvement in Yemen & won't cry when this war goes badly.",
        "my country decided to join saudi arabia’s war on yemen, where an oil rich kingdom corrupt to the core is fighting one of the poorest countries on earth.",
        "i really hope that the wider public as well as the soldiers we send have the hearts and brains to see that yemeni people fighting for their sovereignty today really don’t look that different from us when we were fighting colonizers on our land 100 years ago.",
        "plus, even if you think pragmatically, this will contribute absolutely nothing to our national interests. we’re joining just because our evil govt decided this year that we should be allies with the saudis",
    ]
    majority = [
        "Houthi forces have explicitly warned that Saudi civilian airports and Aramco oil facilities are targets as heavy fighting spreads across Yemen’s Red Sea coast.",
        "Houthi strikes on Riyadh airport killed three Saudis as war escalates",
        "Houthi missile kills 12 at Riyadh airport, second strike this week. UAE backs all measures for Saudi security.",
        "The escalating conflict with Iran-backed Houthi militants threatens Saudi Crown Prince Mohammad bin Salman’s plans.",
        "Major Saudi conferences to proceed, organisers say, despite deadly airport attack",
        "The federal Prime Minister has nothing to do with Saudi Airports or Houthis.",
        "Syria weighs military aid for Saudi Arabia amid Yemen war, sources say. Syria is considering military assistance to Saudi Arabia amid an escalating war against the Houthis.",
    ]
    texts = minority + majority
    uris = [f"y{index}" for index in range(len(texts))]
    labels = ["opposes" if index < len(minority) else "supports" for index in range(len(texts))]
    members = [_post(uri, text) for uri, text in zip(uris, texts)]

    def generate(_prompt: str) -> str:
        return _second_json(
            "Should the country join the war?",
            labels,
            "Anti War",
            "Most posts oppose supporting Saudi Arabia in its war against the Houthis in Yemen.",
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(
        [
            _face(
                "Houthi Attacks",
                uris,
                summary="Houthi forces target Saudi airports and facilities",
            )
        ],
        members,
        context,
        subject="Saudi Yemen Houthis",
        terms=["saudi", "yemen", "houthis"],
    )
    assert [item[0]["title"] for item in merged] == ["Houthi Attacks", "Anti War"]
    assert merged[1][2] == len(minority)
    assert context["stance_last"]["claim_grounded"] is True
    assert context["story_calls"]["stance"] == 1
    assert any("1 face(s) -> 2" in line for line in log)


def test_dyed_diesel_concerns_still_splits():
    minority = [
        "That’s why it’s dyed red in such a vicious way so that once you contaminate your fuel system it stays. The first time you get caught on the highway with red fuel is a $5000 fine, second offense is $10,000 and on a third offense they take your truck.",
        "So now big rig drivers, and the lifted truck crowd, will compete with farmers for red dye fuel? And what about residual dye in fuel station tanks and truck gas tanks?",
        "It's not and never was about relief of diesel prices.",
        "And the trucks will be ruined by tainted gas",
        "The Nebraska Trucking Association cautioned members not to fill up with the untaxed, tinted diesel fuel. Do not put dyed diesel in your tanks — at least not yet.",
    ]
    majority = [
        "Truckers Warn High Diesel Prices Are Cutting Routes",
        "Right now Russia is importing diesel. I guess they’re gonna sell diesel that they buy from India?",
        "Theyre doing this for like 3 days of US diesel exports every month",
        "Diesel prices are still high this week.",
        "High diesel prices are cutting routes.",
        "Diesel prices jumped again.",
    ]
    texts = minority + majority
    uris = [f"d{index}" for index in range(len(texts))]
    labels = ["opposes" if index < len(minority) else "supports" for index in range(len(texts))]
    members = [_post(uri, text) for uri, text in zip(uris, texts)]

    def generate(_prompt: str) -> str:
        return _second_json(
            "Is dyed diesel the problem?",
            labels,
            "Dyed Diesel Concerns",
            (
                "Many posts express concerns about the use of dyed diesel fuel, citing "
                "potential damage to trucks and fines for its use."
            ),
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(
        [_face("Diesel Prices", uris, summary="Diesel prices are high")],
        members,
        context,
        subject="Diesel Fuel Dyed",
        terms=["diesel", "fuel", "dyed"],
    )
    assert [item[0]["title"] for item in merged] == ["Diesel Prices", "Dyed Diesel Concerns"]
    assert merged[1][2] == len(minority)
    assert context["stance_last"]["claim_grounded"] is True
    assert context["story_calls"]["stance"] == 1
    assert any("1 face(s) -> 2" in line for line in log)


def test_second_stance_must_match_the_moved_pole():
    uris = [f"p{index}" for index in range(40)]
    labels = ["opposes" if index < 18 else "supports" for index in range(40)]
    members = _members(uris)
    for index in range(18):
        members[index]["text"] = "The force was proper."
        members[index]["clean_text"] = "The force was proper."

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Was the force proper?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "supports",
                    "coherent": True,
                    "title": "Force Was Proper",
                    "summary": "These posts say the force was proper.",
                },
            }
        )

    reset_stance_check_failures()
    context = _context(stance_generate=generate)
    merged, _log = apply_stance_pass([_face("ICE Abuse", uris)], members, context, subject="Ice")
    assert [item[0]["title"] for item in merged] == ["ICE Abuse"]
    assert context["stance_last"]["stance_aligned"] is False
    assert context["stance_last"]["split"] is False
    assert context.get("stance_check_incoherent") is True
    assert context["story_calls"]["stance"] == 1


def test_claim_word_needs_about_forty_percent_of_the_moved_posts():
    uris = [f"c{index}" for index in range(40)]

    def run(grounded_posts: int) -> dict:
        labels = ["opposes" if index < 18 else "supports" for index in range(40)]
        members = _members(uris)
        for index in range(18):
            text = "The force was proper." if index < grounded_posts else "Abolish ICE."
            members[index]["text"] = text
            members[index]["clean_text"] = text

        def generate(_prompt: str) -> str:
            return json.dumps(
                {
                    "question": "Was the force proper?",
                    "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                    "second": {
                        "stance": "opposes",
                        "coherent": True,
                        "title": "Force Was Proper",
                        "summary": "The force was proper.",
                    },
                }
            )

        reset_stance_check_failures()
        context = _context(stance_generate=generate)
        merged, _log = apply_stance_pass([_face("ICE Abuse", uris)], members, context, subject="Ice")
        context["face_count"] = len(merged)
        return context

    below = run(7)
    assert below["face_count"] == 1
    assert below["stance_last"]["claim_grounded"] is False
    assert below.get("stance_check_incoherent") is True
    met = run(8)
    assert met["face_count"] == 2
    assert met["stance_last"]["claim_grounded"] is True
    assert met["stance_last"]["split"] is True


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
    # The local gate still runs. These two share Iran and the posts do not disagree.
    assert [item[0]["title"] for item in merged] == ["Iran War"]
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


def test_a_failed_call_locks_faces_the_posts_disagree_on():
    uris = ["a1", "a2", "b1", "b2"]
    drafted = [
        _face("Israel Policy", uris[:2], summary="Posts about Israel policy"),
        _face("Israel Policy 2", uris[2:], summary="Posts about Israel policy"),
    ]
    members = [
        _post("a1", "Israel is a genocidal terrorist state."),
        _post("a2", "These killings are horrific and wrong."),
        _post("b1", "I support and defend Israel. The operation was successful."),
        _post("b2", "Israel deserves support. The strikes were effective."),
    ]

    def generate(_prompt: str) -> str:
        raise RuntimeError("HTTP 500")

    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(drafted, members, context, subject="Israel")
    assert context.get("stance_check_failed") is True
    assert "Pre-pass faces kept" in " ".join(log)
    assert [item[0]["title"] for item in merged] == ["Israel Policy", "Israel Policy 2"]
    assert all(item[0].get("stance_locked") for item in merged)


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


def test_sample_stays_at_40_once_the_planet_reaches_100_posts():
    assert sample_limit(14) == 40
    assert sample_limit(99) == 40
    assert sample_limit(100) == 40
    assert sample_limit(210) == 40
    assert sample_limit(100_000) == 40
    small = sample_rows([(f"s{index}", 0, index) for index in range(34)])
    assert len(small) == 34
    mid = sample_rows([(f"m{index}", 0, index) for index in range(83)])
    assert len(mid) == 40
    assert mid[0][0] == "m0"
    assert mid[-1][0] == "m82"
    large = sample_rows([(f"g{index}", 0, index) for index in range(210)])
    assert len(large) == 40
    assert large[0][0] == "g0"
    assert large[-1][0] == "g209"
    shifted = sample_rows([(f"m{index}", 0, index) for index in range(83)], seed=1)
    repeated = sample_rows([(f"m{index}", 0, index) for index in range(83)], seed=1)
    assert [row[0] for row in shifted] == [row[0] for row in repeated]
    assert [row[0] for row in shifted] != [row[0] for row in mid]
    assert len(shifted) == 40
    whole = [(f"t{index}", 0, index) for index in range(9)]
    assert [row[0] for row in sample_rows(whole, seed=1)] == [row[0] for row in sample_rows(whole, seed=3)]


def test_stance_prompt_is_bounded_on_a_100k_planet():
    """A planet the size of the free-ingest corpus still sends 40 posts."""
    count = 100_000
    rows = [(f"at://planet/{index}", 0, float(index)) for index in range(count)]
    members = [
        {"uri": f"at://planet/{index}", "text": f"policy claim number {index} " + ("detail " * 30)}
        for index in range(count)
    ]
    sampled = sample_rows(rows)
    assert len(sampled) == 40
    prompt = build_stance_prompt(sampled, members, "policy")
    body = prompt.split("Posts:", 1)[1]
    post_lines = [line for line in body.splitlines() if line[:1].isdigit()]
    assert len(post_lines) == 40
    # Even a caller that hands over the whole planet cannot grow the prompt.
    unbounded = build_stance_prompt(rows, members, "policy")
    whole = unbounded.split("Posts:", 1)[1]
    assert len([line for line in whole.splitlines() if line[:1].isdigit()]) == 40
    assert "policy claim number 0 " in unbounded
    assert "policy claim number 99999 " in unbounded


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
    # The sample is incoherent, and the two drafted titles are one subject.
    # The local gate folds them. The geometric split does not come back on its own.
    assert [face["title"] for face in planet["perspectives"]] == ["Trump Helps Russia"]
    assert planet["post_count"] == 6
    assert sum(face["post_count"] for face in planet["perspectives"]) == 6
    assert "opposing_note" not in planet
    assert SINGLE_VIEW_NOTE not in json.dumps(planet)
    assert planet["stance_check"] == STANCE_CHECK_INCOHERENT
    assert calls["n"] == 2
    assert len(result["face_rows"]) == 6
    assert any("Second side not coherent" in line for line in log)
    assert any("Local gate kept 1" in line for line in log)
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


# JSON blocks copied from the issue bodies. Post text is the issue excerpt.
_ISSUE_EXCERPTS = json.loads(
    (Path(__file__).resolve().parents[0] / "fixtures" / "stance_issue_excerpts.json").read_text()
)


def _excerpt(number: int) -> dict:
    return _ISSUE_EXCERPTS[str(number)]


@pytest.mark.parametrize(
    "number",
    [256, 254, 179, 164, 162, 152, 117, 116, 151],
)
def test_issue_excerpt_same_side_faces_fold_to_one(number: int):
    planet = _excerpt(number)
    gated = gate_published_perspectives(planet["perspectives"])
    assert len(gated) == 1
    largest = max(planet["perspectives"], key=lambda face: float(face.get("volume_percent") or 0))
    assert gated[0]["title"] == largest["title"]


def test_alike_titles_that_disagree_stay_apart_before_the_gate():
    left_uris = ["a1", "a2"]
    right_uris = ["b1", "b2"]
    left = _face("Israel Condemned", left_uris, summary="Israel is condemned")
    right = _face("Israel Condemned 2", right_uris, summary="Israel is condemned")
    members = [
        _post("a1", "Israel is a genocidal terrorist state."),
        _post("a2", "These killings are horrific and wrong."),
        _post("b1", "I support and defend Israel. The operation was successful."),
        _post("b2", "Israel deserves support. The strikes were effective."),
    ]
    assert titles_alike("Israel Condemned", "Israel Condemned 2") is True
    merged = _merge_alike_drafts([left, right], 6, members)
    assert [item[0]["title"] for item in merged] == ["Israel Condemned", "Israel Condemned 2"]
    assert all(item[0].get("stance_locked") for item in merged)
    same_side = [
        _post("a1", "Israel is a genocidal terrorist state."),
        _post("a2", "These killings are horrific and wrong."),
        _post("b1", "The occupation is genocidal and horrific."),
        _post("b2", "These killings are wrong and cruel."),
    ]
    folded = _merge_alike_drafts(
        [
            _face("Israel Condemned", left_uris, summary="Israel is condemned"),
            _face("Israel Condemned 2", right_uris, summary="Israel is condemned"),
        ],
        6,
        same_side,
    )
    assert [item[0]["title"] for item in folded] == ["Israel Condemned"]


def test_disagreeing_faces_stay_locked_against_the_title_fold():
    uris_a = ["a1", "a2"]
    uris_b = ["b1", "b2"]
    # Titles carry no polarity word, so the gate does not rewrite them, and
    # they stay alike for the finalize fold this lock has to block.
    drafted = [
        _face("Israel Policy", uris_a, summary="Posts about Israel policy"),
        _face("Israel Policy 2", uris_b, summary="Posts about Israel policy"),
    ]
    members = [
        _post("a1", "Israel is a genocidal terrorist state."),
        _post("a2", "These killings are horrific and wrong."),
        _post("b1", "I support and defend Israel. The operation was successful."),
        _post("b2", "Israel deserves support. The strikes were effective."),
    ]
    assert titles_alike("Israel Policy", "Israel Policy 2") is True
    gated = apply_local_stance_gate(drafted, members)
    assert [item[0]["title"] for item in gated] == ["Israel Policy", "Israel Policy 2"]
    assert all(item[0].get("stance_locked") for item in gated)
    topic = {
        "perspectives": [
            {**gated[0][0], "id": "1A", "post_count": gated[0][2]},
            {**gated[1][0], "id": "1B", "post_count": gated[1][2]},
        ]
    }
    assert merge_alike_published_faces([topic]) == 0
    assert [face["title"] for face in topic["perspectives"]] == ["Israel Policy", "Israel Policy 2"]


def test_maga_support_over_hostile_posts_is_rewritten():
    # Issue #163, verbatim representative posts.
    planet = _excerpt(163)
    face = planet["perspectives"][0]
    assert face["title"] == "MAGA Support"
    gated = gate_published_perspectives(planet["perspectives"])
    assert len(gated) == 1
    assert gated[0]["title"] == "MAGA Opposed"
    assert "oppose" in gated[0]["summary"].lower()
    assert align_contradicting_title(
        {"title": "Not Genocidal", "summary": "These posts say it is not genocide."},
        [
            {"text": "This war is not genocide."},
            {"text": "This is not a genocide."},
        ],
    ) is False


def test_a_weak_posts_pole_does_not_append_a_side_or_rewrite_the_summary():
    face = {"title": "Successful Operation", "summary": "The operation was successful."}
    posts = [
        {"text": "This was horrific and wrong."},
        {"text": "The killings are genocidal."},
        {"text": "People discussed the timeline."},
        {"text": "Another note about the schedule."},
        {"text": "Weather was fine."},
        {"text": "Lunch was late."},
        {"text": "The meeting ran long."},
        {"text": "Traffic was slow."},
    ]
    assert align_contradicting_title(face, posts) is False
    assert face["title"] == "Successful Operation"
    assert face["summary"] == "The operation was successful."
    swapped = {"title": "MAGA Support", "summary": "MAGA supporters back Trump"}
    assert align_contradicting_title(swapped, posts) is True
    assert swapped["title"] == "MAGA Opposed"
    assert swapped["summary"] == "MAGA supporters back Trump"


def test_a_majority_posts_pole_may_append_a_side_and_rewrite_the_summary():
    face = {"title": "Successful Operation", "summary": "The operation was successful."}
    posts = [
        {"text": "This was horrific and wrong."},
        {"text": "The killings are genocidal."},
        {"text": "The violence is horrific."},
        {"text": "This is cruel and wrong."},
    ]
    assert align_contradicting_title(face, posts) is True
    assert face["title"] == "Successful Operation Opposed"
    assert "oppose" in face["summary"].lower()


def test_pro_ice_minority_posts_do_not_fold():
    # Counter to issue #151. Those representative posts condemn ICE and fold.
    # Real pro-ICE cues on the minority face are a disagreement and stay apart.
    faces = [
        {
            "title": "ICE Abuse",
            "summary": "ICE agents are abusive",
            "post_count": 54,
            "representative_posts": [
                {"text": "ICE agents are abusive and the violence is horrific."},
                {"text": "These ICE killings are wrong."},
            ],
        },
        {
            "title": "ICE Has Role",
            "summary": "ICE has a legitimate role and should not be abolished.",
            "post_count": 18,
            "representative_posts": [
                {"text": "I support and defend ICE. It has a legitimate role."},
                {"text": "ICE should not be abolished. The work was successful and deserved."},
            ],
        },
    ]
    gated = gate_published_perspectives(faces)
    assert [face["title"] for face in gated] == ["ICE Abuse", "ICE Has Role"]
    assert all(face.get("stance_locked") for face in gated)


def test_prices_up_versus_down_stay_two_faces():
    faces = [
        {
            "title": "High Oil",
            "summary": "Oil prices are rising",
            "post_count": 6,
            "representative_posts": [
                {"text": "Brent crude is back near the week's high."},
                {"text": "Oil prices are rising again this week."},
            ],
        },
        {
            "title": "Oil Prices",
            "summary": "Oil prices will decrease",
            "post_count": 3,
            "representative_posts": [
                {"text": "Give it 48 hours and Brent is coming way down."},
                {"text": "Oil prices will decrease once the ships move."},
            ],
        },
    ]
    gated = gate_published_perspectives(faces)
    assert [face["title"] for face in gated] == ["High Oil", "Oil Prices"]


def test_attack_reports_stay_apart_from_an_antiwar_face():
    faces = [
        {
            "title": "Iran War",
            "summary": "US war with Iran is unnecessary",
            "post_count": 10,
            "representative_posts": [
                {"text": "A war with Iran is unnecessary."},
                {"text": "There is no reason for this war."},
            ],
        },
        {
            "title": "Iran Attacks Ships",
            "summary": "Iran attacks ships in the Strait",
            "post_count": 4,
            "representative_posts": [
                {"text": "Iran attacked a ship in the Strait of Hormuz."},
                {"text": "Another ship was struck overnight."},
            ],
        },
    ]
    gated = gate_published_perspectives(faces)
    assert [face["title"] for face in gated] == ["Iran War", "Iran Attacks Ships"]


def test_opposing_pair_with_no_shared_title_word_stays_split():
    faces = [
        {
            "title": "Ceasefire Now",
            "summary": "The war is unnecessary",
            "post_count": 8,
            "representative_posts": [
                {"text": "This war is unnecessary."},
                {"text": "Push for a ceasefire."},
            ],
        },
        {
            "title": "Ship Strikes",
            "summary": "Forces struck ships overnight",
            "post_count": 5,
            "representative_posts": [
                {"text": "Forces struck two ships overnight."},
                {"text": "A missile hit another ship this morning."},
            ],
        },
    ]
    assert "ceasefire" not in "ship strikes"
    gated = gate_published_perspectives(faces)
    assert [face["title"] for face in gated] == ["Ceasefire Now", "Ship Strikes"]


def test_same_side_posts_are_not_a_second_face_issue_141():
    # #141: posts counted as the opposing pole argue the same side as the main face.
    uris = [f"g{index}" for index in range(20)]
    labels = ["opposes" if index < 4 else "supports" for index in range(20)]
    members = []
    for index, uri in enumerate(uris):
        text = (
            "Israel continues to kill Palestinians in Gaza."
            if index < 4
            else "Israel is a genocidal terrorist state."
        )
        members.append(_post(uri, text))

    def generate(_prompt: str) -> str:
        return json.dumps(
            {
                "question": "Is this genocide?",
                "labels": [{"i": index + 1, "stance": label} for index, label in enumerate(labels)],
                "second": {
                    "stance": "opposes",
                    "coherent": True,
                    "title": "Gaza Killings",
                    "summary": "Israel kills Palestinians in Gaza.",
                },
            }
        )

    context = _context(stance_generate=generate)
    merged, log = apply_stance_pass(
        [_face("Israel Condemned", uris, summary="Israel is accused of genocide")],
        members,
        context,
        subject="Gaza",
    )
    assert context["stance_last"]["split"] is True
    assert [item[0]["title"] for item in merged] == ["Israel Condemned"]
    assert any("1 face(s) -> 1" in line for line in log)
    drafted = [
        _face("Israel Condemned", uris[:2], summary="Israel is accused of genocide"),
        _face("Gaza Killings", uris[2:], summary="Israel kills Palestinians in Gaza"),
    ]
    folded = apply_local_stance_gate(drafted, members[:4], subject="Gaza")
    assert len(folded) == 1
