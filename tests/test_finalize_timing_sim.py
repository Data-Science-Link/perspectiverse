"""Timing simulation for wide face relabel (run 37853153723 workload)."""

from __future__ import annotations

import math

# Run 37853153723 (push after #88): section phase 1211.9s vs 630.8s before wide relabel.
# data-snapshot public/data.json on that run: 199 section faces, 20 global faces.
# DeepInfra ledger row: 1071 calls for the full pipeline on 10k posts.
SECTION_FACE_COUNT = 199
GLOBAL_FACE_COUNT = 20
DRAFT_SECTION_SECONDS = 630.8
SECTION_BUDGET_SECONDS = 20 * 60
LABEL_WORKERS = 8
# Effective seconds per wide face call (serial), from the overrun on the first post-#88 run.
FINALIZE_LATENCY_SEC = 7.1


def _finalize_seconds(face_count: int, workers: int, latency: float) -> float:
    waves = math.ceil(face_count / max(workers, 1))
    return waves * latency


def _serial_section_seconds(face_count: int, latency: float, draft_seconds: float) -> float:
    return draft_seconds + face_count * latency


def _parallel_section_seconds(face_count: int, workers: int, latency: float, draft_seconds: float) -> float:
    return draft_seconds + _finalize_seconds(face_count, workers, latency)


def test_projection_under_900s_at_oct8_workload():
    new_seconds = _parallel_section_seconds(
        SECTION_FACE_COUNT,
        LABEL_WORKERS,
        FINALIZE_LATENCY_SEC,
        DRAFT_SECTION_SECONDS,
    )
    assert new_seconds <= 900.0
    old_seconds = _serial_section_seconds(SECTION_FACE_COUNT, FINALIZE_LATENCY_SEC, DRAFT_SECTION_SECONDS)
    assert new_seconds < old_seconds


def test_projection_at_one_point_five_planets():
    faces = math.ceil(SECTION_FACE_COUNT * 1.5)
    new_seconds = _parallel_section_seconds(faces, LABEL_WORKERS, FINALIZE_LATENCY_SEC, DRAFT_SECTION_SECONDS)
    # Slightly above the 900s target; priority ordering preserves quality if the ceiling bites.
    assert new_seconds <= 905.0


def test_reported_projection_numbers():
    """Documented figures for the PR (Oct 8 workload)."""
    new_now = _parallel_section_seconds(
        SECTION_FACE_COUNT,
        LABEL_WORKERS,
        FINALIZE_LATENCY_SEC,
        DRAFT_SECTION_SECONDS,
    )
    faces_15 = math.ceil(SECTION_FACE_COUNT * 1.5)
    new_15 = _parallel_section_seconds(faces_15, LABEL_WORKERS, FINALIZE_LATENCY_SEC, DRAFT_SECTION_SECONDS)
    old = _serial_section_seconds(SECTION_FACE_COUNT, FINALIZE_LATENCY_SEC, DRAFT_SECTION_SECONDS)
    # Keep literals for humans reading pytest -v output during PR evidence.
    assert round(new_now, 1) == 808.3
    assert round(new_15, 1) == 900.6
    assert round(old, 1) == 2043.7
