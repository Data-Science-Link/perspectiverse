"""Detect and replace placeholder reader-facing labels at finalize (#255, #204, #178, #205).

No network calls. A replacement ships only when it is a phrase the posts
actually use. Term bags, mood words, and template summaries are held pending.
"""

from __future__ import annotations

import math
import re
from typing import Any

from pipeline.assemble import topic_name
from pipeline.cluster_math import salient_terms
from pipeline.label import (
    _GENERIC_BUCKET_WORDS,
    _TITLE_WORDS,
    _WEAK_TITLE_WORDS,
    _is_insult_title,
    topic_name_is_weak,
    unique_label,
)
from pipeline.schema import STANCE_CHECK_LABEL_HELD, TOP_TERMS_LIMIT
from pipeline.spam_guard import post_body

PENDING_TITLE = "Pending"
PENDING_SUMMARY = "Topic label not ready for this edition."

_TEMPLATE_GROUPED = re.compile(r"^posts grouped under (.+)\.\s*$", re.IGNORECASE)
_TEMPLATE_ABOUT = re.compile(r"^these posts are about (.+)\.\s*$", re.IGNORECASE)
_TEMPLATE_CLUSTER = re.compile(r"^a live (?:cluster|remark) around (.+)\.\s*$", re.IGNORECASE)
_TEMPLATE_CENTER = re.compile(r"^posts in this group center on .+[.]\s*$", re.IGNORECASE)
_PROMO = re.compile(r"https?://|www\.|\bvisit\b", re.IGNORECASE)
_MOOD_WORDS = frozenset(
    {
        "crazy",
        "fun",
        "funny",
        "funnier",
        "funniest",
        "too",
        "concept",
        "thought",
        "thoughts",
        "question",
        "person",
        "people",
        "lol",
        "lmao",
        "wow",
        "nice",
        "good",
        "bad",
        "great",
        "sure",
        "yes",
        "okay",
        "ok",
        "certainly",
        "absolutely",
        "definitely",
        "pending",
        "topic",
        "untitled",
    }
)
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
    # A missing summary is filled later from the face. It is not placeholder copy.
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if (
        _TEMPLATE_GROUPED.match(lowered)
        or _TEMPLATE_ABOUT.match(lowered)
        or _TEMPLATE_CLUSTER.match(lowered)
        or _TEMPLATE_CENTER.match(lowered)
    ):
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
    if _is_insult_title(name):
        return "insult title"
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


def _title_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _content_word(word: str) -> bool:
    lower = word.lower()
    if lower in _MOOD_WORDS or lower in _TITLE_WORDS or lower in _WEAK_TITLE_WORDS or lower in _GENERIC_BUCKET_WORDS:
        return False
    if len(lower) <= 2 and lower not in {"ai", "eu", "uk", "un", "us"}:
        return False
    return True


def _family(word: str) -> str:
    return word.lower()[:4]


def _stem_debris(terms: list[str]) -> bool:
    """True when the salient terms are inflections of one word (bully/bullies/bullying)."""
    surfaces = {str(term).lower() for term in terms if str(term).strip()}
    if len(surfaces) < 2:
        return False
    families = {_family(term) for term in surfaces if len(term) >= 4}
    return len(families) == 1


def _stem_family_title(words: list[str]) -> bool:
    keys = [_family(word) for word in words if len(word) >= 4]
    return len(keys) >= 2 and len(set(keys)) == 1


def _generic_title(title: str) -> bool:
    words = _title_words(title)
    if not words:
        return True
    if len(words) == 1 and (
        words[0].lower() in _MOOD_WORDS
        or words[0].lower() in _WEAK_TITLE_WORDS
        or words[0].lower() in _GENERIC_BUCKET_WORDS
        or len(words[0]) <= 3
    ):
        return True
    content = [word for word in words if _content_word(word)]
    return bool(words) and not content


def _phrase_hits(posts: list[dict], words: list[str]) -> int:
    if not words:
        return 0
    pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE)
    return sum(1 for post in posts if pattern.search(post_body(post)))


def _min_hits(post_count: int, *, single: bool) -> int:
    if post_count <= 1:
        return 1
    share = 0.5 if single else 0.3
    return max(2, math.ceil(post_count * share))


def _display_phrase(posts: list[dict], words: list[str]) -> str:
    pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE)
    ranked = sorted(posts, key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        match = pattern.search(post_body(post))
        if match:
            return " ".join(match.group(0).split())[:48]
    return " ".join(word[:1].upper() + word[1:] for word in words)[:48]


def _finished_sentence(summary: str) -> bool:
    text = _normalize(summary)
    if not text or is_template_summary(text):
        return False
    if "…" in text or "..." in text:
        return False
    if text[-1:] not in ".!?":
        return False
    if _PROMO.search(text):
        return False
    words = text.split()
    return 4 <= len(words) <= 32


def _sentences(text: str) -> list[str]:
    found: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = " ".join(part.split())
        if _finished_sentence(sentence):
            found.append(sentence)
    return found


def _summary_for(posts: list[dict], title: str) -> str:
    words = [word.lower() for word in _title_words(title)]
    if not words:
        return ""
    pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE)
    ranked = sorted(posts, key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        for sentence in _sentences(post_body(post)):
            if pattern.search(sentence):
                return sentence[:280]
    return ""


def _best_title(posts: list[dict], terms: list[str]) -> str:
    """A phrase or specific word the posts share, never a joined term list."""
    if not posts:
        return ""
    phrase_counts: dict[tuple[str, ...], int] = {}
    single_counts: dict[str, int] = {}
    for post in posts:
        words = _title_words(post_body(post))
        seen_phrases: set[tuple[str, ...]] = set()
        seen_singles: set[str] = set()
        for size in (2, 3):
            for index in range(len(words) - size + 1):
                gram = words[index : index + size]
                if not all(_content_word(word) for word in gram):
                    continue
                key = tuple(word.lower() for word in gram)
                if key in seen_phrases:
                    continue
                seen_phrases.add(key)
                phrase_counts[key] = phrase_counts.get(key, 0) + 1
        for word in words:
            if not _content_word(word) or len(word) < 5:
                continue
            key = word.lower()
            if key in seen_singles:
                continue
            seen_singles.add(key)
            single_counts[key] = single_counts.get(key, 0) + 1
    phrase_need = _min_hits(len(posts), single=False)
    phrases = [item for item in phrase_counts.items() if item[1] >= phrase_need]
    if phrases:
        phrases.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
        return _display_phrase(posts, list(phrases[0][0]))
    if _stem_debris(terms):
        return ""
    single_need = _min_hits(len(posts), single=True)
    singles = [
        item
        for item in single_counts.items()
        if item[1] >= single_need and not _is_insult_title(item[0]) and item[0] not in _MOOD_WORDS
    ]
    if not singles:
        return ""
    singles.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
    return _display_phrase(posts, [singles[0][0]])


def _reordered_terms(words: list[str], terms: list[str]) -> bool:
    if len(words) < 2 or not terms:
        return False
    term_keys = [term.lower() for term in terms[:4]]

    def matches(word: str, term: str) -> bool:
        if word == term:
            return True
        return len(word) >= 4 and len(term) >= 4 and word[:4] == term[:4]

    return all(any(matches(word.lower(), term) for term in term_keys) for word in words)


def _has_substance(title: str) -> bool:
    for word in _title_words(title):
        if len(word) >= 5 or word.lower() in {"ai", "eu", "uk", "un", "us"}:
            return True
    return False


def candidate_blocked(
    title: str,
    summary: str,
    *,
    terms: list[str],
    posts: list[dict],
) -> str | None:
    """Why a replacement must not ship. None means a newcomer can read it."""
    name = _normalize(title)
    lead = _normalize(summary)
    if is_preamble_label(name) or _generic_title(name) or _is_insult_title(name):
        return "generic or preamble title"
    if _stem_family_title(_title_words(name)):
        return "stem-family title"
    if not _has_substance(name):
        return "thin title"
    if not _finished_sentence(lead):
        return "summary is not a sentence"
    words = _title_words(name)
    if _reordered_terms(words, terms) and _phrase_hits(posts, [word.lower() for word in words]) == 0:
        return "term-bag title"
    return None


def propose_label(
    posts: list[dict],
    terms: list[str] | None = None,
    *,
    draft: dict | None = None,
) -> tuple[str, str] | None:
    """Draft label, then a phrase taken from the posts. None means hold pending."""
    bucket_terms = _terms_for_bucket(posts, terms)
    if draft:
        title = str(draft.get("title") or "")
        summary = str(draft.get("summary") or "")
        if not candidate_blocked(title, summary, terms=bucket_terms, posts=posts):
            issue = reader_label_issue(
                title,
                summary,
                planet_name=title,
                terms=bucket_terms,
                posts=posts,
                kind="face",
            )
            if not issue:
                return title[:48], summary[:280]
    title = _best_title(posts, bucket_terms)
    if not title:
        return None
    summary = _summary_for(posts, title)
    if not summary:
        return None
    if candidate_blocked(title, summary, terms=bucket_terms, posts=posts):
        return None
    if reader_label_issue(title, summary, planet_name=title, terms=bucket_terms, posts=posts, kind="face"):
        return None
    return title[:48], summary[:280]


def readable_face_label(posts: list[dict], terms: list[str] | None = None) -> tuple[str, str]:
    """A readable title and summary, or the pending line when nothing qualifies."""
    proposed = propose_label(posts, terms)
    if proposed:
        return proposed
    return PENDING_TITLE, PENDING_SUMMARY


def readable_planet_name(posts: list[dict], terms: list[str] | None = None) -> str:
    proposed = propose_label(posts, terms)
    if proposed:
        return proposed[0]
    return PENDING_TITLE


def readable_planet_summary(posts: list[dict], planet_name: str, terms: list[str] | None = None) -> str:
    bucket_terms = _terms_for_bucket(posts, terms)
    summary = _summary_for(posts, planet_name)
    if summary and not candidate_blocked(planet_name, summary, terms=bucket_terms, posts=posts):
        return summary
    _title, fallback = readable_face_label(posts, terms)
    if is_template_summary(fallback, planet_name):
        return PENDING_SUMMARY
    return fallback


def _accept_candidate(
    title: str,
    summary: str,
    *,
    planet_name: str | None,
    terms: list[str],
    posts: list[dict],
    kind: str,
) -> bool:
    if candidate_blocked(title, summary, terms=terms, posts=posts):
        return False
    return (
        reader_label_issue(
            title,
            summary,
            planet_name=planet_name,
            terms=terms,
            posts=posts,
            kind=kind,
        )
        is None
    )


def _representative_posts(holder: dict) -> list[dict]:
    rows: list[dict] = []
    for rep in holder.get("representative_posts") or []:
        if isinstance(rep, dict) and post_body(rep).strip():
            rows.append(rep)
    return rows


def _topic_posts(topic: dict, posts_by_uri: dict[str, dict]) -> list[dict]:
    member_uris = [str(uri) for uri in (topic.get("_member_uris") or []) if uri]
    members = [posts_by_uri[uri] for uri in member_uris if uri in posts_by_uri]
    if members:
        return members
    rows: list[dict] = []
    for face in topic.get("perspectives") or []:
        rows.extend(_representative_posts(face))
    return rows


def _face_posts(face: dict, posts_by_uri: dict[str, dict], member_posts: list[dict]) -> list[dict]:
    uris = [str(uri) for uri in (face.get("_face_member_uris") or []) if uri]
    if uris:
        resolved = [posts_by_uri[uri] for uri in uris if uri in posts_by_uri]
        if resolved:
            return resolved
    reps = _representative_posts(face)
    if reps:
        return reps
    return list(member_posts)


def _assign_name(topic: dict, new_name: str, used_names: set[str]) -> str:
    current = str(topic.get("name") or "")
    if new_name.lower() == current.lower():
        return current
    used_names.discard(current.lower())
    renamed = unique_label(new_name, used_names)
    topic["name"] = renamed
    return renamed


def _mark_pending(topic: dict) -> None:
    topic["stance_check"] = STANCE_CHECK_LABEL_HELD
    topic.pop("opposing_note", None)
    topic["summary"] = PENDING_SUMMARY
    topic.pop("brief", None)
    topic.pop("detail", None)


def _mark_face_pending(face: dict, title: str) -> None:
    face["title"] = title
    face["summary"] = PENDING_SUMMARY
    face.pop("brief", None)
    face.pop("detail", None)
    face.pop("arguments", None)


def _apply_label(holder: dict, title_key: str, title: str, summary: str) -> None:
    holder[title_key] = title
    holder["summary"] = summary
    holder.pop("brief", None)
    holder.pop("detail", None)
    if title_key == "title":
        holder.pop("arguments", None)


def guard_published_labels(topics: list[dict], posts: list[dict]) -> list[str]:
    """Replace placeholder labels on published planets and faces. Returns log lines."""
    posts_by_uri = {str(post.get("uri") or ""): post for post in posts}
    used_names = {str(topic.get("name") or "").strip().lower() for topic in topics if topic.get("name")}
    log: list[str] = []
    for topic in topics:
        members = _topic_posts(topic, posts_by_uri)
        planet_terms = _terms_for_bucket(members, None)
        planet_name = str(topic.get("name") or "")
        planet_issue = reader_label_issue(
            planet_name,
            str(topic.get("summary") or ""),
            planet_name=planet_name,
            terms=planet_terms,
            posts=members,
            kind="planet",
        )
        if planet_issue:
            proposed = propose_label(members, planet_terms)
            if proposed and _accept_candidate(
                proposed[0],
                proposed[1],
                planet_name=planet_name,
                terms=planet_terms,
                posts=members,
                kind="planet",
            ):
                new_name, new_summary = proposed
                if new_name != planet_name:
                    log.append(f"Label guard: planet renamed {planet_name!r} → {new_name!r}")
                    planet_name = _assign_name(topic, new_name, used_names)
                if new_summary != topic.get("summary"):
                    topic["summary"] = new_summary
                    topic.pop("brief", None)
                    topic.pop("detail", None)
            else:
                pending_name = _assign_name(topic, PENDING_TITLE, used_names)
                _mark_pending(topic)
                for face in topic.get("perspectives") or []:
                    _mark_face_pending(face, pending_name)
                log.append(f"Label guard: planet {planet_name!r} held pending ({planet_issue})")
                continue
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
            draft = face.get("_draft_face_label") if isinstance(face.get("_draft_face_label"), dict) else None
            proposed = propose_label(face_posts, face_terms, draft=draft)
            if proposed and _accept_candidate(
                proposed[0],
                proposed[1],
                planet_name=planet_name,
                terms=face_terms,
                posts=face_posts,
                kind="face",
            ):
                new_title, new_summary = proposed
                log.append(f"Label guard: face {title!r} → {new_title!r} ({issue})")
                _apply_label(face, "title", new_title, new_summary)
            else:
                _mark_pending(topic)
                shown = planet_name if planet_name.lower().startswith("pending") else PENDING_TITLE
                _mark_face_pending(face, shown)
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
    del title, summary
    proposed = propose_label(posts, terms)
    if proposed and _accept_candidate(
        proposed[0],
        proposed[1],
        planet_name=planet_name,
        terms=terms,
        posts=posts,
        kind=kind,
    ):
        label = "name" if kind == "planet" else "title"
        return f"{label} {proposed[0]}; summary {proposed[1]}"
    return f"hold pending; title {PENDING_TITLE}; summary {PENDING_SUMMARY}"


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
