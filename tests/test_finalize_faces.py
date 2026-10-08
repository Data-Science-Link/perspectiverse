"""Wide face relabel runs only on published catalog planets."""

from __future__ import annotations

import numpy as np

from pipeline import live
from tests.test_faces_53 import SETTINGS, _clustered, _planet_posts


def _topic_with_face(posts: list[dict], title: str = "Real claim") -> dict:
    uris = [str(post["uri"]) for post in posts[:2]]
    rep = {"author": posts[0]["author"], "text": posts[0]["clean_text"], "likes": int(posts[0]["likes"])}
    return {
        "id": 1,
        "name": "Topic",
        "category": "World",
        "total_volume_percent": 100.0,
        "post_count": len(posts),
        "_member_uris": [str(post["uri"]) for post in posts],
        "perspectives": [
            {
                "id": "1A",
                "title": title,
                "summary": "Summary here.",
                "volume_percent": 100.0,
                "post_count": len(posts),
                "top_terms": ["diesel"],
                "representative_posts": [rep],
                "_draft_face_label": {
                    "title": title,
                    "summary": "Summary here.",
                    "representative_posts": [rep],
                    "arguments": ["arg one", "arg two"],
                },
                "_face_member_uris": uris,
            }
        ],
    }


def _posts_and_matrix():
    posts, matrix = _planet_posts("diesel", [4], seed=1)
    clustered = {"matrix": matrix, "topics": [], "assignments": [], "noise_count": 0}
    return posts, clustered


def test_only_published_planets_are_finalized(monkeypatch):
    """Dropped candidates never reach the post-selection finalize pass."""
    groups = [_planet_posts(f"topic{index}", [20, 12], seed=index) for index in range(4)]
    seen: list[int] = []

    def spy(topics, post_list, clustered, context, **kwargs):
        del post_list, clustered, context, kwargs
        seen.append(len(topics))

    monkeypatch.setattr(live, "_finalize_published_planets", spy)
    posts, clustered = _clustered(groups)
    context = live._label_context({**SETTINGS, "label_backend": "heuristic"})
    topics, _membership, _faces = live._build_topics(posts, clustered, SETTINGS, keep=2, context=context)
    assert len(topics) == 2
    assert seen == [2]


def test_finalize_failure_keeps_draft_label(monkeypatch):
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Kept title")
    context = live._label_context({**SETTINGS, "label_backend": "openai", "openai_model": "m"})
    context["chosen"] = "openai"
    context["story_calls"] = {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}

    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(live, "_wide_label_face_from_posts", boom)
    live._finalize_published_planets([topic], posts, clustered, context)
    assert topic["perspectives"][0]["title"] == "Kept title"


def test_finalize_refuses_mixed_remarks_downgrade(monkeypatch):
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Kept title")
    context = live._label_context({**SETTINGS, "label_backend": "openai", "openai_model": "m"})
    context["chosen"] = "openai"
    context["story_calls"] = {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}

    def mixed(*_args, **_kwargs):
        return {
            "title": "Mixed remarks",
            "summary": "These posts do not share a claim.",
            "representative_posts": [{"author": "u", "text": "x", "likes": 0}],
            "arguments": None,
        }

    monkeypatch.setattr(live, "_wide_label_face_from_posts", mixed)
    live._finalize_published_planets([topic], posts, clustered, context)
    face = topic["perspectives"][0]
    assert face["title"] == "Kept title"
    assert context["story_calls"]["finalize_faces"] == 1


def test_finalize_counts_calls(monkeypatch):
    posts, clustered = _posts_and_matrix()
    topic = _topic_with_face(posts, "Wide title")
    context = live._label_context({**SETTINGS, "label_backend": "openai", "openai_model": "m"})
    context["chosen"] = "openai"
    context["story_calls"] = {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}

    def wide(*_args, **_kwargs):
        return {
            "title": "Wide title",
            "summary": "Wide summary.",
            "representative_posts": [{"author": "u", "text": "diesel", "likes": 2}],
            "arguments": ["a", "b"],
        }

    monkeypatch.setattr(live, "_wide_label_face_from_posts", wide)
    live._finalize_published_planets([topic], posts, clustered, context)
    assert context["story_calls"]["finalize_faces"] == 1
    assert context["story_calls"]["faces"] == 1
