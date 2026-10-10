"""Put same-story posts back on the planet that already tells that story.

Three direct checks, none of them a chain:

- A noise post joins the nearest big planet when it is close to that
  planet's original center and its main subject stem is already that
  planet's subject.
- A smaller planet folds into a larger one only when the same check
  passes against that larger planet's original center. A planet that is
  itself folding into someone else is not a parent, so stories cannot
  chain.
- A face the claim gate drops gives a post back to a kept face only when
  that post's main subject is the kept face's subject.

Distinct stories stay apart. A Zionism post does not join a Gaza face
whose subject is Gaza, and two balls do not merge just because each is
close to a third ball.
"""

from __future__ import annotations

import re

import numpy as np

from pipeline.label import (
    _OFFICE_GLUE,
    _PERSON_GLUE,
    _TOPIC_GLUE,
    _VERB_STEMS,
    _is_specific_subject_word,
    _post_word_glue,
    content_tokens,
    subject_stem,
    titles_alike,
)
from pipeline.assemble import face_id
from pipeline.schema import SINGLE_VIEW_NOTE, to_percents

# A planet this large is a parent. Smaller survivors can fold into it.
# Noise posts attach only to a parent, never to another speck.
BIG_PLANET = 20
# Sibling planets below the publish floor are already noise.
MIN_SIBLING = 5
# Member peel is 0.50. Same-story posts often sit just outside that ball.
# The stem check is what keeps a nearby different story out.
ATTACH_COSINE = 0.42
# Direct sibling fold. Lower than the 0.72 center merge on purpose:
# the stem check, not the cosine, decides the story.
FOLD_COSINE = 0.55
# Two parents this close are ambiguous. The post or sibling stays put.
AMBIGUITY = 0.03
# A stem on this many planets is glue ("people", "midterm"), not a story.
GLOBAL_GLUE_PLANETS = 4
DOMINANT_SHARE = 0.18
DOMINANT_MIN = 3
# A second stem belongs to the story when it shows up with the top stem.
COOCCUR_WITH_TOP = 0.50
# Most of a sibling's posts have to be the parent's story.
SIBLING_MAJORITY = 0.60
# An all-caps token this common is the planet's name ("ICE").
ACRONYM_SHARE = 0.40

_ACRONYM = re.compile(r"\b[A-Z]{3}\b")
_ACRONYM_STOP = frozenset(
    {
        "and",
        "are",
        "but",
        "can",
        "did",
        "for",
        "had",
        "has",
        "her",
        "his",
        "how",
        "its",
        "let",
        "may",
        "not",
        "now",
        "one",
        "our",
        "the",
        "two",
        "usa",
        "war",
        "was",
        "who",
        "you",
    }
)
# Race words and other generics are not a story. "White" must not fold two moods together.
_GENERIC_STEMS = frozenset({"whit", "white", "black", "human", "peopl", "people"})
# A person is not a story. Putin alone must not pull a planet into Ukraine.
_PERSON_STEMS = _PERSON_GLUE | _GENERIC_STEMS | frozenset(
    {
        "putin",
        "netanyahu",
        "zelensky",
        "zelenskyy",
        "lukashenko",
        "starmer",
    }
)
_STEM_GLUE = _post_word_glue() | _PERSON_STEMS | _TOPIC_GLUE | _VERB_STEMS | _OFFICE_GLUE


def specific_stems(text: str) -> set[str]:
    """Subject stems in one post, plus an all-caps acronym such as ICE."""
    found: set[str] = set()
    for token in content_tokens(text):
        if len(token) < 4 or token in _STEM_GLUE:
            continue
        stem = subject_stem(token)
        if len(stem) < 4 or stem in _STEM_GLUE or stem in _VERB_STEMS:
            continue
        if not _is_specific_subject_word(stem):
            continue
        found.add(stem)
    for token in _ACRONYM.findall(str(text or "")):
        lowered = token.lower()
        if lowered not in _ACRONYM_STOP:
            found.add(lowered)
    return found


def stems_match(left: str, right: str) -> bool:
    """True when two stems are the same word or the same prefix (ukraine/ukrainian)."""
    if left == right:
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    return len(short) >= 5 and long.startswith(short)


def stem_in(stem: str, story: set[str]) -> bool:
    return any(stems_match(stem, other) for other in story)


def _stem_counts(texts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in texts:
        for stem in specific_stems(text):
            counts[stem] = counts.get(stem, 0) + 1
    return counts


def story_of(texts: list[str]) -> tuple[str | None, set[str]]:
    """The planet's top stem, and the other stems that travel with it.

    Another stem is included only when posts that use it usually also use the
    top stem. Zionism posts inside a Gaza planet mostly do not say Gaza, so
    Zionism is not a reason to attach more posts.
    """
    count = len(texts)
    if count == 0:
        return None, set()
    counts = _stem_counts(texts)
    ranked = sorted(counts, key=lambda stem: (-counts[stem], -len(stem), stem))
    dominant = []
    for stem in ranked:
        seen = counts[stem]
        share = seen / count
        acronym = len(stem) == 3
        if acronym and seen >= DOMINANT_MIN and share >= ACRONYM_SHARE:
            dominant.append(stem)
        elif not acronym and seen >= DOMINANT_MIN and share >= DOMINANT_SHARE:
            dominant.append(stem)
    if not dominant:
        return None, set()
    top = dominant[0]
    kept = {top}
    for stem in dominant[1:]:
        own = [text for text in texts if stem_in(stem, specific_stems(text))]
        if not own:
            continue
        both = sum(1 for text in own if stem_in(top, specific_stems(text)))
        if both / len(own) >= COOCCUR_WITH_TOP:
            kept.add(stem)
    return top, kept


def attachment_stems(texts: list[str]) -> set[str]:
    """Stems that name this planet's story, not a second story sitting inside it."""
    _top, kept = story_of(texts)
    return kept


def post_matches(text: str, story: set[str], required: str | None = None) -> bool:
    """True when the post's subject is already this story.

    ``required`` is the planet's top stem. A secondary stem such as "russia"
    on a Ukraine planet is not enough by itself, or a plague outbreak in
    Russia would join the war. A stem just a character or two longer than the
    story word is a different subject: "zionism" does not match a Gaza story
    even if the post also says Israel. A much longer token is a place name or
    a hashtag ("Zaporizhzhia") and does not cancel a story word already there.
    """
    found = specific_stems(text)
    if not found or not story:
        return False
    if required and not stem_in(required, found):
        return False
    matching = [stem for stem in found if stem_in(stem, story)]
    if not matching:
        return False
    longest = max(found, key=lambda stem: (len(stem), stem))
    if stem_in(longest, story):
        return True
    longest_match = max(matching, key=lambda stem: (len(stem), stem))
    return len(longest) > len(longest_match) + 1


def _groups(labels: np.ndarray) -> dict[int, np.ndarray]:
    found: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        if int(label) < 0:
            continue
        found.setdefault(int(label), []).append(index)
    return {label: np.asarray(members, dtype=int) for label, members in found.items()}


def _center(unit: np.ndarray, members: np.ndarray) -> np.ndarray:
    center = unit[members].mean(axis=0)
    norm = float(np.linalg.norm(center))
    if norm == 0.0:
        return center
    return center / norm


def _l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _without_global_glue(
    stories: dict[int, tuple[str | None, set[str]]],
    sizes: dict[int, int],
) -> dict[int, set[str]]:
    """Drop a stem that names many planets, except on the planet it names.

    "Iran" is the subject of several sibling planets, so the largest of those
    keeps it and the others can fold in. "Midterm" on many unrelated planets
    is not kept as a second magnet.
    """
    counts: dict[str, int] = {}
    for _top, stems in stories.values():
        for stem in stems:
            counts[stem] = counts.get(stem, 0) + 1
    glue = {stem for stem, seen in counts.items() if seen >= GLOBAL_GLUE_PLANETS}
    if not glue:
        return {label: set(stems) for label, (_top, stems) in stories.items()}
    owner: dict[str, int] = {}
    for label, (top, stems) in stories.items():
        for stem in stems & glue:
            if top != stem:
                continue
            current = owner.get(stem)
            if current is None or sizes.get(label, 0) > sizes.get(current, 0):
                owner[stem] = label
    for label, (_top, stems) in stories.items():
        for stem in stems & glue:
            if stem in owner:
                continue
            current = owner.get(stem)
            if current is None or sizes.get(label, 0) > sizes.get(current, 0):
                owner[stem] = label
    cleaned: dict[int, set[str]] = {}
    for label, (_top, stems) in stories.items():
        cleaned[label] = {stem for stem in stems if stem not in glue or owner.get(stem) == label}
    return cleaned


def _fold_targets(
    groups: dict[int, np.ndarray],
    story_stems: dict[int, set[str]],
    tops: dict[int, str | None],
    centroids: dict[int, np.ndarray],
    texts: list[str],
) -> dict[int, int]:
    """Map a sibling onto one larger planet. No parent is itself a sibling."""
    candidates: list[tuple[float, int, int]] = []
    for child, members in groups.items():
        if members.size < MIN_SIBLING:
            continue
        ranked: list[tuple[float, int]] = []
        for parent, parent_members in groups.items():
            if parent == child or parent_members.size < BIG_PLANET:
                continue
            if parent_members.size <= members.size:
                continue
            cosine = float(centroids[child] @ centroids[parent])
            if cosine < FOLD_COSINE:
                continue
            hits = sum(
                1
                for index in members
                if post_matches(texts[int(index)], story_stems[parent], required=tops.get(parent))
            )
            if hits / members.size < SIBLING_MAJORITY:
                continue
            ranked.append((cosine, parent))
        if not ranked:
            continue
        ranked.sort(reverse=True)
        best_cosine, best_parent = ranked[0]
        if len(ranked) > 1 and best_cosine - ranked[1][0] < AMBIGUITY:
            continue
        candidates.append((best_cosine, child, best_parent))
    children = {child for _cosine, child, _parent in candidates}
    chosen: dict[int, int] = {}
    for _cosine, child, parent in candidates:
        if parent in children:
            continue
        chosen[child] = parent
    return chosen


def _attach_noise(
    labels: np.ndarray,
    unit: np.ndarray,
    texts: list[str],
    groups: dict[int, np.ndarray],
    story_stems: dict[int, set[str]],
    tops: dict[int, str | None],
    centroids: dict[int, np.ndarray],
    skip: set[int],
    folded_away: set[int],
) -> int:
    parents = [
        label
        for label, members in groups.items()
        if members.size >= BIG_PLANET and label not in folded_away and tops.get(label) and story_stems.get(label)
    ]
    if not parents:
        return 0
    attached = 0
    noise = np.flatnonzero(labels < 0)
    for index in noise:
        index = int(index)
        if index in skip:
            continue
        ranked: list[tuple[float, int]] = []
        for label in parents:
            cosine = float(unit[index] @ centroids[label])
            if cosine < ATTACH_COSINE:
                continue
            if not post_matches(texts[index], story_stems[label], required=tops.get(label)):
                continue
            ranked.append((cosine, label))
        if not ranked:
            continue
        ranked.sort(reverse=True)
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < AMBIGUITY:
            continue
        labels[index] = ranked[0][1]
        attached += 1
    return attached


def attach_same_story(
    matrix: np.ndarray,
    texts: list[str],
    labels: list[int] | np.ndarray,
    *,
    skip: list[int] | set[int] | None = None,
    noise: bool = True,
    fold: bool = True,
) -> tuple[list[int], dict[str, int]]:
    """Return labels after the direct same-story checks.

    ``skip`` indexes were removed by the author cap and stay noise.
    ``noise`` and ``fold`` select steps so a measurement can run each one.
    Centers and stems are taken before either step, so nothing chains.
    """
    original = np.asarray(labels, dtype=int).copy()
    if original.size == 0:
        return [], {"attached": 0, "folded_planets": 0, "folded_posts": 0}
    unit = _l2(matrix)
    groups = _groups(original)
    sizes = {label: int(members.size) for label, members in groups.items()}
    stories = {label: story_of([texts[int(index)] for index in members]) for label, members in groups.items()}
    tops = {label: top for label, (top, _stems) in stories.items()}
    story_stems = _without_global_glue(stories, sizes)
    centroids = {label: _center(unit, members) for label, members in groups.items()}
    folded = _fold_targets(groups, story_stems, tops, centroids, texts) if fold else {}
    updated = original.copy()
    folded_posts = 0
    for child, parent in folded.items():
        members = groups[child]
        updated[members] = parent
        folded_posts += int(members.size)
    attached = 0
    if noise:
        attached = _attach_noise(
            updated,
            unit,
            texts,
            groups,
            story_stems,
            tops,
            centroids,
            set(skip or ()),
            set(folded),
        )
    stats = {
        "attached": int(attached),
        "folded_planets": len(folded),
        "folded_posts": int(folded_posts),
    }
    return [int(label) for label in updated], stats


def return_same_story_posts(
    kept: list[tuple[dict, list, int]],
    dropped: list[tuple[dict, list, int]],
    members: list[dict],
) -> tuple[list[tuple[dict, list, int]], int]:
    """Move dropped-face posts onto a kept face when the subject matches.

    Returns the kept drafts and how many posts came back. A post whose
    longest stem is a different subject stays off the planet.
    """
    if not kept or not dropped:
        return kept, 0
    by_uri = {str(post.get("uri") or ""): post for post in members}

    def face_texts(rows: list) -> list[str]:
        found = []
        for uri, _position, _distance in rows:
            post = by_uri.get(str(uri))
            if post is None:
                continue
            found.append(str(post.get("clean_text") or post.get("text") or ""))
        return found

    parsed = [story_of(face_texts(rows)) for _perspective, rows, _size in kept]
    updated = [[perspective, list(rows), int(size)] for perspective, rows, size in kept]
    restored = 0
    for _perspective, rows, _size in dropped:
        for uri, position, distance in rows:
            post = by_uri.get(str(uri))
            if post is None:
                continue
            text = str(post.get("clean_text") or post.get("text") or "")
            best = None
            best_size = -1
            for index, (_top, stems) in enumerate(parsed):
                # The kept face already had its posts dropped. Match the whole
                # story, not only the word that is most common on what remains.
                if not post_matches(text, stems):
                    continue
                if updated[index][2] > best_size:
                    best = index
                    best_size = updated[index][2]
            if best is None:
                continue
            target = updated[best]
            seen = {str(item) for item, _position, _distance in target[1]}
            if str(uri) in seen:
                continue
            target[1].append((uri, position, distance))
            target[2] += 1
            uris = target[0].setdefault("_face_member_uris", [])
            if str(uri) not in {str(item) for item in uris}:
                uris.append(str(uri))
            restored += 1
    return [(item[0], item[1], item[2]) for item in updated], restored


def merge_alike_published_faces(topics: list[dict], *, post_limit: int = 36) -> int:
    """Fold faces on one planet whose titles match after the wide relabel.

    The draft merge runs before that relabel, so a rename can recreate a
    duplicate. This pass runs after the new titles exist. Membership adds.
    Returns how many faces were folded in.
    """
    folded = 0
    for topic in topics:
        faces = list(topic.get("perspectives") or [])
        if len(faces) < 2:
            continue
        ranked = sorted(faces, key=lambda face: (-int(face.get("post_count") or 0), str(face.get("id") or "")))
        kept: list[dict] = []
        for face in ranked:
            match = next((item for item in kept if titles_alike(item.get("title"), face.get("title"))), None)
            if match is None:
                kept.append(face)
                continue
            folded += 1
            match["post_count"] = int(match.get("post_count") or 0) + int(face.get("post_count") or 0)
            uris = [str(item) for item in (match.get("_face_member_uris") or [])]
            seen = set(uris)
            for uri in face.get("_face_member_uris") or []:
                if str(uri) in seen:
                    continue
                seen.add(str(uri))
                uris.append(str(uri))
            if uris:
                match["_face_member_uris"] = uris
            shown = list(match.get("representative_posts") or [])
            seen_text = {str(post.get("text") or "") for post in shown}
            for post in face.get("representative_posts") or []:
                if str(post.get("text") or "") in seen_text:
                    continue
                shown.append(post)
                seen_text.add(str(post.get("text") or ""))
            match["representative_posts"] = shown[: max(int(post_limit), 1)]
        if len(kept) == len(faces):
            continue
        counts = [max(int(face.get("post_count") or 0), 0) for face in kept]
        topic["post_count"] = sum(counts)
        volumes = to_percents(counts) if sum(counts) else [0.0 for _ in kept]
        topic_id = int(topic.get("id") or 1)
        for index, (face, volume) in enumerate(zip(kept, volumes)):
            face["volume_percent"] = volume
            face["id"] = face_id(topic_id, index)
        topic["perspectives"] = kept
        if len(kept) == 1:
            topic["opposing_note"] = SINGLE_VIEW_NOTE
        else:
            topic.pop("opposing_note", None)
    return folded
