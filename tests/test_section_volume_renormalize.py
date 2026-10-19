"""Section topic volumes must sum to 100 after planets are relocated (#257)."""

from pipeline.assemble import assemble_payload
from pipeline.live import _assign_section_topic_ids, publish_volumes
from pipeline.schema import NOISE_POLICY
from pipeline.section_sanity import partition_politics_planets


def _politics_topic(name: str, post_count: int, member_uris: list[str], face_id: str):
    return {
        "id": 1,
        "name": name,
        "category": "Politics",
        "post_count": post_count,
        "total_volume_percent": 0.0,
        "summary": "Summary for tests.",
        "perspectives": [
            {
                "id": face_id,
                "title": "Policy view",
                "summary": "Posts share one civic claim.",
                "volume_percent": 100.0,
                "arguments": ["First concrete reason.", "Second concrete reason."],
                "representative_posts": [
                    {
                        "author": "ada",
                        "text": "Congress should publish mail ballot rules before November.",
                        "likes": 2,
                    },
                ],
            }
        ],
        "_member_uris": member_uris,
    }


def test_politics_section_renormalizes_after_planets_relocated():
    posts = [
        {"uri": "a", "text": "youtu.be/x #musicsky"},
        {"uri": "b", "text": "youtu.be/y #musicsky"},
    ]
    topics = [
        _politics_topic("Senate Vote", 93, [], "1A"),
        _politics_topic("Music Videos", 7, ["a", "b"], "2A"),
    ]
    publish_volumes(topics)
    kept, moved = partition_politics_planets(topics, posts)
    assert moved.get("Culture")
    stale_sum = sum(float(topic["total_volume_percent"]) for topic in kept)
    assert 92.0 < stale_sum < 94.0

    publish_volumes(kept)
    politics = _assign_section_topic_ids("Politics", kept)

    global_topic = {
        **politics[0],
        "id": 1,
        "category": "Politics",
        "perspectives": [
            {**politics[0]["perspectives"][0], "id": "1A"},
        ],
        "total_volume_percent": 100.0,
    }
    payload = assemble_payload(
        [global_topic],
        mode="live",
        source="fixture",
        total_posts=100,
        last_updated="2026-10-19",
        sections={"Politics": politics},
    )
    section_sum = sum(float(topic["total_volume_percent"]) for topic in payload["sections"]["Politics"])
    assert abs(section_sum - 100.0) < 0.15
    assert payload["noise_policy"] == NOISE_POLICY
