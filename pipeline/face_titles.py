"""Deterministic face-title repair after wide relabel (issues #229, #220, #151)."""

from __future__ import annotations

import math
from typing import Any, Iterable

from pipeline.assemble import face_id, topic_name
from pipeline.cluster_math import salient_terms
from pipeline.label import (
    content_tokens,
    subject_stem,
    titles_alike,
    unique_label,
)
from pipeline.label import (
    _claim_title,
    _concrete_title,
    _lead_text,
)
from pipeline.schema import apply_opposing_note, to_percents
from pipeline.story_attach import merge_alike_published_faces


def _coverage_needed(count: int) -> int:
    """At least two posts, and about 40% of the sample."""
    return max(2, math.ceil(0.40 * count - 1e-9))


def title_covers_posts(title: str, posts: list[dict]) -> bool:
    """True when the claim's words show up in about 40% of the posts."""
    title_stems = {subject_stem(token) for token in content_tokens(title)}
    title_stems = {stem for stem in title_stems if len(stem) >= 3}
    if len(posts) < 2 or not title_stems:
        return True
    hits = 0
    for post in posts:
        text = str(post.get("text") or post.get("clean_text") or "")
        stems = {subject_stem(token) for token in content_tokens(text)}
        if title_stems & stems:
            hits += 1
    return hits >= _coverage_needed(len(posts))


def iter_all_planets(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for planet in data.get("topics") or []:
        yield planet
    for planets in (data.get("sections") or {}).values():
        for planet in planets:
            yield planet


def count_duplicate_title_faces(data: dict[str, Any] | None = None, *, topics: list[dict] | None = None) -> int:
    """Faces that share a planet with another face of the same or near-same title."""
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
                titles_alike(title, other.get("title"))
                for other_index, other in enumerate(faces)
                if other_index != index and other.get("title")
            ):
                total += 1
    return total


def _post_texts(posts: list[dict]) -> list[str]:
    return [str(post.get("clean_text") or post.get("text") or "") for post in posts]


def _title_candidates(
    posts: list[dict],
    terms: list[str],
    *,
    draft_title: str | None = None,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: str | None) -> None:
        text = " ".join(str(value or "").split())
        if not text or text.lower() in seen:
            return
        seen.add(text.lower())
        ordered.append(text[:48])

    add(_claim_title(posts, terms))
    add(_concrete_title(_lead_text(posts)))
    for post in sorted(posts, key=lambda item: -int(item.get("likes") or 0)):
        add(_concrete_title(str(post.get("text") or post.get("clean_text") or "")))
    texts = _post_texts(posts)
    add(topic_name(salient_terms(texts, limit=6) or terms))
    if len(terms) >= 2:
        add(" ".join(term.capitalize() for term in terms[:3]))
    add(draft_title)
    return ordered


def _pick_supported_title(
    posts: list[dict],
    terms: list[str],
    *,
    draft_title: str | None = None,
    forbidden: set[str] | None = None,
) -> str | None:
    blocked = {item.lower() for item in (forbidden or set())}
    for candidate in _title_candidates(posts, terms, draft_title=draft_title):
        if candidate.lower() in blocked:
            continue
        if any(titles_alike(candidate, item) for item in forbidden or ()):
            continue
        if title_covers_posts(candidate, posts):
            return candidate
    return None


def _face_posts(
    face: dict,
    post_by_uri: dict[str, dict],
) -> list[dict]:
    uris = [str(item) for item in (face.get("_face_member_uris") or [])]
    posts = [post_by_uri[uri] for uri in uris if uri in post_by_uri]
    if posts:
        return posts
    return list(face.get("representative_posts") or [])


def _renumber_face_ids(topic: dict) -> None:
    topic_id = topic.get("id") or 1
    faces = list(topic.get("perspectives") or [])
    counts = [max(int(face.get("post_count") or 0), 0) for face in faces]
    topic["post_count"] = sum(counts)
    volumes = to_percents(counts) if sum(counts) else [0.0 for _ in faces]
    for index, (face, volume) in enumerate(zip(faces, volumes)):
        face["volume_percent"] = volume
        face["id"] = face_id(topic_id, index)
    topic["perspectives"] = faces
    apply_opposing_note(topic)


def _rename_duplicate_faces(topic: dict, post_by_uri: dict[str, dict]) -> int:
    """Give the smaller alike face a distinct grounded title when merge cannot fold it."""
    faces = list(topic.get("perspectives") or [])
    if len(faces) < 2:
        return 0
    renamed = 0
    ranked = sorted(faces, key=lambda face: (-int(face.get("post_count") or 0), str(face.get("id") or "")))
    titles_seen: set[str] = set()
    for face in ranked:
        title = str(face.get("title") or "")
        if not title:
            continue
        clash = next(
            (
                kept
                for kept in titles_seen
                if titles_alike(title, kept)
            ),
            None,
        )
        if clash is None:
            titles_seen.add(title)
            continue
        posts = _face_posts(face, post_by_uri)
        terms = list(face.get("top_terms") or [])
        draft = (face.get("_draft_face_label") or {}).get("title")
        forbidden = {str(item) for item in titles_seen}
        replacement = _pick_supported_title(posts, terms, draft_title=str(draft or ""), forbidden=forbidden)
        if not replacement:
            seen_lower = {item.lower() for item in forbidden}
            for candidate in _title_candidates(posts, terms, draft_title=str(draft or "")):
                replacement = unique_label(candidate, seen_lower)
                if not any(titles_alike(replacement, item) for item in forbidden):
                    break
            else:
                replacement = unique_label(title, seen_lower)
        face["title"] = replacement
        titles_seen.add(replacement)
        renamed += 1
    if renamed:
        _renumber_face_ids(topic)
    return renamed


def repair_published_face_titles(
    topics: list[dict],
    posts: list[dict] | None = None,
    *,
    post_by_uri: dict[str, dict] | None = None,
    after_wide_finalize: bool = False,
) -> dict[str, int]:
    """Fix unsupported titles, merge alike faces, then rename any leftover duplicates."""
    if post_by_uri is None:
        post_by_uri = {str(post.get("uri") or ""): post for post in (posts or [])}
    stats = {"unsupported_renamed": 0, "merged": 0, "duplicate_renamed": 0}

    for topic in topics:
        for face in topic.get("perspectives") or []:
            if face.get("stance_locked"):
                continue
            sample_posts = _face_posts(face, post_by_uri)
            if len(sample_posts) < 2:
                continue
            title = str(face.get("title") or "")
            if not title or title.lower() in {"mixed remarks", "untitled cluster"}:
                continue
            draft_title = str((face.get("_draft_face_label") or {}).get("title") or "")
            if after_wide_finalize:
                if face.get("_wide_finalize_applied"):
                    continue
                if draft_title and title == draft_title:
                    continue
            if title_covers_posts(title, sample_posts):
                continue
            terms = list(face.get("top_terms") or [])
            draft = (face.get("_draft_face_label") or {}).get("title")
            replacement = _pick_supported_title(sample_posts, terms, draft_title=str(draft or ""))
            if not replacement:
                continue
            face["title"] = replacement
            stats["unsupported_renamed"] += 1

    stats["merged"] = merge_alike_published_faces(topics)

    for topic in topics:
        stats["duplicate_renamed"] += _rename_duplicate_faces(topic, post_by_uri)

    return stats


def repair_payload_face_titles(data: dict[str, Any]) -> dict[str, int]:
    """Repair every planet in a published payload (offline checks on data.json)."""
    totals = {"unsupported_renamed": 0, "merged": 0, "duplicate_renamed": 0}
    topics = list(data.get("topics") or [])
    if topics:
        part = repair_published_face_titles(topics, posts=None)
        for key in totals:
            totals[key] += part[key]
    for planets in (data.get("sections") or {}).values():
        section_topics = list(planets)
        if not section_topics:
            continue
        part = repair_published_face_titles(section_topics, posts=None)
        for key in totals:
            totals[key] += part[key]
    return totals
