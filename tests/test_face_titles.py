"""Face title repair: duplicates and unsupported titles (#229, #151)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pipeline.face_titles import (
    count_duplicate_title_faces,
    is_readable_face_phrase,
    repair_payload_face_titles,
    repair_published_face_titles,
    title_covers_posts,
)
from pipeline.label import titles_alike
from pipeline.story_attach import merge_alike_published_faces
from scripts.baseline_metrics import posts_unsupported_title

LIVE_DATA = Path("/tmp/live-data.json")

BAD_SALAD = (
    "Data Believe Center",
    "Rather Instead",
    "Actual Wait",
    "Okay",
    "Weekend Purposes",
    "Time Again Decision",
    "Functional Platforms",
)


def _post(uri: str, text: str, likes: int = 1) -> dict:
    return {"uri": uri, "author": "u", "clean_text": text, "text": text, "likes": likes}


def test_title_covers_posts_matches_live_bar():
    outrage = [
        {"text": "Social media posts spark outrage and generate debate about discrimination."},
        {"text": "People are furious about a trans man in the Odyssey and the casting."},
        {"text": "The grooming meme treats misconduct allegations like a fandom war."},
    ]
    artists = [
        {"text": "Stop spreading AI-generated slop. Small artists cannot thrive."},
        {"text": "Artists do get it. Artists love new tools that are not generative slop."},
        {"text": "AI ripped the passion out of my writing."},
    ]
    assert not title_covers_posts("Outrage Over Issues", outrage)
    assert title_covers_posts("Artists Reject AI", artists)


def test_readable_phrase_rejects_product_review_salad():
    for phrase in BAD_SALAD:
        assert not is_readable_face_phrase(phrase)


def test_readable_phrase_accepts_verbatim_claim_span():
    assert is_readable_face_phrase("ledger chip")
    assert is_readable_face_phrase("chip shortage")
    assert is_readable_face_phrase("trans rights")
    assert is_readable_face_phrase("press secretary")
    assert is_readable_face_phrase("AI Use")


def test_readable_phrase_rejects_weak_verbatim_spans():
    assert not is_readable_face_phrase("shooting")
    assert not is_readable_face_phrase("write good fics")
    assert not is_readable_face_phrase("using this Platform")
    assert not is_readable_face_phrase("wasn't")
    assert not is_readable_face_phrase("any capacity makes")


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
    assert topic["perspectives"][0]["post_count"] == 10


def test_repair_renames_smaller_alike_face_from_post_words():
    posts = [
        _post("a", "Democrats abandoned transgender rights again at the rally.", 5),
        _post("b", "The party walked away from trans healthcare promises.", 4),
        _post("c", "Trans rights matter and must be defended loudly.", 10),
        _post("d", "Protect trans kids in schools everywhere.", 9),
    ]
    topic = {
        "id": 3,
        "name": "Trans Rights Debate",
        "post_count": 28,
        "perspectives": [
            {
                "id": "3A",
                "title": "Trans Rights",
                "summary": "Defend trans rights.",
                "post_count": 19,
                "top_terms": ["trans", "rights"],
                "representative_posts": [posts[2], posts[3]],
                "_face_member_uris": ["c", "d"],
            },
            {
                "id": "3B",
                "title": "Trans Rights",
                "summary": "Party abandoned trans people.",
                "post_count": 9,
                "top_terms": ["democrats", "abandoned", "transgender"],
                "representative_posts": [posts[0], posts[1]],
                "_face_member_uris": ["a", "b"],
            },
        ],
    }
    post_by_uri = {str(post["uri"]): post for post in posts}
    assert count_duplicate_title_faces(topics=[topic]) == 2
    stats = repair_published_face_titles([topic], posts=None, post_by_uri=post_by_uri)
    assert stats["merged"] + stats["duplicate_renamed"] >= 1
    assert count_duplicate_title_faces(topics=[topic]) == 0
    titles = [face["title"] for face in topic["perspectives"]]
    assert len(titles) >= 1
    if len(titles) == 2:
        assert not titles_alike(titles[0], titles[1])
    for rename in stats["renames"]:
        assert is_readable_face_phrase(rename["new"])


def test_unsupported_title_is_replaced_with_verbatim_post_phrase():
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
                "top_terms": ["ledger", "chip", "shortage"],
                "representative_posts": posts,
                "_face_member_uris": ["1", "2", "3"],
            }
        ],
    }
    post_by_uri = {str(post["uri"]): post for post in posts}
    stats = repair_published_face_titles([topic], post_by_uri=post_by_uri)
    title = topic["perspectives"][0]["title"]
    assert title != "Toxic Workplaces"
    assert is_readable_face_phrase(title)
    assert title_covers_posts(title, posts)
    assert stats["unsupported_renamed"] == 1


def test_weak_planet_name_use_becomes_ai_use():
    posts = [
        _post(
            f"p{index}",
            "Schools and workplaces keep arguing about AI use, AI assistants, and AI taking jobs.",
            5 - index,
        )
        for index in range(6)
    ]
    topic = {
        "id": 9,
        "name": "Use",
        "post_count": 739,
        "perspectives": [
            {
                "id": "9A",
                "title": "AI Use Judged",
                "summary": "People judge AI use harshly.",
                "post_count": 739,
                "top_terms": ["ai", "assistants", "jobs"],
                "representative_posts": posts[:3],
                "_face_member_uris": [f"p{index}" for index in range(6)],
            }
        ],
    }
    post_by_uri = {str(post["uri"]): post for post in posts}
    stats = repair_published_face_titles([topic], post_by_uri=post_by_uri)
    assert topic["name"] == "AI Use"
    assert stats["planet_renamed"] == 1
    assert any(row["reason"] == "planet_name" for row in stats["renames"])


def test_unsupported_title_stays_when_no_readable_phrase():
    posts = [
        _post("1", "Okay wait again rather instead actual time weekend.", 1),
        _post("2", "Okay wait again rather instead actual time weekend.", 1),
    ]
    topic = {
        "id": 1,
        "name": "Noise",
        "post_count": 2,
        "perspectives": [
            {
                "id": "1A",
                "title": "Witch Hunt",
                "summary": "Wrong.",
                "post_count": 2,
                "representative_posts": posts,
                "_face_member_uris": ["1", "2"],
            }
        ],
    }
    post_by_uri = {str(post["uri"]): post for post in posts}
    stats = repair_published_face_titles([topic], post_by_uri=post_by_uri)
    assert topic["perspectives"][0]["title"] == "Witch Hunt"
    assert stats["unsupported_renamed"] == 0
    assert stats["still_unsupported"]


def test_live_data_duplicate_faces_go_to_zero_after_repair():
    if not LIVE_DATA.is_file():
        return
    data = json.loads(LIVE_DATA.read_text(encoding="utf-8"))
    before = count_duplicate_title_faces(data)
    payload = copy.deepcopy(data)
    repair_payload_face_titles(payload)
    after = count_duplicate_title_faces(payload)
    assert after == 0
    assert before >= 0


def test_live_renames_are_readable_not_salad():
    if not LIVE_DATA.is_file():
        return
    data = json.loads(LIVE_DATA.read_text(encoding="utf-8"))
    payload = copy.deepcopy(data)
    stats = repair_payload_face_titles(payload)
    for rename in stats["renames"]:
        assert is_readable_face_phrase(rename["new"])
        assert rename["new"].lower() not in {item.lower() for item in BAD_SALAD}
