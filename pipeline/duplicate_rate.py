"""Free near-duplicate rate for one published edition.

This is the definition #275 should reuse. It does not drop or merge planets.

Scores
------
``title_similarity`` is the SequenceMatcher ratio of the two titles after the
same normalization as ``pipeline.label.titles_alike`` (lowercase tokens, a
trailing disambiguation number removed). ``titles_alike`` stays the boolean
title gate: ratio >= 0.80, token Jaccard >= 0.67, containment, or one shared
stem.

``centroid_cosine`` is the cosine of the two mean L2-normalized TF-IDF
vectors of each side's representative posts (``pipeline.cluster_math.vectorize``).
No downloaded embedding model. None when a side has no tokens. 0.90 is the
default cut, the same face-centroid paraphrase line as
``pipeline.perspectives._FACE_COSINE``.

A pair is a near-duplicate when ``titles_alike`` is true, or ``centroid_cosine``
is at least ``centroid_min``. Callers that are calibrating pass ``title_min``
and set ``use_title_min=True`` so the title gate is only that ratio.

Rates
-----
Planet rate: near-duplicate unordered pairs divided by every unordered pair
of published planets. A catalog planet whose name is already in a section is
not paired again. Face rate: the same, for faces inside each planet, pooled.
Day-over-day is the change in that share. A lower share can mean the method
stopped making duplicates. It can also mean a later step removed planets.
The count of pairs is printed next to the share so those two are not confused.

Before and after the guards
----------------------------
The rate is printed twice. ``before`` is the planets as the grouping left
them. ``after`` is a copy with the post-hoc guards applied: the post floor,
the junk filter (``planet_chitchat_reason``), and the face fold
(``merge_alike_published_faces``, plus ``local_faces_fold`` when #268 has
landed). The copy is thrown away. A falling after-figure with a flat
before-figure means those guards hid duplicates. Planets an earlier pipeline
run already dropped are not in a published snapshot, so they are not in
that before-figure.

Labeled sample
--------------
``docs/evidence/275/oct19-pairs.csv`` is #275's hand labels, when that file
exists. Required header:

    pair_type,left_key,right_key,left_title,right_title,duplicate,spot_check

``pair_type`` is ``planet`` or ``face``. Keys are ``planet:{scope}:{id}`` and
``face:{scope}:{planet_id}:{face_index}``. ``duplicate`` is 1 or 0. Titles are
the fallback match when the keys differ. ``spot_check`` (or a row in
``docs/evidence/275/oct19-spot-checks.csv``) marks Michael's pairs.

The other rows are split with seed 273: two-thirds tune the threshold, one
third is held out. Agreement is precision and recall on the held-out third
plus the spot-check pairs only. The tune rows are not in that score.
"""

from __future__ import annotations

import copy
import csv
import random
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.cluster_math import vectorize
from pipeline.label import titles_alike

# SequenceMatcher gate inside titles_alike. Exposed so a labeled sample can
# move one number without editing the boolean helper.
DEFAULT_TITLE_MIN = 0.80
# pipeline.perspectives._FACE_COSINE. Two face centroids at or above this
# are one paraphrase, not two views.
DEFAULT_CENTROID_MIN = 0.90
# Fixed so the same CSV always yields the same tune and holdout rows.
SPLIT_SEED = 273
TITLE_GRID = (0.50, 0.67, 0.80, 0.90)
CENTROID_GRID = (0.55, 0.72, 0.80, 0.90)
_SPOT_VALUES = frozenset({"1", "true", "yes", "michael", "spot", "spot-check", "spot_check"})
LABELED_SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "275" / "oct19-pairs.csv"
SPOT_CHECK_SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "275" / "oct19-spot-checks.csv"
EXAMPLE_LIMIT = 15


def _normalize_title(value: str | None) -> str:
    import re

    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    while words and words[-1].isdigit():
        words.pop()
    return " ".join(words)


def title_similarity(left: str | None, right: str | None) -> float:
    """Continuous title score in 0..1. Same normalization as ``titles_alike``."""
    one = _normalize_title(left)
    two = _normalize_title(right)
    if not one or not two:
        return 0.0
    return float(SequenceMatcher(None, one, two).ratio())


def is_near_duplicate(
    title_score: float,
    centroid_cosine: float | None,
    *,
    titles_are_alike: bool,
    title_min: float = DEFAULT_TITLE_MIN,
    centroid_min: float = DEFAULT_CENTROID_MIN,
    use_title_min: bool = False,
) -> bool:
    """True when the title gate fires or the centroids are at least ``centroid_min``.

    The daily check leaves ``use_title_min`` false, so the title gate is
    ``titles_alike``. A calibration run sets it true and varies ``title_min``.
    """
    if use_title_min:
        title_hit = float(title_score) + 1e-12 >= float(title_min)
    else:
        title_hit = bool(titles_are_alike)
    centroid_hit = centroid_cosine is not None and float(centroid_cosine) + 1e-12 >= float(centroid_min)
    return bool(title_hit or centroid_hit)


def _texts(holder: dict) -> list[str]:
    posts = holder.get("representative_posts")
    if isinstance(posts, list):
        return [str(post.get("text") or "") for post in posts if isinstance(post, dict) and str(post.get("text") or "").strip()]
    found: list[str] = []
    for face in holder.get("perspectives") or []:
        if isinstance(face, dict):
            found.extend(_texts(face))
    return found


def centroids(text_groups: list[list[str]]) -> list[np.ndarray | None]:
    """One unit centroid per group, in a shared TF-IDF space. None if empty."""
    rows: list[str] = []
    owner: list[int] = []
    for index, texts in enumerate(text_groups):
        for text in texts:
            if str(text).strip():
                rows.append(str(text))
                owner.append(index)
    blank: list[np.ndarray | None] = [None] * len(text_groups)
    if not rows:
        return blank
    try:
        matrix = vectorize(rows)
    except ValueError:
        return blank
    owners = np.array(owner)
    for index in range(len(text_groups)):
        members = matrix[owners == index]
        if len(members) == 0:
            continue
        center = members.mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            continue
        blank[index] = center / norm
    return blank


def _cosine(left: np.ndarray | None, right: np.ndarray | None) -> float | None:
    if left is None or right is None:
        return None
    return float(np.dot(left, right))


def planet_key(scope: str, planet: dict) -> str:
    return f"planet:{scope}:{planet.get('id')}"


def face_key(scope: str, planet: dict, index: int) -> str:
    return f"face:{scope}:{planet.get('id')}:{index}"


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


def planets_for_pairs(payload: dict) -> list[tuple[str, dict]]:
    """Section planets, plus catalog planets that are not already in a section."""
    section_names = {
        str(planet.get("name") or "").strip().lower()
        for scope, planet in _iter_planets(payload)
        if scope != "catalog"
    }
    kept: list[tuple[str, dict]] = []
    for scope, planet in _iter_planets(payload):
        name = str(planet.get("name") or "").strip().lower()
        if scope == "catalog" and name in section_names:
            continue
        kept.append((scope, planet))
    return kept


def _score_pair(
    *,
    pair_type: str,
    left_key: str,
    right_key: str,
    left_title: str,
    right_title: str,
    left_centroid: np.ndarray | None,
    right_centroid: np.ndarray | None,
    title_min: float,
    centroid_min: float,
    use_title_min: bool,
) -> dict[str, Any]:
    score = title_similarity(left_title, right_title)
    cosine = _cosine(left_centroid, right_centroid)
    alike = titles_alike(left_title, right_title)
    near = is_near_duplicate(
        score,
        cosine,
        titles_are_alike=alike,
        title_min=title_min,
        centroid_min=centroid_min,
        use_title_min=use_title_min,
    )
    return {
        "pair_type": pair_type,
        "left_key": left_key,
        "right_key": right_key,
        "left_title": left_title,
        "right_title": right_title,
        "title_similarity": round(score, 4),
        "titles_alike": alike,
        "centroid_cosine": None if cosine is None else round(cosine, 4),
        "near_duplicate": near,
    }


def score_pairs(
    payload: dict,
    *,
    title_min: float = DEFAULT_TITLE_MIN,
    centroid_min: float = DEFAULT_CENTROID_MIN,
    use_title_min: bool = False,
) -> list[dict[str, Any]]:
    """Every unordered planet pair and within-planet face pair, with both scores."""
    planets = planets_for_pairs(payload)
    planet_centers = centroids([_texts(planet) for _scope, planet in planets])
    scored: list[dict[str, Any]] = []
    for index, (scope, planet) in enumerate(planets):
        for other in range(index + 1, len(planets)):
            other_scope, other_planet = planets[other]
            scored.append(
                _score_pair(
                    pair_type="planet",
                    left_key=planet_key(scope, planet),
                    right_key=planet_key(other_scope, other_planet),
                    left_title=str(planet.get("name") or ""),
                    right_title=str(other_planet.get("name") or ""),
                    left_centroid=planet_centers[index],
                    right_centroid=planet_centers[other],
                    title_min=title_min,
                    centroid_min=centroid_min,
                    use_title_min=use_title_min,
                )
            )
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        face_centers = centroids([_texts(face) for face in faces])
        for left in range(len(faces)):
            for right in range(left + 1, len(faces)):
                scored.append(
                    _score_pair(
                        pair_type="face",
                        left_key=face_key(scope, planet, left),
                        right_key=face_key(scope, planet, right),
                        left_title=str(faces[left].get("title") or ""),
                        right_title=str(faces[right].get("title") or ""),
                        left_centroid=face_centers[left],
                        right_centroid=face_centers[right],
                        title_min=title_min,
                        centroid_min=centroid_min,
                        use_title_min=use_title_min,
                    )
                )
    return scored


def _rate(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(pairs)
    near = [pair for pair in pairs if pair["near_duplicate"]]
    return {
        "pairs": total,
        "near_duplicates": len(near),
        "rate": round(len(near) / total, 4) if total else 0.0,
    }


def _pair_identity(left: str, right: str) -> tuple[str, str]:
    one, two = left.strip(), right.strip()
    return (one, two) if one <= two else (two, one)


def _spot_check_row(raw: dict) -> bool:
    for column in ("spot_check", "spotcheck", "michael_spot_check"):
        if str(raw.get(column) or "").strip().lower() in _SPOT_VALUES:
            return True
    source = str(raw.get("source") or raw.get("reviewer") or "").strip().lower()
    return source in _SPOT_VALUES


def _label_identity(row: dict[str, str]) -> tuple[str, str, str]:
    left = row["left_key"] or _normalize_title(row["left_title"])
    right = row["right_key"] or _normalize_title(row["right_title"])
    return (row["pair_type"],) + _pair_identity(left, right)


def load_labeled_pairs(path: Path) -> list[dict[str, str]]:
    """Read #275's CSV. Raises FileNotFoundError when the sample is absent."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "duplicate" not in reader.fieldnames or "pair_type" not in reader.fieldnames:
            raise ValueError(f"{path} needs columns pair_type and duplicate")
        rows: list[dict[str, str]] = []
        for raw in reader:
            label = str(raw.get("duplicate") or "").strip().lower()
            if label not in {"0", "1", "true", "false", "yes", "no"}:
                continue
            rows.append(
                {
                    "pair_type": str(raw.get("pair_type") or "").strip().lower(),
                    "left_key": str(raw.get("left_key") or "").strip(),
                    "right_key": str(raw.get("right_key") or "").strip(),
                    "left_title": str(raw.get("left_title") or "").strip(),
                    "right_title": str(raw.get("right_title") or "").strip(),
                    "duplicate": "1" if label in {"1", "true", "yes"} else "0",
                    "spot_check": "1" if _spot_check_row(raw) else "0",
                }
            )
        return rows


def load_label_bundle(path: Path, spot_path: Path | None = None) -> list[dict[str, str]]:
    """Sample rows plus Michael's spot-check file, if that file is present.

    A pair listed in both is kept once, as a spot-check, so it cannot fall
    into the tune split.
    """
    rows = load_labeled_pairs(path)
    extra_path = SPOT_CHECK_SAMPLE if spot_path is None else spot_path
    if extra_path.is_file() and extra_path.resolve() != path.resolve():
        for row in load_labeled_pairs(extra_path):
            row["spot_check"] = "1"
            rows.append(row)
    kept: list[dict[str, str]] = []
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = _label_identity(row)
        existing = index.get(key)
        if existing is None:
            index[key] = row
            kept.append(row)
            continue
        if row["spot_check"] == "1":
            existing["spot_check"] = "1"
        if row["duplicate"] == "1":
            existing["duplicate"] = "1"
    return kept


def split_labeled_sample(
    labels: list[dict[str, str]],
    *,
    seed: int = SPLIT_SEED,
) -> dict[str, list[dict[str, str]]]:
    """Two-thirds tune, one-third holdout. Spot-checks stay out of the tune set.

    The pool is sorted, then shuffled with ``seed``, so the split does not
    depend on row order or ``PYTHONHASHSEED``.
    """
    spots = [row for row in labels if row.get("spot_check") == "1"]
    pool = [row for row in labels if row.get("spot_check") != "1"]
    ordered = sorted(pool, key=_label_identity)
    random.Random(seed).shuffle(ordered)
    tune_count = (len(ordered) * 2) // 3
    tune = ordered[:tune_count]
    holdout = ordered[tune_count:]
    evaluation = holdout + spots
    tune_ids = {_label_identity(row) for row in tune}
    if tune_ids & {_label_identity(row) for row in evaluation}:
        raise RuntimeError("tune rows leaked into the agreement set")
    return {"tune": tune, "holdout": holdout, "spot_checks": spots, "evaluation": evaluation}


def _match_label(label: dict[str, str], by_key: dict, by_title: dict) -> dict[str, Any] | None:
    if label["left_key"] and label["right_key"]:
        found = by_key.get((label["pair_type"],) + _pair_identity(label["left_key"], label["right_key"]))
        if found is not None:
            return found if not isinstance(found, list) else None
    if label["left_title"] and label["right_title"]:
        found = by_title.get(
            (label["pair_type"],) + _pair_identity(_normalize_title(label["left_title"]), _normalize_title(label["right_title"]))
        )
        if isinstance(found, list):
            return None
        return found
    return None


def agreement_with_labels(
    scored: list[dict[str, Any]],
    labels: list[dict[str, str]],
) -> dict[str, Any]:
    """Precision and recall of ``near_duplicate`` on the labeled rows it can match.

    The detector's own rate is not an input. Unmatched labels are reported
    and left out of precision and recall.
    """
    by_key: dict[tuple, dict[str, Any] | list] = {}
    by_title: dict[tuple, dict[str, Any] | list] = {}
    for pair in scored:
        key = (pair["pair_type"],) + _pair_identity(pair["left_key"], pair["right_key"])
        by_key[key] = pair
        title_key = (pair["pair_type"],) + _pair_identity(
            _normalize_title(pair["left_title"]),
            _normalize_title(pair["right_title"]),
        )
        if title_key[1] and title_key[2]:
            existing = by_title.get(title_key)
            if existing is None:
                by_title[title_key] = pair
            elif isinstance(existing, list):
                existing.append(pair)
            else:
                by_title[title_key] = [existing, pair]
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    unmatched = 0
    for label in labels:
        pair = _match_label(label, by_key, by_title)
        if pair is None:
            unmatched += 1
            continue
        predicted = bool(pair["near_duplicate"])
        actual = label["duplicate"] == "1"
        if predicted and actual:
            true_positive += 1
        elif predicted and not actual:
            false_positive += 1
        elif not predicted and actual:
            false_negative += 1
        else:
            true_negative += 1
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    precision = (true_positive / predicted_positive) if predicted_positive else None
    recall = (true_positive / actual_positive) if actual_positive else None
    return {
        "matched": true_positive + false_positive + false_negative + true_negative,
        "unmatched": unmatched,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": None if precision is None else round(precision, 4),
        "recall": None if recall is None else round(recall, 4),
    }


def _post_count(planet: dict) -> int:
    raw = planet.get("post_count")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    total = 0
    for face in planet.get("perspectives") or []:
        if isinstance(face, dict):
            try:
                total += int(face.get("post_count") or 0)
            except (TypeError, ValueError):
                continue
    return total


def _member_posts(planet: dict) -> list[dict]:
    posts = [
        post
        for post in (planet.get("representative_posts") or [])
        if isinstance(post, dict) and str(post.get("text") or "").strip()
    ]
    if posts:
        return posts
    found: list[dict] = []
    for face in planet.get("perspectives") or []:
        if not isinstance(face, dict):
            continue
        for post in face.get("representative_posts") or []:
            if isinstance(post, dict) and str(post.get("text") or "").strip():
                found.append(post)
    return found


def _local_faces_fold():
    """#268's fold once it is on this tree. None until then."""
    try:
        from pipeline import stance
    except ImportError:
        return None
    return getattr(stance, "local_faces_fold", None)


def _fold_alike_faces(planets: list[dict]) -> int:
    """Fold faces with the same title gate as ``merge_alike_published_faces``.

    That helper rewrites face ids with ``int(planet id)``. Published section
    ids look like ``World-7``, so the measurement copy folds here and leaves
    the ids alone.
    """
    folded = 0
    for planet in planets:
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        if len(faces) < 2:
            continue
        ranked = sorted(faces, key=lambda face: (-int(face.get("post_count") or 0), str(face.get("id") or "")))
        kept: list[dict] = []
        for face in ranked:
            if face.get("stance_locked"):
                kept.append(face)
                continue
            match = next(
                (
                    item
                    for item in kept
                    if not item.get("stance_locked") and titles_alike(item.get("title"), face.get("title"))
                ),
                None,
            )
            if match is None:
                kept.append(face)
                continue
            folded += 1
            match["post_count"] = int(match.get("post_count") or 0) + int(face.get("post_count") or 0)
            shown = list(match.get("representative_posts") or [])
            seen_text = {str(post.get("text") or "") for post in shown if isinstance(post, dict)}
            for post in face.get("representative_posts") or []:
                if not isinstance(post, dict) or str(post.get("text") or "") in seen_text:
                    continue
                shown.append(post)
                seen_text.add(str(post.get("text") or ""))
            match["representative_posts"] = shown[:36]
        planet["perspectives"] = kept
    return folded


def apply_post_hoc_guards(payload: dict, *, floor: int) -> tuple[dict, dict[str, int]]:
    """Copy the edition and apply the floor, the junk filter, and the face fold.

    The input payload is not modified. This is a measurement, not a publish step.
    """
    from pipeline.chitchat_guard import planet_chitchat_reason

    guarded = copy.deepcopy(payload)
    removed = {"floor": 0, "junk": 0}
    faces_before = 0

    def keep(planet: dict) -> bool:
        if floor > 0 and _post_count(planet) < floor:
            removed["floor"] += 1
            return False
        reason = planet_chitchat_reason(_member_posts(planet), [])
        if reason:
            removed["junk"] += 1
            return False
        return True

    topics = guarded.get("topics")
    if isinstance(topics, list):
        guarded["topics"] = [planet for planet in topics if isinstance(planet, dict) and keep(planet)]
    sections = guarded.get("sections")
    if isinstance(sections, dict):
        for name, planets in list(sections.items()):
            if not isinstance(planets, list):
                continue
            sections[name] = [planet for planet in planets if isinstance(planet, dict) and keep(planet)]
    folded_hosts: list[dict] = []
    for planet in list(guarded.get("topics") or []):
        if isinstance(planet, dict):
            folded_hosts.append(planet)
    if isinstance(guarded.get("sections"), dict):
        for planets in guarded["sections"].values():
            if isinstance(planets, list):
                folded_hosts.extend(planet for planet in planets if isinstance(planet, dict))
    faces_before = sum(len(planet.get("perspectives") or []) for planet in folded_hosts)
    _fold_alike_faces(folded_hosts)
    fold = _local_faces_fold()
    if fold is not None:
        for planet in folded_hosts:
            try:
                fold(planet)
            except TypeError:
                faces = planet.get("perspectives") or []
                folded = fold(faces)
                if isinstance(folded, list):
                    planet["perspectives"] = folded
    faces_after = sum(len(planet.get("perspectives") or []) for planet in folded_hosts)
    removed["faces_folded"] = max(0, faces_before - faces_after)
    return guarded, removed


def _flag_pairs(
    scored: list[dict[str, Any]],
    *,
    title_min: float,
    centroid_min: float,
    use_title_min: bool,
) -> list[dict[str, Any]]:
    flagged: list[dict[str, Any]] = []
    for pair in scored:
        near = is_near_duplicate(
            float(pair["title_similarity"]),
            pair["centroid_cosine"],
            titles_are_alike=bool(pair["titles_alike"]),
            title_min=title_min,
            centroid_min=centroid_min,
            use_title_min=use_title_min,
        )
        flagged.append({**pair, "near_duplicate": near})
    return flagged


def _f1(precision: float | None, recall: float | None) -> float:
    if precision is None or recall is None:
        return 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def tune_threshold(
    scored: list[dict[str, Any]],
    tune_labels: list[dict[str, str]],
) -> dict[str, Any]:
    """Pick title and centroid cuts from ``tune_labels`` only."""
    best: dict[str, Any] | None = None
    for title_min in TITLE_GRID:
        for centroid_min in CENTROID_GRID:
            flagged = _flag_pairs(
                scored,
                title_min=title_min,
                centroid_min=centroid_min,
                use_title_min=True,
            )
            measured = agreement_with_labels(flagged, tune_labels)
            score = _f1(measured["precision"], measured["recall"])
            candidate = {
                "title_min": title_min,
                "centroid_min": centroid_min,
                "use_title_min": True,
                "f1": round(score, 4),
                "tune_precision": measured["precision"],
                "tune_recall": measured["recall"],
                "tune_matched": measured["matched"],
            }
            if best is None or (score, measured["precision"] or 0, centroid_min, title_min) > (
                best["f1"],
                best["tune_precision"] or 0,
                best["centroid_min"],
                best["title_min"],
            ):
                best = candidate
    assert best is not None
    return best


def _examples(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    near = [pair for pair in pairs if pair["near_duplicate"]]
    near.sort(key=lambda pair: (-(pair["centroid_cosine"] or -1), -pair["title_similarity"], pair["left_title"]))
    trimmed = []
    for pair in near[:EXAMPLE_LIMIT]:
        trimmed.append(
            {
                "pair_type": pair["pair_type"],
                "left_key": pair["left_key"],
                "right_key": pair["right_key"],
                "left_title": pair["left_title"],
                "right_title": pair["right_title"],
                "title_similarity": pair["title_similarity"],
                "centroid_cosine": pair["centroid_cosine"],
                "titles_alike": pair["titles_alike"],
            }
        )
    return trimmed


def _side_rates(flagged: list[dict[str, Any]]) -> dict[str, Any]:
    planets = _rate([pair for pair in flagged if pair["pair_type"] == "planet"])
    faces = _rate([pair for pair in flagged if pair["pair_type"] == "face"])
    return {"planets": planets, "faces": faces}


def _change(today: float, prior: float | None) -> float | None:
    if prior is None:
        return None
    return round(float(today) - float(prior), 4)


def _prior_side(previous: dict, side: str, *, title_min: float, centroid_min: float, use_title_min: bool, floor: int) -> tuple[dict[str, Any] | None, str | None]:
    """Rates for one side of a previous edition, or None when there is no previous."""
    if "duplicate_rate" in previous and isinstance(previous.get("duplicate_rate"), dict):
        block = previous["duplicate_rate"].get(side)
        if isinstance(block, dict) and "planets" in block:
            return block, previous.get("edition_date")
        return None, previous.get("edition_date")
    if side == "after":
        guarded, _removed = apply_post_hoc_guards(previous, floor=floor)
        scored = score_pairs(guarded, title_min=title_min, centroid_min=centroid_min, use_title_min=use_title_min)
    else:
        scored = score_pairs(previous, title_min=title_min, centroid_min=centroid_min, use_title_min=use_title_min)
    flagged = _flag_pairs(scored, title_min=title_min, centroid_min=centroid_min, use_title_min=use_title_min)
    return _side_rates(flagged), previous.get("last_updated") or previous.get("edition_date")


def _guard_reading(before_change: float | None, after_change: float | None, kind: str) -> str | None:
    if before_change is None or after_change is None:
        return None
    if after_change <= -0.005 and abs(before_change) < 0.005:
        return (
            f"The {kind} after-rate fell while the before-rate stayed flat. "
            "The guards are hiding duplicates, not the method improving."
        )
    return None


def duplicate_rates(
    payload: dict,
    *,
    previous: dict | None = None,
    labeled_path: Path | None = None,
    spot_path: Path | None = None,
    floor: int = 0,
    title_min: float = DEFAULT_TITLE_MIN,
    centroid_min: float = DEFAULT_CENTROID_MIN,
) -> dict[str, Any]:
    """Before-guard and after-guard shares, day-over-day, and held-out agreement.

    When the labeled sample exists, the threshold is chosen on the tune split
    and both shares use it. Precision and recall use the holdout and the
    spot-check pairs only.
    """
    raw_scored = score_pairs(payload, title_min=title_min, centroid_min=centroid_min, use_title_min=False)
    guarded, removed = apply_post_hoc_guards(payload, floor=floor)
    after_scored = score_pairs(guarded, title_min=title_min, centroid_min=centroid_min, use_title_min=False)
    use_title_min = False
    chosen_title = title_min
    chosen_centroid = centroid_min
    sample = labeled_path if labeled_path is not None else LABELED_SAMPLE
    spot_file = SPOT_CHECK_SAMPLE if spot_path is None else spot_path
    agreement: dict[str, Any]
    if sample.is_file():
        labels = load_label_bundle(sample, spot_file)
        parts = split_labeled_sample(labels)
        tuned = tune_threshold(raw_scored, parts["tune"])
        chosen_title = float(tuned["title_min"])
        chosen_centroid = float(tuned["centroid_min"])
        use_title_min = True
        flagged_before = _flag_pairs(
            raw_scored,
            title_min=chosen_title,
            centroid_min=chosen_centroid,
            use_title_min=True,
        )
        measured = agreement_with_labels(flagged_before, parts["evaluation"])
        agreement = {
            "present": True,
            "path": str(sample),
            "spot_path": str(spot_file) if spot_file.is_file() else None,
            "seed": SPLIT_SEED,
            "title_min": chosen_title,
            "centroid_min": chosen_centroid,
            "tuned_on": len(parts["tune"]),
            "holdout": len(parts["holdout"]),
            "spot_checks": len(parts["spot_checks"]),
            "scored_on": len(parts["evaluation"]),
            **measured,
            "note": (
                "Precision and recall are the held-out third plus Michael's spot-check pairs. "
                "The tune split is not in these numbers. The shares above are the detector's "
                "own counts, not that grade."
            ),
        }
    else:
        flagged_before = _flag_pairs(
            raw_scored,
            title_min=chosen_title,
            centroid_min=chosen_centroid,
            use_title_min=False,
        )
        agreement = {
            "present": False,
            "path": str(sample),
            "spot_path": str(spot_file),
            "seed": SPLIT_SEED,
            "precision": None,
            "recall": None,
            "tuned_on": 0,
            "holdout": 0,
            "spot_checks": 0,
            "scored_on": 0,
            "note": (
                "The labeled sample is not in the tree yet, so the threshold stays at the "
                "default and precision and recall are not computed. This rate does not grade itself."
            ),
        }
    flagged_after = _flag_pairs(
        after_scored,
        title_min=chosen_title,
        centroid_min=chosen_centroid,
        use_title_min=use_title_min,
    )
    before = _side_rates(flagged_before)
    after = _side_rates(flagged_after)
    previous_date = None
    prior_before = prior_after = None
    if isinstance(previous, dict):
        prior_before, previous_date = _prior_side(
            previous,
            "before",
            title_min=chosen_title,
            centroid_min=chosen_centroid,
            use_title_min=use_title_min,
            floor=floor,
        )
        prior_after, previous_date = _prior_side(
            previous,
            "after",
            title_min=chosen_title,
            centroid_min=chosen_centroid,
            use_title_min=use_title_min,
            floor=floor,
        )
    before["planet_rate_change"] = _change(
        before["planets"]["rate"],
        None if prior_before is None else prior_before["planets"]["rate"],
    )
    before["face_rate_change"] = _change(
        before["faces"]["rate"],
        None if prior_before is None else prior_before["faces"]["rate"],
    )
    after["planet_rate_change"] = _change(
        after["planets"]["rate"],
        None if prior_after is None else prior_after["planets"]["rate"],
    )
    after["face_rate_change"] = _change(
        after["faces"]["rate"],
        None if prior_after is None else prior_after["faces"]["rate"],
    )
    before["guards"] = "not applied"
    after["guards"] = "floor, junk filter, face fold"
    after["removed"] = removed
    readings = [
        text
        for text in (
            _guard_reading(before["planet_rate_change"], after["planet_rate_change"], "planet"),
            _guard_reading(before["face_rate_change"], after["face_rate_change"], "face"),
        )
        if text
    ]
    if use_title_min:
        definition = (
            f"Near-duplicate when title similarity >= {chosen_title} "
            f"or representative-post TF-IDF centroid cosine >= {chosen_centroid}. "
            "Those cuts were tuned on two-thirds of the labeled sample."
        )
    else:
        definition = (
            "Near-duplicate when titles_alike, or when representative-post "
            f"TF-IDF centroid cosine >= {chosen_centroid}."
        )
    return {
        "definition": definition,
        "title_min": chosen_title,
        "centroid_min": chosen_centroid,
        "use_title_min": use_title_min,
        "planet_stage": "clustering/attach",
        "face_stage": "faces/stance",
        "previous_edition": previous_date,
        "before": before,
        "after": after,
        "guard_reading": readings,
        "examples": _examples(flagged_before),
        "agreement": agreement,
    }


def render_duplicate_lines(report: dict[str, Any]) -> list[str]:
    """Markdown lines for the daily summary."""
    block = report.get("duplicate_rate") or {}
    agreement = block.get("agreement") or {}

    def share(part: dict) -> str:
        rate = float(part.get("rate") or 0.0)
        return f"{rate:.1%} ({part.get('near_duplicates', 0)} of {part.get('pairs', 0)} pairs)"

    def delta(value: float | None, prior: str | None) -> str:
        if value is None:
            return "no previous edition"
        points = float(value) * 100
        sign = "+" if points > 0 else ""
        when = f" from {prior}" if prior else ""
        return f"{sign}{points:.1f} pp{when}"

    def side_lines(title: str, side: dict) -> list[str]:
        planets = side.get("planets") or {}
        faces = side.get("faces") or {}
        return [
            f"### {title}",
            "",
            (
                f"- Planets ({block.get('planet_stage')}): {share(planets)}. "
                f"Day-over-day {delta(side.get('planet_rate_change'), block.get('previous_edition'))}."
            ),
            (
                f"- Faces ({block.get('face_stage')}): {share(faces)}. "
                f"Day-over-day {delta(side.get('face_rate_change'), block.get('previous_edition'))}."
            ),
            "",
        ]

    lines = [
        "## Duplicate rate",
        "",
        block.get("definition") or "",
        "",
        "Before is the grouping. After reapplies the floor, the junk filter, and the face fold on a copy. The edition is not changed.",
        "",
    ]
    lines.extend(side_lines("Before the guards", block.get("before") or {}))
    lines.extend(side_lines("After the guards", block.get("after") or {}))
    removed = (block.get("after") or {}).get("removed") or {}
    if removed:
        lines.append(
            f"Guards removed {removed.get('floor', 0)} planets under the floor, "
            f"{removed.get('junk', 0)} junk planets, and folded {removed.get('faces_folded', 0)} faces."
        )
        lines.append("")
    for reading in block.get("guard_reading") or []:
        lines.append(reading)
        lines.append("")
    if agreement.get("present"):
        lines.append(
            f"Agreement on the held-out third plus {agreement.get('spot_checks')} spot-check pairs "
            f"(`{agreement.get('path')}`, seed {agreement.get('seed')}): "
            f"precision {agreement.get('precision')}, recall {agreement.get('recall')} "
            f"(scored {agreement.get('scored_on')}, tuned on {agreement.get('tuned_on')}, "
            f"matched {agreement.get('matched')}, unmatched {agreement.get('unmatched')}). "
            f"{agreement.get('note')}"
        )
    else:
        lines.append(str(agreement.get("note") or "Labeled agreement was not computed."))
    lines.append("")
    return lines
