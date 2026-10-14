"""Tests for scripts/baseline_metrics.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.baseline_metrics import (
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
