"""Reader-facing label guard at finalize. No model and no network."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from pipeline.label_guard import (
    PENDING_SUMMARY,
    PENDING_TITLE,
    guard_published_labels,
    is_preamble_label,
    is_template_summary,
    reader_label_issue,
    readable_face_label,
    scan_edition_labels,
)
from pipeline.schema import STANCE_CHECK_LABEL_HELD

ROOT = Path(__file__).resolve().parents[1]


def _topic(name: str, summary: str, face_title: str, face_summary: str, posts: list[dict]) -> dict:
    return {
        "name": name,
        "summary": summary,
        "perspectives": [
            {
                "title": face_title,
                "summary": face_summary,
                "representative_posts": posts,
            }
        ],
    }


def test_pending_summary_is_not_stance_analyzed_copy():
    assert PENDING_SUMMARY == "Topic label not ready for this edition."
    assert "analyzed" not in PENDING_SUMMARY.lower()


def test_detects_template_preamble_and_insult_labels():
    assert is_template_summary("Posts grouped under Fascist.")
    assert is_template_summary("These posts are about Certainly.")
    assert is_template_summary("Posts in this group center on playstation, games.")
    assert is_preamble_label("Certainly")
    assert is_preamble_label("Here is the claim")
    assert reader_label_issue("Car Let", "Posts grouped under Car Let.", planet_name="Car Let") == "template summary"
    assert reader_label_issue("Fascist", "A real sentence about the posts.", planet_name="Fascist") == "insult title"


def test_readable_face_label_does_not_emit_term_bag_or_placeholder():
    posts = [
        {"text": "Lawmakers are coming after Sony PlayStation for physical games.", "likes": 3},
        {"text": "American cars are notoriously fuel inefficient in traffic.", "likes": 2},
    ]
    title, summary = readable_face_label(posts, ["playstation", "cars", "fuel"])
    assert "Posts grouped under" not in summary
    assert "Posts in this group center on" not in summary
    assert title not in {"Concept Thought", "Funny", "Crazy", "Car Let"}
    assert "Certainly" not in title


def test_guard_holds_insult_placeholder_pending():
    posts = [
        {"uri": "at://1", "text": "Trump and Hegseth are fascists who aspire to copy Hitler.", "likes": 9},
        {"uri": "at://2", "text": "This regime is fascist and must be stopped.", "likes": 4},
    ]
    topic = _topic(
        "Fascist",
        "Posts grouped under Fascist.",
        "Fascist",
        "Posts grouped under Fascist.",
        [{"text": post["text"], "likes": post["likes"]} for post in posts],
    )
    topic["_member_uris"] = ["at://1", "at://2"]
    topic["perspectives"][0]["_face_member_uris"] = ["at://1", "at://2"]
    log = guard_published_labels([topic], posts)
    face = topic["perspectives"][0]
    assert topic["stance_check"] == STANCE_CHECK_LABEL_HELD
    assert topic["name"] == PENDING_TITLE
    assert topic["summary"] == PENDING_SUMMARY
    assert face["title"] == PENDING_TITLE
    assert face["summary"] == PENDING_SUMMARY
    assert "fascist" not in face["title"].lower()
    assert log


def test_guard_uses_a_shared_phrase_and_rejects_term_bags():
    heat = _topic(
        "Angeles Cities Heat",
        "Posts grouped under Angeles Cities Heat.",
        "Angeles Cities Heat",
        "Posts grouped under Angeles Cities Heat.",
        [
            {"text": "It is 93 degrees in West Los Angeles today. I'm glad the game was moved.", "likes": 2},
            {"text": "Los Angeles is on the live heat ranking again this afternoon.", "likes": 1},
            {"text": "Three United States cities are in the heat ranking, led by Los Angeles.", "likes": 0},
        ],
    )
    debris = _topic(
        "Bully Bullies Bullying",
        "Posts grouped under Bully Bullies Bullying.",
        "Bully Bullies Bullying",
        "Posts grouped under Bully Bullies Bullying.",
        [
            {"text": "They have never been bullied. They may have been the bully.", "likes": 1},
            {"text": "Plenty of bullies bully whether or not they are right.", "likes": 0},
            {"text": "The people are just bullies.", "likes": 0},
        ],
    )
    kept = _topic(
        "Early Voting",
        "People are voting early.",
        "Vote Early",
        "People are voting early.",
        [
            {"text": "Early voting starts on Monday.", "likes": 3},
            {"text": "Vote early if you can.", "likes": 2},
        ],
    )
    guard_published_labels([heat, debris, kept], [])
    assert heat["name"] == "Los Angeles"
    assert heat["summary"] == "It is 93 degrees in West Los Angeles today."
    assert heat["perspectives"][0]["title"] == "Los Angeles"
    assert debris["name"] == PENDING_TITLE
    assert debris["summary"] == PENDING_SUMMARY
    assert "Bully" not in debris["perspectives"][0]["title"]
    assert kept["name"] == "Early Voting"
    assert kept["perspectives"][0]["title"] == "Vote Early"
    assert kept["summary"] == "People are voting early."


def test_bad_draft_is_not_retried_as_a_term_bag():
    topic = _topic(
        "Crazy",
        "Posts grouped under Crazy.",
        "Crazy",
        "Posts grouped under Crazy.",
        [
            {"text": "What a crazy concept. Please tell me it's not AI.", "likes": 1},
            {"text": "It is crazy to me that teachers now encourage AI.", "likes": 0},
        ],
    )
    topic["perspectives"][0]["_draft_face_label"] = {
        "title": "Concept Thought",
        "summary": "Please tell me it's not AI.",
    }
    guard_published_labels([topic], [])
    assert topic["name"] == PENDING_TITLE
    assert topic["perspectives"][0]["title"] == PENDING_TITLE
    assert topic["perspectives"][0]["summary"] == PENDING_SUMMARY


def test_scan_flags_templates_and_leaves_a_real_label():
    payload = {
        "topics": [
            _topic(
                "Early Voting",
                "People are voting early.",
                "Vote Early",
                "People are voting early.",
                [{"text": "Vote early if you can.", "likes": 1}],
            )
        ],
        "sections": {
            "Education": [
                _topic(
                    "He Is",
                    "These posts are about Certainly.",
                    "Certainly",
                    "These posts are about Certainly.",
                    [{"text": "He certainly is!", "likes": 1}],
                )
            ]
        },
    }
    report = scan_edition_labels(payload)
    assert any(row["title"] == "Certainly" for row in report["flagged"])
    assert all(row["title"] != "Early Voting" for row in report["flagged"])
    assert any(row["would_show"].startswith("hold pending") for row in report["flagged"])


def test_label_guard_does_not_call_a_model(monkeypatch):
    source = (ROOT / "pipeline" / "label_guard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "_draft_face_label" not in imported
    for needle in ("openai", "urlopen", "requests", "httpx", "jev"):
        assert needle not in source.lower()

    def boom(*_args, **_kwargs):
        raise AssertionError("network call")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    monkeypatch.setattr("http.client.HTTPConnection.request", boom)
    for key in (
        "OPENAI_API_KEY",
        "DEEPINFRA_API_KEY",
        "PERSPECTIVERSE_LABEL_BACKEND",
        "PERSPECTIVERSE_JEV_BATCH",
        "OLLAMA_MODEL",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    topic = _topic(
        "Crazy",
        "Posts grouped under Crazy.",
        "Crazy",
        "Posts grouped under Crazy.",
        [{"text": "What a crazy concept. Please tell me it's not AI.", "likes": 1}],
    )
    guard_published_labels([topic], [])
    scan_edition_labels({"topics": [topic], "sections": {}})


def test_oct19_snapshot_replacements_are_readable():
    fixture = Path(__file__).resolve().parent / "fixtures" / "label_guard_oct19_scan.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    report = scan_edition_labels(payload)
    assert len(report["flagged"]) == 14
    protected = {
        "Trump Ukraine Sanctions",
        "Early Voting",
        "Book Enthusiasm",
        "Movie Enjoyment",
        "US Ukraine War",
        "No Kings Protests",
    }
    assert not any(row["planet"] in protected or row["title"] in protected for row in report["flagged"])
    for row in report["flagged"]:
        shown = row["would_show"]
        assert "Posts grouped under" not in shown
        assert "Posts in this group center on" not in shown
        assert "Concept Thought" not in shown
        assert "Funny Laugh Made" not in shown
        assert "Question Person" not in shown
        assert "Bullies Bully Bullying" not in shown
        assert "Bar Bits Limited" not in shown
