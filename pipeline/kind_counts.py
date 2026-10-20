"""Three report-only counts the duplicate score does not see.

Each count is a reading of the published edition. Nothing here drops,
rewrites, or folds a planet. The duplicate rate stays the duplicate rate.

Greeting titles are published planets in the pleasantry family named in
the #275 spec. Fragments are same-section planet pairs where both sides
are under ``BIG_PLANET`` (20) posts and the two titles share a content
stem or a short entity such as ``ai``. Face stance agreement is a
within-planet pair whose posts are the same subject and do not disagree
(``local_faces_fold``).
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.duplicate_rate import _iter_planets, _normalize_title, _post_count
from pipeline.label import _SHORT_SUBJECTS
from pipeline.stance import local_faces_fold
from pipeline.story_attach import BIG_PLANET, specific_stems, stem_in

# Planet titles the #275 spec calls one pleasantry family.
GREETING_TITLES = frozenset(
    {
        "good day",
        "good morning",
        "great day",
        "hope for the day",
        "wonderful day",
        "great time",
        "glad returns",
        "happy sunday",
        "good sunday",
    }
)


def _pair_key(left: str, right: str) -> tuple[str, str]:
    one, two = _normalize_title(left), _normalize_title(right)
    return (one, two) if one <= two else (two, one)


def _entities(text: str) -> set[str]:
    """Short subjects the stemmer drops, such as ai and ps5."""
    found: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+", str(text or "")):
        lowered = token.lower()
        if lowered in _SHORT_SUBJECTS or any(char.isdigit() for char in lowered):
            found.add(lowered)
    return found


def shares_stem_or_entity(left: dict, right: dict) -> bool:
    """True when the two titles share a content stem or a short entity.

    The stem or entity is read from the planet names. ``ai`` and ``ps5`` are
    entities because the content stemmer drops tokens under four characters.
    Overlap that shows up only inside representative posts is not this count.
    """
    left_name = str(left.get("name") or "")
    right_name = str(right.get("name") or "")
    if _entities(left_name) & _entities(right_name):
        return True
    left_stems = specific_stems(left_name)
    right_stems = specific_stems(right_name)
    return any(stem_in(stem, right_stems) for stem in left_stems)


def greeting_title_planets(payload: dict) -> list[dict[str, Any]]:
    """Published planets whose name is in the pleasantry family."""
    found: list[dict[str, Any]] = []
    for scope, planet in _iter_planets(payload):
        name = str(planet.get("name") or "")
        if _normalize_title(name) not in GREETING_TITLES:
            continue
        found.append(
            {
                "scope": scope,
                "name": name,
                "post_count": _post_count(planet),
            }
        )
    found.sort(key=lambda row: (row["scope"], row["name"].lower()))
    return found


def fragment_pairs(payload: dict) -> list[dict[str, Any]]:
    """Same-section pairs under 20 posts that share a stem or an entity."""
    grouped: dict[str, list[dict]] = {}
    for scope, planet in _iter_planets(payload):
        grouped.setdefault(scope, []).append(planet)
    found: list[dict[str, Any]] = []
    for scope, planets in grouped.items():
        ordered = sorted(planets, key=lambda planet: str(planet.get("name") or "").lower())
        for index, left in enumerate(ordered):
            if _post_count(left) >= BIG_PLANET:
                continue
            for right in ordered[index + 1 :]:
                if _post_count(right) >= BIG_PLANET:
                    continue
                if not shares_stem_or_entity(left, right):
                    continue
                found.append(
                    {
                        "scope": scope,
                        "left_title": str(left.get("name") or ""),
                        "right_title": str(right.get("name") or ""),
                        "left_posts": _post_count(left),
                        "right_posts": _post_count(right),
                    }
                )
    return found


def _face_posts(face: dict) -> list[dict]:
    posts = face.get("representative_posts")
    if not isinstance(posts, list):
        return []
    return [post for post in posts if isinstance(post, dict)]


def stance_agreement_pairs(payload: dict) -> list[dict[str, Any]]:
    """Within-planet face pairs on the same subject with no disagreement."""
    found: list[dict[str, Any]] = []
    for scope, planet in _iter_planets(payload):
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        for index, left in enumerate(faces):
            for right in faces[index + 1 :]:
                if not local_faces_fold(left, right, _face_posts(left), _face_posts(right)):
                    continue
                found.append(
                    {
                        "scope": scope,
                        "planet": str(planet.get("name") or ""),
                        "left_title": str(left.get("title") or ""),
                        "right_title": str(right.get("title") or ""),
                    }
                )
    return found


def measure_kind_counts(payload: dict) -> dict[str, Any]:
    """The three counts on one edition. The payload is not modified."""
    greetings = greeting_title_planets(payload)
    fragments = fragment_pairs(payload)
    stance = stance_agreement_pairs(payload)
    return {
        "report_only": True,
        "changes_edition": False,
        "greeting_titles": {
            "count": len(greetings),
            "planets": greetings,
            "rule": "Published planets whose name is in the pleasantry family.",
        },
        "fragments": {
            "count": len(fragments),
            "pairs": fragments,
            "rule": (
                "Same-section planet pairs where both are under 20 posts "
                "and their titles share a content stem or entity."
            ),
        },
        "stance_agreement": {
            "count": len(stance),
            "pairs": stance,
            "rule": "Within-planet face pairs on the same subject with no disagreement.",
        },
    }


def _yes_no(row: dict[str, str]) -> str | None:
    answer = str(row.get("is_duplicate") or "").strip().lower()
    if answer in {"yes", "no"}:
        return answer
    return None


def score_labeled_kinds(
    payload: dict,
    planet_rows: list[dict[str, str]],
    face_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Recall on labeled yes rows, and false flags on labeled no rows.

    Greeting and fragment rows are ``level`` ``planet``. Face rows are
    ``level`` ``face_census``. ``planet_leak`` and ``unsure`` stay out.
    """
    counts = measure_kind_counts(payload)
    greeting_names = {_normalize_title(row["name"]) for row in counts["greeting_titles"]["planets"]}
    fragment_keys = {
        (row["scope"],) + _pair_key(row["left_title"], row["right_title"])
        for row in counts["fragments"]["pairs"]
    }
    stance_keys = {
        (_normalize_title(row["planet"]),) + _pair_key(row["left_title"], row["right_title"])
        for row in counts["stance_agreement"]["pairs"]
    }

    def blank() -> dict[str, Any]:
        return {"yes": 0, "flagged_yes": 0, "no": 0, "false_flags": 0, "flagged_yes_ids": [], "false_flag_ids": []}

    buckets = {"greeting_titles": blank(), "fragments": blank(), "stance_agreement": blank()}

    def mark(kind: str, row: dict[str, str], flagged: bool) -> None:
        answer = _yes_no(row)
        if answer is None:
            return
        bucket = buckets[kind]
        pair_id = str(row.get("pair_id") or "")
        if answer == "yes":
            bucket["yes"] += 1
            if flagged:
                bucket["flagged_yes"] += 1
                bucket["flagged_yes_ids"].append(pair_id)
        else:
            bucket["no"] += 1
            if flagged:
                bucket["false_flags"] += 1
                bucket["false_flag_ids"].append(pair_id)

    for row in planet_rows:
        if str(row.get("level") or "") != "planet":
            continue
        answer = _yes_no(row)
        if answer is None:
            continue
        left = _normalize_title(str(row.get("title_a") or ""))
        right = _normalize_title(str(row.get("title_b") or ""))
        family = left in GREETING_TITLES and right in GREETING_TITLES
        published_pair = left in greeting_names and right in greeting_names
        if answer == "no" or family:
            mark("greeting_titles", row, published_pair)
        scope = str(row.get("section") or "")
        fragment = (scope,) + _pair_key(left, right) in fragment_keys
        if answer == "no" or not family:
            mark("fragments", row, fragment)

    for row in face_rows:
        if str(row.get("level") or "") != "face_census":
            continue
        if _yes_no(row) is None:
            continue
        key = (_normalize_title(str(row.get("planet") or "")),) + _pair_key(
            str(row.get("title_a") or ""),
            str(row.get("title_b") or ""),
        )
        mark("stance_agreement", row, key in stance_keys)

    labeled = {}
    for kind, bucket in buckets.items():
        labeled[kind] = {
            "recall": f"{bucket['flagged_yes']} of {bucket['yes']}",
            "flagged_yes": bucket["flagged_yes"],
            "yes": bucket["yes"],
            "false_flags": bucket["false_flags"],
            "no": bucket["no"],
            "flagged_yes_ids": bucket["flagged_yes_ids"],
            "false_flag_ids": bucket["false_flag_ids"],
        }
    counts["labeled"] = labeled
    return counts


def render_kind_count_lines(counts: dict[str, Any] | None) -> list[str]:
    """Markdown for the nightly summary. Empty when the block is missing."""
    if not counts:
        return []
    greeting = counts.get("greeting_titles") or {}
    fragments = counts.get("fragments") or {}
    stance = counts.get("stance_agreement") or {}
    lines = [
        "## Kind counts",
        "",
        "Report only. These counts do not change the edition and do not replace the duplicate score.",
        "",
        f"- Greeting titles: {greeting.get('count', 0)} published planets in the pleasantry family.",
        (
            f"- Fragments: {fragments.get('count', 0)} same-section pairs, "
            "both under 20 posts, whose titles share a content stem or entity."
        ),
        (
            f"- Face stance agreement: {stance.get('count', 0)} within-planet pairs "
            "on the same subject with no disagreement."
        ),
    ]
    labeled = counts.get("labeled") or {}
    if labeled:
        lines.extend(["", "Oct 19 labeled sample:", ""])
        captions = {
            "greeting_titles": "Greeting titles",
            "fragments": "Fragments",
            "stance_agreement": "Face stance agreement",
        }
        for key, caption in captions.items():
            row = labeled.get(key) or {}
            false_flags = int(row.get("false_flags") or 0)
            flag_word = "false flag" if false_flags == 1 else "false flags"
            lines.append(
                f"- {caption}: {row.get('flagged_yes', 0)} of {row.get('yes', 0)} labeled yes, "
                f"{false_flags} {flag_word} on {row.get('no', 0)} labeled no."
            )
    lines.append("")
    return lines
