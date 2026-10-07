"""Shared data.json contract for the demo writer and the live pipeline."""

from __future__ import annotations

from collections import Counter
from typing import Any

WINDOW_HOURS = 168
MODES = frozenset({"demo", "live"})
SOURCES = frozenset({"synthetic", "bluesky", "fixture"})
# One solar system is always this many planets. The saved catalog can be larger so each
# category can fill its own solar system when the user switches modes.
SYSTEM_SIZE = 10
# Public live dropdown. Demo catalogs still use DEMO_CATEGORIES.
# Geopolitics and AI remain allowed so a snapshot from before the newspaper
# sections still validates.
CATEGORIES = (
    "World",
    "Politics",
    "Business",
    "Technology",
    "Sports",
    "Culture",
    "Health",
    "Environment",
    "Education",
    "Other",
)
LEGACY_CATEGORIES = (
    "Geopolitics",
    "AI",
)
DEMO_CATEGORIES = (
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
ALLOWED_CATEGORIES = frozenset(CATEGORIES) | frozenset(DEMO_CATEGORIES) | frozenset(LEGACY_CATEGORIES)
NOISE_POLICY = "Topic -1 is dropped and excluded from the volume denominator."
MIN_FACES = 2
MAX_FACES = 6

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "World": (
        "ukraine",
        "gaza",
        "israel",
        "palestine",
        "nato",
        "china",
        "russia",
        "sanction",
        "diplomat",
        "ceasefire",
        "taiwan",
        "iran",
        "war",
    ),
    "Politics": (
        "election",
        "senate",
        "congress",
        "vote",
        "ballot",
        "parliament",
        "president",
        "legislation",
    ),
    "Business": (
        "inflation",
        "market",
        "wage",
        "housing",
        "tariff",
        "layoff",
        "economy",
        "rent",
        "stocks",
    ),
    "Technology": (
        "llm",
        "gpt",
        "chatgpt",
        "openai",
        "anthropic",
        "claude",
        "algorithm",
        "gpu",
        "alignment",
        "copilot",
        "software",
    ),
    "Sports": (
        "sport",
        "football",
        "soccer",
        "nfl",
        "nba",
        "mlb",
        "nhl",
        "league",
        "player",
        "coach",
        "match",
        "tournament",
        "olympic",
        "worldcup",
        "premier",
    ),
    "Culture": (
        "movie",
        "film",
        "album",
        "celebrity",
        "concert",
        "netflix",
        "oscar",
    ),
    "Health": (
        "hospital",
        "vaccine",
        "covid",
        "doctor",
        "cancer",
        "medicaid",
        "pandemic",
    ),
    "Environment": (
        "climate",
        "emission",
        "wildfire",
        "pollution",
        "hurricane",
        "carbon",
    ),
    "Education": (
        "school",
        "teacher",
        "student",
        "university",
        "campus",
        "classroom",
    ),
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


CATEGORY_PHRASES: dict[str, tuple[str, ...]] = {
    "World": ("cease fire", "prime minister"),
    "Politics": ("white house",),
    "Technology": ("artificial intelligence", "machine learning", "large language"),
    "Sports": ("world series", "premier league", "super bowl", "playoff"),
}


def infer_category(name: str, terms: list[str], texts: list[str] | None = None) -> str:
    """Map a topic label onto a newspaper section, or Other."""
    sample = " ".join((texts or [])[:40])
    blob = " ".join([name, *terms, sample]).lower()
    scores = {
        category: sum(1 for word in words if word in blob)
        + 2 * sum(1 for phrase in CATEGORY_PHRASES.get(category, ()) if phrase in blob)
        for category, words in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=lambda category: (scores[category], category))
    if scores[best] == 0:
        return "Other"
    return best


def category_for_members(name: str, terms: list[str], texts: list[str] | None, members: list[dict]) -> str:
    """Majority Jev section when posts are labeled. Otherwise the keyword map.

    A tie, or a winner below 40% of labeled members, is Other.
    """
    labeled = [str(post.get("section")) for post in members if post.get("section") in CATEGORIES]
    if not labeled:
        return infer_category(name, terms, texts)
    counts = Counter(labeled)
    ranked = counts.most_common()
    best, votes = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == votes:
        return "Other"
    if votes / len(labeled) < 0.4:
        return "Other"
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
    # Live weeks publish only the planets that actually separated. The demo
    # catalog still fills every orbit.
    minimum_topics = 1 if payload.get("mode") == "live" else SYSTEM_SIZE
    if len(topics) < minimum_topics:
        raise ValueError(f"Expected at least {minimum_topics} topics, found {len(topics)}")

    topic_volume = 0.0
    seen_topic_ids: set[int] = set()
    for topic in topics:
        topic_id = topic["id"]
        if topic_id in seen_topic_ids:
            raise ValueError(f"Duplicate topic id {topic_id}")
        seen_topic_ids.add(topic_id)
        if not topic.get("name"):
            raise ValueError(f"Topic {topic_id} is missing a name")
        if topic.get("category") not in ALLOWED_CATEGORIES:
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
            arguments = face.get("arguments")
            if arguments is not None:
                if not isinstance(arguments, list) or not 2 <= len(arguments) <= 6:
                    raise ValueError(
                        f"Perspective {face_id} arguments must be a list of 2-6 strings"
                    )
                if any(not isinstance(item, str) or not item.strip() for item in arguments):
                    raise ValueError(f"Perspective {face_id} has an empty argument")
            elif payload.get("mode") == "demo":
                raise ValueError(f"Demo perspective {face_id} needs core arguments")
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

    sections = payload.get("sections")
    if sections is not None:
        if not isinstance(sections, dict):
            raise ValueError("sections must be a dict mapping section name to topic list")
        for section_name, section_topics in sections.items():
            if section_name not in CATEGORIES:
                raise ValueError(f"sections key '{section_name}' is not a valid category")
            if not isinstance(section_topics, list) or not section_topics:
                raise ValueError(f"Section '{section_name}' must be a non-empty list of topics")
            sec_volume = 0.0
            seen_sec_ids: set[int] = set()
            for topic in section_topics:
                topic_id = topic["id"]
                if topic_id in seen_sec_ids:
                    raise ValueError(f"Section '{section_name}' has duplicate topic id {topic_id}")
                seen_sec_ids.add(topic_id)
                if not topic.get("name"):
                    raise ValueError(f"Section '{section_name}' topic {topic_id} is missing a name")
                perspectives = topic.get("perspectives") or []
                if not MIN_FACES <= len(perspectives) <= MAX_FACES:
                    raise ValueError(
                        f"Section '{section_name}' topic {topic_id} should have "
                        f"{MIN_FACES}-{MAX_FACES} perspectives, found {len(perspectives)}"
                    )
                sec_volume += float(topic["total_volume_percent"])
                for face in perspectives:
                    posts = face.get("representative_posts") or []
                    if not posts:
                        raise ValueError(
                            f"Section '{section_name}' perspective {face.get('id')} needs representative posts"
                        )
            if abs(sec_volume - 100.0) > 0.15:
                raise ValueError(
                    f"Section '{section_name}' topic volumes sum to {sec_volume}, not 100"
                )

    # Demo catalogs are a full solar system per category so the dropdown never empties.
    if payload.get("mode") == "demo":
        counts = Counter(topic["category"] for topic in topics)
        missing = [category for category in DEMO_CATEGORIES if counts.get(category, 0) < SYSTEM_SIZE]
        if missing:
            raise ValueError(
                f"Demo catalog needs {SYSTEM_SIZE} topics in every category; short: {missing}"
            )
