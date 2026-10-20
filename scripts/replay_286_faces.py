#!/usr/bin/env python3
"""Guards-off replay of the paraphrase-face gate (issue #286).

Re-scores published within-planet face splits with
``refused_paraphrase_pairs``. A pair at or above the paraphrase line whose
posts do not disagree is merged onto the surviving face. Posts are not
dropped and planets do not change section.

Not applied, on purpose: the 30-post floor (#266), the junk filter (#264),
the post-hoc stance fold (#268), and the exact-title fold (#235). No Jev
call, no section labeling, no label model, no workflow dispatch.

Oct 19 ``is_duplicate`` is joined from the #275 face census. The Oct 20 (or
later) sheet leaves ``is_duplicate`` empty for a blind labeler. This script
does not fill that column.
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

from pipeline.perspectives import refused_paraphrase_pairs  # noqa: E402
from pipeline.stance import local_faces_disagree  # noqa: E402

BLIND_COLUMNS = [
    "pair_id",
    "level",
    "section",
    "planet",
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
PAIR_COLUMNS = [
    "edition",
    *BLIND_COLUMNS,
    "cosine",
    "posts_disagree",
    "direct_refused",
    "merged",
    "label_reason",
]
SECTION_COLUMNS = [
    "edition",
    "section",
    "faces_before",
    "faces_after",
    "repeat_pairs",
    "repeat_merged",
    "different_pairs",
    "different_merged",
    "unsure_pairs",
    "unsure_merged",
    "unlabeled_pairs",
    "unlabeled_merged",
    "posts_before",
    "posts_after",
    "posts_dropped",
    "posts_moved_to_other",
    "posts_kept_on_survivor",
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


def _l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def _embed_map(texts: list[str]) -> dict[str, np.ndarray]:
    from pipeline.embed import embed_minilm

    unique = list(dict.fromkeys(text for text in texts if text))
    if not unique:
        return {}
    vectors = _l2(embed_minilm(unique))
    return {text: vectors[index] for index, text in enumerate(unique)}


def _face_posts(face: dict) -> list[dict]:
    posts = []
    for post in face.get("representative_posts") or []:
        if str(post.get("text") or "").strip():
            posts.append(post)
    return posts


def _label_key(section: str, planet: str, title_a: str, title_b: str, count_a: int, count_b: int) -> tuple:
    titles = tuple(sorted((title_a, title_b)))
    counts = tuple(sorted((int(count_a), int(count_b))))
    return (section, planet, titles, counts)


def _loose_key(section: str, planet: str, title_a: str, title_b: str) -> tuple:
    return (section, planet, tuple(sorted((title_a, title_b))))


def _load_labels(path: Path | None) -> tuple[dict[tuple, dict], dict[tuple, dict]]:
    """Strict keys include post counts. Loose keys are used only when unique."""
    if path is None or not path.exists():
        return {}, {}
    strict: dict[tuple, dict] = {}
    grouped: dict[tuple, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            section = row.get("section") or ""
            planet = row.get("planet") or row.get("planet_a") or ""
            title_a = row.get("title_a") or ""
            title_b = row.get("title_b") or ""
            key = _label_key(
                section,
                planet,
                title_a,
                title_b,
                int(row.get("post_count_a") or 0),
                int(row.get("post_count_b") or 0),
            )
            strict[key] = row
            grouped.setdefault(_loose_key(section, planet, title_a, title_b), []).append(row)
    loose = {key: rows[0] for key, rows in grouped.items() if len(rows) == 1}
    return strict, loose


class _Union:
    def __init__(self, count: int):
        self.parent = list(range(count))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _replay_edition(
    edition: dict,
    *,
    edition_name: str,
    vectors: dict[str, np.ndarray],
    labels: dict[tuple, dict],
    loose_labels: dict[tuple, dict] | None = None,
) -> tuple[list[dict], list[dict], dict]:
    pair_rows: list[dict] = []
    section_rows: list[dict] = []
    unmatched = 0
    next_id = 1
    for section, planets in _catalogs(edition):
        stats = {
            "edition": edition_name,
            "section": section,
            "faces_before": 0,
            "faces_after": 0,
            "repeat_pairs": 0,
            "repeat_merged": 0,
            "different_pairs": 0,
            "different_merged": 0,
            "unsure_pairs": 0,
            "unsure_merged": 0,
            "unlabeled_pairs": 0,
            "unlabeled_merged": 0,
            "posts_before": 0,
            "posts_after": 0,
            "posts_dropped": 0,
            "posts_moved_to_other": 0,
            "posts_kept_on_survivor": 0,
        }
        for planet in planets:
            faces = list(planet.get("perspectives") or [])
            stats["faces_before"] += len(faces)
            texts: list[str] = []
            face_labels: list[int] = []
            face_posts: list[list[dict]] = []
            for index, face in enumerate(faces):
                posts = _face_posts(face)
                face_posts.append(posts)
                for post in posts:
                    text = str(post.get("text") or "").strip()
                    if text not in vectors:
                        continue
                    texts.append(text)
                    face_labels.append(index)
            counts = [int(face.get("post_count") or 0) for face in faces]
            stats["posts_before"] += sum(counts)
            groups = _Union(len(faces))
            direct: set[tuple[int, int]] = set()
            cosine_of: dict[tuple[int, int], float] = {}
            disagree_of: dict[tuple[int, int], bool] = {}
            if len(faces) >= 2 and texts:
                matrix = np.vstack([vectors[text] for text in texts])
                for left, right, cosine in refused_paraphrase_pairs(texts, face_labels, matrix):
                    pair = (min(left, right), max(left, right))
                    direct.add(pair)
                    cosine_of[pair] = cosine
                    groups.union(left, right)
                # Cosine and disagreement for every published pair, including
                # pairs the gate keeps. Centroids use the same representative
                # vectors the refusal check just scored.
                centers: list[np.ndarray | None] = []
                for index, posts in enumerate(face_posts):
                    rows = [vectors[str(post.get("text") or "").strip()] for post in posts if str(post.get("text") or "").strip() in vectors]
                    if not rows:
                        centers.append(None)
                        continue
                    center = np.vstack(rows).mean(axis=0)
                    norm = float(np.linalg.norm(center))
                    centers.append(None if norm == 0.0 else center / norm)
                for left in range(len(faces)):
                    for right in range(left + 1, len(faces)):
                        pair = (left, right)
                        if centers[left] is not None and centers[right] is not None:
                            cosine_of[pair] = float(centers[left] @ centers[right])
                        left_posts = [{"text": str(post.get("text") or "")} for post in face_posts[left]]
                        right_posts = [{"text": str(post.get("text") or "")} for post in face_posts[right]]
                        disagree_of[pair] = bool(local_faces_disagree({}, {}, left_posts, right_posts))
            roots: dict[int, list[int]] = {}
            for index in range(len(faces)):
                roots.setdefault(groups.find(index), []).append(index)
            stats["faces_after"] += len(roots) if faces else 0
            for members in roots.values():
                if len(members) < 2:
                    continue
                ranked = sorted(members, key=lambda index: (-counts[index], index))
                survivor = ranked[0]
                for index in ranked:
                    if index == survivor:
                        continue
                    stats["posts_kept_on_survivor"] += counts[index]
            stats["posts_after"] += sum(counts)
            planet_name = str(planet.get("name") or "")
            for left in range(len(faces)):
                for right in range(left + 1, len(faces)):
                    title_a = str(faces[left].get("title") or "")
                    title_b = str(faces[right].get("title") or "")
                    count_a = counts[left]
                    count_b = counts[right]
                    key = _label_key(section, planet_name, title_a, title_b, count_a, count_b)
                    label = labels.get(key)
                    if label is None and loose_labels:
                        label = loose_labels.get(_loose_key(section, planet_name, title_a, title_b))
                    if label is None:
                        unmatched += 1 if labels or loose_labels else 0
                        pair_id = f"u{next_id:03d}"
                        next_id += 1
                        duplicate = ""
                        reason = ""
                    else:
                        pair_id = label.get("pair_id") or f"u{next_id:03d}"
                        if not label.get("pair_id"):
                            next_id += 1
                        duplicate = (label.get("is_duplicate") or "").strip()
                        reason = label.get("label_reason") or ""
                    merged = groups.find(left) == groups.find(right)
                    pair = (left, right)
                    row = {
                        "edition": edition_name,
                        "pair_id": pair_id,
                        "level": "face_census",
                        "section": section,
                        "planet": planet_name,
                        "planet_a": planet_name,
                        "planet_b": planet_name,
                        "title_a": title_a,
                        "title_b": title_b,
                        "post_count_a": count_a,
                        "post_count_b": count_b,
                        "sample_texts_a": _samples(face_posts[left]),
                        "sample_texts_b": _samples(face_posts[right]),
                        "is_duplicate": duplicate,
                        "cosine": "" if pair not in cosine_of else round(cosine_of[pair], 4),
                        "posts_disagree": "yes" if disagree_of.get(pair) else "no",
                        "direct_refused": "yes" if pair in direct else "no",
                        "merged": "yes" if merged else "no",
                        "label_reason": reason,
                    }
                    pair_rows.append(row)
                    bucket = {
                        "yes": ("repeat_pairs", "repeat_merged"),
                        "no": ("different_pairs", "different_merged"),
                        "unsure": ("unsure_pairs", "unsure_merged"),
                    }.get(duplicate)
                    if bucket is None:
                        stats["unlabeled_pairs"] += 1
                        if merged:
                            stats["unlabeled_merged"] += 1
                    else:
                        stats[bucket[0]] += 1
                        if merged:
                            stats[bucket[1]] += 1
        # Section does not change, so nothing moves into Other.
        stats["posts_dropped"] = stats["posts_before"] - stats["posts_after"]
        stats["posts_moved_to_other"] = 0
        section_rows.append(stats)
    labels_present = any((row.get("is_duplicate") or "").strip() for row in pair_rows)
    for row in section_rows:
        if labels_present:
            continue
        for column in (
            "repeat_pairs",
            "repeat_merged",
            "different_pairs",
            "different_merged",
            "unsure_pairs",
            "unsure_merged",
        ):
            row[column] = ""
    summary = {
        "edition": edition_name,
        "faces_before": sum(int(row["faces_before"]) for row in section_rows),
        "faces_after": sum(int(row["faces_after"]) for row in section_rows),
        "posts_before": sum(int(row["posts_before"]) for row in section_rows),
        "posts_after": sum(int(row["posts_after"]) for row in section_rows),
        "posts_dropped": sum(int(row["posts_dropped"]) for row in section_rows),
        "posts_moved_to_other": 0,
        "posts_kept_on_survivor": sum(int(row["posts_kept_on_survivor"]) for row in section_rows),
        "labels_present": labels_present,
        "label_rows_unmatched_or_extra": unmatched,
    }
    return pair_rows, section_rows, summary


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _edition_date(edition: dict, fallback: str) -> str:
    stamp = str(edition.get("last_updated") or "").strip()
    return stamp or fallback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oct19", type=Path, required=True, help="Published Oct 19 data.json")
    parser.add_argument("--later", type=Path, required=True, help="Oct 20 or the latest later edition")
    parser.add_argument(
        "--labels",
        type=Path,
        default=ROOT / "docs" / "evidence" / "286" / "oct19-face-census-labels.csv",
        help="Oct 19 face-census labels. Oct 20 labels are not read.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "evidence" / "286",
        help="Directory for the replay tables and the blind Oct 20 sheet",
    )
    args = parser.parse_args()
    oct19 = json.loads(args.oct19.read_text(encoding="utf-8"))
    later = json.loads(args.later.read_text(encoding="utf-8"))
    labels, loose_labels = _load_labels(args.labels)
    texts: list[str] = []
    for edition in (oct19, later):
        for _section, planets in _catalogs(edition):
            for planet in planets:
                for face in planet.get("perspectives") or []:
                    for post in _face_posts(face):
                        texts.append(str(post.get("text") or "").strip())
    vectors = _embed_map(texts)
    date19 = _edition_date(oct19, "2026-10-19")
    date_later = _edition_date(later, "later")
    pairs_19, sections_19, summary_19 = _replay_edition(
        oct19, edition_name=date19, vectors=vectors, labels=labels, loose_labels=loose_labels
    )
    # The later edition stays unlabeled. Passing the Oct 19 sheet would
    # mis-join a same title on a different day.
    pairs_later, sections_later, summary_later = _replay_edition(
        later, edition_name=date_later, vectors=vectors, labels={}
    )
    out = args.out
    _write_csv(out / "replay-by-section.csv", SECTION_COLUMNS, sections_19 + sections_later)
    _write_csv(out / "replay-pairs.csv", PAIR_COLUMNS, pairs_19 + pairs_later)
    blind = [{column: row.get(column, "") for column in BLIND_COLUMNS} for row in pairs_later]
    for row in blind:
        row["is_duplicate"] = ""
    _write_csv(out / "oct20-face-pairs-unlabeled.csv", BLIND_COLUMNS, blind)
    report = {
        "guards": "off",
        "paid_calls": 0,
        "workflow_dispatch": False,
        "oct19": summary_19,
        "later": summary_later,
        "later_last_updated": date_later,
        "oct19_last_updated": date19,
        "blind_sheet": str(out / "oct20-face-pairs-unlabeled.csv"),
        "note": (
            "Cosines are MiniLM centroids of published representative posts, "
            "not the full-membership vectors the live split scored. "
            "is_duplicate on the later edition is empty."
        ),
    }
    (out / "replay-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
