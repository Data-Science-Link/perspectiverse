"""Section solar systems share one label pool (#71).

Run 37696485020 labeled sections one after another and skipped 6 of 10 once
the 15-minute ceiling was spent (1,052s for Politics, World, Business, and
Other). These tests pin the replacement: one pool, biggest sections first,
a 20-minute ceiling, and no extra label calls.

The latency tests stub the LLM. Each planet pays for 16 sequential calls,
which is the wave time from that run (1,052s / 6 waves ≈ 175s) divided across
the 7–11s band. Calls in one planet stay serial; planets share the pool.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time

import numpy as np
import pytest

from pipeline import live
from pipeline.schema import CATEGORIES, MAX_FACES, MIN_FACES
from tests.test_faces_53 import SETTINGS, _clustered, _fake_labels, _planet_posts

# 16 calls × 11s = 176s, against the observed ~175s wave in run 37696485020.
CALLS_PER_PLANET = 16
# Post counts are the live corpus (run 37696485020). Planet counts for the four
# sections that run labeled are that run's; the six it skipped use the planet
# counts from the heuristic relabel of the same corpus.
ROSTER = (
    ("Politics", 5123, 10),
    ("World", 1286, 9),
    ("Business", 659, 4),
    ("Other", 644, 7),
    ("Technology", 630, 4),
    ("Culture", 551, 2),
    ("Environment", 304, 3),
    ("Health", 299, 2),
    ("Sports", 276, 2),
    ("Education", 228, 3),
)
assert sum(posts for _name, posts, _planets in ROSTER) == 10_000
assert [name for name, _posts, _planets in ROSTER] == [
    "Politics",
    "World",
    "Business",
    "Other",
    "Technology",
    "Culture",
    "Environment",
    "Health",
    "Sports",
    "Education",
]


class VirtualClock:
    """Records label-call cost. The slot pool, not the clock, advances ``now``."""

    def __init__(self):
        self.now = 0.0
        self.batch: list[float] | None = None

    def monotonic(self) -> float:
        return self.now

    def charge(self, seconds: float) -> None:
        if self.batch is not None:
            self.batch.append(float(seconds))
        else:
            self.now += float(seconds)


class SlotPool:
    """Threadless pool with the same submit/wait contract as the scheduler.

    Each submitted planet occupies one slot for the sum of its call latencies.
    ``wait`` completes every planet that ends at the next slot-free time, which
    matches a real pool when every planet costs the same.
    """

    def __init__(self, clock: VirtualClock, max_workers: int):
        self.clock = clock
        self.free = [0.0] * max(1, int(max_workers))
        self.queue: list[tuple] = []
        self.running: list[tuple] = []

    def submit(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()
        self.queue.append((fn, args, kwargs, future))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None

    def wait(self, futures):
        wanted = set(futures)
        self._materialize()
        mine = [item for item in self.running if item[1] in wanted]
        if not mine:
            done = {future for future in wanted if future.done()}
            return done, wanted - done
        end = min(item[0] for item in mine)
        self.clock.now = max(self.clock.now, end)
        ready = [item for item in mine if item[0] <= end + 1e-9]
        ready_ids = {id(item) for item in ready}
        self.running = [item for item in self.running if id(item) not in ready_ids]
        done = set()
        for _end, future, result in ready:
            if not future.done():
                future.set_result(result)
            done.add(future)
        return done, wanted - done

    def _materialize(self) -> None:
        queued, self.queue = self.queue, []
        for fn, args, kwargs, future in queued:
            charges: list[float] = []
            self.clock.batch = charges
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - the pool surfaces it like a thread
                future.set_exception(exc)
                continue
            finally:
                self.clock.batch = None
            if future.done():
                continue
            duration = sum(charges)
            slot = min(range(len(self.free)), key=lambda index: self.free[index])
            start = self.free[slot]
            self.free[slot] = start + duration
            self.running.append((self.free[slot], future, result))


def _install_slot_pool(monkeypatch, clock: VirtualClock) -> None:
    holder: dict = {}

    class Factory:
        def __init__(self, max_workers=1):
            holder["pool"] = SlotPool(clock, max_workers)

        def submit(self, fn, *args, **kwargs):
            return holder["pool"].submit(fn, *args, **kwargs)

        def shutdown(self, wait=True):
            return None

    def wait(futures, timeout=None, return_when=None):
        return holder["pool"].wait(futures)

    monkeypatch.setattr(live, "ThreadPoolExecutor", Factory)
    monkeypatch.setattr(live, "wait", wait)
    monkeypatch.setattr(time, "monotonic", clock.monotonic)


def _roster_inputs():
    posts = []
    for name, post_count, _planets in ROSTER:
        for index in range(post_count):
            posts.append(
                {
                    "uri": f"at://{name}/{index}",
                    "author": f"{name}.{index}",
                    "clean_text": f"{name} claim words {index}",
                    "text": f"{name} claim words {index}",
                    "section": name,
                    "likes": 0,
                }
            )
    return posts, np.zeros((len(posts), 4))


def _cluster_stub(texts, **kwargs):
    name = texts[0].split()[0]
    planets = {item[0]: item[2] for item in ROSTER}[name]
    return {
        "topics": [
            {"id": index, "size": 10, "member_indices": [index], "terms": [name, "claim"]}
            for index in range(planets)
        ],
        "matrix": kwargs["embed"](texts),
        "assignments": [],
        "noise_count": 0,
    }


def _planet_result(name: str):
    return {
        "planet": {
            "id": 1,
            "name": name,
            "category": "World",
            "total_volume_percent": 0.0,
            "post_count": 10,
            "perspectives": [
                {
                    "id": "1A",
                    "title": f"{name} alpha",
                    "summary": f"{name} alpha is the claim.",
                    "volume_percent": 60,
                    "post_count": 6,
                },
                {
                    "id": "1B",
                    "title": f"{name} beta",
                    "summary": f"{name} beta is the claim.",
                    "volume_percent": 40,
                    "post_count": 4,
                },
            ],
        },
        "membership": [],
        "face_rows": [],
    }


def _settings():
    return {
        **SETTINGS,
        "min_cluster_size": 8,
        "cluster_backend": "embedding",
        "embedding_model": "unused",
    }


def _network_context(workers: int = 8):
    return {
        "workers": workers,
        "backend": "openai",
        "model": "m",
        "chosen": "openai",
        "summary_model": None,
        "limit": 6,
        "seed": 0,
    }


def _old_serial(latency: float, *, workers: int = 8, ceiling: float = 15 * 60):
    """The pre-#71 loop: finish a section, then start the next, 8 at a time."""
    planet_s = CALLS_PER_PLANET * latency
    now = 0.0
    done = []
    for name, _posts, count in ROSTER:
        if now >= ceiling:
            break
        waves = (count + workers - 1) // workers
        now += waves * planet_s
        done.append(name)
    return done, now


def test_section_budget_zero_skips_and_none_is_twenty_minutes():
    assert live.DEFAULT_SECTION_BUDGET_MINUTES == 20
    assert live._section_budget_minutes(None) == 20
    assert live._section_budget_minutes(0) == 0
    assert live._section_budget_minutes(0.0) == 0
    assert live._section_budget_minutes(15) == 15


def test_section_pool_is_twelve_at_the_default_and_honors_other_caps():
    assert live._section_pool_size({"workers": 1}) == 1
    assert live._section_pool_size({"workers": 8}) == 12
    assert live._section_pool_size({"workers": 4}) == 4
    assert live._section_pool_size({"workers": 12}) == 12
    assert live._section_pool_size({"workers": 16}) == 16


@pytest.mark.parametrize("latency", [7.0, 11.0])
def test_all_ten_sections_finish_within_twenty_minutes(monkeypatch, latency):
    """Stubbed calls at 7s and at 11s. The shared pool finishes all 10 sections."""
    clock = VirtualClock()
    _install_slot_pool(monkeypatch, clock)
    drafted = []

    def draft(posts, clustered, topic, context):
        for _call in range(CALLS_PER_PLANET):
            clock.charge(latency)
        drafted.append((topic["terms"][0], topic["id"]))
        return _planet_result(f"{topic['terms'][0]} {topic['id']}"), []

    monkeypatch.setattr(live, "cluster_texts", _cluster_stub)
    monkeypatch.setattr(live, "_draft_planet", draft)
    posts, matrix = _roster_inputs()
    sections = live._cluster_sections(
        posts,
        matrix,
        _settings(),
        10,
        8,
        context=_network_context(8),
        deadline=clock.monotonic() + 20 * 60,
    )
    assert list(sections) == [name for name in CATEGORIES if name in sections]
    assert set(sections) == {name for name, _posts, _planets in ROSTER}
    for name, _posts, planets in ROSTER:
        assert len(sections[name]) == planets
        assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in sections[name])
    assert clock.now < 20 * 60, f"shared pool took {clock.now:.0f}s"
    # One draft per surviving planet. No spare candidates were labeled.
    assert len(drafted) == sum(planets for _name, _posts, planets in ROSTER)
    if latency == 11.0:
        old_done, old_elapsed = _old_serial(latency)
        assert old_done == ["Politics", "World", "Business", "Other"]
        assert old_elapsed > 15 * 60


def test_section_ceiling_cuts_off_after_the_biggest_sections(monkeypatch, capsys):
    """A ceiling shorter than one planet keeps the largest section and stops cleanly."""
    clock = VirtualClock()
    _install_slot_pool(monkeypatch, clock)
    drafted = []

    def draft(posts, clustered, topic, context):
        for _call in range(CALLS_PER_PLANET):
            clock.charge(11.0)
        drafted.append(topic["terms"][0])
        return _planet_result(f"{topic['terms'][0]} {topic['id']}"), []

    monkeypatch.setattr(live, "cluster_texts", _cluster_stub)
    monkeypatch.setattr(live, "_draft_planet", draft)
    posts, matrix = _roster_inputs()
    sections = live._cluster_sections(
        posts,
        matrix,
        _settings(),
        10,
        8,
        context=_network_context(8),
        deadline=30.0,
    )
    # Pool is 12. The first wave is Politics (10) plus the first 2 World planets.
    # They started before the ceiling and finish; nothing else is submitted.
    assert set(sections) == {"Politics", "World"}
    assert len(sections["Politics"]) == 10
    assert len(sections["World"]) == 2
    assert len(drafted) == 12
    log = capsys.readouterr().out
    for name in ("Technology", "Culture", "Environment", "Health", "Sports", "Education"):
        assert f"Section {name}: skipped, the section time budget is spent." in log
    assert "Business" in log and "skipped, the section time budget is spent." in log


def test_shared_pool_does_not_label_past_keep(monkeypatch):
    """Two sections, five candidates, keep 2. Four drafts, not ten."""
    base_posts = []
    blocks = []
    for section, prefix, seed in (("Health", "medicare", 12), ("World", "ukraine", 11)):
        group, block = _planet_posts(prefix, [30, 12], seed=seed)
        for post in group:
            post["section"] = section
        base_posts.extend(group)
        blocks.append(block)
    matrix = np.vstack(blocks)
    drafted = []
    original = live._draft_planet

    def counting(posts, clustered, topic, context):
        drafted.append((posts[0]["section"], topic["id"]))
        return original(posts, clustered, topic, context)

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    def cluster_texts(texts, **kwargs):
        prefix = texts[0].split()[0]
        # One real split-able topic, plus four more that reuse the same members.
        topics = [
            {"id": index, "size": len(texts), "member_indices": list(range(len(texts))), "terms": [prefix]}
            for index in range(5)
        ]
        return {
            "topics": topics,
            "matrix": kwargs["embed"](texts),
            "assignments": [0] * len(texts),
            "noise_count": 0,
        }

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    sections = live._cluster_sections(
        base_posts,
        matrix,
        _settings(),
        2,
        8,
        context=_network_context(8),
        deadline=None,
    )
    assert set(sections) == {"World", "Health"}
    world_ids = [item[1] for item in drafted if item[0] == "World"]
    health_ids = [item[1] for item in drafted if item[0] == "Health"]
    assert sorted(world_ids) == [0, 1]
    assert sorted(health_ids) == [0, 1]
    assert len(drafted) == 4
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in sections["World"])


def test_a_dropped_planet_labels_the_next_candidate_and_not_the_rest(monkeypatch):
    posts, block = _planet_posts("ukraine", [30, 12], seed=11)
    for post in posts:
        post["section"] = "World"
    drafted = []
    original = live._draft_planet

    def counting(section_posts, clustered, topic, context):
        drafted.append(topic["id"])
        if topic["id"] == 0:
            raise RuntimeError("label backend exploded")
        return original(section_posts, clustered, topic, context)

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    def cluster_texts(texts, **kwargs):
        return {
            "topics": [
                {
                    "id": index,
                    "size": len(texts),
                    "member_indices": list(range(len(texts))),
                    "terms": ["ukraine"],
                }
                for index in range(4)
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [0] * len(texts),
            "noise_count": 0,
        }

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "_draft_planet", counting)
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    sections = live._cluster_sections(
        posts,
        block,
        _settings(),
        2,
        8,
        context=_network_context(8),
        deadline=None,
    )
    assert sorted(drafted) == [0, 1, 2]
    assert drafted[-1] == 2
    assert len(sections["World"]) == 2
    assert all(MIN_FACES <= len(topic["perspectives"]) <= MAX_FACES for topic in sections["World"])


def test_one_bad_section_does_not_drop_the_other(monkeypatch, capsys):
    world = _planet_posts("ukraine", [30, 12], seed=11)
    health = _planet_posts("medicare", [30, 12], seed=12)
    posts, clustered = _clustered([world, health])
    for post in posts:
        post["section"] = "World" if post["uri"].startswith("at://ukraine") else "Health"

    def titles_for(prefix, text):
        return f"{prefix} first" if "stance0" in text else f"{prefix} second view"

    def cluster_texts(texts, **kwargs):
        if texts[0].startswith("medicare"):
            raise ValueError("section exploded")
        return {
            "topics": [
                {"id": 0, "size": len(texts), "member_indices": list(range(len(texts))), "terms": ["ukraine"]}
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [0] * len(texts),
            "noise_count": 0,
        }

    _fake_labels(monkeypatch, titles_for)
    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    sections = live._cluster_sections(
        posts,
        clustered["matrix"],
        _settings(),
        10,
        8,
        context=_network_context(8),
        deadline=None,
    )
    assert list(sections) == ["World"]
    log = capsys.readouterr().out
    assert "Section Health: skipped (ValueError: section exploded)." in log


def test_shared_pool_overlaps_real_threads(monkeypatch):
    """The production pool, not the slot model: several sections are in flight at once."""
    posts = []
    for name in CATEGORIES:
        for index in range(16):
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
    state = {"current": 0, "peak": 0}
    lock = threading.Lock()

    def draft(section_posts, clustered, topic, context):
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.15)
        with lock:
            state["current"] -= 1
        return _planet_result(f"{topic['terms'][0]} {topic['id']}"), []

    def cluster_texts(texts, **kwargs):
        name = texts[0].split()[0]
        return {
            "topics": [
                {"id": index, "size": 8, "member_indices": [index], "terms": [name]}
                for index in range(2)
            ],
            "matrix": kwargs["embed"](texts),
            "assignments": [],
            "noise_count": 0,
        }

    monkeypatch.setattr(live, "cluster_texts", cluster_texts)
    monkeypatch.setattr(live, "_draft_planet", draft)
    started = time.perf_counter()
    sections = live._cluster_sections(
        posts,
        np.zeros((len(posts), 4)),
        _settings(),
        2,
        8,
        context=_network_context(8),
        deadline=time.monotonic() + 60,
    )
    elapsed = time.perf_counter() - started
    assert list(sections) == list(CATEGORIES)
    # 12 slots, 20 planets. Serial sections would be about 10 sleeps.
    assert state["peak"] >= 8
    assert elapsed < 0.15 * len(CATEGORIES)


def test_timing_table_old_serial_versus_shared_pool(monkeypatch, capsys):
    """Evidence row: sections finished and wall time, old loop versus the shared pool."""
    latency = 11.0
    clock = VirtualClock()
    _install_slot_pool(monkeypatch, clock)

    def draft(posts, clustered, topic, context):
        for _call in range(CALLS_PER_PLANET):
            clock.charge(latency)
        return _planet_result(f"{topic['terms'][0]} {topic['id']}"), []

    monkeypatch.setattr(live, "cluster_texts", _cluster_stub)
    monkeypatch.setattr(live, "_draft_planet", draft)
    posts, matrix = _roster_inputs()
    sections = live._cluster_sections(
        posts,
        matrix,
        _settings(),
        10,
        8,
        context=_network_context(8),
        deadline=clock.monotonic() + 20 * 60,
    )
    old_done, old_elapsed = _old_serial(latency)
    new_elapsed = clock.now
    print(
        "\n".join(
            [
                "section label timing (16 calls/planet, 11s/call, stubbed)",
                f"old serial, 8 workers, 15 min ceiling: {len(old_done)} sections in {old_elapsed:.0f}s ({', '.join(old_done)})",
                f"new shared pool, 12 in flight, 20 min ceiling: {len(sections)} sections in {new_elapsed:.0f}s",
            ]
        )
    )
    assert len(old_done) == 4
    assert len(sections) == 10
    assert new_elapsed < 20 * 60
    assert new_elapsed < old_elapsed
