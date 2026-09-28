"""Shared data.json contract for the demo writer and the live pipeline."""

from __future__ import annotations

from collections import Counter
from typing import Any

WINDOW_HOURS = 168
MODES = frozenset({"demo", "live"})
SOURCES = frozenset({"synthetic", "bluesky", "fixture"})
# One sky is always this many planets. The saved catalog can be larger so each
# category can fill its own sky when the user switches modes.
SKY_SIZE = 10
CATEGORIES = (
    "Politics",
    "Sports",
    "Technology",
    "Economy",
    "Environment",
    "Health",
    "Education",
    "Media",
    "Entertainment",
    "Religion",
)
NOISE_POLICY = "Topic -1 is dropped and excluded from the volume denominator."
MIN_FACES = 2
MAX_FACES = 6

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Sports": ("sport", "football", "soccer", "league", "player", "game", "coach"),
    "Health": ("health", "hospital", "vaccine", "clinic", "covid", "patient"),
    "Education": ("school", "student", "teacher", "tuition", "campus", "education"),
    "Environment": ("climate", "emission", "wildfire", "energy", "drought", "carbon"),
    "Politics": ("election", "border", "senate", "vote", "congress", "policy", "immigration"),
    "Technology": ("software", "privacy", "algorithm", "model", "ai", "app", "data"),
    "Economy": ("housing", "rent", "wage", "labor", "market", "price", "job"),
    "Media": ("headline", "news", "media", "journalist", "trust", "newspaper"),
    "Entertainment": ("film", "movie", "music", "concert", "celebrity", "streaming", "actor", "album"),
    "Religion": ("church", "faith", "god", "prayer", "mosque", "clergy", "religious", "secular"),
}


def to_percents(counts: list[int]) -> list[float]:
    """Turn counts into percentages that sum to exactly 100.0 at one decimal."""
    total = sum(counts)
    if total <= 0:
        raise ValueError("Cannot compute percentages for an empty group")

    exact = [count * 1000 / total for count in counts]
    tenths = [int(round(value)) for value in exact]
    drift = 1000 - sum(tenths)
    order = sorted(range(len(counts)), key=lambda index: (-counts[index], index))
    cursor = 0
    while drift != 0:
        index = order[cursor % len(order)]
        step = 1 if drift > 0 else -1
        tenths[index] += step
        drift -= step
        cursor += 1
        if cursor > 10000:
            raise ValueError("Could not reconcile percentage rounding")
    return [value / 10 for value in tenths]


def infer_category(name: str, terms: list[str]) -> str:
    """Map a topic label onto one precomputed sidebar category."""
    blob = " ".join([name, *terms]).lower()
    scores = {
        category: sum(1 for word in words if word in blob)
        for category, words in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=lambda category: (scores[category], category))
    if scores[best] == 0:
        return "Media"
    return best


def validate_payload(payload: dict[str, Any]) -> None:
    """Fail fast if a snapshot drifts from the contract the UI expects."""
    if payload.get("mode") not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}")
    if payload.get("source") not in SOURCES:
        raise ValueError(f"source must be one of {sorted(SOURCES)}")
    if payload.get("window_hours") != WINDOW_HOURS:
        raise ValueError(f"window_hours must be {WINDOW_HOURS}")
    if payload.get("noise_policy") != NOISE_POLICY:
        raise ValueError("noise_policy is missing or does not match the documented rule")
    if not payload.get("last_updated"):
        raise ValueError("last_updated is required")

    topics = payload.get("topics") or []
    if len(topics) < SKY_SIZE:
        raise ValueError(f"Expected at least {SKY_SIZE} topics, found {len(topics)}")

    topic_volume = 0.0
    seen_topic_ids: set[int] = set()
    for topic in topics:
        topic_id = topic["id"]
        if topic_id in seen_topic_ids:
            raise ValueError(f"Duplicate topic id {topic_id}")
        seen_topic_ids.add(topic_id)
        if not topic.get("name"):
            raise ValueError(f"Topic {topic_id} is missing a name")
        if topic.get("category") not in CATEGORIES:
            raise ValueError(f"Topic {topic_id} has an unknown category")
        perspectives = topic.get("perspectives") or []
        if not MIN_FACES <= len(perspectives) <= MAX_FACES:
            raise ValueError(
                f"Topic {topic_id} should have {MIN_FACES}-{MAX_FACES} perspectives, "
                f"found {len(perspectives)}"
            )
        topic_volume += float(topic["total_volume_percent"])
        face_volume = 0.0
        seen_faces: set[str] = set()
        for face in perspectives:
            face_id = face["id"]
            if face_id in seen_faces:
                raise ValueError(f"Duplicate perspective id {face_id}")
            seen_faces.add(face_id)
            if not face.get("title") or not face.get("summary"):
                raise ValueError(f"Perspective {face_id} needs a title and summary")
            posts = face.get("representative_posts") or []
            if not posts:
                raise ValueError(f"Perspective {face_id} needs representative posts")
            for post in posts:
                if "likes" not in post or "text" not in post or "author" not in post:
                    raise ValueError(f"Perspective {face_id} posts need author, text, and likes")
            face_volume += float(face["volume_percent"])
        if abs(face_volume - 100.0) > 0.15:
            raise ValueError(f"Topic {topic_id} perspective volumes sum to {face_volume}, not 100")

    if abs(topic_volume - 100.0) > 0.15:
        raise ValueError(f"Topic volumes sum to {topic_volume}, not 100")

    # Demo catalogs are a full sky per category so the dropdown never empties.
    if payload.get("mode") == "demo":
        counts = Counter(topic["category"] for topic in topics)
        missing = [category for category in CATEGORIES if counts.get(category, 0) < SKY_SIZE]
        if missing:
            raise ValueError(
                f"Demo catalog needs {SKY_SIZE} topics in every category; short: {missing}"
            )
