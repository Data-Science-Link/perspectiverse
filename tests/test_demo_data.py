from pipeline.generate_demo_data import build_demo_payload, validate_payload


def test_demo_payload_matches_ui_contract():
    payload = build_demo_payload()
    validate_payload(payload)
    assert payload["total_posts"] == 100_000
    assert len(payload["topics"]) == 10
    assert payload["topics"][0]["id"] == 1
    assert payload["topics"][0]["total_volume_percent"] >= payload["topics"][-1]["total_volume_percent"]


def test_each_planet_has_six_faces_and_posts():
    payload = build_demo_payload()
    for topic in payload["topics"]:
        assert len(topic["perspectives"]) == 6
        for face in topic["perspectives"]:
            assert len(face["representative_posts"]) >= 2
            assert all("likes" in post for post in face["representative_posts"])
