"""Parallel wide face relabel: ordering, deadline, and regression guards."""

from __future__ import annotations

import time
from unittest.mock import patch

import numpy as np

from pipeline import live
from tests.test_faces_53 import SETTINGS, _clustered, _planet_posts
from tests.test_finalize_faces import _posts_and_matrix, _topic_with_face


def _context():
    context = live._label_context({**SETTINGS, "label_backend": "openai", "openai_model": "m"})
    context["chosen"] = "openai"
    context["workers"] = 4
    context["story_calls"] = {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}
    return context


def test_priority_order_puts_mixed_and_thin_faces_first():
    posts, clustered = _posts_and_matrix()
    mixed = _topic_with_face(posts, "Mixed remarks")
    mixed["perspectives"][0]["_draft_face_label"] = {
        "title": "Mixed remarks",
        "summary": "These posts do not share a claim.",
        "representative_posts": mixed["perspectives"][0]["representative_posts"],
        "arguments": None,
    }
    named = _topic_with_face(posts, "Named claim")
    named["perspectives"][0]["_draft_face_label"]["arguments"] = ["a", "b", "c"]

    jobs = live._collect_finalize_face_jobs(
        [named, mixed],
        posts,
        clustered,
        _context(),
        section="Politics",
    )
    order = live._fair_finalize_order(jobs)
    assert order[0].draft["title"] == "Mixed remarks"
    assert order[1].draft["title"] == "Named claim"


def test_mixed_relabel_never_overwrites_named_draft():
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Medicare Payments")
    context = _context()

    def wide(*_args, **_kwargs):
        return {
            "title": "Mixed remarks",
            "summary": "These posts do not share a claim.",
            "representative_posts": [{"author": "u", "text": "x", "likes": 0}],
            "arguments": None,
        }

    with patch.object(live, "_wide_label_face_from_posts", side_effect=wide):
        live._finalize_published_planets([topic], posts, clustered, context)
    face = topic["perspectives"][0]
    assert face["title"] == "Medicare Payments"
    assert face.get("summary") == "Summary here."
    assert context["story_calls"]["finalize_faces"] == 1


def test_mixed_relabel_never_overwrites_thin_named_draft():
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Thin named")
    topic["perspectives"][0]["_draft_face_label"]["arguments"] = ["only one"]
    context = _context()

    def wide(*_args, **_kwargs):
        return {
            "title": "Mixed remarks",
            "summary": "These posts do not share a claim.",
            "representative_posts": [{"author": "u", "text": "x", "likes": 0}],
            "arguments": None,
        }

    with patch.object(live, "_wide_label_face_from_posts", side_effect=wide):
        live._finalize_published_planets([topic], posts, clustered, context)
    assert topic["perspectives"][0]["title"] == "Thin named"


def test_mixed_draft_gets_named_wide_relabel():
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Mixed remarks")
    topic["perspectives"][0]["title"] = "Mixed remarks"
    topic["perspectives"][0]["_draft_face_label"] = {
        "title": "Mixed remarks",
        "summary": "These posts do not share a claim.",
        "representative_posts": topic["perspectives"][0]["representative_posts"],
        "arguments": None,
    }
    context = _context()

    def wide(*_args, **_kwargs):
        return {
            "title": "Medicare Payments",
            "summary": "Posts about Medicare funding.",
            "representative_posts": [{"author": "u", "text": "medicare payments", "likes": 1}],
            "arguments": ["a", "b"],
        }

    with patch.object(live, "_wide_label_face_from_posts", side_effect=wide):
        live._finalize_published_planets([topic], posts, clustered, context)
    assert topic["perspectives"][0]["title"] == "Medicare Payments"


def test_thin_named_survives_mixed_relabel_after_section_finish():
    posts, clustered = _posts_and_matrix()
    planet = _topic_with_face(posts, "Solid face")
    rep = planet["perspectives"][0]["representative_posts"][0]
    uris = list(planet["perspectives"][0]["_face_member_uris"])
    planet["perspectives"].append(
        {
            "id": "1B",
            "title": "Thin named",
            "summary": "Thin summary.",
            "volume_percent": 0.0,
            "post_count": len(posts),
            "top_terms": ["diesel"],
            "representative_posts": [rep],
            "_draft_face_label": {
                "title": "Thin named",
                "summary": "Thin summary.",
                "representative_posts": [rep],
                "arguments": ["one"],
            },
            "_face_member_uris": uris,
        }
    )
    planet["perspectives"][0]["_draft_face_label"]["arguments"] = ["a", "b"]
    context = _context()
    wide_results = [
        {
            "title": "Mixed remarks",
            "summary": "These posts do not share a claim.",
            "representative_posts": [{"author": "u", "text": "x", "likes": 0}],
            "arguments": None,
        },
        {
            "title": "Solid face",
            "summary": "Still solid.",
            "representative_posts": [{"author": "u", "text": "diesel", "likes": 1}],
            "arguments": ["a", "b"],
        },
    ]

    def wide(*_args, **_kwargs):
        return wide_results.pop(0)

    with patch.object(live, "_wide_label_face_from_posts", side_effect=wide):
        built = live._drop_unshared_planets([planet])
        live._finalize_published_planets(built, posts, clustered, context)
        finished = live._finish_section_planets(
            built,
            posts,
            clustered,
            context,
            finalize=False,
        )
    titles = [face["title"] for face in finished[0]["perspectives"]]
    assert "Thin named" in titles
    assert "Solid face" in titles


def test_parallel_finalize_respects_deadline(monkeypatch):
    posts, clustered = _posts_and_matrix()
    topics = [_topic_with_face(posts, f"Face {index}") for index in range(6)]
    context = _context()
    context["workers"] = 2
    deadline = time.monotonic() + 0.05

    def slow(*_args, **_kwargs):
        time.sleep(0.08)
        return {
            "title": "Wide",
            "summary": "Wide summary.",
            "representative_posts": [{"author": "u", "text": "diesel", "likes": 1}],
            "arguments": ["a", "b"],
        }

    monkeypatch.setattr(live, "_wide_label_face_from_posts", slow)
    incomplete = live._finalize_published_planets([topic for topic in topics], posts, clustered, context, deadline=deadline)
    assert incomplete == {"All topics"}
    assert context["story_calls"]["finalize_faces"] < 6


def test_inflight_results_after_deadline_are_still_applied(monkeypatch, capsys):
    posts, clustered = _posts_and_matrix()
    topics = [_topic_with_face(posts, f"Face {index}") for index in range(2)]
    context = _context()
    context["workers"] = 1
    deadline = time.monotonic() + 0.02

    def slow(*_args, **_kwargs):
        time.sleep(0.08)
        return {
            "title": "Upgraded",
            "summary": "Wide summary.",
            "representative_posts": [{"author": "u", "text": "diesel", "likes": 1}],
            "arguments": ["a", "b"],
        }

    monkeypatch.setattr(live, "_wide_label_face_from_posts", slow)
    live._finalize_published_planets(topics, posts, clustered, context, deadline=deadline)
    assert topics[0]["perspectives"][0]["title"] == "Upgraded"
    out = capsys.readouterr().out
    assert "past the section deadline" in out


def test_finalize_logs_call_count(capsys):
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Wide title")
    context = _context()

    def wide(*_args, **_kwargs):
        return {
            "title": "Wide title",
            "summary": "Wide summary.",
            "representative_posts": [{"author": "u", "text": "diesel", "likes": 2}],
            "arguments": ["a", "b"],
        }

    with patch.object(live, "_wide_label_face_from_posts", side_effect=wide):
        live._finalize_published_planets([topic], posts, clustered, context)
    out = capsys.readouterr().out
    assert "Wide face relabel: 1 call(s) in" in out


def test_fair_order_interleaves_sections():
    posts_a, matrix_a = _planet_posts("alpha", [4], seed=1)
    posts_b, matrix_b = _planet_posts("beta", [4], seed=2)
    clustered_a = {"matrix": matrix_a, "topics": [], "assignments": [], "noise_count": 0}
    clustered_b = {"matrix": matrix_b, "topics": [], "assignments": [], "noise_count": 0}
    context = _context()
    jobs = []
    for section, posts, clustered in (
        ("Politics", posts_a, clustered_a),
        ("World", posts_b, clustered_b),
    ):
        jobs.extend(
            live._collect_finalize_face_jobs(
                [_topic_with_face(posts, "Named")],
                posts,
                clustered,
                context,
                section=section,
            )
        )
        jobs.extend(
            live._collect_finalize_face_jobs(
                [_topic_with_face(posts, "Mixed remarks")],
                posts,
                clustered,
                context,
                section=section,
            )
        )
    order = live._fair_finalize_order(jobs)
    sections = [job.section for job in order[:4]]
    assert sections[0] != sections[1]
    assert set(sections[:2]) == {"Politics", "World"}
