"""Dry-run replay of GitHub Actions run 39260526877 (Politics 93.1% → validate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.assemble import assemble_payload
from pipeline.schema import NOISE_POLICY, validate_payload
from pipeline.section_relocate import (
    RUN_39260526877_FIXTURE,
    apply_politics_post_label_relocate,
    minimal_global_topic_from_section,
    politics_topics_from_run_39260526877_fixture,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "run_39260526877_politics_relocate.json"


def test_run_39260526877_stale_sum_without_renormalize():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    topics, posts = politics_topics_from_run_39260526877_fixture(data)
    sections = apply_politics_post_label_relocate(topics, posts, renormalize=False)
    stale = sum(float(topic["total_volume_percent"]) for topic in sections["Politics"])
    assert abs(stale - float(data["stale_politics_sum_after_relocate"])) < 0.05
    payload = {
        "last_updated": "2026-10-19",
        "total_posts": sum(int(row["post_count"]) for row in data["politics_post_counts"]),
        "window_hours": 168,
        "source": "fixture",
        "mode": "live",
        "noise_policy": NOISE_POLICY,
        "topics": [minimal_global_topic_from_section(sections["Politics"][0])],
        "sections": sections,
    }
    with pytest.raises(ValueError, match="Section 'Politics' topic volumes sum to 93.1, not 100"):
        validate_payload(payload)


def test_run_39260526877_validate_after_renormalize():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    topics, posts = politics_topics_from_run_39260526877_fixture(data)
    sections = apply_politics_post_label_relocate(topics, posts, renormalize=True)
    politics_sum = sum(float(topic["total_volume_percent"]) for topic in sections["Politics"])
    culture_sum = sum(float(topic["total_volume_percent"]) for topic in sections["Culture"])
    assert abs(politics_sum - 100.0) < 0.15
    assert abs(culture_sum - 100.0) < 0.15
    assert sections["Culture"][0]["name"] == "Tax Purposes"
    payload = assemble_payload(
        [minimal_global_topic_from_section(sections["Politics"][0])],
        mode="live",
        source="fixture",
        total_posts=sum(int(row["post_count"]) for row in data["politics_post_counts"]),
        last_updated="2026-10-19",
        sections=sections,
    )
    validate_payload(payload)
    assert RUN_39260526877_FIXTURE.is_file()
