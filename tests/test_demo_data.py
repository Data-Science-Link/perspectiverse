from collections import Counter

from pipeline.demo_briefs import FACE_BRIEFS, FEATURED_ARGUMENTS
from pipeline.demo_catalog import CATEGORY_ROSTERS
from pipeline.generate_demo_data import DEMO_TOPICS, build_demo_payload, validate_payload
from pipeline.schema import DEMO_CATEGORIES, SYSTEM_SIZE


def test_demo_payload_matches_ui_contract():
    payload = build_demo_payload()
    validate_payload(payload)
    assert payload["total_posts"] == 100_000
    assert payload["mode"] == "demo"
    assert payload["source"] == "synthetic"
    assert payload["window_hours"] == 168
    assert len(payload["topics"]) == SYSTEM_SIZE * len(DEMO_CATEGORIES)
    assert payload["topics"][0]["total_volume_percent"] >= payload["topics"][-1]["total_volume_percent"]
    assert set(payload["topics"][i]["category"] for i in range(len(payload["topics"]))) == set(DEMO_CATEGORIES)


def test_each_category_can_fill_a_solar_system():
    payload = build_demo_payload()
    counts = Counter(topic["category"] for topic in payload["topics"])
    for category in DEMO_CATEGORIES:
        assert counts[category] == SYSTEM_SIZE
        assert len(CATEGORY_ROSTERS[category]) == SYSTEM_SIZE
    ranked = payload["topics"][:SYSTEM_SIZE]
    assert len({topic["category"] for topic in ranked}) >= 5
    names = {topic["name"] for topic in ranked}
    assert "AI Futures" in names


def test_each_planet_has_two_to_six_faces_and_posts():
    payload = build_demo_payload()
    by_name = {topic["name"]: topic for topic in payload["topics"]}
    assert len(by_name["AI Futures"]["perspectives"]) == 6
    assert len(by_name["Housing Costs"]["perspectives"]) == 4
    assert len(by_name["Border Policy"]["perspectives"]) == 2
    counts = {topic["id"]: len(topic["perspectives"]) for topic in payload["topics"]}
    assert min(counts.values()) >= 2
    assert max(counts.values()) <= 6
    assert len(set(counts.values())) > 1
    for topic in payload["topics"]:
        for face in topic["perspectives"]:
            assert len(face["representative_posts"]) >= 2
            assert all("likes" in post for post in face["representative_posts"])


PLACEHOLDER_SNIPPETS = (
    "shorter name",
    "how this cluster argues",
    "thread by the third reply",
    "the rest is branding",
    "i do not need another panel",
)


def test_every_extra_topic_has_unique_briefs():
    featured = {topic["name"] for topic in DEMO_TOPICS}
    extra = [
        name
        for roster in CATEGORY_ROSTERS.values()
        for name in roster
        if name not in featured
    ]
    assert set(FACE_BRIEFS) == set(extra)
    for name, faces in FACE_BRIEFS.items():
        assert 2 <= len(faces) <= 6
        titles = [face["title"] for face in faces]
        assert len(titles) == len(set(titles))
        for face in faces:
            blob = " ".join(
                [face["summary"], *face["arguments"], *(post["text"] for post in face["posts"])]
            ).lower()
            for snippet in PLACEHOLDER_SNIPPETS:
                assert snippet not in blob
            assert 2 <= len(face["arguments"]) <= 6
            assert len(face["posts"]) >= 2


def test_featured_and_demo_faces_include_core_arguments():
    for topic in DEMO_TOPICS:
        by_title = FEATURED_ARGUMENTS[topic["name"]]
        for face in topic["perspectives"]:
            arguments = by_title[face["title"]]
            assert 2 <= len(arguments) <= 6
            assert face["summary"] not in arguments
    payload = build_demo_payload()
    drills = next(
        face
        for topic in payload["topics"]
        if topic["name"] == "School Safety"
        for face in topic["perspectives"]
        if face["title"] == "Drills"
    )
    drills_blob = " ".join(
        [drills["summary"], *drills["arguments"], *(post["text"] for post in drills["representative_posts"])]
    ).lower()
    assert "lockdown" in drills_blob
    assert "alice" in drills_blob or "drill" in drills_blob
    assert all("shorter name" not in post["text"] for post in drills["representative_posts"])
    for topic in payload["topics"]:
        for face in topic["perspectives"]:
            assert 2 <= len(face["arguments"]) <= 6
            for snippet in PLACEHOLDER_SNIPPETS:
                assert snippet not in face["summary"].lower()

