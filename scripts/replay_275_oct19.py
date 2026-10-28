#!/usr/bin/env python3
"""Oct 19 baseline pair sample for issue #275.

Draws a seeded stratified sample of same-section planet pairs and
within-planet face pairs from the published edition. A face pair is two
faces of one planet. Cross-planet face pairs are not sampled. Similarity
bands are fixed cosine cuts on MiniLM centroids of representative posts.
The sample over-represents rare bands; the duplicate rate is the band rate
times that band's share of every pair in that population, not the
unweighted sample mean.

``validate_label_sheet`` runs before either CSV is written. It refuses a
sheet a labeler should not see.

``is_duplicate`` is left empty. Hand-picked examples are not in this sample.
They can be written to a separate sheet with ``--handpicked-out``.

No Jev call, no label model, no workflow dispatch. The 30-post floor (#266),
junk filter (#264), stance gate (#268), and exact-title fold (#235) are not
applied to the sample. A guards-on recount is stored beside the headline.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fixed before any draw. Not fit to labels.
SEED = 275
SAMPLE_SIZE = 60
# B0 starts below 0 so a negative cosine stays in the bottom band.
BANDS = (
    ("B0", -1.01, 0.40),
    ("B1", 0.40, 0.55),
    ("B2", 0.55, 0.70),
    ("B3", 0.70, 0.85),
    ("B4", 0.85, 1.01),
)
# Secondary similarity rule used only until blind labels exist.
# It is not written into the sample sheet.
NEAR_DUP_COSINE = 0.70
_STOP = frozenset(
    "the a an of and or to in on for is are be by with vs not no".split()
)
COLUMNS = [
    "pair_id",
    "level",
    "section",
    "planet_a",
    "planet_b",
    "title_a",
    "title_b",
    "post_count_a",
    "post_count_b",
    "sample_texts_a",
    "sample_texts_b",
    "is_duplicate",
]
HAND_COLUMNS = ["edition", "source", *COLUMNS]

# Trace examples. Never fed to the baseline sampler.
HAND_PLANETS_OCT19 = [
    ("272-comment", "Technology", "AI Generated Articles", "AI bots"),
    ("272-comment", "Technology", "AI Generated Articles", "AI Adoption"),
    ("272-comment", "Technology", "AI Generated Articles", "AI Creative Effort"),
    ("272-comment", "Technology", "AI Generated Articles", "Crazy"),
    ("272-comment", "Technology", "AI Generated Articles", "AI Art"),
    ("272-comment", "Technology", "AI bots", "AI Adoption"),
    ("272-comment", "Technology", "AI bots", "AI Creative Effort"),
    ("272-comment", "Technology", "AI bots", "Crazy"),
    ("272-comment", "Technology", "AI bots", "AI Art"),
    ("272-comment", "Technology", "AI Adoption", "AI Creative Effort"),
    ("272-comment", "Technology", "AI Adoption", "Crazy"),
    ("272-comment", "Technology", "AI Adoption", "AI Art"),
    ("272-comment", "Technology", "AI Creative Effort", "Crazy"),
    ("272-comment", "Technology", "AI Creative Effort", "AI Art"),
    ("272-comment", "Technology", "Crazy", "AI Art"),
    ("272-comment", "Technology", "AI Control", "AI Generated Articles"),
    ("272-comment", "Technology", "AI Control", "AI Art"),
    ("272-comment", "Sports", "PS6 Pricing", "PS5 Compatibility"),
    ("272-comment", "Sports", "PS6 Pricing", "Sony PS5"),
    ("272-comment", "Sports", "PS6 Pricing", "Playstation Games Sony"),
    ("272-comment", "Sports", "PS5 Compatibility", "Sony PS5"),
    ("272-comment", "Sports", "PS5 Compatibility", "Playstation Games Sony"),
    ("272-comment", "Sports", "Sony PS5", "Playstation Games Sony"),
    ("272-comment", "Culture", "Tax Movie Titles", "Tax Purposes"),
    ("272-comment", "Health", "ADHD Struggles", "ADHD Struggles 2"),
    ("272-comment", "Education", "School Surgeries", "School Medical Care"),
    ("272-comment", "Other", "Good Day", "Good Morning"),
    ("272-comment", "Other", "Good Morning", "Great Day"),
    ("272-comment", "Other", "Great Day", "Hope For The Day"),
    ("272-comment", "Other", "Hope For The Day", "wonderful day"),
    ("272-comment", "Other", "wonderful day", "Great Time"),
    ("272-comment", "Other", "Great Time", "Glad Returns"),
    ("272-comment", "Other", "Glad Returns", "Happy Sunday"),
    ("272-comment", "Other", "Good Day", "Happy Sunday"),
    ("272-comment", "Business", "Trump Gas Prices", "Brent Oil Prices"),
    ("272-comment", "Business", "Millionaire Definition", "Ultra Rich"),
    ("272-comment", "World", "US Ukraine War", "Russia Sanctions"),
    ("272-comment", "World", "US Ukraine War", "Trump Krasnov Link"),
    ("272-comment", "World", "Russia Sanctions", "US Unreliable"),
    ("272-comment", "Sports", "College Football Playoff", "BYU vs Notre Dame"),
    ("272-comment", "Environment", "Fires", "Coffee Building Fire"),
    ("272-comment", "Environment", "Cold Weather", "Angeles Cities Heat"),
    ("272-comment", "Environment", "Cold Weather", "Autumn Foliage"),
    ("272-comment", "Environment", "Cold Weather", "Pretty Flowers"),
    ("272-comment", "Education", "Bar Exam", "Bits Limited Neighborhood"),
    ("272-comment", "Health", "Mental Health Struggles", "ADHD Struggles"),
]
HAND_PLANETS_OCT20 = [
    ("2026-10-20 live", "Technology", "AI Use", "AI Use 2"),
    ("2026-10-20 live", "Technology", "Data Centers", "AI Data Centres"),
    ("2026-10-20 live", "Business", "Tesla Flying Roadster", "Elon Flying Cars"),
    ("2026-10-20 live", "Other", "Cat Behavior", "Kitten Behavior"),
]
HAND_FACES_OCT20 = [
    ("#278", "global", "Bad Jobs", "Bad Jobs", "global", "Bad Jobs", "Short Lived Jobs"),
    ("#279", "global", "Trump Putin Ukraine", "Trump Helps Russia", "global", "Trump Putin Ukraine", "Trump Supports Putin"),
]


def _catalogs(edition: dict) -> list[tuple[str, list[dict]]]:
    rows = [("global", list(edition.get("topics") or []))]
    for name, planets in (edition.get("sections") or {}).items():
        rows.append((str(name), list(planets or [])))
    return rows


def _clip(text: str, limit: int = 240) -> str:
    flat = " ".join(str(text or "").split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


def _samples(posts: list[dict], n: int = 3) -> str:
    chunks = []
    for post in posts[:n]:
        text = _clip(str(post.get("text") or ""))
        if text:
            chunks.append(text)
    return " || ".join(chunks)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", str(text or "").lower())
        if len(token) >= 3 and token not in _STOP
    }


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _centroid(rows: np.ndarray) -> np.ndarray | None:
    if len(rows) == 0:
        return None
    center = rows.mean(axis=0)
    norm = float(np.linalg.norm(center))
    if norm == 0.0:
        return None
    return center / norm


def _embed_map(texts: list[str]) -> dict[str, np.ndarray]:
    from pipeline.embed import embed_minilm

    unique = list(dict.fromkeys(text for text in texts if text))
    if not unique:
        return {}
    vectors = _l2(embed_minilm(unique))
    return {text: vectors[index] for index, text in enumerate(unique)}


def _band(cosine: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= cosine < hi:
            return name
    if cosine < BANDS[0][1]:
        return BANDS[0][0]
    return BANDS[-1][0]


def _planet_posts(planet: dict) -> list[dict]:
    posts: list[dict] = []
    for face in planet.get("perspectives") or []:
        posts.extend(face.get("representative_posts") or [])
    return posts


def _center_of(posts: list[dict], vectors: dict[str, np.ndarray]) -> np.ndarray | None:
    rows = []
    for post in posts:
        text = str(post.get("text") or "").strip()
        if text in vectors:
            rows.append(vectors[text])
    if not rows:
        return None
    return _centroid(np.vstack(rows))


def _enumerate(edition: dict, vectors: dict[str, np.ndarray]) -> tuple[list[dict], list[dict]]:
    planets: list[dict] = []
    faces: list[dict] = []
    for scope, group in _catalogs(edition):
        centers = [_center_of(_planet_posts(planet), vectors) for planet in group]
        for left in range(len(group)):
            if centers[left] is None:
                continue
            for right in range(left + 1, len(group)):
                if centers[right] is None:
                    continue
                cosine = float(centers[left] @ centers[right])
                planets.append(
                    {
                        "level": "planet",
                        "section": scope,
                        "planet_a": group[left].get("name") or "",
                        "planet_b": group[right].get("name") or "",
                        "title_a": group[left].get("name") or "",
                        "title_b": group[right].get("name") or "",
                        "post_count_a": int(group[left].get("post_count") or 0),
                        "post_count_b": int(group[right].get("post_count") or 0),
                        "sample_texts_a": _samples(_planet_posts(group[left])),
                        "sample_texts_b": _samples(_planet_posts(group[right])),
                        "cosine": cosine,
                        "title_jaccard": _jaccard(group[left].get("name") or "", group[right].get("name") or ""),
                        "band": _band(cosine),
                        "same_planet": False,
                        "keep_planet": True,
                    }
                )
        face_rows = []
        for planet in group:
            for face in planet.get("perspectives") or []:
                posts = list(face.get("representative_posts") or [])
                center = _center_of(posts, vectors)
                if center is None:
                    continue
                face_rows.append((planet, face, center, posts))
        for left in range(len(face_rows)):
            planet_a, face_a, center_a, posts_a = face_rows[left]
            for right in range(left + 1, len(face_rows)):
                planet_b, face_b, center_b, posts_b = face_rows[right]
                cosine = float(center_a @ center_b)
                same = planet_a is planet_b
                faces.append(
                    {
                        "level": "face",
                        "section": scope,
                        "planet_a": planet_a.get("name") or "",
                        "planet_b": planet_b.get("name") or "",
                        "title_a": face_a.get("title") or "",
                        "title_b": face_b.get("title") or "",
                        "post_count_a": int(face_a.get("post_count") or 0),
                        "post_count_b": int(face_b.get("post_count") or 0),
                        "sample_texts_a": _samples(posts_a),
                        "sample_texts_b": _samples(posts_b),
                        "cosine": cosine,
                        "title_jaccard": _jaccard(face_a.get("title") or "", face_b.get("title") or ""),
                        "band": _band(cosine),
                        "same_planet": same,
                        "planet_posts": int(planet_a.get("post_count") or 0),
                    }
                )
    return planets, faces


def _allocate(groups: dict[str, list[dict]], target: int) -> dict[str, int]:
    names = [name for name, _lo, _hi in BANDS if groups.get(name)]
    base = target // len(BANDS)
    alloc = {name: min(base, len(groups.get(name, []))) for name in names}
    left = target - sum(alloc.values())
    order = sorted(names, key=lambda name: -len(groups[name]))
    while left > 0:
        moved = False
        for name in order:
            if alloc[name] < len(groups[name]):
                alloc[name] += 1
                left -= 1
                moved = True
                if left == 0:
                    break
        if not moved:
            break
    return alloc


# The labeled Oct 19 planet ids live on these paths. A later edition must not overwrite them.
OCT19_PAIRS = ROOT / "docs" / "evidence" / "275" / "oct19-pairs.csv"
OCT19_DESIGN = ROOT / "docs" / "evidence" / "275" / "oct19-sample-design.json"
SNAPSHOTS = {"2026-10-19": "44a537b", "2026-10-20": "b049731"}


def _trace_planet_specs(edition_day: str) -> list[tuple]:
    if edition_day == "2026-10-19":
        return list(HAND_PLANETS_OCT19)
    if edition_day == "2026-10-20":
        return list(HAND_PLANETS_OCT20)
    return []


def _trace_planet_keys(edition_day: str = "2026-10-19") -> set[tuple[str, str, str]]:
    """Title pairs that belong on the hand-picked sheet, either order."""
    keys: set[tuple[str, str, str]] = set()
    for _source, section, left, right in _trace_planet_specs(edition_day):
        keys.add((section, left, right))
        keys.add((section, right, left))
    return keys


def _trace_face_keys(edition_day: str) -> set[tuple[str, str, str, str]]:
    """Within-planet face pairs that stay on the hand-picked sheet, either order."""
    if edition_day != "2026-10-20":
        return set()
    keys: set[tuple[str, str, str, str]] = set()
    for _source, scope_a, planet_a, title_a, _scope_b, planet_b, title_b in HAND_FACES_OCT20:
        if scope_a == _scope_b and planet_a == planet_b:
            keys.add((scope_a, planet_a, title_a, title_b))
            keys.add((scope_a, planet_a, title_b, title_a))
    return keys


def _guard_edition_outputs(last_updated: str, out: Path, design_out: Path) -> str | None:
    """Block a run that would replace the Oct 19 labeled yardstick."""
    if not last_updated:
        return "edition has no last_updated"
    protected = {OCT19_PAIRS.resolve(), OCT19_DESIGN.resolve()}
    targets = {Path(out).resolve(), Path(design_out).resolve()}
    if last_updated != "2026-10-19" and targets & protected:
        return (
            f"Refusing to write the Oct 19 yardstick from edition {last_updated}. "
            "Pass --out and --design-out for the other day."
        )
    if OCT19_PAIRS.resolve() in targets and OCT19_PAIRS.exists():
        return "Refusing to overwrite docs/evidence/275/oct19-pairs.csv (the labeled yardstick)."
    if OCT19_DESIGN.resolve() in targets and OCT19_DESIGN.exists():
        return "Refusing to overwrite docs/evidence/275/oct19-sample-design.json."
    return None


def _census_sheet(within_faces: list[dict]) -> list[dict]:
    """Every within-planet face pair, in a stable order, unlabeled."""
    ordered = sorted(
        (
            pair
            for pair in within_faces
            if pair.get("same_planet") is True
            and pair.get("planet_a")
            and pair.get("planet_a") == pair.get("planet_b")
            and pair.get("title_a")
            and pair.get("title_a") != pair.get("title_b")
        ),
        key=lambda pair: (
            pair.get("section") or "",
            pair.get("planet_a") or "",
            pair.get("title_a") or "",
            pair.get("title_b") or "",
        ),
    )
    rows = []
    for index, pair in enumerate(ordered, start=1):
        row = dict(pair)
        row["pair_id"] = f"c{index:03d}"
        row["level"] = "face"
        row["is_duplicate"] = ""
        rows.append(row)
    return rows


class SampleSheetError(ValueError):
    """The sheet about to be labeled does not match its buckets."""


def _endpoint(row: dict) -> tuple:
    section = str(row.get("section") or "")
    ends = [
        (section, str(row.get("planet_a") or ""), str(row.get("title_a") or "")),
        (section, str(row.get("planet_b") or ""), str(row.get("title_b") or "")),
    ]
    return tuple(sorted(ends))


def validate_label_sheet(rows: list[dict]) -> None:
    """Fail before a CSV is handed to a labeler.

    Face rows are two distinct faces of one planet (``same_planet`` true).
    Planet rows are two different planets in one section. No row may repeat
    another row's endpoints, in either order, including a face row that
    copies a planet row.
    """
    errors: list[str] = []
    seen: dict[tuple, str] = {}
    seen_ids: set[str] = set()
    for row in rows:
        pair_id = str(row.get("pair_id") or "?")
        level = row.get("level")
        section = str(row.get("section") or "")
        planet_a = str(row.get("planet_a") or "")
        planet_b = str(row.get("planet_b") or "")
        title_a = str(row.get("title_a") or "")
        title_b = str(row.get("title_b") or "")
        if level == "face":
            if row.get("same_planet") is not True:
                errors.append(f"{pair_id}: face row requires same_planet true")
            if not planet_a or planet_a != planet_b:
                errors.append(f"{pair_id}: face row must be two faces of one planet")
            if not title_a or not title_b or title_a == title_b:
                errors.append(f"{pair_id}: face row must be two distinct faces")
            if not section or "|" in section:
                errors.append(f"{pair_id}: face row must name one section")
        elif level == "planet":
            if row.get("same_planet") is True:
                errors.append(f"{pair_id}: planet row cannot have same_planet true")
            if not planet_a or not planet_b or planet_a == planet_b:
                errors.append(f"{pair_id}: planet row must be two different planets")
            if not section or "|" in section:
                errors.append(f"{pair_id}: planet row must be one section")
        else:
            errors.append(f"{pair_id}: level must be planet or face, got {level!r}")
        key = _endpoint(row)
        if key in seen:
            errors.append(f"{pair_id}: duplicates {seen[key]}")
        else:
            seen[key] = pair_id
        if pair_id in seen_ids:
            errors.append(f"{pair_id}: duplicate pair id")
        else:
            seen_ids.add(pair_id)
    if errors:
        raise SampleSheetError("label sheet failed validation:\n" + "\n".join(errors))


def _draw(pairs: list[dict], *, prefix: str, require_same_planet: bool = False) -> list[dict]:
    pool = pairs
    if require_same_planet:
        pool = [
            pair
            for pair in pairs
            if pair.get("same_planet") is True
            and pair.get("planet_a")
            and pair.get("planet_a") == pair.get("planet_b")
            and pair.get("title_a")
            and pair.get("title_a") != pair.get("title_b")
        ]
    groups: dict[str, list[dict]] = {name: [] for name, _lo, _hi in BANDS}
    for pair in pool:
        groups[pair["band"]].append(pair)
    alloc = _allocate(groups, SAMPLE_SIZE)
    rng = random.Random(SEED)
    chosen: list[dict] = []
    for name, _lo, _hi in BANDS:
        pool = list(groups.get(name, []))
        rng.shuffle(pool)
        chosen.extend(pool[: alloc.get(name, 0)])
    rng.shuffle(chosen)
    for index, pair in enumerate(chosen, start=1):
        pair["pair_id"] = f"{prefix}{index:03d}"
        pair["is_duplicate"] = ""
    return chosen


def _band_table(pairs: list[dict]) -> list[dict]:
    total = len(pairs) or 1
    rows = []
    for name, lo, hi in BANDS:
        members = [pair for pair in pairs if pair["band"] == name]
        dup = [pair for pair in members if pair["cosine"] >= NEAR_DUP_COSINE]
        share = len(members) / total if pairs else 0.0
        rate = (len(dup) / len(members)) if members else 0.0
        rows.append(
            {
                "band": name,
                "lo": lo,
                "hi": hi,
                "pairs": len(members),
                "share": round(share, 6),
                "secondary_near_dup_pairs": len(dup),
                "secondary_near_dup_rate": round(rate, 6),
                "contribution": round(share * rate, 6),
            }
        )
    return rows


def _headline_from_bands(table: list[dict]) -> float:
    return round(sum(row["contribution"] for row in table), 6)


def _planet_headline(pairs: list[dict]) -> dict:
    """Near-duplicate planets per section, from the full pair census.

    A pair at or above NEAR_DUP_COSINE counts. The pair rate is the reweighted
    band sum. Planets per section is that census divided by the number of
    solar systems, which matches the reweighted count and does not use the
    sample's unweighted mean.
    """
    table = _band_table(pairs)
    by_section: dict[str, list[dict]] = {}
    for pair in pairs:
        by_section.setdefault(pair["section"], []).append(pair)
    per_section = []
    involved_total = 0
    dup_total = 0
    for section, members in sorted(by_section.items()):
        dup = [pair for pair in members if pair["cosine"] >= NEAR_DUP_COSINE]
        names: set[str] = set()
        for pair in dup:
            names.add(pair["planet_a"])
            names.add(pair["planet_b"])
        planets = {pair["planet_a"] for pair in members} | {pair["planet_b"] for pair in members}
        dup_total += len(dup)
        involved_total += len(names)
        per_section.append(
            {
                "section": section,
                "planets": len(planets),
                "pairs": len(members),
                "near_dup_pairs": len(dup),
                "planets_in_a_near_dup_pair": len(names),
            }
        )
    sections = len(per_section) or 1
    return {
        "pair_rate_reweighted": _headline_from_bands(table),
        "near_dup_pairs": dup_total,
        "near_duplicate_planet_pairs_per_section": round(dup_total / sections, 4),
        "planets_in_a_near_dup_pair_per_section": round(involved_total / sections, 4),
        "sections": len(per_section),
        "bands": table,
        "per_section": per_section,
    }


def _face_headline(pairs: list[dict], n_planets: int) -> dict:
    """Near-duplicate faces per planet.

    The population is within-planet face pairs. Cross-planet pairs in the
    same section are a different set and are not mixed into this rate.
    """
    within = [pair for pair in pairs if pair.get("same_planet")]
    table = _band_table(within)
    dup = [pair for pair in within if pair["cosine"] >= NEAR_DUP_COSINE]
    planets = n_planets or 1
    by_planet: dict[tuple[str, str], int] = {}
    for pair in dup:
        key = (pair["section"], pair["planet_a"])
        by_planet[key] = by_planet.get(key, 0) + 1
    return {
        "within_planet_pairs": len(within),
        "pair_rate_reweighted": _headline_from_bands(table),
        "near_dup_face_pairs": len(dup),
        "near_duplicate_face_pairs_per_planet": round(len(dup) / planets, 4),
        "planets": n_planets,
        "planets_with_a_near_dup_face_pair": len(by_planet),
        "bands": table,
        "same_section_including_cross_planet": {
            "pairs": len(pairs),
            "bands": _band_table(pairs),
            "pair_rate_reweighted": _headline_from_bands(_band_table(pairs)),
        },
    }


def _junk_names(edition: dict) -> set[tuple[str, str]]:
    from pipeline.chitchat_guard import planet_chitchat_reason

    dropped = set()
    for scope, group in _catalogs(edition):
        for planet in group:
            reps = [
                {"text": post.get("text") or "", "author": post.get("author") or ""}
                for post in _planet_posts(planet)
            ]
            if planet_chitchat_reason(reps, []):
                dropped.add((scope, str(planet.get("name") or "")))
            elif int(planet.get("post_count") or 0) < 30:
                dropped.add((scope, str(planet.get("name") or "")))
    return dropped


def _filter_guards(planets: list[dict], faces: list[dict], dropped: set[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    def keep_planet(pair: dict) -> bool:
        return (pair["section"], pair["planet_a"]) not in dropped and (
            pair["section"], pair["planet_b"]
        ) not in dropped

    def keep_face(pair: dict) -> bool:
        return (pair["section"], pair["planet_a"]) not in dropped and (
            pair["section"], pair["planet_b"]
        ) not in dropped

    return [pair for pair in planets if keep_planet(pair)], [pair for pair in faces if keep_face(pair)]


def _csv_row(pair: dict) -> dict:
    return {column: pair.get(column, "") for column in COLUMNS}


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = {column: row.get(column, "") for column in columns}
            writer.writerow(out)


def _index(edition: dict) -> dict[tuple[str, str], dict]:
    found = {}
    for scope, group in _catalogs(edition):
        for planet in group:
            found[(scope, str(planet.get("name") or ""))] = planet
    return found


def _hand_rows(edition: dict, edition_name: str, planet_specs, face_specs) -> list[dict]:
    index = _index(edition)
    rows = []
    number = 1
    for source, scope, left_name, right_name in planet_specs:
        left = index[(scope, left_name)]
        right = index[(scope, right_name)]
        rows.append(
            {
                "edition": edition_name,
                "source": source,
                "pair_id": f"h{number:03d}",
                "level": "planet",
                "section": scope,
                "planet_a": left_name,
                "planet_b": right_name,
                "title_a": left_name,
                "title_b": right_name,
                "post_count_a": int(left.get("post_count") or 0),
                "post_count_b": int(right.get("post_count") or 0),
                "sample_texts_a": _samples(_planet_posts(left)),
                "sample_texts_b": _samples(_planet_posts(right)),
                "same_planet": False,
                "is_duplicate": "",
            }
        )
        number += 1
    for source, scope_a, planet_a, title_a, scope_b, planet_b, title_b in face_specs:
        left = index[(scope_a, planet_a)]
        right = index[(scope_b, planet_b)]
        face_a = next(face for face in left.get("perspectives") or [] if face.get("title") == title_a)
        face_b = next(face for face in right.get("perspectives") or [] if face.get("title") == title_b)
        rows.append(
            {
                "edition": edition_name,
                "source": source,
                "pair_id": f"h{number:03d}",
                "level": "face",
                "section": scope_a if scope_a == scope_b else f"{scope_a}|{scope_b}",
                "planet_a": planet_a,
                "planet_b": planet_b,
                "title_a": title_a,
                "title_b": title_b,
                "post_count_a": int(face_a.get("post_count") or 0),
                "post_count_b": int(face_b.get("post_count") or 0),
                "sample_texts_a": _samples(list(face_a.get("representative_posts") or [])),
                "sample_texts_b": _samples(list(face_b.get("representative_posts") or [])),
                "same_planet": scope_a == scope_b and planet_a == planet_b,
                "is_duplicate": "",
            }
        )
        number += 1
    return rows


def _design(level: str, population: list[dict], sample: list[dict], headline: dict) -> dict:
    alloc: dict[str, int] = {}
    for pair in sample:
        alloc[pair["band"]] = alloc.get(pair["band"], 0) + 1
    return {
        "level": level,
        "population_pairs": len(population),
        "sampled_pairs": len(sample),
        "allocation": alloc,
        "headline": {key: value for key, value in headline.items() if key != "per_section"},
        "sample": [
            {
                "pair_id": pair["pair_id"],
                "section": pair["section"],
                "band": pair["band"],
                "cosine": round(pair["cosine"], 4),
                "title_jaccard": round(pair["title_jaccard"], 4),
                "same_planet": bool(pair.get("same_planet")),
            }
            for pair in sample
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stratified Oct 19 pair sample")
    parser.add_argument("--edition", type=Path, required=True)
    parser.add_argument("--oct20", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evidence" / "275" / "oct19-pairs.csv")
    parser.add_argument(
        "--design-out",
        type=Path,
        default=ROOT / "docs" / "evidence" / "275" / "oct19-sample-design.json",
    )
    parser.add_argument(
        "--handpicked-out",
        type=Path,
        default=ROOT / "docs" / "evidence" / "275" / "handpicked-pairs.csv",
    )
    parser.add_argument("--census-out", type=Path, default=None)
    parser.add_argument("--skip-handpicked", action="store_true")
    args = parser.parse_args(argv)
    edition = json.loads(args.edition.read_text(encoding="utf-8"))
    edition_day = str(edition.get("last_updated") or "")
    blocked = _guard_edition_outputs(edition_day, args.out, args.design_out)
    if blocked:
        print(blocked, file=sys.stderr)
        return 2
    texts: list[str] = []
    for _scope, group in _catalogs(edition):
        for planet in group:
            for post in _planet_posts(planet):
                text = str(post.get("text") or "").strip()
                if text:
                    texts.append(text)
    print(f"Embedding {len(set(texts))} representative posts...", flush=True)
    vectors = _embed_map(texts)
    planet_pairs, face_pairs = _enumerate(edition, vectors)
    trace_keys = _trace_planet_keys(edition_day)
    face_trace_keys = _trace_face_keys(edition_day)
    drawable_planets = [
        pair
        for pair in planet_pairs
        if (pair["section"], pair["title_a"], pair["title_b"]) not in trace_keys
    ]
    planet_sample = _draw([dict(pair) for pair in drawable_planets], prefix="p")
    within_planet = [
        pair
        for pair in face_pairs
        if pair.get("same_planet") is True and pair.get("planet_a") == pair.get("planet_b")
    ]
    held_same_title = [pair for pair in within_planet if pair.get("title_a") == pair.get("title_b")]
    within_faces = [pair for pair in within_planet if pair.get("title_a") != pair.get("title_b")]
    drawable_faces = [
        pair
        for pair in within_faces
        if (pair["section"], pair["planet_a"], pair["title_a"], pair["title_b"]) not in face_trace_keys
    ]
    face_sample = _draw([dict(pair) for pair in drawable_faces], prefix="f", require_same_planet=True)
    census = _census_sheet(within_faces)
    leaked = [
        pair["pair_id"]
        for pair in planet_sample
        if (pair["section"], pair["title_a"], pair["title_b"]) in trace_keys
    ]
    if leaked:
        print(f"trace pairs leaked into the baseline sample: {leaked}", file=sys.stderr)
        return 2
    if any(row["is_duplicate"] for row in planet_sample + face_sample):
        print("is_duplicate must stay empty", file=sys.stderr)
        return 2
    n_planets = sum(len(group) for _scope, group in _catalogs(edition))
    planet_head = _planet_headline(planet_pairs)
    face_head = _face_headline(face_pairs, n_planets)
    dropped = _junk_names(edition)
    guarded_planets, guarded_faces = _filter_guards(planet_pairs, face_pairs, dropped)
    guarded_n = n_planets - len({name for _scope, name in dropped})
    design = {
        "edition": edition_day,
        "snapshot": SNAPSHOTS.get(edition_day),
        "seed": SEED,
        "rng": (
            "Each level starts its own random.Random(275). For each band in "
            "B0..B4 order, shuffle that band's pairs and take the allocation. "
            "Then shuffle the chosen rows and number them. Face rows are drawn "
            "only from pairs with same_planet true. Hand-picked planet pairs for "
            "this edition are removed before the planet draw. On 2026-10-20 the "
            "hand-picked face pairs are removed before the face draw and stay "
            "in the face census. Band shares and the similarity headline still "
            "count every pair in that population. validate_label_sheet runs "
            "before any CSV is written."
        ),
        "similarity": (
            "Cosine of MiniLM (all-MiniLM-L6-v2) centroids of representative "
            "posts. Title Jaccard is stored on the design file only."
        ),
        "bands": [
            {"id": name, "lo_inclusive": lo, "hi_exclusive": hi} for name, lo, hi in BANDS
        ],
        "secondary_near_duplicate_rule": f"representative centroid cosine >= {NEAR_DUP_COSINE}",
        "reweight": (
            "Headline = sum over bands of (near-dup rate inside the band) "
            "* (band's share of all pairs in that population). The sample "
            "mean is not the headline."
        ),
        "guards": "off for the sample and the headline. guards_on drops planets under 30 posts or flagged by planet_chitchat_reason on representative posts.",
        "planets": {
            **_design("planet", planet_pairs, planet_sample, planet_head),
            "excluded_trace_pairs": len(planet_pairs) - len(drawable_planets),
            "sample_pool_pairs": len(drawable_planets),
        },
        "faces": {
            **_design("face", within_faces, face_sample, face_head),
            "excluded_trace_pairs": len(within_faces) - len(drawable_faces),
            "census_pairs": len(census),
            "held_out_same_title": [
                {
                    "section": pair["section"],
                    "planet": pair["planet_a"],
                    "title": pair["title_a"],
                    "post_count_a": pair["post_count_a"],
                    "post_count_b": pair["post_count_b"],
                }
                for pair in held_same_title
            ],
        },
        "face_census": [
            {
                "pair_id": row["pair_id"],
                "section": row["section"],
                "planet": row["planet_a"],
                "title_a": row["title_a"],
                "title_b": row["title_b"],
                "band": row["band"],
                "cosine": round(row["cosine"], 4),
                "post_count_a": row["post_count_a"],
                "post_count_b": row["post_count_b"],
            }
            for row in census
        ],
        "headline_guards_off": {
            "near_duplicate_planet_pairs_per_section": planet_head["near_duplicate_planet_pairs_per_section"],
            "planets_in_a_near_dup_pair_per_section": planet_head["planets_in_a_near_dup_pair_per_section"],
            "planet_pair_rate_reweighted": planet_head["pair_rate_reweighted"],
            "near_duplicate_face_pairs_per_planet": face_head["near_duplicate_face_pairs_per_planet"],
            "face_pair_rate_reweighted_within_planet": face_head["pair_rate_reweighted"],
            "planet_bands": planet_head["bands"],
            "within_planet_face_bands": face_head["bands"],
        },
        "headline_guards_on_floor30_and_junk": {
            "planets_dropped": len(dropped),
            "near_duplicate_planet_pairs_per_section": _planet_headline(guarded_planets)[
                "near_duplicate_planet_pairs_per_section"
            ],
            "planet_pair_rate_reweighted": _planet_headline(guarded_planets)["pair_rate_reweighted"],
            "near_duplicate_face_pairs_per_planet": _face_headline(guarded_faces, guarded_n)[
                "near_duplicate_face_pairs_per_planet"
            ],
            "face_pair_rate_reweighted_within_planet": _face_headline(guarded_faces, guarded_n)[
                "pair_rate_reweighted"
            ],
            "planet_bands": _planet_headline(guarded_planets)["bands"],
            "within_planet_face_bands": _face_headline(guarded_faces, guarded_n)["bands"],
        },
        "per_section_guards_off": planet_head["per_section"],
    }
    sheet = planet_sample + face_sample
    census_endpoints = {_endpoint(row) for row in census}
    missing = [row["pair_id"] for row in face_sample if _endpoint(row) not in census_endpoints]
    if missing:
        print(f"face sample is not inside the census: {missing}", file=sys.stderr)
        return 2
    try:
        validate_label_sheet(sheet)
        validate_label_sheet(census)
        validate_label_sheet(planet_sample + census)
    except SampleSheetError as exc:
        print(exc, file=sys.stderr)
        return 2
    _write_csv(args.out, [_csv_row(pair) for pair in sheet], COLUMNS)
    if args.census_out:
        _write_csv(args.census_out, [_csv_row(pair) for pair in census], COLUMNS)
        print(f"Face census {len(census)} within-planet pairs.")
    args.design_out.parent.mkdir(parents=True, exist_ok=True)
    args.design_out.write_text(json.dumps(design, indent=2), encoding="utf-8")
    print(
        f"Sample {len(planet_sample)} planet pairs, {len(face_sample)} face pairs. "
        f"Planet pairs/section {planet_head['near_duplicate_planet_pairs_per_section']}. "
        f"Face pairs/planet {face_head['near_duplicate_face_pairs_per_planet']}."
    )
    if args.handpicked_out and args.oct20 and not args.skip_handpicked:
        oct20 = json.loads(args.oct20.read_text(encoding="utf-8"))
        rows = _hand_rows(edition, "2026-10-19", HAND_PLANETS_OCT19, [])
        rows.extend(_hand_rows(oct20, "2026-10-20", HAND_PLANETS_OCT20, HAND_FACES_OCT20))
        # Renumber across editions.
        for index, row in enumerate(rows, start=1):
            row["pair_id"] = f"h{index:03d}"
            row["is_duplicate"] = ""
        try:
            validate_label_sheet(rows)
        except SampleSheetError as exc:
            print(exc, file=sys.stderr)
            return 2
        _write_csv(args.handpicked_out, rows, HAND_COLUMNS)
        print(f"Hand-picked sheet {len(rows)} rows (not in the baseline sample).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
