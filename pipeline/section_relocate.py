"""Replay helpers for post-label section planet moves (#258)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.live import _assign_section_topic_ids, publish_volumes, renormalize_section_catalogs
from pipeline.section_sanity import partition_politics_planets

RUN_39260526877_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "run_39260526877_politics_relocate.json"
)


def _policy_face(face_id: str, text: str) -> dict[str, Any]:
    return {
        "id": face_id,
        "title": "Civic view",
        "summary": "Posts share one policy claim.",
        "volume_percent": 100.0,
        "arguments": ["First concrete reason.", "Second concrete reason."],
        "representative_posts": [
            {"author": "ada", "text": text, "likes": 2},
        ],
    }


def politics_topics_from_run_39260526877_fixture(
    data: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build labeled Politics planets + member posts for the failed-run replay."""
    payload = data if data is not None else json.loads(RUN_39260526877_FIXTURE.read_text(encoding="utf-8"))
    posts: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    for index, row in enumerate(payload["politics_post_counts"]):
        name = row["name"]
        post_count = int(row["post_count"])
        uris: list[str] = []
        if name == "Tax Purposes":
            for offset, text in enumerate(payload["tax_member_texts"]):
                uri = f"tax-{offset}"
                uris.append(uri)
                posts.append({"uri": uri, "text": text})
            face = _policy_face(f"{index}A", payload["tax_member_texts"][0])
        else:
            face = _policy_face(
                f"{index}A",
                "Congress should publish mail ballot rules before November.",
            )
        topics.append(
            {
                "id": index + 1,
                "name": name,
                "category": "Politics",
                "post_count": post_count,
                "total_volume_percent": 0.0,
                "summary": "Summary for replay.",
                "perspectives": [face],
                "_member_uris": uris,
            }
        )
    return topics, posts


def minimal_global_topic_from_section(section_topic: dict[str, Any]) -> dict[str, Any]:
    return {
        **section_topic,
        "id": 1,
        "category": "Politics",
        "perspectives": [{**section_topic["perspectives"][0], "id": "1A"}],
        "total_volume_percent": 100.0,
    }


def apply_politics_post_label_relocate(
    politics_topics: list[dict[str, Any]],
    posts: list[dict[str, Any]],
    *,
    renormalize: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Mirror ``_cluster_sections`` after ``_finish_section_planets`` for Politics.

    When *renormalize* is false, section volumes stay at the pre-move shares (the
    run 39260526877 failure mode). When true, matches the fixed pipeline tail.
    """
    publish_volumes(politics_topics)
    kept, moved = partition_politics_planets(politics_topics, posts)
    result: dict[str, list[dict[str, Any]]] = {}
    if kept:
        result["Politics"] = _assign_section_topic_ids("Politics", kept)
    for dest, planets in moved.items():
        assigned = _assign_section_topic_ids(dest, planets)
        result.setdefault(dest, []).extend(assigned)
    if renormalize:
        renormalize_section_catalogs(result)
    return result
