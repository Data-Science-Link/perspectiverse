from pipeline.live import _assign_section_topic_ids, _renumber_planets
from pipeline.schema import NOISE_POLICY, validate_payload


def _minimal_topic(topic_id, face_id: str):
    return {
        "id": topic_id,
        "name": "Sample",
        "category": "Technology",
        "total_volume_percent": 10.0,
        "summary": "Sample summary for tests.",
        "perspectives": [
            {
                "id": face_id,
                "title": "Sample View",
                "summary": "The posts share one claim.",
                "volume_percent": 100.0,
                "arguments": ["First reason is concrete.", "Second reason is also concrete."],
                "representative_posts": [
                    {"author": "ada", "text": "Sample posts share one claim in the corpus.", "likes": 2},
                    {"author": "bea", "text": "Another sample post shares the same claim here.", "likes": 1},
                ],
            }
        ],
    }


def test_assign_section_topic_ids_prefixes_planets():
    topics = [_minimal_topic(3, "3A")]
    prefixed = _assign_section_topic_ids("Technology", topics)
    assert prefixed[0]["id"] == "Technology-3"
    assert prefixed[0]["perspectives"][0]["id"] == "Technology-3A"


def test_reused_and_topped_up_planets_do_not_share_a_section_id():
    """A global planet keeps its catalog id until publish. A top-up restarts at 1."""
    reused = _minimal_topic(8, "8A")
    reused["name"] = "Gaza Genocide"
    reused["total_volume_percent"] = 50.0
    topped = _minimal_topic(8, "8A")
    topped["name"] = "Local Election"
    topped["total_volume_percent"] = 50.0
    planets, _membership, _faces = _renumber_planets([reused, topped], [], [])
    planets = _assign_section_topic_ids("Politics", planets)
    assert [planet["id"] for planet in planets] == ["Politics-1", "Politics-2"]
    assert planets[0]["perspectives"][0]["id"] == "Politics-1A"
    assert planets[1]["perspectives"][0]["id"] == "Politics-2A"
    payload = {
        "last_updated": "2026-10-11",
        "total_posts": 100,
        "window_hours": 168,
        "source": "fixture",
        "mode": "live",
        "noise_policy": NOISE_POLICY,
        "topics": [{**_minimal_topic(1, "1A"), "total_volume_percent": 100.0}],
        "sections": {"Politics": planets},
    }
    validate_payload(payload)


def test_schema_accepts_prefixed_section_topic_ids():
    topic = _minimal_topic("Technology-3", "Technology-3A")
    payload = {
        "last_updated": "2026-10-10",
        "total_posts": 100,
        "window_hours": 168,
        "source": "fixture",
        "mode": "live",
        "noise_policy": NOISE_POLICY,
        "topics": [{**_minimal_topic(1, "1A"), "total_volume_percent": 100.0}],
        "sections": {"Technology": [{**topic, "total_volume_percent": 100.0}]},
    }
    validate_payload(payload)
