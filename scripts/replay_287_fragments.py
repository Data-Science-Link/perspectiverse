#!/usr/bin/env python3
"""Guards-off replay of same-story fragment attach on a published edition.

Compares today's fold with the fold after fragments that share an allowlisted
short subject can join. Paid Jev, section labeling, and workflow dispatch are
not used. The 30-post floor, junk filter, stance gate, and title fold stay off.

Representative posts are the member texts. ``post_count`` is the size gate.
A pair counts as joined only when the new fold puts the two planets on one
parent and the previous fold does not.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline.story_attach as story_attach
from pipeline.story_attach import _SHORT_SUBJECT_ALLOWLIST, attach_same_story


def _catalogs(edition: dict) -> list[tuple[str, list[dict]]]:
    rows = [("global", list(edition.get("topics") or []))]
    for name, planets in (edition.get("sections") or {}).items():
        rows.append((str(name), list(planets or [])))
    return rows


def _reps(planet: dict) -> list[str]:
    texts = []
    for face in planet.get("perspectives") or []:
        for post in face.get("representative_posts") or []:
            text = str(post.get("text") or "").strip()
            if text:
                texts.append(text)
    return texts


def _embed(texts: list[str]) -> dict[str, np.ndarray]:
    from pipeline.embed import embed_minilm

    unique = list(dict.fromkeys(texts))
    if not unique:
        return {}
    vectors = np.asarray(embed_minilm(unique), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms
    return {text: vectors[index] for index, text in enumerate(unique)}


def _fold_map(
    planets: list[dict],
    vectors: dict[str, np.ndarray],
    allowlist: frozenset[str],
) -> dict[str, str]:
    """Planet name to the name of the planet it lands on."""
    saved = story_attach._SHORT_SUBJECT_ALLOWLIST
    story_attach._SHORT_SUBJECT_ALLOWLIST = allowlist
    try:
        texts: list[str] = []
        labels: list[int] = []
        rows: list[np.ndarray] = []
        sizes: dict[int, int] = {}
        names: dict[int, str] = {}
        for planet in planets:
            reps = [text for text in _reps(planet) if text in vectors]
            if not reps:
                continue
            label = len(names)
            names[label] = str(planet.get("name") or "")
            sizes[label] = int(planet.get("post_count") or len(reps))
            for text in reps:
                texts.append(text)
                labels.append(label)
                rows.append(vectors[text])
        if not rows:
            return {}
        updated, _stats = attach_same_story(
            np.vstack(rows),
            texts,
            labels,
            noise=False,
            sizes=sizes,
        )
        landed: dict[int, int] = {}
        for before, after in zip(labels, updated):
            landed[int(before)] = int(after)

        def find(label: int) -> int:
            seen: set[int] = set()
            while label in landed and landed[label] != label:
                if label in seen:
                    break
                seen.add(label)
                label = landed[label]
            return label

        return {names[label]: names[find(label)] for label in names}
    finally:
        story_attach._SHORT_SUBJECT_ALLOWLIST = saved


def _parent(name: str, landed: dict[str, str]) -> str:
    seen: set[str] = set()
    while name in landed and landed[name] != name:
        if name in seen:
            break
        seen.add(name)
        name = landed[name]
    return name


def replay_edition(edition: dict, vectors: dict[str, np.ndarray], labeled: list[dict] | None) -> dict:
    sections = []
    yes_joined = []
    no_joined = []
    unsure_joined = []
    for scope, planets in _catalogs(edition):
        before = _fold_map(planets, vectors, frozenset())
        after = _fold_map(planets, vectors, _SHORT_SUBJECT_ALLOWLIST)
        new_only = []
        for planet in planets:
            name = str(planet.get("name") or "")
            if name not in after:
                continue
            if _parent(name, after) != name and _parent(name, before) == name:
                new_only.append(
                    {
                        "child": name,
                        "parent": _parent(name, after),
                        "posts": int(planet.get("post_count") or 0),
                    }
                )
        sections.append(
            {
                "section": scope,
                "planets_before": len(planets),
                "planets_after": len(planets) - len(new_only),
                "labeled_duplicate_pairs_joined": None,
                "labeled_different_pairs_joined": None,
                "planets_or_posts_moved_to_other": 0,
                "posts_dropped": 0,
                "posts_folded": sum(item["posts"] for item in new_only),
                "folds": new_only,
            }
        )
        if not labeled:
            continue
        present = {str(planet.get("name") or "") for planet in planets}
        yes = no = unsure = 0
        for row in labeled:
            if row.get("level") != "planet" or row.get("section") != scope:
                continue
            left, right = row["planet_a"], row["planet_b"]
            if left not in present or right not in present:
                continue
            joined = _parent(left, after) == _parent(right, after)
            joined_before = _parent(left, before) == _parent(right, before)
            if not joined or joined_before:
                continue
            label = row.get("is_duplicate") or ""
            item = {"pair_id": row["pair_id"], "section": scope, "planets": [left, right]}
            if label == "yes":
                yes += 1
                yes_joined.append(item)
            elif label == "no":
                no += 1
                no_joined.append(item)
            else:
                unsure += 1
                unsure_joined.append(item)
        sections[-1]["labeled_duplicate_pairs_joined"] = yes
        sections[-1]["labeled_different_pairs_joined"] = no
        sections[-1]["labeled_unsure_pairs_joined"] = unsure
    return {
        "sections": sections,
        "labeled_duplicate_pairs_joined": yes_joined,
        "labeled_different_pairs_joined": no_joined,
        "labeled_unsure_pairs_joined": unsure_joined,
        "planets_before": sum(row["planets_before"] for row in sections),
        "planets_after": sum(row["planets_after"] for row in sections),
        "moved_to_other": 0,
        "posts_dropped": 0,
    }


def _watch(edition: dict) -> list[dict]:
    """Where Fascism and Inequality sit. Attach does not move sections."""
    found = []
    for scope, planets in _catalogs(edition):
        for planet in planets:
            name = str(planet.get("name") or "")
            lowered = name.lower()
            if "fascis" in lowered or "inequal" in lowered:
                found.append(
                    {
                        "section": scope,
                        "name": name,
                        "posts": int(planet.get("post_count") or 0),
                        "section_after": scope,
                    }
                )
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", required=True, type=Path)
    parser.add_argument("--labeled", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--joins-out", type=Path)
    args = parser.parse_args()
    edition = json.loads(args.edition.read_text())
    labeled = None
    if args.labeled:
        with args.labeled.open(newline="") as handle:
            labeled = list(csv.DictReader(handle))
    texts = []
    for _scope, planets in _catalogs(edition):
        for planet in planets:
            texts.extend(_reps(planet))
    vectors = _embed(texts)
    report = replay_edition(edition, vectors, labeled)
    report["edition"] = edition.get("last_updated")
    report["watch"] = _watch(edition)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    if args.joins_out:
        with args.joins_out.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "edition",
                    "section",
                    "planet_a",
                    "planet_b",
                    "post_count_a",
                    "post_count_b",
                    "is_duplicate",
                    "label_reason",
                ],
            )
            writer.writeheader()
            counts = {}
            for scope, planets in _catalogs(edition):
                for planet in planets:
                    counts[str(planet.get("name") or "")] = int(planet.get("post_count") or 0)
            for section in report["sections"]:
                for fold in section["folds"]:
                    writer.writerow(
                        {
                            "edition": edition.get("last_updated"),
                            "section": section["section"],
                            "planet_a": fold["child"],
                            "planet_b": fold["parent"],
                            "post_count_a": fold["posts"],
                            "post_count_b": counts.get(fold["parent"], ""),
                            "is_duplicate": "",
                            "label_reason": "",
                        }
                    )


if __name__ == "__main__":
    main()
