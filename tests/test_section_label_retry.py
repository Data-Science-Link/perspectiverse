"""End-of-draft retry and the section ceiling (#210).

Skipped sections are marked only when the main pass stops. The retry has its
own reserved slice of the draft window, so these tests drive the scheduler
instead of planting ``skipped_budget`` on a deadline that is still in the future.
"""

from __future__ import annotations

import time

import numpy as np

from pipeline import live
from pipeline.label import (
    LABEL_READ_TIMEOUT_DEFAULT,
    LabelBudgetExceeded,
    get_label_deadline,
    reset_label_latency_samples,
    reset_label_timeout_circuit,
    set_label_deadline,
    _openai_generate,
)
from tests.test_section_pool import _network_context, _planet_result, _settings


def _job(name: str, keep: int, candidates: int, posts: int) -> live._SectionLabelJob:
    topics = [
        {"id": index, "terms": [name], "member_indices": [0], "size": 1} for index in range(candidates)
    ]
    return live._SectionLabelJob(name, [], {"topics": topics}, keep, {"section": name}, posts)


def test_draft_timed_out_detects_timeout_log():
    assert live._draft_timed_out(["Dropping candidate 3: drafting failed (RuntimeError: timed out)."])
    assert not live._draft_timed_out(["Dropping candidate 3: drafting failed (RuntimeError: HTTP 500)."])


def test_main_pass_reserves_one_read_for_the_retry(monkeypatch):
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    section = 30 * 60
    draft = live._section_draft_deadline(section)
    main = live._section_main_deadline(draft)
    assert draft == section - live.SECTION_RELABEL_RESERVE_SECONDS
    assert main == draft - live.SECTION_LABEL_RETRY_RESERVE_SECONDS
    assert live.SECTION_LABEL_RETRY_RESERVE_SECONDS == 45.0
    # A short ceiling still leaves half the draft window for the main pass.
    short_draft = live._section_draft_deadline(30.0)
    assert live._section_main_deadline(short_draft) == short_draft - (short_draft / 2.0)


def test_no_retry_after_the_deadline(monkeypatch):
    """The scheduler records the timeout. The retry does not run once the deadline is due."""
    clock = {"now": 5_000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    calls = []

    def draft(posts, clustered, topic, context):
        calls.append(topic["id"])
        raise RuntimeError("The read operation timed out")

    monkeypatch.setattr(live, "_draft_planet", draft)
    job = _job("World", 2, 1, posts=40)
    live._label_section_jobs([job], 1, clock["now"] + 100)
    assert calls == [0]
    assert job.timeout_candidates
    assert job.timeout_candidates[0][1]["id"] == 0
    clock["now"] = 5_100.0
    live._retry_section_labeling([job], 1, 5_100.0)
    assert calls == [0]


def test_built_planet_is_kept_and_a_full_catalog_does_not_drop_the_next_section(monkeypatch):
    """State comes from the scheduler: a timeout, then a built planet, per section.

    World fills its catalog. Health still has room. The old ``break`` stopped
    at World and never retried Health.
    """
    clock = {"now": 1_000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    calls = []

    def draft(posts, clustered, topic, context):
        key = (context["section"], topic["id"])
        calls.append(key)
        if topic["id"] == 0 and calls.count(key) == 1:
            raise RuntimeError("The read operation timed out")
        return _planet_result(f"{context['section']} {topic['id']}"), []

    monkeypatch.setattr(live, "_draft_planet", draft)
    world = _job("World", 1, 2, posts=80)
    health = _job("Health", 2, 2, posts=20)
    deadline = clock["now"] + 500
    live._label_section_jobs([world, health], 1, deadline)
    assert [topic["name"] for topic in world.built] == ["World 1"]
    assert [topic["name"] for topic in health.built] == ["Health 1"]
    world_planet = world.built[0]
    health_planet = health.built[0]
    assert world.timeout_candidates and health.timeout_candidates

    live._retry_section_labeling([world, health], 1, deadline)

    assert world.built[0] is world_planet
    assert health.built[0] is health_planet
    assert calls.count(("World", 0)) == 1
    assert calls.count(("World", 1)) == 1
    assert calls.count(("Health", 0)) == 2
    assert calls.count(("Health", 1)) == 1
    assert [topic["name"] for topic in health.built] == ["Health 1", "Health 0"]
    assert len(world.built) == 1


def test_skipped_section_is_retried_inside_the_reserved_window(monkeypatch):
    """The main pass marks the untouched section skipped, and the reserve labels it."""
    clock = {"now": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    drafted: list[str] = []

    def draft(posts, clustered, topic, context):
        deadline = get_label_deadline()
        now = time.monotonic()
        if deadline is not None and deadline - now < LABEL_READ_TIMEOUT_DEFAULT:
            raise LabelBudgetExceeded(
                f"{deadline - now:.1f}s left in the section time budget, need {LABEL_READ_TIMEOUT_DEFAULT:.1f}s"
            )
        clock["now"] = now + LABEL_READ_TIMEOUT_DEFAULT
        drafted.append(str(context["section"]))
        return _planet_result(f"{context['section']} {topic['id']}"), []

    def cluster_texts(texts, **kwargs):
        name = texts[0].split()[0]
        count = 40 if name == "World" else 5
        return {
            "topics": [
                {"id": index, "size": 8, "member_indices": [0], "terms": [name]} for index in range(count)
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [],
            "noise_count": 0,
        }

    monkeypatch.setattr(live, "_draft_planet", draft)
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    posts = []
    for name, count in (("World", 40), ("Health", 16)):
        for index in range(count):
            posts.append(
                {
                    "uri": f"at://{name}/{index}",
                    "author": f"{name}.{index}",
                    "clean_text": f"{name} claim {index}",
                    "text": f"{name} claim {index}",
                    "section": name,
                    "likes": 0,
                }
            )
    sections = live._cluster_sections(
        posts,
        np.zeros((len(posts), 4)),
        _settings(),
        100,
        8,
        context=_network_context(1),
        deadline=30 * 60,
    )
    assert clock["now"] <= 24 * 60
    assert clock["now"] <= 30 * 60
    assert "Health" in drafted
    assert "World" in drafted
    assert "Health" in sections
    assert sections["Health"]
    # World kept the planets it built before the retry. Health was the skipped section.
    assert len(sections["World"]) >= 1


def test_section_phase_ends_by_its_ceiling(monkeypatch):
    """A dead provider's reads stop at the draft ceiling instead of running past 30 minutes."""
    clock = {"now": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(time, "sleep", lambda seconds: clock.__setitem__("now", clock["now"] + float(seconds)))
    reset_label_latency_samples()
    reset_label_timeout_circuit()
    set_label_deadline(None)
    reads = []

    def fake_read_json(url, *, timeout, data=None, headers=None):
        deadline = get_label_deadline()
        now = time.monotonic()
        reads.append((now, float(timeout), None if deadline is None else deadline))
        if deadline is not None:
            assert deadline - now >= float(timeout) - 1e-6
        clock["now"] = now + float(timeout)
        raise RuntimeError("The read operation timed out")

    def draft(posts, clustered, topic, context):
        for _call in range(16):
            try:
                _openai_generate("prompt", "model")
            except LabelBudgetExceeded:
                raise
            except RuntimeError:
                continue
        raise RuntimeError("The read operation timed out")

    def cluster_texts(texts, **kwargs):
        return {
            "topics": [
                {"id": index, "size": 8, "member_indices": [0], "terms": ["World"]} for index in range(8)
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [],
            "noise_count": 0,
        }

    monkeypatch.setattr("pipeline.label.read_json", fake_read_json)
    monkeypatch.setattr(live, "_draft_planet", draft)
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    posts = [
        {
            "uri": f"at://World/{index}",
            "author": f"World.{index}",
            "clean_text": f"World claim {index}",
            "text": f"World claim {index}",
            "section": "World",
            "likes": 0,
        }
        for index in range(24)
    ]
    live._cluster_sections(
        posts,
        np.zeros((len(posts), 4)),
        _settings(),
        10,
        8,
        context=_network_context(1),
        deadline=30 * 60,
    )
    assert reads
    assert clock["now"] <= 24 * 60
    assert clock["now"] <= 30 * 60
    # The relabel reserve starts at 24 minutes. No read runs into it.
    assert max(start + timeout for start, timeout, _deadline in reads) <= 24 * 60 + 1e-6
