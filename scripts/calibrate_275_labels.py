"""Calibrate the duplicate threshold on #275's labeled Oct 19 sheet.

Reads ``oct19-pairs-labeled.csv`` and the band shares in
``oct19-sample-design.json``. Planet rows and within-planet face rows are
scored separately. ``planet_leak`` rows are not face pairs. ``unsure`` is not
a yes or a no. Seed 273 holds out one third of each band. Spot-check ids are
kept out of the tune split.

The headline is withheld unless every population band with a non-zero share
has a yes/no label. A raw average of the sample is not the headline.
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

from pipeline.duplicate_rate import (
    SPLIT_SEED,
    agreement_with_labels,
    score_pairs,
    split_labeled_sample,
    tune_threshold,
    _flag_pairs,
)

# Rebuilt spot-check sheet (spot-check-20.md). Michael's column is blank there.
PLANET_SPOT_IDS = frozenset(
    {"p006", "p060", "p002", "p003", "p004", "p001", "p007", "p009", "p011", "p015"}
)


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
            if row_level != "face":
                continue
        answer = str(row.get("is_duplicate") or "").strip().lower()
        if answer == "unsure":
            unsure += 1
            continue
        if answer not in {"yes", "no"}:
            continue
        band = bands.get(str(row.get("pair_id") or ""))
        if not band:
            missing_band += 1
            continue
        pair_id = str(row.get("pair_id") or "")
        kept.append(
            {
                "pair_type": "planet" if level == "planet" else "face",
                "left_key": "",
                "right_key": "",
                "left_title": str(row.get("title_a") or ""),
                "right_title": str(row.get("title_b") or ""),
                "duplicate": "1" if answer == "yes" else "0",
                "spot_check": "1" if pair_id in PLANET_SPOT_IDS else "0",
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


def _calibrate_level(scored: list[dict], prepared: dict) -> dict:
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
    complete = not prepared["missing_population_bands"]
    headline_precision = measured["precision"] if complete and measured["weighted"] else None
    headline_recall = measured["recall"] if complete and measured["weighted"] else None
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
            "weighted": bool(complete and measured["weighted"]),
            "precision": headline_precision,
            "recall": headline_recall,
            "withheld_because": (
                None
                if complete and measured["weighted"]
                else (
                    "Population bands with no yes/no label: " + ", ".join(prepared["missing_population_bands"])
                    if prepared["missing_population_bands"]
                    else "Not every scored band has a real share."
                )
            ),
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
        "A band with no predicted positive in the held-out rows has no precision, "
        "so it is left out of the precision average. Its share is still listed below.",
        "",
    ]
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
    parser.add_argument("--design", required=True)
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    with Path(args.labeled).open(newline="", encoding="utf-8") as handle:
        labeled = list(csv.DictReader(handle))
    design = json.loads(Path(args.design).read_text(encoding="utf-8"))
    scored = score_pairs(payload)
    report = {
        "source_commit": args.source_commit,
        "labeled_csv": str(args.labeled),
        "design_json": str(args.design),
        "edition": payload.get("last_updated"),
        "label_source": (
            "Yes/no labels from cursor/root-cause-duplicates-3988 "
            "docs/evidence/275/oct19-pairs-labeled.csv at 2082bf1. "
            "The perspective-definition pass is b62ec0d; planet yes/no did not change after that, "
            "and 2c1c384 only reclassified 51 leaked face rows as planet_leak. "
            "Those 51 are not in the face score. The labeler is composer-2.5, not Michael. "
            "spot-check-20.md has an empty Michael column, so the spot-check ids use the "
            "composer label and are kept out of the tune split. Unsure is excluded. "
            "Bands and population shares come from oct19-sample-design.json."
        ),
        "planet": _calibrate_level(
            [row for row in scored if row["pair_type"] == "planet"],
            calibration_rows(labeled, design, level="planet"),
        ),
        "face": _calibrate_level(
            [row for row in scored if row["pair_type"] == "face"],
            calibration_rows(labeled, design, level="face"),
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
    rendered = "\n".join(lines)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_path:
        Path(args.markdown_path).write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
