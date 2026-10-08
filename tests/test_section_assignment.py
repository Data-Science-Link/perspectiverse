"""One clustering can fill the section lists, or each section can be clustered again."""

from __future__ import annotations

import numpy as np

from pipeline import live
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


def test_one_clustering_is_the_default():
    assert DEFAULTS["section_grouping"] == "cluster_once"


def test_majority_section_lists_one_home_and_thirty_five_percent_lists_both():
    politics = _posts(["Politics"] * 7 + ["World"] * 3)
    assert live.sections_for_members(politics, list(range(10))) == ["Politics"]

    split = _posts(["Politics"] * 4 + ["World"] * 4 + ["Other"] * 2)
    # A tie lists both. The earlier newspaper section is the home.
    assert live.sections_for_members(split, list(range(10))) == ["World", "Politics"]

    boundary = _posts(["Sports"] * 7 + ["Health"] * 7 + ["Other"] * 6)
    assert live.sections_for_members(boundary, list(range(20))) == ["Sports", "Health"]

    just_under = _posts(["Politics"] * 35 + ["World"] * 34 + ["Other"] * 31)
    assert live.sections_for_members(just_under, list(range(100))) == ["Politics"]

    diluted = _posts(["Politics"] * 4 + [""] * 6)
    assert live.sections_for_members(diluted, list(range(10))) == ["Politics"]


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


def test_a_planet_listed_in_two_sections_is_labeled_once(monkeypatch):
    """Ten Politics, ten World, and one planet that is half of each."""
    posts = _posts(["Politics"] * 20 + ["World"] * 20)
    topics = []
    for index in range(9):
        topics.append(
            {"id": index, "size": 1, "member_indices": [index], "terms": [f"pol{index}"]}
        )
    for index in range(9):
        topics.append(
            {
                "id": 20 + index,
                "size": 1,
                "member_indices": [20 + index],
                "terms": [f"world{index}"],
            }
        )
    topics.append(
        {
            "id": 99,
            "size": 20,
            "member_indices": list(range(10, 20)) + list(range(30, 40)),
            "terms": ["shared"],
        }
    )
    drafted: list[tuple[int, ...]] = []

    def draft(_posts, _clustered, topic, _context):
        drafted.append(tuple(topic["member_indices"]))
        result = _planet_result(" ".join(topic["terms"]))
        result["membership"] = [_posts[index]["uri"] for index in topic["member_indices"]]
        result["planet"]["post_count"] = len(topic["member_indices"])
        result["planet"]["_member_uris"] = list(result["membership"])
        return result, []

    monkeypatch.setattr(live, "_draft_planet", draft)
    settings = {
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
    }
    context = live._label_context(settings)
    sections = live._cluster_sections_once(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        settings,
        10,
        1,
        context=context,
    )
    assert len(sections["Politics"]) == 10
    assert len(sections["World"]) == 10
    assert drafted.count(tuple(topics[-1]["member_indices"])) == 1
    assert len(drafted) == 19


def test_global_draft_is_reused_when_the_section_list_is_built(monkeypatch):
    posts = _posts(["Politics"] * 4)
    topic = {"id": 1, "size": 4, "member_indices": [0, 1, 2, 3], "terms": ["shared"]}
    calls: list[int] = []

    def draft(members, _clustered, candidate, _context):
        calls.append(len(candidate["member_indices"]))
        result = _planet_result("shared")
        result["membership"] = [members[index]["uri"] for index in candidate["member_indices"]]
        result["planet"]["post_count"] = len(candidate["member_indices"])
        result["planet"]["_member_uris"] = list(result["membership"])
        return result, []

    monkeypatch.setattr(live, "_draft_planet", draft)
    settings = {
        "label_backend": "heuristic",
        "representative_posts": 6,
        "prompt_sample_size": 40,
        "draft_prompt_sample_size": 12,
        "planet_prompt_sample_size": 20,
        "seed": 0,
        "label_workers": 0,
        "min_planet_posts": 1,
        "openai_model": "",
    }
    context = live._label_context(settings)
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

    def draft(members, _clustered, candidate, _context):
        if candidate["terms"][0] == "drop":
            return None, ["dropped"]
        result = _planet_result(candidate["terms"][0])
        result["membership"] = [members[index]["uri"] for index in candidate["member_indices"]]
        result["planet"]["post_count"] = 1
        result["planet"]["_member_uris"] = list(result["membership"])
        return result, []

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
    settings = {
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
    }
    context = live._label_context(settings)
    context["section_fallbacks"] = []
    sections = live._cluster_sections_once(
        posts,
        np.zeros((len(posts), 4)),
        topics,
        settings,
        3,
        1,
        context=context,
    )
    assert context["section_fallbacks"] == ["Sports"]
    assert [planet["name"] for planet in sections["Sports"]] == ["keep", "keep 2", "also"]
