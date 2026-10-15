"""Tests for scripts/baseline_metrics.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.baseline_metrics import (
    flagged_planets,
    format_report,
    parse_hidden_from_log,
    posts_unsupported_title,
    total_posts,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "baseline"


def _load_data() -> dict:
    return json.loads((FIXTURES / "minimal_data.json").read_text(encoding="utf-8"))


def test_total_posts():
    assert total_posts(_load_data()) == 100


def test_unsupported_title_counts_only_failing_faces():
    posts, faces = posts_unsupported_title(_load_data())
    assert posts == 20
    assert faces == 1


def test_hidden_log_parts_and_totals():
    log = (FIXTURES / "minimal_log.txt").read_text(encoding="utf-8")
    hidden = parse_hidden_from_log(log)
    assert hidden["noise"] == 10
    assert hidden["catch_all_leftover"] == 3
    assert hidden["stayed_off_face"] == 2
    assert hidden["thin_fragments"] == 4
    assert hidden["grouping_controls"] == 9
    assert hidden["hidden_total"] == 19


def test_hidden_log_prefers_end_of_run_unique_lines():
    """Global and section passes both log the same thin fragment and leftover."""
    log = (FIXTURES / "deduped_log.txt").read_text(encoding="utf-8")
    hidden = parse_hidden_from_log(log)
    assert hidden["noise"] == 10
    assert hidden["thin_fragments"] == 4
    assert hidden["catch_all_leftover"] == 5
    assert hidden["stayed_off_face"] == 3
    assert hidden["grouping_controls"] == 12
    assert hidden["hidden_total"] == 22


def test_ad4e6f3_planets_same_side_and_negative():
    data = json.loads((FIXTURES / "ad4e6f3_planets.json").read_text(encoding="utf-8"))
    flagged = {row["name"]: row for row in flagged_planets(data)}
    assert "Gaza Genocide" in flagged
    assert "same_side" in flagged["Gaza Genocide"]["reasons"]
    assert "Maga Movement" in flagged
    assert "title_contradicts_posts" in flagged["Maga Movement"]["reasons"]
    assert "Public Execution" in flagged
    assert "same_side" in flagged["Public Execution"]["reasons"]
    assert "Trans Rights" not in flagged


def test_unsupported_title_is_labeled_informational():
    report = format_report(_load_data(), unflagged_sample=0)
    assert "informational_unsupported_title_posts: 20 (1 faces)" in report
    assert "not a done bar" in report
