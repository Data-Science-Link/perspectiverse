"""Which published planets would keep yesterday's label.

The published ``data.json`` does not carry post URIs. A planet's post set is
the representative ``(author, text)`` pairs on its faces. ``post_count`` is
the full membership and is not part of the set.

Same planet: inside one scope (the global list, or one section), a greedy
one-to-one match. Highest Jaccard wins. A tie goes to the larger intersection,
then the earlier planet in today's list, then the earlier planet in
yesterday's list. A pair with an empty intersection is not a match.

Changed, at a threshold: today's planet has no match, or its match scores
below that threshold. Equal sets score 1. The labeling prompt is a separate
gate: if it changed, every planet needs a label and this overlap does not
apply.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def representative_posts(topic: dict) -> frozenset[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for face in topic.get("perspectives") or []:
        for post in face.get("representative_posts") or []:
            found.add((str(post.get("author") or ""), str(post.get("text") or "")))
    return frozenset(found)


def planets_from_payload(payload: dict) -> list[dict[str, Any]]:
    """One row per published planet, global list first, then each section."""
    rows: list[dict[str, Any]] = []

    def add(scope: str, topics: list) -> None:
        for topic in topics or []:
            posts = representative_posts(topic)
            rows.append(
                {
                    "scope": scope,
                    "name": str(topic.get("name") or ""),
                    "posts": posts,
                    "post_count": int(topic.get("post_count") or 0),
                }
            )

    add("global", payload.get("topics") or [])
    sections = payload.get("sections") or {}
    if isinstance(sections, dict):
        for name, topics in sections.items():
            add(f"section:{name}", topics)
    return rows


def jaccard(left: frozenset, right: frozenset) -> Decimal:
    if not left and not right:
        return Decimal(1)
    union = len(left | right)
    if union == 0:
        return Decimal(0)
    return Decimal(len(left & right)) / Decimal(union)


def match_planets(today: list[dict], yesterday: list[dict]) -> list[dict | None]:
    """One match slot per today's planet. ``None`` means no overlapping planet."""
    by_scope: dict[str, list[int]] = {}
    for index, planet in enumerate(yesterday):
        by_scope.setdefault(str(planet["scope"]), []).append(index)
    pairs: list[tuple] = []
    for today_index, planet in enumerate(today):
        for yesterday_index in by_scope.get(str(planet["scope"]), []):
            score = jaccard(planet["posts"], yesterday[yesterday_index]["posts"])
            if score <= 0:
                continue
            intersection = len(planet["posts"] & yesterday[yesterday_index]["posts"])
            pairs.append((score, intersection, -today_index, -yesterday_index, today_index, yesterday_index))
    pairs.sort(reverse=True)
    assigned: dict[int, dict] = {}
    used: set[int] = set()
    for score, _intersection, _today_index, _yesterday_index, today_index, yesterday_index in pairs:
        if today_index in assigned or yesterday_index in used:
            continue
        assigned[today_index] = {
            "yesterday_index": yesterday_index,
            "score": score,
            "name": yesterday[yesterday_index]["name"],
        }
        used.add(yesterday_index)
    return [assigned.get(index) for index in range(len(today))]


def share_changed(matches: list[dict | None], threshold: Decimal | str) -> dict[str, Decimal | int]:
    """Planets that would need a new label at this overlap threshold."""
    total = len(matches)
    if total <= 0:
        raise ValueError("today has no planets")
    bar = threshold if isinstance(threshold, Decimal) else Decimal(str(threshold))
    if bar < 0 or bar > 1:
        raise ValueError("threshold must be from 0 to 1")
    kept = sum(1 for item in matches if item is not None and item["score"] >= bar)
    changed = total - kept
    return {
        "planets": total,
        "kept": kept,
        "changed": changed,
        "share": Decimal(changed) / Decimal(total),
    }
