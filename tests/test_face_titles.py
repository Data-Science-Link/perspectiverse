"""Face title repair: exact duplicate merge and coverage (#229)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pipeline import live
from pipeline.face_titles import (
    count_duplicate_title_faces,
    face_title_changes,
    face_titles_equal,
    normalize_face_title,
    repair_payload_face_titles,
    repair_published_face_titles,
    title_strictly_supported_by_posts,
)
from pipeline.story_attach import merge_alike_published_faces

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "face_titles_snapshot.json"


def _post(uri: str, text: str, likes: int = 1) -> dict:
    return {"uri": uri, "author": "u", "clean_text": text, "text": text, "likes": likes}


def test_face_titles_equal_not_subset():
    assert face_titles_equal("Frost Advisory", "Frost Advisory")
    assert not face_titles_equal("Frost Advisory", "Frost Advisory Ended")
    assert normalize_face_title("Pro Ukraine 2") == normalize_face_title("Pro Ukraine")


def test_publish_path_keeps_loose_stem_coverage():
    outrage = [
        {"text": "Social media posts spark outrage and generate debate about discrimination."},
        {"text": "People are furious about a trans man in the Odyssey and the casting."},
        {"text": "The grooming meme treats misconduct allegations like a fandom war."},
    ]
    artists = [
        {"text": "Stop spreading AI-generated slop. Small artists cannot thrive."},
        {"text": "Small artists do get it when the tools are not generative slop."},
        {"text": "AI ripped the passion out of my writing."},
    ]
    assert not live._title_covers_posts("Outrage Over Issues", outrage)
    assert live._title_covers_posts("Artists Reject AI", artists)


def test_strict_reporting_requires_every_title_word():
    outrage = [
        {"text": "Social media posts spark outrage and generate debate about discrimination."},
        {"text": "People are furious about a trans man in the Odyssey and the casting."},
        {"text": "The grooming meme treats misconduct allegations like a fandom war."},
    ]
    artists = [
        {"text": "Stop spreading AI-generated slop. Small artists cannot thrive."},
        {"text": "Small artists do get it when the tools are not generative slop."},
        {"text": "AI ripped the passion out of my writing."},
    ]
    assert not title_strictly_supported_by_posts("Outrage Over Issues", outrage)
    assert not title_strictly_supported_by_posts("AI Use", artists)
    assert title_strictly_supported_by_posts("Small Artists", artists)


def test_merge_alike_works_with_section_string_planet_id():
    topic = {
        "id": "World-7",
        "name": "WWII Veterans",
        "post_count": 10,
        "perspectives": [
            {
                "id": "World-7A",
                "title": "WWII Veterans",
                "summary": "Honor the veterans.",
                "post_count": 5,
                "representative_posts": [{"text": "WWII veterans deserve honor.", "likes": 1}],
            },
            {
                "id": "World-7B",
                "title": "WWII Veterans",
                "summary": "Remember the veterans.",
                "post_count": 5,
                "representative_posts": [{"text": "Remember WWII veterans today.", "likes": 1}],
            },
        ],
    }
    folded = merge_alike_published_faces([topic])
    assert folded == 1
    assert len(topic["perspectives"]) == 1


def test_frost_advisory_and_ended_stay_separate():
    topic = {
        "id": 1,
        "name": "Frost Advisory",
        "post_count": 14,
        "perspectives": [
            {
                "id": "1A",
                "title": "Frost Advisory",
                "summary": "Advisory in effect.",
                "post_count": 9,
                "representative_posts": [{"text": "Frost advisory tonight.", "likes": 1}],
            },
            {
                "id": "1B",
                "title": "Frost Advisory Ended",
                "summary": "Frost ended.",
                "post_count": 5,
                "representative_posts": [{"text": "Frost advisory ended this morning.", "likes": 1}],
            },
        ],
    }
    assert merge_alike_published_faces([topic]) == 0
    assert len(topic["perspectives"]) == 2


def test_repair_does_not_rename_unsupported_faces():
    posts = [
        _post("1", "Ledger chip shortage is crushing small hardware shops.", 3),
        _post("2", "Ledger chip supply cannot keep up with demand.", 2),
        _post("3", "Hardware makers need ledger chips to ship devices.", 1),
    ]
    topic = {
        "id": 1,
        "name": "Ledger Chip",
        "post_count": 3,
        "perspectives": [
            {
                "id": "1A",
                "title": "Toxic Workplaces",
                "summary": "Wrong label.",
                "post_count": 3,
                "representative_posts": posts,
                "_face_member_uris": ["1", "2", "3"],
            }
        ],
    }
    post_by_uri = {str(post["uri"]): post for post in posts}
    stats = repair_published_face_titles([topic], post_by_uri=post_by_uri)
    assert topic["perspectives"][0]["title"] == "Toxic Workplaces"
    assert stats["unsupported_faces"]


def test_snapshot_fixture_duplicate_faces_go_to_zero():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    before = count_duplicate_title_faces(data)
    payload = copy.deepcopy(data)
    stats = repair_payload_face_titles(payload)
    after = count_duplicate_title_faces(payload)
    assert before > 0
    assert after == 0
    assert stats["merged"] >= 1


def test_face_title_changes_lists_merged_planet_only():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = copy.deepcopy(data)
    repair_payload_face_titles(payload)
    changes = face_title_changes(data, payload)
    assert len(changes) == 1
    assert changes[0]["planet"] == "WWII Veterans"
    assert changes[0]["before"] == ["WWII Veterans", "WWII Veterans"]
    assert changes[0]["after"] == ["WWII Veterans"]
