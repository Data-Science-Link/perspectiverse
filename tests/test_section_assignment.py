"""One clustering lists planets into sections. Each planet is labeled once."""

from __future__ import annotations

import json

import numpy as np

from pipeline import live
from pipeline.jev import sections_from_choice
from pipeline.settings import DEFAULTS
from tests.test_section_pool import _planet_result


def _posts(sections: list[str]) -> list[dict]:
    return [
        {
            "uri": f"at://{section}/{index}",
            "author": f"{section}-{index}",
            "section": section,
            "clean_text": f"{section} claim {index}",
            "text": f"{section} claim {index}",
            "likes": 0,
        }
        for index, section in enumerate(sections)
    ]


def test_one_clustering_is_the_default_and_pytest_does_not_call_jev():
    assert DEFAULTS["section_grouping"] == "cluster_once"
    # The October shadow was 78/107 (72.9%). Jev stays available, not the default.
    assert DEFAULTS["section_assignment"] == "majority"
    assert live._section_assignment_mode(DEFAULTS, {}) == "majority"


def test_majority_section_lists_one_home_and_thirty_five_percent_lists_both():
    politics = _posts(["Politics"] * 7 + ["World"] * 3)
    assert live.sections_for_members(politics, list(range(10))) == ["Politics"]

    split = _posts(["Politics"] * 4 + ["World"] * 4 + ["Other"] * 2)
    assert live.sections_for_members(split, list(range(10))) == ["World", "Politics"]

    boundary = _posts(["Sports"] * 7 + ["Health"] * 7 + ["Other"] * 6)
    assert live.sections_for_members(boundary, list(range(20))) == ["Sports", "Health"]

    just_under = _posts(["Politics"] * 35 + ["World"] * 34 + ["Other"] * 31)
    assert live.sections_for_members(just_under, list(range(100))) == ["Politics"]

    diluted = _posts(["Politics"] * 4 + [""] * 6)
    assert live.sections_for_members(diluted, list(range(10))) == ["Politics"]


def test_close_probabilities_list_both_sections_and_a_wide_gap_lists_one():
    assert sections_from_choice("Culture", {"Culture": 0.46, "Other": 0.40}) == ["Culture", "Other"]
    assert sections_from_choice("Politics", {"Politics": 0.80, "World": 0.12}) == ["Politics"]
    assert sections_from_choice("Sports", None) == ["Sports"]


def test_culture_agreement_is_reported_on_its_own():
    rows = [
        {"name": "Dress", "majority": "Culture", "jev": "Other", "agree": False, "mixed": False},
        {"name": "Film", "majority": "Culture", "jev": "Culture", "agree": True, "mixed": False},
        {"name": "Vote", "majority": "Politics", "jev": "Politics", "agree": True, "mixed": True},
    ]
    report = live.section_agreement_report(rows)
    assert report["judged"] == 3
    assert report["agreed"] == 2
    assert report["culture"]["judged"] == 2
    assert report["culture"]["agreed"] == 1
    assert report["culture"]["rate"] == 0.5
    assert report["passes_bar"] is False
    assert report["disagreements"] == [
        {"name": "Dress", "majority": "Culture", "jev": "Other", "mixed": False}
    ]


def test_planet_section_question_nudges_culture_away_from_other(monkeypatch):
    from pipeline.jev import reset_jev_state

    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    seen = {}

    def fake(url, **kwargs):
        body = json.loads(kwargs["data"].decode("utf-8"))
        seen["question"] = body["questions"]["section"]
        return {
            "model": "jev-test",
            "answers": {
                "section": {
                    "choice": "Culture",
                    "probabilities": {"Culture": 0.7, "Other": 0.2},
                }
            },
        }

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    from pipeline.jev import classify_planet_section

    choice = classify_planet_section("Planet: Dress code\nPerspective: School clothes\nA uniform rule.")
    assert choice["primary"] == "Culture"
    instructions = seen["question"]["instructions"]
    assert "Culture, not Other" in instructions
    assert "celebrity" in seen["question"]["criteria"]["Other"]
    assert "post's primary subject" not in instructions


def test_short_section_falls_back_and_skips_a_group_already_listed(monkeypatch):
    sections = ["Politics"] * 10 + ["Education"] * 8
    posts = _posts(sections)
    topics = [
        {"id": index, "size": 1, "member_indices": [index], "terms": ["politics"]}
        for index in range(10)
    ]
    topics.append({"id": 10, "size": 1, "member_indices": [10], "terms": ["education"]})
    topics.append({"id": 11, "size": 1, "member_indices": [11], "terms": ["education"]})

    def fake_cluster(texts, **_kwargs):
        assert len(texts) == 8
        return {
            "topics": [
                {"id": 0, "size": 2, "member_indices": [0, 1], "terms": ["covered"]},
                {"id": 1, "size": 1, "member_indices": [5], "terms": ["fresh"]},
            ],
            "noise_count": 0,
        }

    monkeypatch.setattr(live, "cluster_texts", fake_cluster)
    settings = {
        "min_planet_posts": 1,
        "min_cluster_size": 1,
        "cluster_backend": "embedding",
        "embedding_model": "unused",
        "seed": 0,
    }
    chosen, fallbacks = live.section_candidate_planets(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        settings,
        10,
        1,
    )
    assert fallbacks == ["Education"]
    assert len(chosen["Politics"]) == 10
    education_terms = [topic["terms"][0] for topic in chosen["Education"]]
    assert education_terms == ["education", "education", "fresh"]


def _draft(members, _clustered, topic, _context):
    result = _planet_result(" ".join(topic["terms"]))
    result["membership"] = [members[index]["uri"] for index in topic["member_indices"]]
    result["planet"]["post_count"] = len(topic["member_indices"])
    result["planet"]["_member_uris"] = list(result["membership"])
    return result, []


def _settings():
    return {
        "label_backend": "heuristic",
        "representative_posts": 6,
        "prompt_sample_size": 40,
        "draft_prompt_sample_size": 12,
        "planet_prompt_sample_size": 20,
        "seed": 0,
        "label_workers": 0,
        "min_planet_posts": 1,
        "min_cluster_size": 1,
        "cluster_backend": "embedding",
        "embedding_model": "unused",
        "openai_model": "",
        "section_assignment": "majority",
    }


def test_a_planet_listed_in_two_sections_is_labeled_once(monkeypatch):
    posts = _posts(["Politics"] * 20 + ["World"] * 20)
    topics = []
    for index in range(9):
        topics.append({"id": index, "size": 1, "member_indices": [index], "terms": [f"pol{index}"]})
    for index in range(9):
        topics.append(
            {"id": 20 + index, "size": 1, "member_indices": [20 + index], "terms": [f"world{index}"]}
        )
    shared = list(range(10, 20)) + list(range(30, 40))
    topics.append({"id": 99, "size": 20, "member_indices": shared, "terms": ["shared"]})
    drafted: list[tuple[int, ...]] = []

    def draft(members, clustered, topic, context):
        drafted.append(tuple(topic["member_indices"]))
        return _draft(members, clustered, topic, context)

    monkeypatch.setattr(live, "_draft_planet", draft)
    context = live._label_context(_settings())
    sections = live._cluster_sections_once(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        _settings(),
        10,
        1,
        context=context,
    )
    assert len(sections["Politics"]) == 10
    assert len(sections["World"]) == 10
    assert drafted.count(tuple(shared)) == 1
    assert len(drafted) == 19


def test_wide_relabel_of_shared_planets_uses_the_section_pool_once(monkeypatch):
    posts = _posts(["Politics"] * 4 + ["World"] * 4)
    topics = [
        {"id": 1, "size": 4, "member_indices": [0, 1, 2, 3], "terms": ["shared"]},
        {"id": 2, "size": 4, "member_indices": [4, 5, 6, 7], "terms": ["world"]},
    ]
    calls = []

    def batch(jobs, deadline, *, strip=True):
        calls.append((len(jobs), strip, sorted(job.name for job in jobs)))
        for job in jobs:
            live._remember_finalized(job.context, job.built)

    monkeypatch.setattr(live, "_draft_planet", _draft)
    monkeypatch.setattr(live, "_finalize_section_planets_batch", batch)
    context = live._label_context(_settings())
    context["chosen"] = "openai"
    live._cluster_sections_once(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        _settings(),
        2,
        1,
        context=context,
    )
    assert calls
    assert all(strip is False for _jobs, strip, _names in calls)
    assert sum(count for count, _strip, _names in calls) >= 1


def test_global_draft_is_reused_when_the_section_list_is_built(monkeypatch):
    posts = _posts(["Politics"] * 4)
    topic = {"id": 1, "size": 4, "member_indices": [0, 1, 2, 3], "terms": ["shared"]}
    calls: list[int] = []

    def draft(members, clustered, candidate, context):
        calls.append(len(candidate["member_indices"]))
        return _draft(members, clustered, candidate, context)

    monkeypatch.setattr(live, "_draft_planet", draft)
    context = live._label_context(_settings())
    context["reuse_labels"] = True
    context["planet_label_cache"] = {}
    clustered = {"topics": [topic], "matrix": np.zeros((4, 4)), "assignments": [], "noise_count": 0}
    live._build_topics(posts, clustered, {}, keep=1, context=context)
    live._build_topics(posts, clustered, {}, keep=1, context=context)
    assert calls == [4]


def test_a_short_published_list_is_topped_up_from_that_section(monkeypatch):
    posts = _posts(["Sports"] * 6)
    topics = [
        {"id": index, "size": 1, "member_indices": [index], "terms": ["keep" if index == 0 else "drop"]}
        for index in range(4)
    ]

    def draft(members, clustered, candidate, context):
        if candidate["terms"][0] == "drop":
            return None, ["dropped"]
        return _draft(members, clustered, candidate, context)

    def fake_cluster(texts, **_kwargs):
        assert len(texts) == 6
        return {
            "topics": [
                {"id": 0, "size": 1, "member_indices": [4], "terms": ["keep"]},
                {"id": 1, "size": 1, "member_indices": [5], "terms": ["also"]},
            ],
            "noise_count": 0,
        }

    monkeypatch.setattr(live, "_draft_planet", draft)
    monkeypatch.setattr(live, "cluster_texts", fake_cluster)
    context = live._label_context(_settings())
    context["section_fallbacks"] = []
    sections = live._cluster_sections_once(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        _settings(),
        3,
        1,
        context=context,
    )
    assert "Sports" in context["section_fallbacks"]
    assert [planet["name"] for planet in sections["Sports"]] == ["keep", "keep 2", "also"]
