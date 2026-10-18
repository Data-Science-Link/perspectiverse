"""Deterministic face-title repair after wide relabel (issues #229, #220, #151)."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

from pipeline.assemble import face_id
from pipeline.label import _ACRONYM_CASE, _title_is_weak, content_tokens, subject_stem, titles_alike
from pipeline.schema import apply_opposing_note, to_percents
from pipeline.story_attach import merge_alike_published_faces

_WORD = re.compile(r"[A-Za-z][A-Za-z']*")

# Whole-word fillers that must not dominate a face title (product review #235).
TITLE_FILLER = frozenset(
    """
    okay ok wait again rather instead actual actually time weekend believe functional
    platforms purposes decision maybe really very just like well yeah nah hmm
    tho though literally honestly seriously basically totally good have every people
    school thank guess gently tree cats dont could when youre you're isn't he's just
    our programa resultado gently every people good have could use face yikes
    """.split()
)

# Short verbs/pronouns that are not a subject or claim on their own.
GENERIC_CLAIM_WORDS = frozenset(
    """
    good have has had having every people person school thank thanks guess gently tree
    cats dont could would should might must shall will being been being goes going went
    come came take took make made look looks looked think thinks thought know knows knew
    want wants wanted need needs needed feel feels felt tell tells told say says said
    give gives gave get gets got use uses used work works worked play plays played
    dont isnt wasnt werent cant wont thats theres heres yours ours theirs
    eat start makes sound sounds quite alright healthy capacity getting mass
    """.split()
)

PRONOUN_WORDS = frozenset("i me my we us our you your he him his she her it its they them their".split())

# Short second word allowed after an acronym when posts use that span (e.g. AI use).
ACRONYM_COMPANIONS = frozenset(
    "use jobs art chat bias risk tools models slop assistants usage".split()
)

TITLE_STOP = frozenset(
    "the a an of and or to in on for is are be by with vs not no at as it its this that "
    "from into over under than then there their they them you your we our us if so but "
    "about when what who how all any some more most other while back".split()
)

# Regression guard: phrases the old heuristic must never emit again.
_REJECTED_SALAD = frozenset(
    phrase.lower()
    for phrase in (
        "Data Believe Center",
        "Rather Instead",
        "Actual Wait",
        "Okay",
        "Weekend Purposes",
        "Time Again Decision",
        "Functional Platforms",
    )
)


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


def _substantive_tokens(lowers: list[str]) -> list[str]:
    return [
        word
        for word in lowers
        if word not in TITLE_STOP
        and word not in TITLE_FILLER
        and word not in GENERIC_CLAIM_WORDS
        and len(word) >= 4
    ]


def _is_acronym_token(word: str) -> bool:
    lower = word.lower()
    return lower in _ACRONYM_CASE or (word.isupper() and 2 <= len(word) <= 5)


def _acronym_topic_pair(words: list[str], lowers: list[str]) -> bool:
    """Two-word subject like AI Use from the posts, not a generic bigram."""
    if len(words) != 2 or not _is_acronym_token(words[0]):
        return False
    companion = lowers[1]
    if companion in TITLE_STOP or companion in PRONOUN_WORDS:
        return False
    if companion in TITLE_FILLER and companion not in ACRONYM_COMPANIONS:
        return False
    if companion in GENERIC_CLAIM_WORDS and companion not in ACRONYM_COMPANIONS:
        return False
    return companion in ACRONYM_COMPANIONS or len(companion) >= 4


def is_readable_face_phrase(phrase: str) -> bool:
    """A title must be a short verbatim span that names a subject or claim."""
    text = " ".join(str(phrase or "").split())
    if not text or text.lower() in _REJECTED_SALAD:
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z\s-]*", text):
        return False
    words = _WORD.findall(text)
    if len(words) < 2 or len(words) > 3:
        return False
    lowers = [word.lower() for word in words]
    if _acronym_topic_pair(words, lowers):
        return True
    if any(len(word) < 4 for word in lowers):
        return False
    if any(word in TITLE_STOP or word in PRONOUN_WORDS for word in lowers):
        return False
    if any(word in TITLE_FILLER for word in lowers):
        return False
    if any(word in GENERIC_CLAIM_WORDS for word in lowers):
        return False
    substantive = _substantive_tokens(lowers)
    if len(substantive) < 2:
        return False
    return max(len(word) for word in substantive) >= 5


def _post_bodies(posts: list[dict]) -> list[str]:
    return [str(post.get("clean_text") or post.get("text") or "") for post in posts]


def _tokens_with_spans(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in _WORD.finditer(text)]


def _phrase_from_span(text: str, start: int, end: int) -> str:
    return text[start:end].strip()


def _verbatim_phrase_candidates(posts: list[dict]) -> list[tuple[str, int]]:
    """Return (phrase, post_hit_count) for contiguous 1–3 word spans in the posts."""
    tallies: dict[str, int] = {}
    display: dict[str, str] = {}
    for body in _post_bodies(posts):
        tokens = _tokens_with_spans(body)
        if not tokens:
            continue
        hit_phrases: set[str] = set()
        for width in (1, 2, 3):
            for index in range(len(tokens) - width + 1):
                chunk = tokens[index : index + width]
                phrase = _phrase_from_span(body, chunk[0][1], chunk[-1][2])
                key = " ".join(phrase.split()).lower()
                if not key or key in hit_phrases:
                    continue
                hit_phrases.add(key)
                if not is_readable_face_phrase(phrase):
                    continue
                tallies[key] = tallies.get(key, 0) + 1
                if key not in display:
                    display[key] = " ".join(phrase.split())
    ranked = sorted(
        tallies,
        key=lambda key: (
            -tallies[key],
            -len(key.split()),
            -max(len(word) for word in key.split()),
            key,
        ),
    )
    return [(display[key], tallies[key]) for key in ranked]


def _phrase_hits_top_terms(phrase: str, terms: list[str]) -> bool:
    if not terms:
        return True
    stems = {subject_stem(word) for word in _WORD.findall(phrase)}
    for term in terms:
        stem = subject_stem(str(term))
        if len(stem) >= 3 and stem in stems:
            return True
    return False


def _pick_readable_title(
    posts: list[dict],
    *,
    forbidden: set[str] | None = None,
    terms: list[str] | None = None,
    prefer_words: list[str] | None = None,
) -> str | None:
    blocked = {item.lower() for item in (forbidden or set())}
    prefer = {str(word).lower() for word in (prefer_words or []) if str(word).strip()}
    weak_planet_token = (
        next(iter(prefer)) if len(prefer) == 1 and len(next(iter(prefer))) <= 4 else None
    )
    best: tuple[tuple[int, ...], str] | None = None
    for phrase, hits in _verbatim_phrase_candidates(posts):
        if phrase.lower() in blocked:
            continue
        phrase_words = [word.lower() for word in _WORD.findall(phrase)]
        if weak_planet_token and weak_planet_token not in phrase_words:
            continue
        if any(titles_alike(phrase, item) for item in forbidden or ()):
            continue
        if not _phrase_hits_top_terms(phrase, list(terms or [])):
            continue
        if not title_covers_posts(phrase, posts):
            continue
        words = _WORD.findall(phrase)
        lowers = [word.lower() for word in words]
        prefer_hits = sum(1 for word in prefer if word in lowers)
        acronym_pair = 1 if _acronym_topic_pair(words, lowers) else 0
        rank = (-prefer_hits, -acronym_pair, -hits, len(words), phrase.lower())
        if best is None or rank < best[0]:
            best = (rank, phrase)
    return best[1] if best else None


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


def _planet_name_needs_repair(name: str) -> bool:
    """Weak planet labels such as a single word 'Use'."""
    cleaned = str(name or "").strip()
    if not cleaned:
        return True
    return _title_is_weak(cleaned)


def _planet_posts(topic: dict, post_by_uri: dict[str, dict]) -> list[dict]:
    seen: set[str] = set()
    posts: list[dict] = []
    for face in topic.get("perspectives") or []:
        for post in _face_posts(face, post_by_uri):
            key = str(post.get("uri") or post.get("text") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            posts.append(post)
    return posts


def _planet_terms(topic: dict) -> list[str]:
    terms: list[str] = []
    for face in topic.get("perspectives") or []:
        for term in face.get("top_terms") or []:
            if term not in terms:
                terms.append(str(term))
    return terms[:10]


def _readable_prefix_from_face_title(title: str) -> str | None:
    words = _WORD.findall(str(title or ""))
    for width in (3, 2):
        if len(words) < width:
            continue
        candidate = " ".join(words[:width])
        if is_readable_face_phrase(candidate):
            return candidate
    return None


def _repair_planet_name(topic: dict, post_by_uri: dict[str, dict], stats: dict[str, Any]) -> None:
    name = str(topic.get("name") or "")
    if not _planet_name_needs_repair(name):
        return
    posts = _planet_posts(topic, post_by_uri)
    if len(posts) < 2:
        return
    terms = _planet_terms(topic)
    replacement = _pick_readable_title(posts, terms=terms, prefer_words=[name])
    if not replacement:
        faces = sorted(
            topic.get("perspectives") or [],
            key=lambda face: -int(face.get("post_count") or 0),
        )
        for face in faces:
            replacement = _readable_prefix_from_face_title(str(face.get("title") or ""))
            if replacement and title_covers_posts(replacement, posts):
                break
        else:
            replacement = None
    if not replacement:
        _record_still_unsupported(stats, planet=name, title=f"planet name: {name}")
        return
    _record_rename(stats, planet=name, old=name, new=replacement, reason="planet_name")
    topic["name"] = replacement
    stats["planet_renamed"] = int(stats.get("planet_renamed") or 0) + 1


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


def _record_rename(
    stats: dict[str, Any],
    *,
    planet: str,
    old: str,
    new: str,
    reason: str,
) -> None:
    stats["renames"].append(
        {"planet": planet, "old": old, "new": new, "reason": reason},
    )


def _record_still_unsupported(stats: dict[str, Any], *, planet: str, title: str) -> None:
    stats["still_unsupported"].append({"planet": planet, "title": title})


def _rename_duplicate_faces(
    topic: dict,
    post_by_uri: dict[str, dict],
    stats: dict[str, Any],
) -> int:
    """Give the smaller alike face a distinct grounded title when merge cannot fold it."""
    faces = list(topic.get("perspectives") or [])
    if len(faces) < 2:
        return 0
    renamed = 0
    planet_name = str(topic.get("name") or "")
    ranked = sorted(faces, key=lambda face: (-int(face.get("post_count") or 0), str(face.get("id") or "")))
    titles_seen: set[str] = set()
    for face in ranked:
        title = str(face.get("title") or "")
        if not title:
            continue
        clash = next((kept for kept in titles_seen if titles_alike(title, kept)), None)
        if clash is None:
            titles_seen.add(title)
            continue
        posts = _face_posts(face, post_by_uri)
        forbidden = {str(item) for item in titles_seen}
        replacement = _pick_readable_title(
            posts,
            forbidden=forbidden,
            terms=list(face.get("top_terms") or []),
        )
        if not replacement:
            titles_seen.add(title)
            continue
        _record_rename(stats, planet=planet_name, old=title, new=replacement, reason="duplicate")
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
) -> dict[str, Any]:
    """Fix unsupported titles, merge alike faces, then rename any leftover duplicates."""
    if post_by_uri is None:
        post_by_uri = {str(post.get("uri") or ""): post for post in (posts or [])}
    stats: dict[str, Any] = {
        "unsupported_renamed": 0,
        "merged": 0,
        "duplicate_renamed": 0,
        "planet_renamed": 0,
        "renames": [],
        "still_unsupported": [],
    }

    for topic in topics:
        _repair_planet_name(topic, post_by_uri, stats)
        planet_name = str(topic.get("name") or "")
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
            replacement = _pick_readable_title(
                sample_posts,
                terms=list(face.get("top_terms") or []),
            )
            if not replacement:
                _record_still_unsupported(stats, planet=planet_name, title=title)
                continue
            _record_rename(stats, planet=planet_name, old=title, new=replacement, reason="unsupported")
            face["title"] = replacement
            stats["unsupported_renamed"] += 1

    stats["merged"] = merge_alike_published_faces(topics)

    for topic in topics:
        stats["duplicate_renamed"] += _rename_duplicate_faces(topic, post_by_uri, stats)

    return stats


def repair_payload_face_titles(data: dict[str, Any]) -> dict[str, Any]:
    """Repair every planet in a published payload (offline checks on data.json)."""
    totals: dict[str, Any] = {
        "unsupported_renamed": 0,
        "merged": 0,
        "duplicate_renamed": 0,
        "planet_renamed": 0,
        "renames": [],
        "still_unsupported": [],
    }
    topics = list(data.get("topics") or [])
    if topics:
        part = repair_published_face_titles(topics, posts=None)
        _merge_stats(totals, part)
    for planets in (data.get("sections") or {}).values():
        section_topics = list(planets)
        if not section_topics:
            continue
        part = repair_published_face_titles(section_topics, posts=None)
        _merge_stats(totals, part)
    return totals


def _merge_stats(totals: dict[str, Any], part: dict[str, Any]) -> None:
    totals["unsupported_renamed"] += int(part.get("unsupported_renamed") or 0)
    totals["merged"] += int(part.get("merged") or 0)
    totals["duplicate_renamed"] += int(part.get("duplicate_renamed") or 0)
    totals["planet_renamed"] += int(part.get("planet_renamed") or 0)
    totals["renames"].extend(part.get("renames") or [])
    totals["still_unsupported"].extend(part.get("still_unsupported") or [])


def collect_renames(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(planet, old_title, new_title) for every changed face title."""
    rows: list[tuple[str, str, str]] = []
    for planet_before, planet_after in zip(
        list(iter_all_planets(before)),
        list(iter_all_planets(after)),
    ):
        name = str(planet_before.get("name") or "")
        for face_before, face_after in zip(
            planet_before.get("perspectives") or [],
            planet_after.get("perspectives") or [],
        ):
            old = str(face_before.get("title") or "")
            new = str(face_after.get("title") or "")
            if old and new and old != new:
                rows.append((name, old, new))
    return rows
