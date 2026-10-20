"""Reader-facing label guard at finalize."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.label_guard import (
    guard_published_labels,
    is_preamble_label,
    is_template_summary,
    reader_label_issue,
    readable_face_label,
    scan_edition_labels,
)


def test_detects_template_and_preamble_labels():
    assert is_template_summary("Posts grouped under Fascist.")
    assert is_template_summary("These posts are about Certainly.")
    assert is_preamble_label("Certainly")
    assert is_preamble_label("Here is the claim")
    assert reader_label_issue("Car Let", "Posts grouped under Car Let.", planet_name="Car Let") == "template summary"


def test_readable_face_label_uses_terms_not_placeholder():
    posts = [
        {"text": "Lawmakers are coming after Sony PlayStation for physical games.", "likes": 3},
        {"text": "American cars are notoriously fuel inefficient in traffic.", "likes": 2},
    ]
    title, summary = readable_face_label(posts, ["playstation", "cars", "fuel"])
    assert "Posts grouped under" not in summary
    assert "Certainly" not in title
    assert title


def test_guard_replaces_bad_face_with_terms_fallback():
    posts = [
        {"uri": "at://1", "text": "Trump and Hegseth are fascists who aspire to copy Hitler.", "likes": 9},
        {"uri": "at://2", "text": "This regime is fascist and must be stopped.", "likes": 4},
    ]
    topic = {
        "name": "Fascist",
        "summary": "Posts grouped under Fascist.",
        "_member_uris": ["at://1", "at://2"],
        "perspectives": [
            {
                "title": "Fascist",
                "summary": "Posts grouped under Fascist.",
                "_face_member_uris": ["at://1", "at://2"],
            }
        ],
    }
    log = guard_published_labels([topic], posts)
    face = topic["perspectives"][0]
    assert "Posts grouped under" not in face["summary"]
    assert face["title"] != "Fascist" or "fascist" not in face["title"].lower()
    assert log


def test_scan_live_edition_fixture_flags_templates():
    path = Path("/home/ubuntu/.cursor/projects/workspace/uploads/data_2026-10-19_79cf.json")
    if not path.is_file():
        path = Path(__file__).resolve().parents[1] / "public" / "data.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = scan_edition_labels(payload)
    assert report["flagged"]
    assert report["clean_samples"]
    assert any("Posts grouped under" in row.get("summary", "") for row in report["flagged"])
