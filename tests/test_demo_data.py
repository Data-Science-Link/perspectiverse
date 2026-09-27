from pipeline.generate_demo_data import build_demo_payload, validate_payload


def test_demo_payload_matches_ui_contract():
    payload = build_demo_payload()
    validate_payload(payload)
    assert payload["total_posts"] == 100_000
    assert payload["mode"] == "demo"
    assert payload["source"] == "synthetic"
    assert payload["window_hours"] == 168
    assert len(payload["topics"]) == 10
    assert payload["topics"][0]["id"] == 1
    assert payload["topics"][0]["category"]
    assert payload["topics"][0]["total_volume_percent"] >= payload["topics"][-1]["total_volume_percent"]
    assert {topic["category"] for topic in payload["topics"]} >= {
        "Politics",
        "Sports",
        "Technology",
        "Economy",
        "Environment",
        "Health",
        "Education",
        "Media",
    }


def test_each_planet_has_two_to_six_faces_and_posts():
    payload = build_demo_payload()
    counts = {topic["id"]: len(topic["perspectives"]) for topic in payload["topics"]}
    assert counts[1] == 6
    assert counts[2] == 4
    assert counts[6] == 2
    assert min(counts.values()) >= 2
    assert max(counts.values()) <= 6
    assert len(set(counts.values())) > 1
    for topic in payload["topics"]:
        for face in topic["perspectives"]:
            assert len(face["representative_posts"]) >= 2
            assert all("likes" in post for post in face["representative_posts"])
