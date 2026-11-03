#!/usr/bin/env python3
"""Guards-off measurement of the Oct 19 edition and a global attach replay.

Paid Jev and section labeling stay off. Nothing is dispatched.

The 30-post floor (#266), junk-planet filter (#264), stance gate (#268),
and exact-title fold (#235) are not part of the primary counts. The script
prints those four as a secondary pass over the same published planets.

The blind sheet's is_duplicate column is not written here.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# News-story extras named by the #272 planet trace on this same file.
# Greeting planets are counted separately. Console planets are not one story.
NEWS_EXTRA_PLANETS = {
    "Technology": ["AI bots", "AI Adoption", "AI Creative Effort", "Crazy", "AI Art"],
    "Culture": ["Tax Purposes"],
    "Health": ["ADHD Struggles 2"],
    "Education": ["School Medical Care"],
}
GREETING_PLANETS = [
    "Good Day",
    "Good Morning",
    "Great Day",
    "Hope For The Day",
    "wonderful day",
    "Great Time",
    "Glad Returns",
    "Happy Sunday",
]


def _catalogs(edition: dict) -> list[tuple[str, list[dict]]]:
    rows = [("global", list(edition.get("topics") or []))]
    for name, planets in (edition.get("sections") or {}).items():
        rows.append((str(name), list(planets or [])))
    return rows


def _l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _centroid(rows: np.ndarray) -> np.ndarray:
    center = rows.mean(axis=0)
    norm = float(np.linalg.norm(center))
    if norm == 0.0:
        return center
    return center / norm


def _embed(texts: list[str]) -> np.ndarray:
    from pipeline.embed import embed_minilm

    if not texts:
        return np.zeros((0, 384), dtype=np.float64)
    return _l2(embed_minilm(texts))


def _planet_reps(planet: dict) -> list[str]:
    texts = []
    for face in planet.get("perspectives") or []:
        for post in face.get("representative_posts") or []:
            text = str(post.get("text") or "").strip()
            if text:
                texts.append(text)
    return texts


def published_geometry(edition: dict) -> dict:
    """Centroid cosine of representative posts. Secondary to the blind labels."""
    catalogs = _catalogs(edition)
    bag: list[tuple[str, int, str]] = []
    texts: list[str] = []
    for scope, planets in catalogs:
        for index, planet in enumerate(planets):
            reps = _planet_reps(planet)
            for text in reps:
                bag.append((scope, index, "planet"))
                texts.append(text)
            for face_index, face in enumerate(planet.get("perspectives") or []):
                for post in face.get("representative_posts") or []:
                    text = str(post.get("text") or "").strip()
                    if not text:
                        continue
                    bag.append((scope, index, f"face:{face_index}"))
                    texts.append(text)
    # Planet reps are already inside the face loop above when faces exist.
    # Embedding the planet bag twice would skew nothing if we embed unique
    # strings once and look up. Do that.
    unique = list(dict.fromkeys(texts))
    vectors = {text: row for text, row in zip(unique, _embed(unique))}

    planet_pairs = []
    face_pairs = []
    per_section = []
    for scope, planets in catalogs:
        centers = []
        for planet in planets:
            reps = _planet_reps(planet)
            if not reps:
                centers.append(None)
                continue
            centers.append(_centroid(np.vstack([vectors[text] for text in reps])))
        high = 0
        mid = 0
        involved_high: set[int] = set()
        for left in range(len(planets)):
            if centers[left] is None:
                continue
            for right in range(left + 1, len(planets)):
                if centers[right] is None:
                    continue
                cosine = float(centers[left] @ centers[right])
                if cosine >= 0.55:
                    mid += 1
                    planet_pairs.append(
                        {
                            "section": scope,
                            "a": planets[left].get("name"),
                            "b": planets[right].get("name"),
                            "posts_a": int(planets[left].get("post_count") or 0),
                            "posts_b": int(planets[right].get("post_count") or 0),
                            "rep_centroid_cosine": round(cosine, 3),
                        }
                    )
                if cosine >= 0.70:
                    high += 1
                    involved_high.add(left)
                    involved_high.add(right)
        per_section.append(
            {
                "section": scope,
                "planets": len(planets),
                "pairs_cosine_ge_0.55": mid,
                "pairs_cosine_ge_0.70": high,
                "planets_with_partner_ge_0.70": len(involved_high),
            }
        )
        for planet in planets:
            faces = list(planet.get("perspectives") or [])
            face_centers = []
            for face in faces:
                reps = [
                    str(post.get("text") or "").strip()
                    for post in face.get("representative_posts") or []
                    if str(post.get("text") or "").strip()
                ]
                if not reps:
                    face_centers.append(None)
                    continue
                face_centers.append(_centroid(np.vstack([vectors[text] for text in reps])))
            for left in range(len(faces)):
                if face_centers[left] is None:
                    continue
                for right in range(left + 1, len(faces)):
                    if face_centers[right] is None:
                        continue
                    cosine = float(face_centers[left] @ face_centers[right])
                    face_pairs.append(
                        {
                            "section": scope,
                            "planet": planet.get("name"),
                            "planet_posts": int(planet.get("post_count") or 0),
                            "a": faces[left].get("title"),
                            "b": faces[right].get("title"),
                            "posts_a": int(faces[left].get("post_count") or 0),
                            "posts_b": int(faces[right].get("post_count") or 0),
                            "rep_centroid_cosine": round(cosine, 3),
                            "stored_distinctness": planet.get("face_distinctness"),
                        }
                    )
    face_pairs.sort(key=lambda row: -row["rep_centroid_cosine"])
    planet_pairs.sort(key=lambda row: -row["rep_centroid_cosine"])
    return {
        "per_section_rep_cosine": per_section,
        "planet_pairs_cosine_ge_0.55": planet_pairs,
        "face_pairs": face_pairs,
    }


def hand_planet_rates(edition: dict) -> dict:
    """#272's same-story extras, guards off. Greetings reported beside them."""
    by_scope = {scope: planets for scope, planets in _catalogs(edition)}
    rows = []
    news_extras = 0
    for scope, planets in _catalogs(edition):
        names = {str(planet.get("name") or "") for planet in planets}
        extras = [name for name in NEWS_EXTRA_PLANETS.get(scope, []) if name in names]
        greeting_hits = [name for name in GREETING_PLANETS if name in names] if scope == "Other" else []
        greeting_extras = max(len(greeting_hits) - 1, 0) if greeting_hits else 0
        news_extras += len(extras)
        rows.append(
            {
                "section": scope,
                "planets": len(planets),
                "posts": sum(int(planet.get("post_count") or 0) for planet in planets),
                "news_story_extra_planets": len(extras),
                "news_story_extra_names": extras,
                "greeting_family_planets": len(greeting_hits),
                "greeting_extra_planets": greeting_extras,
                "near_duplicate_extra_planets": len(extras) + greeting_extras,
            }
        )
    planets = sum(row["planets"] for row in rows)
    extras = sum(row["near_duplicate_extra_planets"] for row in rows)
    return {
        "sections": rows,
        "planets": planets,
        "news_story_extra_planets": news_extras,
        "greeting_extra_planets": extras - news_extras,
        "near_duplicate_extra_planets": extras,
        "extra_planets_per_section": round(extras / len(rows), 3) if rows else 0,
        "news_extra_planets_per_section": round(news_extras / len(rows), 3) if rows else 0,
        "note": (
            "Extra planets are published planets beyond one per same-story group, "
            "inside one solar system. Built from the #272 trace plus the eight "
            "Other greeting planets as one pleasantry family. Console fragments "
            "are not counted as one story."
        ),
    }


def face_rates(face_pairs: list[dict], edition: dict) -> dict:
    """Near-duplicate faces per planet, using representative centroids.

    Cosine >= 0.80 is the secondary bar. It sits under the face gate of 0.90
    (pipeline/perspectives.py _FACE_COSINE) and above the planet merge of 0.72.
    Pairs between 0.72 and 0.80 are listed and not counted as the rate.
    """
    planets = [planet for _scope, group in _catalogs(edition) for planet in group]
    multi = [planet for planet in planets if len(planet.get("perspectives") or []) >= 2]
    high = [row for row in face_pairs if row["rep_centroid_cosine"] >= 0.80]
    mid = [row for row in face_pairs if 0.72 <= row["rep_centroid_cosine"] < 0.80]
    planets_with_high: set[tuple[str, str]] = {(row["section"], row["planet"]) for row in high}
    return {
        "planets": len(planets),
        "multi_face_planets": len(multi),
        "within_planet_face_pairs": len(face_pairs),
        "pairs_cosine_ge_0.80": len(high),
        "pairs_cosine_0.72_to_0.80": len(mid),
        "planets_with_a_face_pair_ge_0.80": len(planets_with_high),
        "near_duplicate_face_pairs_per_planet": round(len(high) / len(planets), 4) if planets else 0,
        "near_duplicate_face_pairs_per_multi_face_planet": (
            round(len(high) / len(multi), 4) if multi else 0
        ),
        "bar": 0.80,
        "high_pairs": high,
        "mid_pairs": mid,
    }


def guards_on(edition: dict, planet_rates: dict) -> dict:
    """Secondary figure. Primary rates above do not use these drops."""
    from pipeline.chitchat_guard import planet_chitchat_reason
    from pipeline.label import titles_alike

    floor_dropped = []
    junk_dropped = []
    kept_names: dict[str, set[str]] = {}
    for scope, planets in _catalogs(edition):
        kept_names[scope] = set()
        for planet in planets:
            name = str(planet.get("name") or "")
            posts = int(planet.get("post_count") or 0)
            reps = []
            for face in planet.get("perspectives") or []:
                for post in face.get("representative_posts") or []:
                    reps.append({"text": post.get("text") or "", "author": post.get("author") or ""})
            reason = planet_chitchat_reason(reps, [])
            under_floor = posts < 30
            if under_floor:
                floor_dropped.append({"section": scope, "name": name, "posts": posts})
            if reason:
                junk_dropped.append({"section": scope, "name": name, "posts": posts, "reason": reason})
            if not under_floor and not reason:
                kept_names[scope].add(name)
    exact_folds = []
    alike_left = []
    for scope, planets in _catalogs(edition):
        for planet in planets:
            faces = list(planet.get("perspectives") or [])
            for left in range(len(faces)):
                for right in range(left + 1, len(faces)):
                    a = str(faces[left].get("title") or "")
                    b = str(faces[right].get("title") or "")
                    if _exact_title(a) == _exact_title(b) and _exact_title(a):
                        exact_folds.append({"section": scope, "planet": planet.get("name"), "a": a, "b": b})
                    if titles_alike(a, b):
                        alike_left.append({"section": scope, "planet": planet.get("name"), "a": a, "b": b})
    surviving_news = 0
    surviving_greeting = 0
    for scope, names in NEWS_EXTRA_PLANETS.items():
        surviving_news += sum(1 for name in names if name in kept_names.get(scope, set()))
    surviving_greeting = sum(
        1 for name in GREETING_PLANETS if name in kept_names.get("Other", set())
    )
    # One of a greeting family would remain if any survived; extras are the rest.
    greeting_extra_if_any = max(surviving_greeting - 1, 0) if surviving_greeting else 0
    return {
        "floor_30_planets_dropped": len(floor_dropped),
        "floor_30_posts_dropped": sum(row["posts"] for row in floor_dropped),
        "junk_planets_dropped_on_representatives": len(junk_dropped),
        "junk_dropped": junk_dropped,
        "exact_title_face_pairs_235": exact_folds,
        "titles_alike_face_pairs_still_published": alike_left,
        "news_extra_planets_surviving_floor_and_junk": surviving_news,
        "greeting_planets_surviving_floor_and_junk": surviving_greeting,
        "near_duplicate_extra_planets_after_floor_and_junk": surviving_news + greeting_extra_if_any,
        "planets_published_guards_off": sum(len(planets) for _scope, planets in _catalogs(edition)),
        "planets_after_floor_and_junk": sum(len(names) for names in kept_names.values()),
    }


def _exact_title(title: str) -> str:
    words = __import__("re").findall(r"[a-z0-9]+", title.lower())
    while words and words[-1].isdigit():
        words.pop()
    return " ".join(words)


def global_face_store(db_path: Path, edition: dict) -> dict:
    """Full-member face geometry for the 10 global planets stored in the run db.

    perspectives rows are the face split written for the global catalog.
    Posts in topic_membership but not perspectives stayed off the published face.
    """
    from pipeline.story_attach import post_matches, story_of

    connection = sqlite3.connect(db_path)
    posts = {
        row[0]: row[1]
        for row in connection.execute("SELECT uri, clean_text FROM posts")
    }
    membership: dict[int, list[str]] = defaultdict(list)
    for uri, topic_id in connection.execute("SELECT uri, topic_id FROM topic_membership"):
        membership[int(topic_id)].append(uri)
    faces: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for uri, topic_id, face_index, _distance in connection.execute(
        "SELECT uri, topic_id, face_index, distance FROM perspectives"
    ):
        faces[int(topic_id)][int(face_index)].append(uri)
    connection.close()

    # Match a stored topic to a published global planet by on-face post count.
    published = list(edition.get("topics") or [])
    used: set[int] = set()
    matched = []
    for topic_id, face_map in sorted(faces.items()):
        on_face = sum(len(uris) for uris in face_map.values())
        planet = next(
            (
                item
                for item in published
                if int(item.get("post_count") or 0) == on_face and id(item) not in used
            ),
            None,
        )
        if planet is None:
            continue
        used.add(id(planet))
        all_uris = membership.get(topic_id, [])
        on_uris = {uri for uris in face_map.values() for uri in uris}
        off_uris = [uri for uri in all_uris if uri not in on_uris]
        unique_texts = []
        owners = []
        for face_index, uris in sorted(face_map.items()):
            for uri in uris:
                owners.append(("face", face_index))
                unique_texts.append(posts.get(uri) or "")
        off_start = len(unique_texts)
        for uri in off_uris:
            owners.append(("off", -1))
            unique_texts.append(posts.get(uri) or "")
        vectors = _embed(unique_texts)
        face_rows = []
        face_centers = {}
        for face_index, uris in sorted(face_map.items()):
            rows = vectors[[index for index, owner in enumerate(owners) if owner == ("face", face_index)]]
            center = _centroid(rows)
            face_centers[face_index] = center
            face_rows.append(
                {
                    "face_index": face_index,
                    "posts": len(uris),
                    "sample": [(posts.get(uri) or "")[:180] for uri in uris[:2]],
                }
            )
        pair_cosines = []
        indexes = sorted(face_centers)
        for left in range(len(indexes)):
            for right in range(left + 1, len(indexes)):
                pair_cosines.append(
                    {
                        "a": indexes[left],
                        "b": indexes[right],
                        "cosine": round(float(face_centers[indexes[left]] @ face_centers[indexes[right]]), 3),
                    }
                )
        off_stats = {"off_posts": len(off_uris)}
        if off_uris and face_centers:
            # The published page's kept text is every on-face post when the
            # page shows one face, and the larger face when it shows two.
            largest = max(face_map, key=lambda index: len(face_map[index]))
            kept_texts = [posts.get(uri) or "" for uri in face_map[largest]]
            top, stems = story_of(kept_texts)
            off_rows = vectors[off_start:]
            center = face_centers[largest]
            cosines = off_rows @ center
            stem_hits = sum(1 for text in (posts.get(uri) or "" for uri in off_uris) if post_matches(text, stems, required=top))
            off_stats.update(
                {
                    "kept_face_posts": len(face_map[largest]),
                    "kept_story_stem": top,
                    "off_mean_cosine_to_kept_face": round(float(cosines.mean()), 3) if len(cosines) else None,
                    "off_cosine_ge_0.50": int((cosines >= 0.50).sum()),
                    "off_cosine_ge_0.42": int((cosines >= 0.42).sum()),
                    "off_posts_matching_kept_stem": int(stem_hits),
                    "off_samples": [(posts.get(uri) or "")[:180] for uri in off_uris[:4]],
                }
            )
        matched.append(
            {
                "topic_id": topic_id,
                "planet": planet.get("name"),
                "published_faces": [face.get("title") for face in planet.get("perspectives") or []],
                "stored_face_counts": {str(row["face_index"]): row["posts"] for row in face_rows},
                "stored_face_pair_cosines": pair_cosines,
                "stored_face_samples": face_rows,
                "off_face": off_stats,
            }
        )
    return {"global_planets": matched}


def attach_replay(db_path: Path) -> dict:
    """Replay global density + attach on the Oct 19 corpus. No labels, no Jev."""
    from pipeline.grouping import density_labels
    from pipeline.story_attach import (
        AMBIGUITY,
        ATTACH_COSINE,
        BIG_PLANET,
        FOLD_COSINE,
        MIN_SIBLING,
        SIBLING_MAJORITY,
        _center,
        _groups,
        _l2,
        _without_global_glue,
        attach_same_story,
        post_matches,
        story_of,
    )
    from pipeline.topics import _cap_author_posts

    connection = sqlite3.connect(db_path)
    rows = connection.execute(
        "SELECT uri, author, clean_text FROM posts ORDER BY created_at ASC"
    ).fetchall()
    connection.close()
    texts = [row[2] or "" for row in rows]
    authors = [row[1] or "unknown" for row in rows]
    print(f"Embedding {len(texts)} Oct 19 posts...", flush=True)
    matrix = _embed(texts)
    print("Clustering...", flush=True)
    raw = density_labels(matrix, min_cluster_size=5, seed=0)
    capped = _cap_author_posts([int(label) for label in raw], authors, 3)
    author_dropped = sum(1 for before, after in zip(raw, capped) if int(before) >= 0 and int(after) < 0)
    labels = np.asarray(capped, dtype=int)
    unit = _l2(matrix)
    groups = _groups(labels)
    sizes = {label: int(members.size) for label, members in groups.items()}
    stories = {label: story_of([texts[int(index)] for index in members]) for label, members in groups.items()}
    tops = {label: top for label, (top, _stems) in stories.items()}
    story_stems = _without_global_glue(stories, sizes)
    centroids = {label: _center(unit, members) for label, members in groups.items()}

    # Vectorized noise-to-parent cosine, then the same stem rules as _attach_noise.
    parents = [
        label
        for label, members in groups.items()
        if members.size >= BIG_PLANET and tops.get(label) and story_stems.get(label)
    ]
    noise = np.flatnonzero(labels < 0)
    parent_matrix = np.vstack([centroids[label] for label in parents]) if parents else np.zeros((0, unit.shape[1]))
    stem_fail = 0
    stem_fail_ge_055 = 0
    would_attach = 0
    ambiguous = 0
    below_042_stem = 0
    below_042_stem_band = 0  # 0.35-0.42
    no_parent_cosine = 0
    if len(noise) and len(parents):
        sims = unit[noise] @ parent_matrix.T
        for row_index, post_index in enumerate(noise):
            ranked = []
            for parent_index, label in enumerate(parents):
                cosine = float(sims[row_index, parent_index])
                if cosine < ATTACH_COSINE:
                    continue
                if not post_matches(texts[int(post_index)], story_stems[label], required=tops.get(label)):
                    continue
                ranked.append((cosine, label))
            best = float(sims[row_index].max())
            if not ranked:
                if best < ATTACH_COSINE:
                    no_parent_cosine += 1
                    # Stem-matching parent just under the cosine gate.
                    stem_band = False
                    for parent_index, label in enumerate(parents):
                        cosine = float(sims[row_index, parent_index])
                        if cosine < 0.35 or cosine >= ATTACH_COSINE:
                            continue
                        if post_matches(texts[int(post_index)], story_stems[label], required=tops.get(label)):
                            stem_band = True
                            break
                    if stem_band and best >= 0.35:
                        below_042_stem_band += 1
                    if best >= 0.35:
                        # Count stem failures above 0.42 separately below.
                        pass
                else:
                    stem_fail += 1
                    if best >= 0.55:
                        stem_fail_ge_055 += 1
                continue
            ranked.sort(reverse=True)
            if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < AMBIGUITY:
                ambiguous += 1
                continue
            would_attach += 1
    else:
        no_parent_cosine = int(noise.size)

    # Sibling fold misses: close balls the parent-size rule cannot join.
    ids = [label for label, size in sizes.items() if size >= MIN_SIBLING]
    equal_or_no_parent = 0
    stem_majority_fail = 0
    close_under_20 = 0
    examples = []
    for left_i, left in enumerate(ids):
        for right in ids[left_i + 1 :]:
            cosine = float(centroids[left] @ centroids[right])
            if cosine < FOLD_COSINE:
                continue
            big, small = (left, right) if sizes[left] >= sizes[right] else (right, left)
            if sizes[big] < BIG_PLANET:
                close_under_20 += 1
                if len(examples) < 12:
                    examples.append(
                        {
                            "cosine": round(cosine, 3),
                            "sizes": [sizes[left], sizes[right]],
                            "tops": [tops.get(left), tops.get(right)],
                            "reason": "neither planet has 20 posts",
                        }
                    )
                continue
            if sizes[big] <= sizes[small]:
                equal_or_no_parent += 1
                continue
            hits = sum(
                1
                for index in groups[small]
                if post_matches(texts[int(index)], story_stems[big], required=tops.get(big))
            )
            if hits / sizes[small] < SIBLING_MAJORITY:
                stem_majority_fail += 1
                if len(examples) < 12:
                    examples.append(
                        {
                            "cosine": round(cosine, 3),
                            "sizes": [int(sizes[big]), int(sizes[small])],
                            "tops": [tops.get(big), tops.get(small)],
                            "stem_hit_share": round(hits / sizes[small], 3),
                            "reason": "under sibling majority",
                        }
                    )

    updated, stats = attach_same_story(matrix, texts, capped)
    assigned_before = int(sum(1 for label in capped if label >= 0))
    assigned_after = int(sum(1 for label in updated if label >= 0))
    noise_after = len(updated) - assigned_after
    return {
        "posts": len(texts),
        "candidate_planets_before_attach": len(sizes),
        "author_cap_posts_moved_to_noise": author_dropped,
        "assigned_before_attach": assigned_before,
        "noise_before_attach": len(texts) - assigned_before,
        "attach_stats": stats,
        "assigned_after_attach": assigned_after,
        "noise_after_attach": noise_after,
        "noise_gate": {
            "parents_ge_20_with_a_stem": len(parents),
            "would_attach": would_attach,
            "ambiguous_two_parents": ambiguous,
            "cosine_ge_0.42_stem_fail": stem_fail,
            "cosine_ge_0.55_stem_fail": stem_fail_ge_055,
            "cosine_under_0.42": no_parent_cosine,
            "stem_match_but_cosine_0.35_to_0.42": below_042_stem_band,
            "unused_below_counter": below_042_stem,
        },
        "sibling_gate": {
            "pairs_cosine_ge_0.55_both_under_20": close_under_20,
            "pairs_blocked_because_parent_not_strictly_larger": equal_or_no_parent,
            "pairs_under_sibling_majority": stem_majority_fail,
            "examples": examples,
        },
        "balls_under_20": sum(1 for size in sizes.values() if size < BIG_PLANET),
        "balls_ge_20": sum(1 for size in sizes.values() if size >= BIG_PLANET),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Oct 19 duplicates with guards off")
    parser.add_argument("--edition", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--skip-attach", action="store_true")
    parser.add_argument("--attach-only", action="store_true")
    args = parser.parse_args(argv)
    edition = json.loads(args.edition.read_text(encoding="utf-8"))
    if str(edition.get("last_updated")) != "2026-10-19":
        print("Refusing non-Oct-19 edition", file=sys.stderr)
        return 2
    if args.attach_only:
        if args.corpus is None:
            print("--corpus is required", file=sys.stderr)
            return 2
        payload = {"attach_replay": attach_replay(args.corpus)}
    else:
        geometry = published_geometry(edition)
        planets = hand_planet_rates(edition)
        faces = face_rates(geometry["face_pairs"], edition)
        secondary = guards_on(edition, planets)
        payload = {
            "edition": "2026-10-19",
            "snapshot": "44a537b",
            "guards_off": {
                "planets": planets,
                "faces": {key: value for key, value in faces.items() if key not in {"high_pairs", "mid_pairs"}},
                "face_pairs_cosine_ge_0.80": faces["high_pairs"],
                "face_pairs_cosine_0.72_to_0.80": faces["mid_pairs"],
                "rep_cosine_by_section": geometry["per_section_rep_cosine"],
            },
            "guards_on_secondary": secondary,
            "global_membership": global_face_store(args.corpus, edition) if args.corpus else None,
        }
        if args.corpus and not args.skip_attach:
            payload["attach_replay"] = attach_replay(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
