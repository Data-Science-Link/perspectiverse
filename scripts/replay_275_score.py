#!/usr/bin/env python3
"""Band-weighted duplicate rates for the Oct 19 labeled sample.

Reads ``is_duplicate`` from ``docs/evidence/275/oct19-pairs-labeled.csv``.
Does not label pairs. Does not call Jev or a label model and does not
dispatch a workflow. Guards (floor, junk filter, stance gate, title fold)
are not applied: the sample is the published Oct 19 edition.

Planet rates use the planet rows of ``oct19-pairs-labeled.csv``.
Face rates use ``oct19-face-census.csv`` (every within-planet pair).
The 60-row face sample leaked cross-planet pairs and is not scored.

A pair the simulated fix would unpublish is removed from the duplicate
count. ``unsure`` is its own count. Rates are reported with unsure held
out, and again with unsure counted as a duplicate.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Subject tokens shorter than 4 characters that proposal 2 may treat as a stem.
# "bar", "ps5", and "ps6" stay off this list on purpose.
SHORT_STEMS = frozenset({"ai"})
FOLD_COSINE = 0.55
PARAPHRASE_COSINE = 0.80
# A ball is a daypart greeting planet when at least half of its
# representative posts open with a daypart and carry no news cue.
DAYPART_PLANET_SHARE = 0.50
DAYPART_RE = re.compile(
    r"\b(?:good\s+(?:morning|afternoon|evening|night)|"
    r"happy\s+(?:sunday|saturday|monday|tuesday|wednesday|thursday|friday))\b",
    re.IGNORECASE,
)


def _load_labels(path: Path) -> dict[str, dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows or "is_duplicate" not in rows[0]:
        raise SystemExit(f"{path} has no is_duplicate column")
    return {row["pair_id"]: row for row in rows}


def _census_rows(path: Path) -> list[dict]:
    rows = []
    for raw in csv.DictReader(path.open(encoding="utf-8")):
        label = (raw.get("is_duplicate") or "").strip().lower()
        if label not in {"yes", "no", "unsure"}:
            raise SystemExit(f"{raw.get('pair_id')} census is_duplicate={label!r}")
        if raw.get("planet_a") != raw.get("planet_b"):
            raise SystemExit(f"{raw.get('pair_id')} census row is not one planet")
        if raw.get("title_a") == raw.get("title_b"):
            raise SystemExit(f"{raw.get('pair_id')} census row is not two faces")
        rows.append(
            {
                "pair_id": raw["pair_id"],
                "band": raw["band"],
                "cosine": float(raw["cosine"]),
                "label": label,
                "reason": raw.get("label_reason") or "",
                "section": raw.get("section") or "",
                "planet_a": raw.get("planet_a") or "",
                "planet_b": raw.get("planet_b") or "",
                "title_a": raw.get("title_a") or "",
                "title_b": raw.get("title_b") or "",
                "post_count_a": int(raw.get("post_count_a") or 0),
                "post_count_b": int(raw.get("post_count_b") or 0),
                "texts_a": raw.get("sample_texts_a") or "",
                "texts_b": raw.get("sample_texts_b") or "",
                "same_planet": True,
            }
        )
    return rows


def _census_bands(rows: list[dict]) -> list[dict]:
    order = ["B0", "B1", "B2", "B3", "B4"]
    total = len(rows) or 1
    bands = []
    for name in order:
        count = sum(1 for row in rows if row["band"] == name)
        bands.append({"band": name, "pairs": count, "share": count / total if rows else 0.0})
    return bands


def _join(design: dict, labels: dict[str, dict], level: str) -> list[dict]:
    joined = []
    for sample in design[level]["sample"]:
        label = labels.get(sample["pair_id"])
        if label is None:
            raise SystemExit(f"missing label for {sample['pair_id']}")
        raw = (label.get("is_duplicate") or "").strip().lower()
        if raw not in {"yes", "no", "unsure"}:
            raise SystemExit(f"{sample['pair_id']} is_duplicate={raw!r}")
        joined.append(
            {
                **sample,
                "label": raw,
                "reason": label.get("label_reason") or "",
                "title_a": label.get("title_a") or "",
                "title_b": label.get("title_b") or "",
                "planet_a": label.get("planet_a") or "",
                "planet_b": label.get("planet_b") or "",
                "section": label.get("section") or sample["section"],
                "post_count_a": int(label.get("post_count_a") or 0),
                "post_count_b": int(label.get("post_count_b") or 0),
                "texts_a": label.get("sample_texts_a") or "",
                "texts_b": label.get("sample_texts_b") or "",
            }
        )
    return joined


def _rates(members: list[dict]) -> dict[str, float]:
    if not members:
        return {"n": 0, "yes": 0, "unsure": 0, "no": 0, "yes_rate": None, "yes_or_unsure_rate": None, "unsure_rate": None}
    yes = sum(1 for row in members if row["label"] == "yes")
    unsure = sum(1 for row in members if row["label"] == "unsure")
    no = sum(1 for row in members if row["label"] == "no")
    n = len(members)
    return {
        "n": n,
        "yes": yes,
        "unsure": unsure,
        "no": no,
        "yes_rate": yes / n,
        "yes_or_unsure_rate": (yes + unsure) / n,
        "unsure_rate": unsure / n,
    }


def _reweight(sample: list[dict], bands: list[dict], *, drop: set[str]) -> dict:
    """Stratified estimate. ``drop`` pairs are treated as no longer published."""
    kept = []
    for row in sample:
        if row["pair_id"] in drop:
            kept.append({**row, "label": "no"})
        else:
            kept.append(row)
    by: dict[str, list[dict]] = defaultdict(list)
    for row in kept:
        by[row["band"]].append(row)
    rows = []
    yes_rate = 0.0
    yes_or_unsure = 0.0
    unsure_rate = 0.0
    for band in bands:
        name = band["band"]
        share = float(band["share"])
        stats = _rates(by.get(name, []))
        contribution_yes = 0.0 if stats["yes_rate"] is None else share * stats["yes_rate"]
        contribution_either = 0.0 if stats["yes_or_unsure_rate"] is None else share * stats["yes_or_unsure_rate"]
        contribution_unsure = 0.0 if stats["unsure_rate"] is None else share * stats["unsure_rate"]
        yes_rate += contribution_yes
        yes_or_unsure += contribution_either
        unsure_rate += contribution_unsure
        rows.append(
            {
                "band": name,
                "share": share,
                "population_pairs": band["pairs"],
                **{key: (None if value is None else value) for key, value in stats.items()},
                "contribution_yes": round(contribution_yes, 6),
                "contribution_yes_or_unsure": round(contribution_either, 6),
                "contribution_unsure": round(contribution_unsure, 6),
            }
        )
    return {
        "yes": round(yes_rate, 6),
        "yes_or_unsure": round(yes_or_unsure, 6),
        "unsure": round(unsure_rate, 6),
        "bands": rows,
    }


def _per_section(rate: float, population: int, sections: int) -> float:
    if not sections:
        return 0.0
    return round(rate * population / sections, 4)


def _per_planet(rate: float, population: int, planets: int) -> float:
    if not planets:
        return 0.0
    return round(rate * population / planets, 4)


def _posts(blob: str) -> list[dict]:
    posts = []
    for chunk in (blob or "").split(" || "):
        text = chunk.strip()
        if text:
            posts.append({"text": text})
    return posts


def _fix1_ids(faces: list[dict]) -> tuple[list[str], list[dict]]:
    """Same-planet pairs a paraphrase bar at 0.80 would unpublish, unless they disagree."""
    from pipeline.stance import local_faces_disagree, local_faces_fold

    resolved = []
    detail = []
    for row in faces:
        if not row.get("same_planet"):
            continue
        left = {"title": row["title_a"], "summary": ""}
        right = {"title": row["title_b"], "summary": ""}
        left_posts = _posts(row["texts_a"])
        right_posts = _posts(row["texts_b"])
        disagree = bool(local_faces_disagree(left, right, left_posts, right_posts))
        fold = bool(local_faces_fold(left, right, left_posts, right_posts))
        paraphrase = row["cosine"] >= PARAPHRASE_COSINE and not disagree
        if paraphrase:
            resolved.append(row["pair_id"])
        detail.append(
            {
                "pair_id": row["pair_id"],
                "cosine": round(row["cosine"], 4),
                "band": row["band"],
                "label": row["label"],
                "titles": f"{row['title_a']} | {row['title_b']}",
                "disagree": disagree,
                "lexicon_fold": fold,
                "paraphrase_bar": paraphrase,
            }
        )
    return resolved, detail


def _shared_subject(row: dict) -> set[str]:
    from pipeline.story_attach import specific_stems

    left = set()
    right = set()
    left_short = set()
    right_short = set()
    for post in _posts(row["texts_a"]):
        left |= specific_stems(post["text"])
        left_short |= set(re.findall(r"[a-z0-9]+", post["text"].lower())) & SHORT_STEMS
    for post in _posts(row["texts_b"]):
        right |= specific_stems(post["text"])
        right_short |= set(re.findall(r"[a-z0-9]+", post["text"].lower())) & SHORT_STEMS
    return (left & right) | (left_short & right_short)


_PLEASANTRY_STEMS = frozenset(
    {"good", "morn", "happy", "sunday", "night", "evening", "great", "hope", "wish", "day"}
)


def _fix2_ids(planets: list[dict]) -> tuple[list[str], list[dict], list[str]]:
    """Allowlisted ``ai`` stem, both sides under 20, cosine at least 0.55.

    A raw ``specific_stems`` intersection on the sample texts also joins labeled
    ``no`` pairs. Those ids are returned separately and are not the measured fix.
    """
    resolved = []
    unsafe = []
    detail = []
    for row in planets:
        shared = _shared_subject(row)
        content = {stem for stem in shared if stem not in _PLEASANTRY_STEMS}
        both_small = row["post_count_a"] < 20 and row["post_count_b"] < 20
        ai_join = "ai" in shared and both_small and row["cosine"] >= FOLD_COSINE
        raw_join = bool(content) and both_small and row["cosine"] >= FOLD_COSINE
        if ai_join:
            resolved.append(row["pair_id"])
        if raw_join and not ai_join:
            unsafe.append(row["pair_id"])
        if ai_join or raw_join or (row["label"] != "no" and row["cosine"] < 0.70):
            detail.append(
                {
                    "pair_id": row["pair_id"],
                    "cosine": round(row["cosine"], 4),
                    "band": row["band"],
                    "label": row["label"],
                    "titles": f"{row['title_a']} | {row['title_b']}",
                    "posts": [row["post_count_a"], row["post_count_b"]],
                    "shared": sorted(shared),
                    "both_under_20": both_small,
                    "fix2_ai_allowlist": ai_join,
                    "raw_stem_join_not_used": raw_join and not ai_join,
                }
            )
    return resolved, detail, unsafe


def _daypart_card(raw: str) -> bool:
    from pipeline.chitchat_guard import (
        _GREETING_HARD_TOPIC_RE,
        _news,
        _plain,
        _word_count,
        _work_topic,
    )

    plain = _plain(raw)
    if not plain or _word_count(plain) > 60:
        return False
    if _news(plain) or _work_topic(plain) or _GREETING_HARD_TOPIC_RE.search(plain):
        return False
    head = " ".join(plain.split()[:8])
    return bool(DAYPART_RE.search(head))


def _planet_reps(edition: dict) -> list[dict]:
    rows = [("global", edition.get("topics") or [])]
    for name, planets in (edition.get("sections") or {}).items():
        rows.append((str(name), planets or []))
    found = []
    for scope, group in rows:
        for planet in group:
            reps = []
            for face in planet.get("perspectives") or []:
                reps.extend(face.get("representative_posts") or [])
            found.append(
                {
                    "section": scope,
                    "name": planet.get("name") or "",
                    "posts": int(planet.get("post_count") or 0),
                    "reps": reps,
                }
            )
    return found


def _greeting_census(path: Path) -> dict:
    from pipeline.chitchat_guard import planet_chitchat_reason, pleasantry_reason

    edition = json.loads(path.read_text(encoding="utf-8"))
    planets = []
    for planet in _planet_reps(edition):
        members = [
            {"text": post.get("text") or "", "author": post.get("author") or ""}
            for post in planet["reps"]
        ]
        if not members:
            continue
        cards = [member for member in members if _daypart_card(member["text"])]
        already = sum(1 for member in members if pleasantry_reason(member))
        share = len(cards) / len(members)
        reason = planet_chitchat_reason(members, [])
        gate = share >= DAYPART_PLANET_SHARE
        if gate or reason or share > 0:
            planets.append(
                {
                    "section": planet["section"],
                    "name": planet["name"],
                    "posts": planet["posts"],
                    "reps": len(members),
                    "daypart_share": round(share, 4),
                    "already_pleasantry": already,
                    "junk_filter": reason,
                    "daypart_gate_drops": gate,
                    "new_cards": [
                        " ".join(member["text"].split())[:180]
                        for member in cards
                        if pleasantry_reason(member) is None
                    ][:3],
                }
            )
    return {
        "edition": edition.get("last_updated"),
        "rule": (
            "Drop the ball when at least half of its representative posts have a "
            "daypart greeting in the first 8 words, are at most 60 words, and do "
            "not trip _news, _work_topic, or _GREETING_HARD_TOPIC_RE. The tail "
            "allowlist is not consulted."
        ),
        "planets": planets,
    }


def _greeting_pair_ids(planets: list[dict], census: dict) -> list[str]:
    dropped = {
        (row["section"], row["name"])
        for row in census["planets"]
        if row["daypart_gate_drops"]
    }
    resolved = []
    for row in planets:
        if (row["section"], row["title_a"]) in dropped or (row["section"], row["title_b"]) in dropped:
            resolved.append(row["pair_id"])
    return resolved


def _proxy_vs_labels(sample: list[dict]) -> dict:
    under = []
    over = []
    for row in sample:
        proxy_yes = row["cosine"] >= 0.70
        if row["label"] == "yes" and not proxy_yes:
            under.append(row["pair_id"])
        if proxy_yes and row["label"] == "no":
            over.append(row["pair_id"])
    return {"label_yes_proxy_no": under, "label_no_proxy_yes": over}


def _package(level: str, before: dict, after: dict, population: int, unit: int, unit_name: str) -> dict:
    return {
        "level": level,
        "before_yes": before["yes"],
        "before_yes_or_unsure": before["yes_or_unsure"],
        "before_unsure": before["unsure"],
        "after_yes": after["yes"],
        "after_yes_or_unsure": after["yes_or_unsure"],
        "after_unsure": after["unsure"],
        f"before_{unit_name}_yes": _per_section(before["yes"], population, unit) if unit_name == "pairs_per_section" else _per_planet(before["yes"], population, unit),
        f"before_{unit_name}_yes_or_unsure": _per_section(before["yes_or_unsure"], population, unit) if unit_name == "pairs_per_section" else _per_planet(before["yes_or_unsure"], population, unit),
        f"after_{unit_name}_yes": _per_section(after["yes"], population, unit) if unit_name == "pairs_per_section" else _per_planet(after["yes"], population, unit),
        f"after_{unit_name}_yes_or_unsure": _per_section(after["yes_or_unsure"], population, unit) if unit_name == "pairs_per_section" else _per_planet(after["yes_or_unsure"], population, unit),
        "before_bands": before["bands"],
        "after_bands": after["bands"],
    }


MERGE_BAR_COLUMNS = [
    "fix_id",
    "day",
    "guards",
    "scorer",
    "good_labeled_duplicates_removed_or_joined",
    "over_merge_labeled_different",
    "moved_to_other_planets",
    "moved_to_other_posts",
    "dropped_planets",
    "dropped_posts",
    "per_section",
    "verdict",
]


def _per_section_drops(planets: list[dict]) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in planets:
        grouped[row["section"]].append(f"{row['name']} {row['posts']} posts")
    return "; ".join(
        f"{section}: " + ", ".join(items) for section, items in sorted(grouped.items())
    )


def merge_bar_rows(greeting: dict) -> list[dict]:
    """(a) and (b) stay empty until a grok-4.7 label file is the scorer.

    composer-2.5 labels are a separate reading. They do not fill these columns.
    (c) is the section move or drop this fix adds, with guards off. A later
    label pass must not overwrite (c) with a label count.
    """
    notes = {
        "fix1_paraphrase_face": (
            "Does not call section_sanity and does not drop a planet. "
            "Unpublishing a paraphrase face is (a) or (b), once labeled."
        ),
        "fix2_attach_stem": (
            "A join stays in the section. Posts are kept. No planet moves to Other."
        ),
        "fix3_keep_dropped_face_posts": (
            "Stayed-off posts return to the surviving face. Drops do not rise."
        ),
    }
    days: list[tuple[str, dict | None]] = []
    for key, census in greeting.items():
        days.append((str(census.get("edition") or key), census))
    if not days:
        days = [("2026-10-19", None), ("2026-10-20", None)]
    rows = []
    for fix_id, note in notes.items():
        for day, _census in days:
            rows.append(
                {
                    "fix_id": fix_id,
                    "day": day,
                    "guards": "off",
                    "scorer": "awaiting grok-4.7",
                    "good_labeled_duplicates_removed_or_joined": "",
                    "over_merge_labeled_different": "",
                    "moved_to_other_planets": 0,
                    "moved_to_other_posts": 0,
                    "dropped_planets": 0,
                    "dropped_posts": 0,
                    "per_section": "",
                    "verdict": "awaiting grok-4.7; (c) does not rise",
                    "note": note,
                }
            )
    for day, census in days:
        dropped = [row for row in (census or {}).get("planets") or [] if row.get("daypart_gate_drops")]
        posts = sum(int(row["posts"]) for row in dropped)
        rises = bool(dropped) or posts > 0
        rows.append(
            {
                "fix_id": "daypart_planet_gate",
                "day": day,
                "guards": "off",
                "scorer": "awaiting grok-4.7",
                "good_labeled_duplicates_removed_or_joined": "",
                "over_merge_labeled_different": "",
                "moved_to_other_planets": 0,
                "moved_to_other_posts": 0,
                "dropped_planets": len(dropped),
                "dropped_posts": posts,
                "per_section": _per_section_drops(dropped),
                "verdict": (
                    "fails (c); (a) and (b) awaiting grok-4.7"
                    if rises
                    else "awaiting grok-4.7; (c) does not rise"
                ),
                "note": (
                    "Drops a planet when at least half of its representative posts "
                    "open with a daypart. That drop is (c). It does not move a "
                    "Politics planet to Other."
                ),
            }
        )
    rows.append(
        {
            "fix_id": "published_edition_not_a_275_fix",
            "day": "2026-10-20",
            "guards": "live run post-label sanity, not held off",
            "scorer": "n/a",
            "good_labeled_duplicates_removed_or_joined": "",
            "over_merge_labeled_different": "",
            "moved_to_other_planets": 6,
            "moved_to_other_posts": 402,
            "dropped_planets": 0,
            "dropped_posts": 0,
            "per_section": (
                "Politics → Other: Fascism 201, Wealth Inequality 164, Texas 21, "
                "Texas Derogatory 6, College Football Playoff 5, Notre Dame Miami Game 5 "
                "(#280, Actions 39417351709). The sports moves match the section. "
                "Fascism and Wealth Inequality do not."
            ),
            "verdict": "baseline already has the (c) shape; fixes 1–3 do not add to it",
            "note": "Not a #275 proposal. Shown so a fix's (c) is a rise over this, not a retelling of it.",
        }
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Score the Oct 19 labeled pair sample")
    parser.add_argument("--labels", type=Path, default=ROOT / "docs" / "evidence" / "275" / "oct19-pairs-labeled.csv")
    parser.add_argument("--design", type=Path, default=ROOT / "docs" / "evidence" / "275" / "oct19-sample-design.json")
    parser.add_argument(
        "--census",
        type=Path,
        default=ROOT / "docs" / "evidence" / "275" / "oct19-face-census.csv",
    )
    parser.add_argument("--edition", type=Path, default=None)
    parser.add_argument("--oct20", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evidence" / "275" / "oct19-score.json")
    args = parser.parse_args(argv)
    if not args.labels.exists():
        print("awaiting labels: oct19-pairs-labeled.csv is not on the branch", file=sys.stderr)
        return 2
    design = json.loads(args.design.read_text(encoding="utf-8"))
    labels = _load_labels(args.labels)
    if not args.census.exists():
        print("awaiting labels: oct19-face-census.csv is not on the branch", file=sys.stderr)
        return 2
    planets = _join(design, labels, "planets")
    census = _census_rows(args.census)
    face_status = "census"
    planet_bands = design["headline_guards_off"]["planet_bands"]
    census_bands = _census_bands(census)
    before_planets = _reweight(planets, planet_bands, drop=set())
    before_faces = _reweight(census, census_bands, drop=set())
    fix1, fix1_detail = _fix1_ids(census)
    fix2, fix2_detail, unsafe_stem_ids = _fix2_ids(planets)
    greeting = {}
    greeting_ids: list[str] = []
    if args.edition:
        greeting["oct19"] = _greeting_census(args.edition)
        greeting_ids = _greeting_pair_ids(planets, greeting["oct19"])
    if args.oct20:
        greeting["oct20"] = _greeting_census(args.oct20)
    after = {
        "fix1_paraphrase_face": {
            "resolved_pair_ids": fix1,
            "detail": fix1_detail,
            "planets": _package(
                "planet",
                before_planets,
                _reweight(planets, planet_bands, drop=set()),
                480,
                11,
                "pairs_per_section",
            ),
            "faces": _package(
                "face",
                before_faces,
                _reweight(census, census_bands, drop=set(fix1)),
                27,
                107,
                "pairs_per_planet",
            ),
            "note": (
                "Within-planet census pairs with representative cosine >= 0.80 whose "
                "posts do not trip local_faces_disagree. Pairs from 0.48 to 0.69 are not resolved."
            ),
        },
        "fix2_attach_stem": {
            "resolved_pair_ids": fix2,
            "unsafe_raw_stem_ids": unsafe_stem_ids,
            "detail": [row for row in fix2_detail if row["fix2_ai_allowlist"] or row["raw_stem_join_not_used"] or row["label"] != "no"],
            "planets": _package(
                "planet",
                before_planets,
                _reweight(planets, planet_bands, drop=set(fix2)),
                480,
                11,
                "pairs_per_section",
            ),
            "faces": _package(
                "face",
                before_faces,
                _reweight(census, census_bands, drop=set()),
                27,
                107,
                "pairs_per_planet",
            ),
            "note": (
                "Measured fix: both planets under 20 posts, cosine >= 0.55, shared stem ai. "
                "A raw specific_stems intersection also joins labeled no pairs; those ids "
                "are unsafe_raw_stem_ids and are not removed from the rate."
            ),
        },
        "fix3_keep_dropped_face_posts": {
            "resolved_pair_ids": [],
            "planets": _package(
                "planet",
                before_planets,
                _reweight(planets, planet_bands, drop=set()),
                480,
                11,
                "pairs_per_section",
            ),
            "faces": _package(
                "face",
                before_faces,
                _reweight(census, census_bands, drop=set()),
                27,
                107,
                "pairs_per_planet",
            ),
            "note": "Unpublished stayed-off posts are not rows in the census. The pair rate does not move.",
        },
        "daypart_planet_gate": {
            "resolved_pair_ids": greeting_ids,
            "planets": _package(
                "planet",
                before_planets,
                _reweight(planets, planet_bands, drop=set(greeting_ids)),
                480,
                11,
                "pairs_per_section",
            ),
            "note": "Either planet is a daypart-majority ball, so the pair is not published.",
        },
    }
    proxy = {
        "planets": _proxy_vs_labels(planets),
        "faces": _proxy_vs_labels(census),
    }
    elapsed = time.perf_counter() - started
    report = {
        "labels": str(args.labels.relative_to(ROOT)),
        "label_model_on_file": "composer-2.5",
        "scorer": "awaiting grok-4.7",
        "guards": "off",
        "paid_calls_usd": 0,
        "runtime_seconds": round(elapsed, 3),
        "face_labels": face_status,
        "face_label_note": (
            "Face rates use oct19-face-census.csv, the 27 within-planet pairs, "
            "labeled on the same-viewpoint definition. The 60-row face sample in "
            "oct19-pairs.csv leaked cross-planet pairs and is not scored."
        ),
        "face_sample_leak": {
            "sampled_face_rows": 60,
            "within_planet_rows": 9,
            "cross_planet_rows": 51,
            "exact_planet_row_copies": ["f008", "f018", "f019", "f025", "f038", "f042"],
        },
        "formula": (
            "Planet band rate = labeled planet rows in that band of the stratified "
            "sample, divided by the sample count in the band. Headline = sum of "
            "band rate times that band's share of all 480 same-section planet pairs. "
            "Face rates are the census: each band's share is its count of the 27 "
            "within-planet pairs, and the band rate is the labeled rate in that band. "
            "unsure is reported alone, held out of yes, and included in yes_or_unsure."
        ),
        "planets_before": _package("planet", before_planets, before_planets, 480, 11, "pairs_per_section"),
        "faces_before": _package("face", before_faces, before_faces, 27, 107, "pairs_per_planet"),
        "proxy_cutoff_0.70": {
            "under_call_ids": proxy["planets"]["label_yes_proxy_no"] + proxy["faces"]["label_yes_proxy_no"],
            "over_call_ids": proxy["planets"]["label_no_proxy_yes"] + proxy["faces"]["label_no_proxy_yes"],
            "planet_under": len(proxy["planets"]["label_yes_proxy_no"]),
            "planet_over": len(proxy["planets"]["label_no_proxy_yes"]),
            "face_under": len(proxy["faces"]["label_yes_proxy_no"]),
            "face_over": len(proxy["faces"]["label_no_proxy_yes"]),
        },
        "fixes": after,
        "greeting_census": greeting,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    bar_path = args.out.with_name("merge-bar.csv")
    with bar_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MERGE_BAR_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merge_bar_rows(greeting))
    planet = report["planets_before"]
    print(
        f"Planets yes {planet['before_yes']} ({planet['before_pairs_per_section_yes']} pairs/section), "
        f"yes+unsure {planet['before_yes_or_unsure']} ({planet['before_pairs_per_section_yes_or_unsure']}). "
        f"Faces {face_status} yes {report['faces_before']['before_yes']} "
        f"({report['faces_before']['before_pairs_per_planet_yes']} pairs/planet). "
        f"Runtime {elapsed:.2f}s, $0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
