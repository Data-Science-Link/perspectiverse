"""Three report-only counts. They do not change the edition.

Each count uses a signal the matching fix does not, so the fix cannot
zero the count just by being the same predicate.

Greeting planets (#288). The count is per-post: the share of posts with
almost no content tokens, or pairwise TF-IDF agreement among a planet's
own posts together with a short median length. It does not use the
greeting matcher, the daypart gate, or a pleasantry title list.

Fragments (#287). The count is same-section planet pairs whose titles
share a surface entity (an all-caps token or a token with a digit). The
post cap is tuned. It does not use ``story_attach`` stems or that
module's 20-post parent size.

Face agreement (#286). The count is the highest cosine between one
post on each face. It is not the cosine of the two mean vectors, and
it does not call the stance fold or ``split_perspectives``.

Thresholds are chosen on two-thirds of the labeled sample with seed 273,
inside each similarity band. Recall and false flags are the held-out
third plus the spot-check ids. A weekly blind sample for a second model
is designed and left off.
"""

from __future__ import annotations

import random
import re
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from pipeline.cluster_math import tokenize, vectorize
from pipeline.costs import (
    JEV_POST_TEXT_TOKENS,
    JEV_PRICE_AS_OF,
    JEV_REQUEST_OVERHEAD_TOKENS,
    JEV_USD_PER_MILLION_INPUT_TOKENS,
    jev_cost_usd,
)
from pipeline.duplicate_rate import (
    SPLIT_SEED,
    _iter_planets,
    _normalize_title,
    _post_count,
    _texts,
    split_labeled_sample,
)

# Chosen on the Oct 19 tune split (seed 273). Not refit on the holdout.
# The post cap is 12. It is not the attach gate's 20-post parent.
DEFAULT_GREETING = {"min_sparse": 0.6, "min_agreement": 0.12, "max_median_words": 16}
DEFAULT_FRAGMENT = {"min_shared_entities": 1, "max_posts": 12}
# Highest post-to-post cosine. Not the 0.90 face-centroid cut.
DEFAULT_FACE = {"min_post_cosine": 0.1}

# Posts with this few content tokens count as sparse. Not a greeting word list.
_SPARSE_CONTENT_TOKENS = 2
_GREETING_GRID = tuple(
    {"min_sparse": sparse, "min_agreement": agreement, "max_median_words": median}
    for sparse in (0.35, 0.45, 0.6, 1.1)
    for agreement in (0.12, 0.18, 0.28, 1.1)
    for median in (10, 16, 28)
)
_FRAGMENT_GRID = tuple(
    {"min_shared_entities": shared, "max_posts": posts} for shared in (1, 2) for posts in (12, 30, 48)
)
_FACE_GRID = tuple({"min_post_cosine": cut} for cut in (0.1, 0.14, 0.18, 0.24))

# Off until Michael turns it on. No paid call is made while this is false.
WEEKLY_BLIND_SAMPLE_ENABLED = False
WEEKLY_PLANET_PAIRS = 20
WEEKLY_FACE_PAIRS = 10
# One request wrapper, two titles, four posts on each side, and the question.
BLIND_PAIR_INPUT_TOKENS = JEV_REQUEST_OVERHEAD_TOKENS + 2 * JEV_POST_TEXT_TOKENS + 8 * JEV_POST_TEXT_TOKENS + 40
_DAILY_BUDGET_LOW = Decimal("0.25")
_DAILY_BUDGET_HIGH = Decimal("0.30")


def surface_entities(text: str) -> set[str]:
    """All-caps tokens and tokens with a digit. Not stems."""
    found: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+", str(text or "")):
        if any(char.isdigit() for char in token) or (len(token) >= 2 and token.isupper()):
            found.add(token.lower())
    return found


def _median_words(texts: list[str]) -> int | None:
    lengths = sorted(len(text.split()) for text in texts if str(text).strip())
    if not lengths:
        return None
    return lengths[len(lengths) // 2]


def _sparse_fraction(texts: list[str]) -> float:
    kept = [text for text in texts if str(text).strip()]
    if not kept:
        return 0.0
    sparse = sum(1 for text in kept if len(tokenize(text)) <= _SPARSE_CONTENT_TOKENS)
    return sparse / len(kept)


def _pairwise_mean(matrix: np.ndarray) -> float | None:
    count = len(matrix)
    if count < 2:
        return None
    total = 0.0
    pairs = 0
    for left in range(count):
        for right in range(left + 1, count):
            total += float(np.dot(matrix[left], matrix[right]))
            pairs += 1
    if pairs == 0:
        return None
    return total / pairs


def _embed(texts: list[str]) -> np.ndarray | None:
    kept = [text for text in texts if str(text).strip()]
    if len(kept) < 2:
        return None
    try:
        return vectorize(kept[:12])
    except ValueError:
        return None


def within_post_agreement(texts: list[str]) -> float | None:
    """Mean cosine of post pairs inside one planet. Not a centroid."""
    matrix = _embed(texts)
    if matrix is None:
        return None
    return _pairwise_mean(matrix)


def cross_post_agreement(left_texts: list[str], right_texts: list[str]) -> float | None:
    """Highest cosine between one post on the left and one on the right.

    The duplicate score compares the two mean vectors. One agreeing post
    pair can clear this bar while the centroids stay apart, and the
    reverse is also true.
    """
    left = [text for text in left_texts if str(text).strip()][:8]
    right = [text for text in right_texts if str(text).strip()][:8]
    if not left or not right:
        return None
    try:
        matrix = vectorize(left + right)
    except ValueError:
        return None
    best = 0.0
    for left_index in range(len(left)):
        for right_index in range(len(left), len(left) + len(right)):
            best = max(best, float(np.dot(matrix[left_index], matrix[right_index])))
    return best


def _planet_feature(planet: dict) -> dict[str, Any]:
    texts = _texts(planet)
    agreement = within_post_agreement(texts)
    return {
        "name": str(planet.get("name") or ""),
        "posts": _post_count(planet),
        "entities": surface_entities(str(planet.get("name") or "")),
        "agreement": agreement,
        "median_words": _median_words(texts),
        "sparse": _sparse_fraction(texts),
    }


def _greeting_planet(feature: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    sparse = float(feature.get("sparse") or 0.0) + 1e-12 >= float(thresholds["min_sparse"])
    agreement = feature.get("agreement")
    median = feature.get("median_words")
    agreed = (
        agreement is not None
        and median is not None
        and float(agreement) + 1e-12 >= float(thresholds["min_agreement"])
        and int(median) <= int(thresholds["max_median_words"])
    )
    return bool(sparse or agreed)


def _fragment_pair(left: dict[str, Any], right: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    if int(left["posts"]) > int(thresholds["max_posts"]) or int(right["posts"]) > int(thresholds["max_posts"]):
        return False
    shared = left["entities"] & right["entities"]
    return len(shared) >= int(thresholds["min_shared_entities"])


def _index(payload: dict) -> dict[tuple[str, str], dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for scope, planet in _iter_planets(payload):
        found[(scope, _normalize_title(planet.get("name")))] = _planet_feature(planet)
    return found


def _lookup(index: dict[tuple[str, str], dict[str, Any]], section: str, title: str) -> dict[str, Any] | None:
    name = _normalize_title(title)
    if (section, name) in index:
        return index[(section, name)]
    if section in {"global", "catalog"}:
        return index.get(("catalog", name))
    return None


def greeting_planets(payload: dict, thresholds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    chosen = thresholds or DEFAULT_GREETING
    found = []
    for scope, planet in _iter_planets(payload):
        feature = _planet_feature(planet)
        if not _greeting_planet(feature, chosen):
            continue
        found.append(
            {
                "scope": scope,
                "name": feature["name"],
                "post_count": feature["posts"],
            }
        )
    found.sort(key=lambda row: (row["scope"], row["name"].lower()))
    return found


def fragment_pairs(payload: dict, thresholds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    chosen = thresholds or DEFAULT_FRAGMENT
    grouped: dict[str, list[dict[str, Any]]] = {}
    for scope, planet in _iter_planets(payload):
        grouped.setdefault(scope, []).append(_planet_feature(planet))
    found = []
    for scope, planets in grouped.items():
        ordered = sorted(planets, key=lambda row: row["name"].lower())
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if not _fragment_pair(left, right, chosen):
                    continue
                found.append(
                    {
                        "scope": scope,
                        "left_title": left["name"],
                        "right_title": right["name"],
                        "left_posts": left["posts"],
                        "right_posts": right["posts"],
                        "shared_entities": sorted(left["entities"] & right["entities"]),
                    }
                )
    return found


def _face_texts(face: dict) -> list[str]:
    posts = face.get("representative_posts")
    if not isinstance(posts, list):
        return []
    return [str(post.get("text") or "") for post in posts if isinstance(post, dict) and str(post.get("text") or "").strip()]


def face_agreement_pairs(payload: dict, thresholds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    chosen = thresholds or DEFAULT_FACE
    cut = float(chosen["min_post_cosine"])
    found = []
    for scope, planet in _iter_planets(payload):
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        for index, left in enumerate(faces):
            for right in faces[index + 1 :]:
                agreement = cross_post_agreement(_face_texts(left), _face_texts(right))
                if agreement is None or float(agreement) + 1e-12 < cut:
                    continue
                found.append(
                    {
                        "scope": scope,
                        "planet": str(planet.get("name") or ""),
                        "left_title": str(left.get("title") or ""),
                        "right_title": str(right.get("title") or ""),
                        "post_agreement": round(float(agreement), 4),
                    }
                )
    return found


def _pair_key(left: str, right: str) -> tuple[str, str]:
    one, two = _normalize_title(left), _normalize_title(right)
    return (one, two) if one <= two else (two, one)


def measure_kind_counts(
    payload: dict,
    *,
    greeting: dict[str, Any] | None = None,
    fragment: dict[str, Any] | None = None,
    face: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The three counts. The payload is not modified."""
    greeting_cut = greeting or DEFAULT_GREETING
    fragment_cut = fragment or DEFAULT_FRAGMENT
    face_cut = face or DEFAULT_FACE
    greetings = greeting_planets(payload, greeting_cut)
    fragments = fragment_pairs(payload, fragment_cut)
    faces = face_agreement_pairs(payload, face_cut)
    return {
        "report_only": True,
        "changes_edition": False,
        "independent_of_fixes": True,
        "greeting_titles": {
            "count": len(greetings),
            "planets": greetings,
            "thresholds": greeting_cut,
            "rule": (
                "A planet whose posts are sparse, or whose own posts agree and are short. "
                "Not the greeting matcher or a title list."
            ),
        },
        "fragments": {
            "count": len(fragments),
            "pairs": fragments,
            "thresholds": fragment_cut,
            "rule": (
                "Same-section pairs whose titles share an acronym or a digit token, "
                "both at or under the tuned post cap. Not stems."
            ),
        },
        "stance_agreement": {
            "count": len(faces),
            "pairs": faces,
            "thresholds": face_cut,
            "rule": (
                "Within-planet face pairs whose closest posts agree. "
                "Not the face centroid and not the stance fold."
            ),
        },
        "weekly_blind_sample": weekly_blind_sample(payload),
    }


def _yes_no(row: dict[str, str]) -> str | None:
    answer = str(row.get("is_duplicate") or "").strip().lower()
    if answer in {"yes", "no"}:
        return answer
    return None


def _label_rows(
    raw_rows: list[dict[str, str]],
    *,
    level: str,
    spot_ids: set[str],
    bands: dict[str, str],
) -> list[dict[str, str]]:
    labels = []
    for row in raw_rows:
        if str(row.get("level") or "") != level:
            continue
        answer = _yes_no(row)
        if answer is None:
            continue
        pair_id = str(row.get("pair_id") or "")
        band = str(row.get("band") or bands.get(pair_id) or "")
        labels.append(
            {
                "pair_type": "planet" if level == "planet" else "face",
                "left_key": pair_id,
                "right_key": pair_id,
                "left_title": str(row.get("title_a") or ""),
                "right_title": str(row.get("title_b") or ""),
                "duplicate": "1" if answer == "yes" else "0",
                "spot_check": "1" if pair_id in spot_ids else "0",
                "band": band,
                "pair_id": pair_id,
                "section": str(row.get("section") or ""),
                "planet": str(row.get("planet") or ""),
            }
        )
    return labels


def _f1(flagged_yes: int, yes: int, false_flags: int) -> float:
    if yes <= 0:
        return 0.0
    precision_den = flagged_yes + false_flags
    precision = flagged_yes / precision_den if precision_den else 0.0
    recall = flagged_yes / yes
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _score_rows(
    rows: list[dict[str, str]],
    flagged: set[str],
    *,
    positive_ids: set[str] | None,
) -> dict[str, Any]:
    yes = flagged_yes = no = false_flags = 0
    yes_ids: list[str] = []
    false_ids: list[str] = []
    for row in rows:
        pair_id = str(row.get("pair_id") or "")
        is_yes = row.get("duplicate") == "1"
        if is_yes and positive_ids is not None and pair_id not in positive_ids:
            continue
        hit = pair_id in flagged
        if is_yes:
            yes += 1
            if hit:
                flagged_yes += 1
                yes_ids.append(pair_id)
        else:
            no += 1
            if hit:
                false_flags += 1
                false_ids.append(pair_id)
    return {
        "yes": yes,
        "flagged_yes": flagged_yes,
        "no": no,
        "false_flags": false_flags,
        "flagged_yes_ids": yes_ids,
        "false_flag_ids": false_ids,
        "recall": f"{flagged_yes} of {yes}",
    }


def _planet_flags(
    rows: list[dict[str, str]],
    index: dict[tuple[str, str], dict[str, Any]],
    *,
    greeting: dict[str, Any],
    fragment: dict[str, Any],
) -> tuple[set[str], set[str]]:
    greeting_hits: set[str] = set()
    fragment_hits: set[str] = set()
    for row in rows:
        left = _lookup(index, row["section"], row["left_title"])
        right = _lookup(index, row["section"], row["right_title"])
        if left is None or right is None:
            continue
        if _greeting_planet(left, greeting) and _greeting_planet(right, greeting):
            greeting_hits.add(row["pair_id"])
        if _fragment_pair(left, right, fragment):
            fragment_hits.add(row["pair_id"])
    return greeting_hits, fragment_hits


def _face_index(payload: dict) -> dict[tuple[str, str, str], float | None]:
    found: dict[tuple[str, str, str], float | None] = {}
    for _scope, planet in _iter_planets(payload):
        name = _normalize_title(planet.get("name"))
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        for index, left in enumerate(faces):
            for right in faces[index + 1 :]:
                key = (name,) + _pair_key(str(left.get("title") or ""), str(right.get("title") or ""))
                found[key] = cross_post_agreement(_face_texts(left), _face_texts(right))
    return found


def _face_flags(rows: list[dict[str, str]], agreements: dict[tuple[str, str, str], float | None], cut: float) -> set[str]:
    hits: set[str] = set()
    for row in rows:
        key = (_normalize_title(row.get("planet") or ""),) + _pair_key(row["left_title"], row["right_title"])
        agreement = agreements.get(key)
        if agreement is not None and float(agreement) + 1e-12 >= cut:
            hits.add(row["pair_id"])
    return hits


def _pick(grid: Any, score_of) -> dict[str, Any]:
    best_params: dict[str, Any] | None = None
    best_key: tuple | None = None
    for params in grid:
        f1, false_flags, strictness = score_of(params)
        key = (round(f1, 4), -false_flags, strictness)
        if best_key is None or key > best_key:
            best_key = key
            best_params = dict(params)
    assert best_params is not None
    return best_params


def score_labeled_kinds(
    payload: dict,
    planet_rows: list[dict[str, str]],
    face_rows: list[dict[str, str]],
    *,
    greeting_ids: set[str],
    planet_spot_ids: set[str],
    face_spot_ids: set[str],
    bands: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Tune on two-thirds and score recall on the held-out rows.

    ``greeting_ids`` names the greeting label class. The thresholds do
    not read those titles.
    """
    band_map = bands or {}
    planet_labels = _label_rows(planet_rows, level="planet", spot_ids=planet_spot_ids, bands=band_map)
    face_labels = _label_rows(face_rows, level="face_census", spot_ids=face_spot_ids, bands=band_map)
    planet_split = split_labeled_sample(planet_labels)
    face_split = split_labeled_sample(face_labels)
    index = _index(payload)
    face_agreements = _face_index(payload)
    same_story_ids = {
        row["pair_id"]
        for row in planet_labels
        if row["duplicate"] == "1" and row["pair_id"] not in greeting_ids
    }

    def greeting_score(params: dict[str, Any]) -> tuple[float, int, float]:
        hits, _fragments = _planet_flags(planet_split["tune"], index, greeting=params, fragment=DEFAULT_FRAGMENT)
        scored = _score_rows(planet_split["tune"], hits, positive_ids=greeting_ids)
        strict = float(params["min_sparse"]) + float(params["min_agreement"]) - float(params["max_median_words"]) / 100
        return _f1(scored["flagged_yes"], scored["yes"], scored["false_flags"]), scored["false_flags"], strict

    def fragment_score(params: dict[str, Any]) -> tuple[float, int, float]:
        _greetings, hits = _planet_flags(planet_split["tune"], index, greeting=DEFAULT_GREETING, fragment=params)
        scored = _score_rows(planet_split["tune"], hits, positive_ids=same_story_ids)
        strict = float(params["min_shared_entities"]) - float(params["max_posts"]) / 100
        return _f1(scored["flagged_yes"], scored["yes"], scored["false_flags"]), scored["false_flags"], strict

    def face_score(params: dict[str, Any]) -> tuple[float, int, float]:
        hits = _face_flags(face_split["tune"], face_agreements, float(params["min_post_cosine"]))
        scored = _score_rows(face_split["tune"], hits, positive_ids=None)
        return _f1(scored["flagged_yes"], scored["yes"], scored["false_flags"]), scored["false_flags"], float(params["min_post_cosine"])

    greeting_cut = _pick(_GREETING_GRID, greeting_score) if planet_split["tune"] else dict(DEFAULT_GREETING)
    fragment_cut = _pick(_FRAGMENT_GRID, fragment_score) if planet_split["tune"] else dict(DEFAULT_FRAGMENT)
    face_cut = _pick(_FACE_GRID, face_score) if face_split["tune"] else dict(DEFAULT_FACE)

    greeting_hits, fragment_hits = _planet_flags(
        planet_split["evaluation"],
        index,
        greeting=greeting_cut,
        fragment=fragment_cut,
    )
    face_hits = _face_flags(face_split["evaluation"], face_agreements, float(face_cut["min_post_cosine"]))
    counts = measure_kind_counts(payload, greeting=greeting_cut, fragment=fragment_cut, face=face_cut)
    held = {
        "seed": SPLIT_SEED,
        "note": "Tuned on two-thirds of each band. Recall is the held-out third plus spot-check ids.",
    }
    blocks = {
        "greeting_titles": (_score_rows(planet_split["evaluation"], greeting_hits, positive_ids=greeting_ids), greeting_cut, planet_split),
        "fragments": (_score_rows(planet_split["evaluation"], fragment_hits, positive_ids=same_story_ids), fragment_cut, planet_split),
        "stance_agreement": (_score_rows(face_split["evaluation"], face_hits, positive_ids=None), face_cut, face_split),
    }
    labeled = {"seed": SPLIT_SEED, "note": held["note"]}
    for key, (scored, cut, parts) in blocks.items():
        tune_ids = {row["pair_id"] for row in parts["tune"]}
        scored_ids = {row["pair_id"] for row in parts["evaluation"]}
        if tune_ids & scored_ids:
            raise RuntimeError("tune rows leaked into the kind-count holdout")
        labeled[key] = {
            **scored,
            "thresholds": cut,
            "tuned_on": len(parts["tune"]),
            "holdout": len(parts["holdout"]),
            "spot_checks": len(parts["spot_checks"]),
            "seed": SPLIT_SEED,
        }
    counts["labeled"] = labeled
    return counts


def weekly_seed(edition_day: str) -> int:
    """Seed 273 plus the ISO week, so one week draws one sample."""
    parsed = date.fromisoformat(str(edition_day)[:10])
    return SPLIT_SEED * 100 + parsed.isocalendar().week


def blind_label_cost(*, planet_pairs: int = WEEKLY_PLANET_PAIRS, face_pairs: int = WEEKLY_FACE_PAIRS) -> dict[str, Any]:
    """Expected Jev input cost. No call is made."""
    pairs = int(planet_pairs) + int(face_pairs)
    tokens = pairs * BLIND_PAIR_INPUT_TOKENS
    week = jev_cost_usd(tokens)
    day = week / Decimal(7)
    return {
        "enabled": WEEKLY_BLIND_SAMPLE_ENABLED,
        "planet_pairs": int(planet_pairs),
        "face_pairs": int(face_pairs),
        "input_tokens": tokens,
        "tokens_per_pair": BLIND_PAIR_INPUT_TOKENS,
        "price_per_million_input_tokens": str(JEV_USD_PER_MILLION_INPUT_TOKENS),
        "price_as_of": JEV_PRICE_AS_OF,
        "usd_per_week": f"{week.quantize(Decimal('0.000001'))}",
        "usd_per_day": f"{day.quantize(Decimal('0.000001'))}",
        "daily_budget_low": str(_DAILY_BUDGET_LOW),
        "daily_budget_high": str(_DAILY_BUDGET_HIGH),
        "paid_calls": 0,
    }


def _same_section_pairs(payload: dict) -> list[dict[str, str]]:
    grouped: dict[str, list[dict]] = {}
    for scope, planet in _iter_planets(payload):
        grouped.setdefault(scope, []).append(planet)
    pairs = []
    number = 0
    for scope, planets in grouped.items():
        ordered = sorted(planets, key=lambda planet: str(planet.get("name") or "").lower())
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                number += 1
                pairs.append(
                    {
                        "pair_id": f"w{number:04d}",
                        "level": "planet",
                        "section": scope,
                        "title_a": str(left.get("name") or ""),
                        "title_b": str(right.get("name") or ""),
                    }
                )
    return pairs


def _face_pair_sheet(payload: dict) -> list[dict[str, str]]:
    pairs = []
    number = 0
    for scope, planet in _iter_planets(payload):
        faces = [face for face in (planet.get("perspectives") or []) if isinstance(face, dict)]
        ordered = sorted(faces, key=lambda face: str(face.get("title") or "").lower())
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                number += 1
                pairs.append(
                    {
                        "pair_id": f"wf{number:04d}",
                        "level": "face",
                        "section": scope,
                        "planet": str(planet.get("name") or ""),
                        "title_a": str(left.get("title") or ""),
                        "title_b": str(right.get("title") or ""),
                    }
                )
    return pairs


def draw_weekly_sample(payload: dict, *, seed: int) -> dict[str, list[dict[str, str]]]:
    """A blind sheet: titles only. No cosine, band, or count verdict."""
    rng = random.Random(seed)
    planets = _same_section_pairs(payload)
    faces = _face_pair_sheet(payload)
    rng.shuffle(planets)
    rng.shuffle(faces)
    return {
        "planet_pairs": planets[:WEEKLY_PLANET_PAIRS],
        "face_pairs": faces[:WEEKLY_FACE_PAIRS],
    }


def weekly_blind_sample(payload: dict, *, enabled: bool | None = None) -> dict[str, Any]:
    """The weekly second-model sample. Off unless ``enabled`` is true."""
    switched = WEEKLY_BLIND_SAMPLE_ENABLED if enabled is None else bool(enabled)
    edition_day = str(payload.get("last_updated") or payload.get("edition_date") or "2026-01-01")[:10]
    seed = weekly_seed(edition_day)
    cost = blind_label_cost()
    cost["enabled"] = switched
    if not switched:
        return {
            "enabled": False,
            "seed": seed,
            "planet_pairs": [],
            "face_pairs": [],
            "cost": cost,
            "note": "Off. A second model does not label this sample until Michael turns it on.",
        }
    drawn = draw_weekly_sample(payload, seed=seed)
    return {
        "enabled": True,
        "seed": seed,
        "planet_pairs": drawn["planet_pairs"],
        "face_pairs": drawn["face_pairs"],
        "cost": cost,
        "note": "Blind sheet. The count verdicts are not on these rows.",
    }


def _flag_phrase(count: int) -> str:
    return "1 false flag" if int(count) == 1 else f"{int(count)} false flags"


def render_kind_count_lines(counts: dict[str, Any] | None) -> list[str]:
    """Markdown for the nightly summary."""
    if not counts:
        return []
    greeting = counts.get("greeting_titles") or {}
    fragments = counts.get("fragments") or {}
    stance = counts.get("stance_agreement") or {}
    lines = [
        "## Kind counts",
        "",
        "Report only. These counts do not change the edition and do not replace the duplicate score. "
        "Each signal is different from the fix it is watching, so the fix cannot zero the count by being the same rule.",
        "",
        (
            f"- Greeting planets: {greeting.get('count', 0)}. "
            "Per-post sparsity or pairwise agreement inside the planet. "
            "Not the greeting matcher, the daypart gate, or a title list."
        ),
        (
            f"- Fragments: {fragments.get('count', 0)} same-section pairs whose titles share an acronym or a digit token, "
            "both under the tuned post cap. Not stem overlap and not the attach gate's 20-post parent."
        ),
        (
            f"- Face agreement: {stance.get('count', 0)} within-planet pairs. "
            "Highest cosine between one post on each face. Not the face centroid and not the stance fold."
        ),
    ]
    labeled = counts.get("labeled") or {}
    if labeled.get("greeting_titles"):
        lines.extend(
            [
                "",
                f"Held-out recall, seed {labeled.get('seed', SPLIT_SEED)}. "
                f"{labeled.get('note', '')}",
                "",
            ]
        )
        captions = {
            "greeting_titles": "Greeting planets",
            "fragments": "Fragments",
            "stance_agreement": "Face agreement",
        }
        for key, caption in captions.items():
            row = labeled.get(key) or {}
            lines.append(
                f"- {caption}: {row.get('flagged_yes', 0)} of {row.get('yes', 0)} labeled yes, "
                f"{_flag_phrase(row.get('false_flags') or 0)} on {row.get('no', 0)} labeled no."
            )
    sample = counts.get("weekly_blind_sample") or {}
    cost = sample.get("cost") or {}
    if cost:
        lines.extend(
            [
                "",
                (
                    f"Weekly blind sample is {'on' if sample.get('enabled') else 'off'}: "
                    f"{cost.get('planet_pairs', WEEKLY_PLANET_PAIRS)} planet pairs and "
                    f"{cost.get('face_pairs', WEEKLY_FACE_PAIRS)} face pairs, "
                    f"seed {sample.get('seed', SPLIT_SEED)} (273 plus the ISO week). "
                    f"Expected second-model cost at ${cost.get('price_per_million_input_tokens')} "
                    f"per million input tokens ({cost.get('price_as_of')}): "
                    f"${cost.get('usd_per_week')} per week, ${cost.get('usd_per_day')} per day. "
                    f"The daily budget is ${cost.get('daily_budget_low')} to ${cost.get('daily_budget_high')}. "
                    "No paid call is made in this check."
                ),
                "",
            ]
        )
    else:
        lines.append("")
    return lines
