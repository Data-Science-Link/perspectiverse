"""Face title repair: duplicates and unsupported titles (#229, #151)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pipeline.face_titles import (
    count_duplicate_title_faces,
    repair_payload_face_titles,
    repair_published_face_titles,
    title_covers_posts,
)
from pipeline.label import titles_alike
from pipeline.story_attach import merge_alike_published_faces
from scripts.baseline_metrics import posts_unsupported_title

LIVE_DATA = Path("/tmp/live-data.json")


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


def test_unsupported_title_is_replaced_with_post_words():
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
    repair_published_face_titles([topic], post_by_uri=post_by_uri)
    title = topic["perspectives"][0]["title"]
    assert title != "Toxic Workplaces"
    assert title_covers_posts(title, posts)


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


def test_live_data_unsupported_faces_drop_after_repair():
    if not LIVE_DATA.is_file():
        return
    data = json.loads(LIVE_DATA.read_text(encoding="utf-8"))
    before_posts, before_faces = posts_unsupported_title(data)
    payload = copy.deepcopy(data)
    repair_payload_face_titles(payload)
    after_posts, after_faces = posts_unsupported_title(payload)
    assert after_faces <= before_faces
    assert after_posts <= before_posts
