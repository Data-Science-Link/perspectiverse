"""Calibrate the duplicate threshold on #275's labeled Oct 19 sheet.

Reads ``oct19-pairs-labeled.csv`` and the band shares in
``oct19-sample-design.json``. Planet rows and within-planet face rows are
scored separately. ``planet_leak`` rows are not face pairs. ``unsure`` is not
a yes or a no. Seed 273 holds out one third of each band. Spot-check ids are
kept out of the tune split.

The planet headline is withheld unless every population band with a non-zero
share has a yes/no label. A raw average of the sample is not the headline.

Face rows come from the within-planet census, not the leaked face sample.
A face percentage is withheld when the held-out set is smaller than
``MIN_FACE_HOLDOUT``. The face result is then raw counts. Pooling more days
of face pairs is what makes a real rate.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.kind_counts import render_kind_count_lines, score_labeled_kinds
from pipeline.label_kinds import FACE_SPOT_IDS, GREETING_TITLES, PLANET_SPOT_IDS, greeting_pair_ids
from pipeline.duplicate_rate import (
    SPLIT_SEED,
    agreement_with_labels,
    score_pairs,
    split_labeled_sample,
    tune_threshold,
    _flag_pairs,
    _match_label,
    _normalize_title,
    _pair_identity,
)

# Spot-check ids live in pipeline.label_kinds. Michael's column on the sheet is blank.
# One day of within-planet faces holds out about 9 pairs. A percentage on
# that few rows is not a rate. 30 is the smallest held-out set that gets one.
MIN_FACE_HOLDOUT = 30

KIND_ORDER = ("greeting", "same_story", "paraphrase_face", "other")
KIND_LABEL = {
    "greeting": "Greeting/chit-chat planets (#288)",
    "same_story": "Same-story fragments (#287)",
    "paraphrase_face": "Paraphrase faces (#286)",
    "other": "Other",
}
# A kind the gate almost never flags cannot show whether that fix moved.
_NEAR_ZERO_FACTOR = 5
KIND_TRACKER = {
    "greeting": (
        "The nightly check can't track this fix. "
        "The kind count uses per-post agreement, not a greeting-title list."
    ),
    "same_story": (
        "The nightly check can't track this fix. "
        "The kind count uses shared surface entities, not stems."
    ),
    "paraphrase_face": (
        "The nightly check can't track this fix. "
        "The kind count uses per-post agreement, not the face centroid."
    ),
    "other": (
        "The nightly check can't track this fix. "
        "A $0 count of labeled duplicates outside the three kinds can, once those rows exist."
    ),
}


def percentage_withheld(held_out: int, *, minimum: int = MIN_FACE_HOLDOUT) -> bool:
    """True when a face held-out set is too small for a percentage."""
    return int(held_out) < int(minimum)


def recall_is_near_zero(flagged: int, total: int) -> bool:
    """True when the gate flags too few of a kind to track a fix."""
    if int(total) <= 0:
        return False
    return int(flagged) * _NEAR_ZERO_FACTOR < int(total)


def duplicate_kind(row: dict[str, str]) -> str | None:
    """Kind of one model-labeled duplicate.

    Planet yes/no rows use ``level`` ``planet``. Face yes/no rows use
    ``level`` ``face_census``. A ``planet_leak`` row is not tagged. Unsure
    and no are not duplicates.
    """
    answer = str(row.get("is_duplicate") or "").strip().lower()
    if answer != "yes":
        return None
    level = str(row.get("level") or "")
    if level == "face_census":
        return "paraphrase_face"
    if level != "planet":
        return None
    left = _normalize_title(str(row.get("title_a") or row.get("left_title") or ""))
    right = _normalize_title(str(row.get("title_b") or row.get("right_title") or ""))
    if left in GREETING_TITLES and right in GREETING_TITLES:
        return "greeting"
    if left and right:
        return "same_story"
    return "other"


def _index_scored(scored: list[dict]) -> dict:
    by_title: dict = {}
    for pair in scored:
        key = (
            pair["pair_type"],
            *_pair_title_key(pair["left_title"], pair["right_title"]),
        )
        current = by_title.get(key)
        if current is None:
            by_title[key] = pair
        elif isinstance(current, list):
            current.append(pair)
        else:
            by_title[key] = [current, pair]
    return by_title


def _pair_title_key(left: str, right: str) -> tuple[str, str]:
    return _pair_identity(_normalize_title(left), _normalize_title(right))


def kind_recall(rows: list[dict[str, str]], scored: list[dict]) -> dict:
    """How many labeled duplicates the nightly gate flags, by kind.

    The nightly gate is the default one: ``titles_alike`` or centroid cosine
    at least 0.90. Counts are raw. A kind near zero names a $0 count that
    could move when that fix lands.
    """
    by_title = _index_scored(scored)
    buckets = {
        kind: {"kind": kind, "label": KIND_LABEL[kind], "total": 0, "flagged": 0, "unmatched": 0, "pairs": []}
        for kind in KIND_ORDER
    }
    for row in rows:
        kind = duplicate_kind(row)
        if kind is None:
            continue
        pair_type = "face" if kind == "paraphrase_face" else "planet"
        label = {
            "pair_type": pair_type,
            "left_key": "",
            "right_key": "",
            "left_title": str(row.get("title_a") or row.get("left_title") or ""),
            "right_title": str(row.get("title_b") or row.get("right_title") or ""),
        }
        found = _match_label(label, {}, by_title)
        flagged = bool(found and found.get("near_duplicate"))
        bucket = buckets[kind]
        bucket["total"] += 1
        bucket["flagged"] += int(flagged)
        bucket["unmatched"] += int(found is None)
        bucket["pairs"].append(
            {
                "pair_id": str(row.get("pair_id") or ""),
                "left_title": label["left_title"],
                "right_title": label["right_title"],
                "flagged": flagged,
                "titles_alike": None if found is None else bool(found.get("titles_alike")),
                "centroid_cosine": None if found is None else found.get("centroid_cosine"),
            }
        )
    kinds = []
    for kind in KIND_ORDER:
        bucket = buckets[kind]
        near = recall_is_near_zero(bucket["flagged"], bucket["total"])
        bucket["near_zero"] = near
        bucket["tracker"] = KIND_TRACKER[kind] if near else None
        kinds.append(bucket)
    return {
        "gate": "titles_alike or centroid cosine >= 0.90",
        "kinds": kinds,
    }


def render_kind_recall(report: dict) -> list[str]:
    lines = [
        "## Recall by duplicate kind",
        "",
        "Every model-labeled duplicate on the Oct 19 planet sheet and the face census. "
        "The nightly check flags a pair when titles look alike or the TF-IDF centroid "
        "cosine is at least 0.90. Counts are raw. `planet_leak` rows are not included.",
        "",
    ]
    for kind in report["kinds"]:
        lines.append(
            f"- {kind['label']}: {kind['flagged']} of {kind['total']}"
        )
        flagged = [pair for pair in kind["pairs"] if pair["flagged"]]
        if flagged and kind["flagged"] < kind["total"]:
            named = ", ".join(f"{pair['left_title']} | {pair['right_title']}" for pair in flagged)
            lines.append(f"  Flagged: {named}.")
        if kind.get("tracker"):
            lines.append(f"  {kind['tracker']}")
    lines.append("")
    return lines


def _shares(design: dict, side: str) -> dict[str, float]:
    shares = {}
    for band in design[side]["headline"]["bands"]:
        shares[str(band["band"])] = float(band["share"])
    return shares


def _band_by_id(design: dict) -> dict[str, str]:
    found = {}
    for side in ("planets", "faces"):
        for row in design[side]["sample"]:
            found[str(row["pair_id"])] = str(row["band"])
    return found


def calibration_rows(labeled: list[dict[str, str]], design: dict, *, level: str) -> dict:
    """Yes/no rows for one level, with #275's population band share attached."""
    side = "planets" if level == "planet" else "faces"
    shares = _shares(design, side)
    bands = _band_by_id(design)
    kept = []
    unsure = 0
    excluded_leak = 0
    missing_band = 0
    for row in labeled:
        row_level = str(row.get("level") or "")
        if level == "planet" and row_level != "planet":
            continue
        if level == "face":
            if row_level == "planet_leak":
                excluded_leak += 1
                continue
            if row_level != "face_census":
                continue
        answer = str(row.get("is_duplicate") or "").strip().lower()
        if answer == "unsure":
            unsure += 1
            continue
        if answer not in {"yes", "no"}:
            continue
        pair_id = str(row.get("pair_id") or "")
        band = str(row.get("band") or "").strip() or bands.get(pair_id)
        if not band:
            missing_band += 1
            continue
        spot_ids = PLANET_SPOT_IDS if level == "planet" else FACE_SPOT_IDS
        kept.append(
            {
                "pair_type": "planet" if level == "planet" else "face",
                "left_key": "",
                "right_key": "",
                "left_title": str(row.get("title_a") or ""),
                "right_title": str(row.get("title_b") or ""),
                "duplicate": "1" if answer == "yes" else "0",
                "spot_check": "1" if pair_id in spot_ids else "0",
                "band": band,
                "band_share": str(shares.get(band, "")),
                "pair_id": pair_id,
            }
        )
    covered = {row["band"] for row in kept}
    missing_population = sorted(band for band, share in shares.items() if share > 0 and band not in covered)
    return {
        "rows": kept,
        "unsure": unsure,
        "excluded_leak": excluded_leak,
        "missing_band": missing_band,
        "missing_population_bands": missing_population,
        "shares": shares,
    }


def _calibrate_level(scored: list[dict], prepared: dict, *, counts_only: bool = False) -> dict:
    labels = prepared["rows"]
    parts = split_labeled_sample(labels)
    tuned = tune_threshold(scored, parts["tune"])
    flagged = _flag_pairs(
        scored,
        title_min=float(tuned["title_min"]),
        centroid_min=float(tuned["centroid_min"]),
        use_title_min=True,
    )
    measured = agreement_with_labels(flagged, parts["evaluation"])
    held_out = len(parts["evaluation"])
    agree = int(measured["true_positive"]) + int(measured["true_negative"])
    small = counts_only and percentage_withheld(held_out)
    complete = not prepared["missing_population_bands"]
    weighted = bool(complete and measured["weighted"] and not small)
    if small:
        withheld = (
            f"Held-out set is {held_out}, under {MIN_FACE_HOLDOUT}. "
            "No face percentage. Pooling more days of face pairs is the path to a real rate."
        )
    elif not complete:
        withheld = "Population bands with no yes/no label: " + ", ".join(prepared["missing_population_bands"])
    elif not measured["weighted"]:
        withheld = "Not every scored band has a real share."
    else:
        withheld = None
    headline_precision = measured["precision"] if weighted else None
    headline_recall = measured["recall"] if weighted else None
    return {
        "tuned_threshold": {
            "title_min": tuned["title_min"],
            "centroid_min": tuned["centroid_min"],
            "tune_f1": tuned["f1"],
        },
        "split": {
            "seed": SPLIT_SEED,
            "tuned_on": len(parts["tune"]),
            "holdout": len(parts["holdout"]),
            "spot_checks": len(parts["spot_checks"]),
            "tune_ids": [row["pair_id"] for row in parts["tune"]],
            "holdout_ids": [row["pair_id"] for row in parts["holdout"]],
            "spot_ids": [row["pair_id"] for row in parts["spot_checks"]],
        },
        "headline": {
            "weighted": weighted,
            "precision": headline_precision,
            "recall": headline_recall,
            "counts_only": bool(counts_only and small),
            "agree": agree,
            "judged": int(measured["matched"]),
            "held_out": held_out,
            "withheld_because": withheld,
        },
        "bands": measured["bands"],
        "matched": measured["matched"],
        "unmatched": measured["unmatched"],
        "sample_mix_not_headline": measured["sample_mix"],
        "labels": {
            "yes_no_rows": len(labels),
            "unsure_excluded": prepared["unsure"],
            "planet_leak_excluded": prepared["excluded_leak"],
            "missing_population_bands": prepared["missing_population_bands"],
            "band_shares": prepared["shares"],
        },
    }


def render_level(name: str, result: dict) -> list[str]:
    tuned = result["tuned_threshold"]
    headline = result["headline"]
    lines = [
        f"## {name}",
        "",
        f"Tuned threshold: title similarity >= {tuned['title_min']}, "
        f"centroid cosine >= {tuned['centroid_min']} "
        f"(tune F1 {tuned['tune_f1']}, seed {result['split']['seed']}).",
        "",
    ]
    if headline.get("counts_only"):
        lines.append(
            f"Held-out agreement: {headline['agree']} of {headline['judged']} agree."
        )
        lines.append(str(headline["withheld_because"]))
    else:
        lines.append(
            "A band with no predicted positive in the held-out rows has no precision, "
            "so it is left out of the precision average. Its share is still listed below."
        )
        lines.append("")
        if headline["weighted"]:
            lines.append(
                f"Band-weighted held-out agreement: precision {headline['precision']}, "
                f"recall {headline['recall']}."
            )
        else:
            lines.append(
                "Band-weighted held-out agreement withheld. " + str(headline["withheld_because"])
            )
    lines.extend(["", "Per band:", ""])
    for band in result["bands"]:
        share = band.get("share")
        share_text = "share not recorded" if share is None else f"real share {float(share):.1%}"
        if headline.get("counts_only"):
            agreed = int(band.get("true_positive") or 0) + int(band.get("true_negative") or 0)
            lines.append(
                f"- {band['band']} ({share_text}): {agreed} of {band['matched']} agree"
            )
        else:
            lines.append(
                f"- {band['band']} ({share_text}): precision {band['precision']}, "
                f"recall {band['recall']}, matched {band['matched']}"
            )
    split = result["split"]
    lines.extend(
        [
            "",
            f"Tuned on {split['tuned_on']} rows, held out {split['holdout']}, "
            f"spot-check ids in the agreement set {split['spot_checks']}. "
            f"Matched {result['matched']}, unmatched {result['unmatched']}.",
            "",
        ]
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate on the #275 Oct 19 labeled sheet")
    parser.add_argument("--data", default="public/data.json")
    parser.add_argument("--labeled", required=True)
    parser.add_argument("--faces", required=True, help="Within-planet face census CSV")
    parser.add_argument("--design", required=True)
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    with Path(args.labeled).open(newline="", encoding="utf-8") as handle:
        labeled = list(csv.DictReader(handle))
    with Path(args.faces).open(newline="", encoding="utf-8") as handle:
        faces = list(csv.DictReader(handle))
    design = json.loads(Path(args.design).read_text(encoding="utf-8"))
    scored = score_pairs(payload)
    report = {
        "source_commit": args.source_commit,
        "labeled_csv": str(args.labeled),
        "design_json": str(args.design),
        "edition": payload.get("last_updated"),
        "label_source": (
            "Planet yes/no labels from cursor/root-cause-duplicates-3988 "
            "docs/evidence/275/oct19-pairs-labeled.csv. "
            "Face yes/no labels from docs/evidence/275/oct19-face-census.csv, "
            "the within-planet census. The 60-row face sample is not used: 51 of those "
            "rows were planet pairs. The labeler is composer-2.5, not Michael. "
            "spot-check-20.md has an empty Michael column, so those ids use the composer "
            "label and stay out of the tune split. Unsure is excluded. "
            "Planet bands and shares come from oct19-sample-design.json. "
            f"A face percentage is withheld below {MIN_FACE_HOLDOUT} held-out pairs."
        ),
        "face_census": str(args.faces),
        "planet": _calibrate_level(
            [row for row in scored if row["pair_type"] == "planet"],
            calibration_rows(labeled, design, level="planet"),
        ),
        "face": _calibrate_level(
            [row for row in scored if row["pair_type"] == "face"],
            calibration_rows(faces, design, level="face"),
            counts_only=True,
        ),
        "kind_recall": kind_recall(list(labeled) + list(faces), scored),
        "kind_counts": score_labeled_kinds(
            payload,
            labeled,
            faces,
            greeting_ids=greeting_pair_ids(labeled),
            planet_spot_ids=set(PLANET_SPOT_IDS),
            face_spot_ids=set(FACE_SPOT_IDS),
            bands=_band_by_id(design),
        ),
    }
    lines = [
        "# Oct 19 duplicate-threshold calibration",
        "",
        report["label_source"],
        "",
        f"Source commit: {args.source_commit or 'not recorded'}.",
        f"Edition date: {report['edition']}.",
        "",
    ]
    lines.extend(render_level("Planets", report["planet"]))
    lines.extend(render_level("Faces", report["face"]))
    lines.extend(render_kind_recall(report["kind_recall"]))
    lines.extend(render_kind_count_lines(report["kind_counts"]))
    rendered = "\n".join(lines)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_path:
        Path(args.markdown_path).write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
