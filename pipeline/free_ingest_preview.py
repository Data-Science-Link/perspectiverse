"""Summary artifact for a free-ingest preview. No network and no paid calls.

The workflow uploads ``data.json`` plus ``summary.json`` as the
``free-ingest-preview`` artifact. It does not upload the corpus or publish
the edition.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path

from pipeline.costs import SERVICE_JEV, count_published_planets, format_usd

SUMMARY_NAME = "summary.json"
DATA_NAME = "data.json"


def posts_per_utc_day(db_path: Path) -> dict[str, int]:
    """Count stored posts by the UTC day in ``created_at``. Missing dates are ``unknown``."""
    if not db_path.is_file():
        return {}
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT created_at FROM posts").fetchall()
    except sqlite3.Error:
        return {}
    finally:
        connection.close()
    counts: dict[str, int] = {}
    for (created,) in rows:
        text = str(created or "")
        day = text[:10]
        if len(day) != 10 or day[4] != "-" or day[7] != "-":
            day = "unknown"
        counts[day] = counts.get(day, 0) + 1
    return dict(sorted(counts.items()))


def jev_planet_label_totals(cost: dict) -> tuple[int, Decimal]:
    """Calls and dollars on ``typesafe-jev`` rows. A free-ingest run's Jev calls are planet labels."""
    calls = 0
    usd = Decimal("0")
    for row in cost.get("rows") or []:
        if not isinstance(row, dict) or str(row.get("service") or "") != SERVICE_JEV:
            continue
        calls += int(row.get("calls") or 0)
        usd += Decimal(str(row.get("cost_usd") or "0"))
    return calls, usd


def build_summary(
    *,
    data: dict,
    posts_by_day: dict[str, int],
    cost: dict | None,
    stages: dict | None,
) -> dict:
    """Fields the preview artifact reports. Dollars are the ledger's Jev total."""
    meter_calls, usd = jev_planet_label_totals(cost or {})
    stage_calls = None if not isinstance(stages, dict) else stages.get("jev_planet_label_calls")
    calls = int(stage_calls) if stage_calls is not None else meter_calls
    wall = {}
    if isinstance(stages, dict) and isinstance(stages.get("wall_seconds"), dict):
        for name, seconds in stages["wall_seconds"].items():
            wall[str(name)] = round(float(seconds), 3)
    summary = {
        "posts_per_utc_day": dict(posts_by_day),
        "post_count": int(sum(posts_by_day.values())),
        "edition_posts": int(data.get("total_posts") or 0),
        "planet_count": count_published_planets(data),
        "jev_planet_label_calls": calls,
        "jev_planet_label_usd": format_usd(usd),
        "wall_seconds": wall,
    }
    if isinstance(stages, dict):
        if isinstance(stages.get("edition_pipeline"), dict):
            summary["edition_pipeline"] = stages["edition_pipeline"]
            pipeline = stages["edition_pipeline"]
            reason = pipeline.get("edition_fill_stop_reason")
            if reason:
                summary["edition_fill_stop_reason"] = reason
            if "edition_posts_for_clustering" in pipeline:
                summary["edition_quality_count"] = int(pipeline["edition_posts_for_clustering"])
        if isinstance(stages.get("chitchat_ingest"), dict):
            summary["chitchat_ingest"] = stages["chitchat_ingest"]
    return summary


def write_stage_timings(
    path: Path,
    *,
    wall_seconds: dict[str, float],
    jev_planet_label_calls: int,
    edition_pipeline: dict | None = None,
    chitchat_ingest: dict | None = None,
) -> None:
    """Persist stage timings next to the corpus. Gitignored under ``pipeline/data/``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wall_seconds": {name: round(float(seconds), 3) for name, seconds in wall_seconds.items()},
        "jev_planet_label_calls": int(jev_planet_label_calls),
    }
    if edition_pipeline:
        payload["edition_pipeline"] = edition_pipeline
    if chitchat_ingest:
        payload["chitchat_ingest"] = chitchat_ingest
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def write_preview(
    out_dir: Path,
    *,
    data_path: Path,
    db_path: Path,
    cost_path: Path,
    stages_path: Path,
) -> Path:
    """Copy the trial edition and write ``summary.json``. Raises if ``data.json`` is missing."""
    if not data_path.is_file():
        raise FileNotFoundError(f"No trial data.json at {data_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(data_path, out_dir / DATA_NAME)
    chitchat_path = db_path.parent / "chitchat_removed.json"
    if chitchat_path.is_file():
        shutil.copyfile(chitchat_path, out_dir / "chitchat_removed.json")
    summary = build_summary(
        data=_read_json(data_path),
        posts_by_day=posts_per_utc_day(db_path),
        cost=_read_json(cost_path),
        stages=_read_json(stages_path),
    )
    destination = out_dir / SUMMARY_NAME
    destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        "Free-ingest preview: "
        f"{summary['post_count']} posts, {summary['planet_count']} planets, "
        f"{summary['jev_planet_label_calls']} Jev planet-label calls, "
        f"${summary['jev_planet_label_usd']}."
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the free-ingest preview artifact files")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cost", type=Path, required=True)
    parser.add_argument("--stages", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        write_preview(
            args.out,
            data_path=args.data,
            db_path=args.db,
            cost_path=args.cost,
            stages_path=args.stages,
        )
    except FileNotFoundError as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
