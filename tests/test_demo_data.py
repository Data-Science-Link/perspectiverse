from collections import Counter

from pipeline.demo_catalog import CATEGORY_ROSTERS
from pipeline.generate_demo_data import build_demo_payload, validate_payload
from pipeline.schema import CATEGORIES, SYSTEM_SIZE


def test_demo_payload_matches_ui_contract():
    payload = build_demo_payload()
    validate_payload(payload)
    assert payload["total_posts"] == 100_000
    assert payload["mode"] == "demo"
    assert payload["source"] == "synthetic"
    assert payload["window_hours"] == 168
    assert len(payload["topics"]) == SYSTEM_SIZE * len(CATEGORIES)
    assert payload["topics"][0]["total_volume_percent"] >= payload["topics"][-1]["total_volume_percent"]
    assert set(payload["topics"][i]["category"] for i in range(len(payload["topics"]))) == set(CATEGORIES)


def test_each_category_can_fill_a_solar_system():
    payload = build_demo_payload()
    counts = Counter(topic["category"] for topic in payload["topics"])
    for category in CATEGORIES:
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
