"""Face-title helpers: exact duplicate merge and coverage checks (#229)."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


_TITLE_WORD = re.compile(r"[a-z0-9]+")


def _coverage_needed(count: int) -> int:
    """At least two posts, and about 40% of the sample."""
    return max(2, math.ceil(0.40 * count - 1e-9))


def normalize_face_title(value: str | None) -> str:
    """Lowercase title with trailing copy numbers stripped."""
    words = _TITLE_WORD.findall(str(value or "").lower())
    while words and words[-1].isdigit():
        words.pop()
    return " ".join(words)


def face_titles_equal(left: str | None, right: str | None) -> bool:
    """True only when normalized titles are the same (not a token subset)."""
    a = normalize_face_title(left)
    b = normalize_face_title(right)
    return bool(a) and a == b


def title_covers_posts(title: str, posts: list[dict]) -> bool:
    """True when every title word appears in about 40% of the posts.

    A post counts only when the full title vocabulary is present in its text.
    Titles with no countable words are never treated as covered.
    """
    words = _TITLE_WORD.findall(str(title or "").lower())
    if len(posts) < 2 or not words:
        return False
    needed = _coverage_needed(len(posts))
    hits = 0
    for post in posts:
        text = str(post.get("text") or post.get("clean_text") or "").lower()
        if all(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
            hits += 1
    return hits >= needed


def iter_all_planets(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for planet in data.get("topics") or []:
        yield planet
    for planets in (data.get("sections") or {}).values():
        for planet in planets:
            yield planet


def count_duplicate_title_faces(data: dict[str, Any] | None = None, *, topics: list[dict] | None = None) -> int:
    """Faces that share a planet with another face of the same normalized title."""
    planets: Iterable[dict[str, Any]]
    if topics is not None:
        planets = topics
    elif data is not None:
        planets = iter_all_planets(data)
    else:
        return 0
    total = 0
    for planet in planets:
        faces = list(planet.get("perspectives") or [])
        for index, face in enumerate(faces):
            title = face.get("title")
            if not title:
                continue
            if any(
                face_titles_equal(title, other.get("title"))
                for other_index, other in enumerate(faces)
                if other_index != index and other.get("title")
            ):
                total += 1
    return total


def _face_posts(face: dict, post_by_uri: dict[str, dict]) -> list[dict]:
    uris = [str(item) for item in (face.get("_face_member_uris") or [])]
    posts = [post_by_uri[uri] for uri in uris if uri in post_by_uri]
    if posts:
        return posts
    return list(face.get("representative_posts") or [])


def report_unsupported_face_titles(
    topics: list[dict],
    post_by_uri: dict[str, dict],
    stats: dict[str, Any],
) -> None:
    """Record faces whose titles are not carried by their posts (no rename)."""
    for topic in topics:
        planet_name = str(topic.get("name") or "")
        for face in topic.get("perspectives") or []:
            title = str(face.get("title") or "")
            if not title or title.lower() in {"mixed remarks", "untitled cluster"}:
                continue
            posts = _face_posts(face, post_by_uri)
            if len(posts) < 2:
                continue
            if title_covers_posts(title, posts):
                continue
            stats["unsupported_faces"].append({"planet": planet_name, "title": title})


def repair_published_face_titles(
    topics: list[dict],
    posts: list[dict] | None = None,
    *,
    post_by_uri: dict[str, dict] | None = None,
    after_wide_finalize: bool = False,
) -> dict[str, Any]:
    """Merge exact duplicate face titles; report unsupported titles without renaming."""
    del after_wide_finalize
    if post_by_uri is None:
        post_by_uri = {str(post.get("uri") or ""): post for post in (posts or [])}
    stats: dict[str, Any] = {
        "merged": 0,
        "unsupported_faces": [],
    }
    report_unsupported_face_titles(topics, post_by_uri, stats)
    from pipeline.story_attach import merge_alike_published_faces

    stats["merged"] = merge_alike_published_faces(topics)
    return stats


def repair_payload_face_titles(data: dict[str, Any]) -> dict[str, Any]:
    """Offline pass on published JSON: merge exact duplicates, list unsupported faces."""
    totals: dict[str, Any] = {"merged": 0, "unsupported_faces": []}
    topics = list(data.get("topics") or [])
    if topics:
        part = repair_published_face_titles(topics, posts=None)
        totals["merged"] += int(part.get("merged") or 0)
        totals["unsupported_faces"].extend(part.get("unsupported_faces") or [])
    for planets in (data.get("sections") or {}).values():
        section_topics = list(planets)
        if not section_topics:
            continue
        part = repair_published_face_titles(section_topics, posts=None)
        totals["merged"] += int(part.get("merged") or 0)
        totals["unsupported_faces"].extend(part.get("unsupported_faces") or [])
    return totals
