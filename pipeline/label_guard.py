"""Detect and replace placeholder reader-facing labels at finalize (#255, #204, #178, #205).

No network calls. Heuristic fallbacks only.
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.assemble import topic_name
from pipeline.cluster_math import salient_terms
from pipeline.label import (
    _is_insult_title,
    heuristic_label,
    heuristic_topic_label,
    perspective_needs_repair,
    topic_name_is_weak,
)
from pipeline.schema import STANCE_CHECK_UNSHARED, TOP_TERMS_LIMIT
from pipeline.spam_guard import post_body

_TEMPLATE_GROUPED = re.compile(r"^posts grouped under (.+)\.\s*$", re.IGNORECASE)
_TEMPLATE_ABOUT = re.compile(r"^these posts are about (.+)\.\s*$", re.IGNORECASE)
_TEMPLATE_CLUSTER = re.compile(r"^a live (?:cluster|remark) around (.+)\.\s*$", re.IGNORECASE)
_LLM_PREAMBLE_TITLE = frozenset(
    {
        "certainly",
        "sure",
        "okay",
        "ok",
        "yes",
        "absolutely",
        "definitely",
        "here",
        "here's",
        "hereis",
    }
)
_LLM_PREAMBLE_START = re.compile(
    r"^(?:certainly|sure|okay|ok|yes|absolutely|definitely|here(?:'s| is))\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split())


def is_template_summary(text: str, reference_name: str | None = None) -> bool:
    """True for internal grouping filler shipped to readers."""
    cleaned = _normalize(text)
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if _TEMPLATE_GROUPED.match(lowered) or _TEMPLATE_ABOUT.match(lowered) or _TEMPLATE_CLUSTER.match(lowered):
        return True
    if reference_name:
        name = _normalize(reference_name)
        if lowered == f"posts grouped under {name.lower()}.":
            return True
        if lowered == f"these posts are about {name.lower()}.":
            return True
    return False


def is_preamble_label(text: str) -> bool:
    """LLM opener or agreement word used as the whole title."""
    words = [part.lower().strip(".,!?") for part in _normalize(text).split()]
    if not words:
        return True
    if len(words) == 1 and words[0] in _LLM_PREAMBLE_TITLE:
        return True
    if _LLM_PREAMBLE_START.match(_normalize(text)):
        return True
    return False


def reader_label_issue(
    title: str,
    summary: str,
    *,
    planet_name: str | None = None,
    terms: list[str] | None = None,
    posts: list[dict] | None = None,
    kind: str = "face",
) -> str | None:
    """Return a short reason when a title or summary must not ship; else None."""
    name = _normalize(title)
    lead = _normalize(summary)
    if not name:
        return "empty title"
    if is_preamble_label(name):
        return "llm preamble title"
    if is_template_summary(lead, planet_name or name):
        return "template summary"
    if kind == "planet" and planet_name and name.lower() == _normalize(planet_name).lower():
        if is_template_summary(lead, planet_name):
            return "planet echo template"
    if kind == "face" and posts and terms:
        bag = topic_name(terms)
        if bag and name.lower() == bag.lower() and topic_name_is_weak(name, posts, terms):
            return "term-bag face title"
    if kind == "planet" and posts and terms:
        if is_template_summary(lead, planet_name or name):
            return "template summary"
        if _is_insult_title(name) and is_template_summary(lead, name):
            return "insult placeholder planet"
        bag = topic_name(terms)
        if bag and name.lower() == bag.lower() and topic_name_is_weak(name, posts, terms):
            return "term-bag planet name"
    if planet_name and name.lower() == _normalize(planet_name).lower() and is_template_summary(lead, planet_name):
        return "title matches planet template summary"
    return None


def _member_texts(posts: list[dict]) -> list[str]:
    return [post_body(post) for post in posts if post_body(post).strip()]


def _terms_for_bucket(posts: list[dict], terms: list[str] | None) -> list[str]:
    if terms:
        cleaned = [str(term).strip() for term in terms if str(term).strip()]
        if cleaned:
            return cleaned
    texts = _member_texts(posts)
    return salient_terms(texts, limit=TOP_TERMS_LIMIT) or salient_terms(texts, limit=6)


def readable_face_label(posts: list[dict], terms: list[str] | None = None) -> tuple[str, str]:
    """Build a title and summary from salient terms and post text."""
    from pipeline.label import _claim_title, _concrete_title, _lead_text, _shown_sentence

    bucket_terms = _terms_for_bucket(posts, terms)
    title = _claim_title(posts, bucket_terms) or _concrete_title(_lead_text(posts))
    if not title or topic_name_is_weak(title, posts, bucket_terms):
        title = topic_name(bucket_terms) if bucket_terms else "Topic"
    if topic_name_is_weak(title, posts, bucket_terms):
        heuristic = heuristic_label(bucket_terms, posts)
        title = str(heuristic.get("title") or title)
    summary = _shown_sentence(posts)
    if not summary or is_template_summary(summary, title):
        summary = str(heuristic_label(bucket_terms, posts).get("summary") or "")
    if is_template_summary(summary, title) or perspective_needs_repair({"title": title, "summary": summary}, posts):
        shown = ", ".join(bucket_terms[:5]) if bucket_terms else "these posts"
        summary = f"Posts in this group center on {shown}."
    return title[:48], summary[:280]


def readable_planet_name(posts: list[dict], terms: list[str] | None = None) -> str:
    bucket_terms = _terms_for_bucket(posts, terms)
    named = topic_name(bucket_terms)
    if topic_name_is_weak(named, posts, bucket_terms):
        topic = heuristic_topic_label(bucket_terms, posts)
        named = str(topic.get("name") or named)
    return named[:48]


def readable_planet_summary(posts: list[dict], planet_name: str, terms: list[str] | None = None) -> str:
    _title, summary = readable_face_label(posts, terms)
    if is_template_summary(summary, planet_name):
        shown = ", ".join(_terms_for_bucket(posts, terms)[:5])
        return f"Posts in this group center on {shown}."[:280]
    return summary


def _pick_candidate(
    candidates: list[tuple[str, str]],
    *,
    planet_name: str | None,
    terms: list[str],
    posts: list[dict],
    kind: str,
) -> tuple[str, str] | None:
    for title, summary in candidates:
        if reader_label_issue(
            title,
            summary,
            planet_name=planet_name,
            terms=terms,
            posts=posts,
            kind=kind,
        ):
            continue
        return title, summary
    return None


def _face_posts(face: dict, posts_by_uri: dict[str, dict], member_posts: list[dict]) -> list[dict]:
    uris = list(face.get("_face_member_uris") or [])
    if uris:
        return [posts_by_uri[uri] for uri in uris if uri in posts_by_uri]
    return list(member_posts)


def guard_published_labels(topics: list[dict], posts: list[dict]) -> list[str]:
    """Replace placeholder labels on published planets and faces. Returns log lines."""
    posts_by_uri = {str(post.get("uri") or ""): post for post in posts}
    log: list[str] = []
    for topic in topics:
        member_uris = [str(uri) for uri in (topic.get("_member_uris") or []) if uri]
        members = [posts_by_uri[uri] for uri in member_uris if uri in posts_by_uri]
        planet_terms = _terms_for_bucket(members, None)
        planet_name = str(topic.get("name") or "")
        if reader_label_issue(
            planet_name,
            str(topic.get("summary") or ""),
            planet_name=planet_name,
            terms=planet_terms,
            posts=members,
            kind="planet",
        ):
            candidates = [(planet_name, str(topic.get("summary") or ""))]
            candidates.append(
                (
                    readable_planet_name(members, planet_terms),
                    readable_planet_summary(members, planet_name, planet_terms),
                )
            )
            picked = _pick_candidate(
                candidates[1:],
                planet_name=planet_name,
                terms=planet_terms,
                posts=members,
                kind="planet",
            )
            if picked:
                new_name, new_summary = picked
                if new_name != planet_name:
                    log.append(f"Label guard: planet renamed {planet_name!r} → {new_name!r}")
                    topic["name"] = new_name
                    planet_name = new_name
                if new_summary and new_summary != topic.get("summary"):
                    topic["summary"] = new_summary
                    topic.pop("brief", None)
                    topic.pop("detail", None)
        for face in topic.get("perspectives") or []:
            face_posts = _face_posts(face, posts_by_uri, members)
            face_terms = list(face.get("top_terms") or []) or planet_terms
            title = str(face.get("title") or "")
            summary = str(face.get("summary") or "")
            issue = reader_label_issue(
                title,
                summary,
                planet_name=planet_name,
                terms=face_terms,
                posts=face_posts,
                kind="face",
            )
            if not issue:
                continue
            draft = face.get("_draft_face_label") or {}
            candidates: list[tuple[str, str]] = []
            if draft:
                candidates.append((str(draft.get("title") or ""), str(draft.get("summary") or "")))
            candidates.append(readable_face_label(face_posts, face_terms))
            picked = _pick_candidate(
                candidates,
                planet_name=planet_name,
                terms=face_terms,
                posts=face_posts,
                kind="face",
            )
            if picked:
                new_title, new_summary = picked
                log.append(f"Label guard: face {title!r} → {new_title!r} ({issue})")
                face["title"] = new_title
                face["summary"] = new_summary
                face.pop("brief", None)
                face.pop("detail", None)
                face.pop("arguments", None)
            else:
                topic["stance_check"] = STANCE_CHECK_UNSHARED
                log.append(f"Label guard: face {title!r} held pending ({issue})")
    return log


def _iter_planets(payload: dict) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for topic in payload.get("topics") or []:
        if isinstance(topic, dict):
            rows.append(("catalog", topic))
    sections = payload.get("sections") or {}
    if isinstance(sections, dict):
        for section, planets in sections.items():
            if not isinstance(planets, list):
                continue
            for planet in planets:
                if isinstance(planet, dict):
                    rows.append((str(section), planet))
    return rows


def _would_replace(
    title: str,
    summary: str,
    *,
    planet_name: str,
    terms: list[str],
    posts: list[dict],
    kind: str,
) -> str:
    if kind == "planet":
        replacement = readable_planet_name(posts, terms)
        summary_replacement = readable_planet_summary(posts, replacement, terms)
        picked = _pick_candidate(
            [(replacement, summary_replacement)],
            planet_name=replacement,
            terms=terms,
            posts=posts,
            kind=kind,
        )
        if picked:
            return f"name {picked[0]}; summary {picked[1]}"
        return replacement
    picked = _pick_candidate(
        [readable_face_label(posts, terms)],
        planet_name=planet_name,
        terms=terms,
        posts=posts,
        kind=kind,
    )
    if picked:
        return f"title {picked[0]}; summary {picked[1]}"
    return "hold pending (no readable fallback)"


def scan_edition_labels(payload: dict) -> dict[str, Any]:
    """Scan a published snapshot. Returns flagged rows and clean samples."""
    flagged: list[dict[str, Any]] = []
    clean: list[dict[str, str]] = []
    for section, planet in _iter_planets(payload):
        name = str(planet.get("name") or "")
        member_posts: list[dict] = []
        for face in planet.get("perspectives") or []:
            for rep in face.get("representative_posts") or []:
                if isinstance(rep, dict) and rep.get("text"):
                    member_posts.append({"text": rep.get("text"), "clean_text": rep.get("text")})
        terms = _terms_for_bucket(member_posts, None)
        planet_issue = reader_label_issue(
            name,
            str(planet.get("summary") or ""),
            planet_name=name,
            terms=terms,
            posts=member_posts,
            kind="planet",
        )
        if planet_issue:
            flagged.append(
                {
                    "section": section,
                    "planet": name,
                    "field": "planet",
                    "title": name,
                    "summary": str(planet.get("summary") or ""),
                    "reason": planet_issue,
                    "would_show": _would_replace(
                        name,
                        str(planet.get("summary") or ""),
                        planet_name=name,
                        terms=terms,
                        posts=member_posts,
                        kind="planet",
                    ),
                }
            )
        elif len(clean) < 8:
            clean.append({"section": section, "planet": name, "title": name})
        for face in planet.get("perspectives") or []:
            title = str(face.get("title") or "")
            summary = str(face.get("summary") or "")
            face_terms = list(face.get("top_terms") or []) or terms
            face_issue = reader_label_issue(
                title,
                summary,
                planet_name=name,
                terms=face_terms,
                posts=member_posts,
                kind="face",
            )
            if face_issue:
                flagged.append(
                    {
                        "section": section,
                        "planet": name,
                        "field": "face",
                        "title": title,
                        "summary": summary,
                        "reason": face_issue,
                        "would_show": _would_replace(
                            title,
                            summary,
                            planet_name=name,
                            terms=face_terms,
                            posts=member_posts,
                            kind="face",
                        ),
                    }
                )
            elif len(clean) < 12:
                clean.append({"section": section, "planet": name, "title": title})
    return {"flagged": flagged, "clean_samples": clean}
