#!/usr/bin/env python3
"""Build a JSON summary for the #87 Jetstream readiness workflow."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.costs import SERVICE_DEEPINFRA, SERVICE_JEV, format_usd  # noqa: E402

SECTION_TIMING = re.compile(
    r"Timing: (\d+) section solar system\(s\), (\d+) planet\(s\) in ([0-9.]+)s\."
)
GLOBAL_TIMING = re.compile(r"Timing: (\d+) global planet\(s\) labeled in ([0-9.]+)s\.")
CLUSTER_TIMING = re.compile(
    r"Timing: embedded and clustered (\d+) claims into (\d+) candidate planets in ([0-9.]+)s\."
)
JEV_CACHE = re.compile(
    r"Jev cache hits: (\d+)\. Dedup skips: (\d+)\. Pre-filter skips: (\d+)"
)
DROP_CLAIM = re.compile(r"Dropping ([^:]+): no face kept a shared claim")
STANCE_FAIL = re.compile(r"Stance check failed: (\d+) planet\(s\)")
STANCE_INCOHERENT = re.compile(r"Second side not coherent: (\d+) planet\(s\)")


def _face_quality(payload: dict) -> dict:
    topics = payload.get("topics") or []
    sections = payload.get("sections") or {}
    global_faces = sum(len(t.get("perspectives") or []) for t in topics if isinstance(t, dict))
    section_planets = sum(len(v) for v in sections.values() if isinstance(v, list))
    section_faces = 0
    for planets in sections.values():
        if not isinstance(planets, list):
            continue
        for planet in planets:
            if isinstance(planet, dict):
                section_faces += len(planet.get("perspectives") or [])
    return {
        "global_planets": len(topics),
        "global_faces": global_faces,
        "section_planets": section_planets,
        "section_systems": len(sections),
        "section_faces": section_faces,
    }


def _drops_from_log(log_text: str, posts_by_planet: dict[str, int]) -> dict:
    drops = DROP_CLAIM.findall(log_text)
    vanished_posts = 0
    large_drops: list[dict] = []
    catchalls = {"Companies", "Think", "Other"}
    catchall_hits: list[str] = []
    for name in drops:
        key = name.strip()
        if key.split()[0] in catchalls or key in catchalls:
            catchall_hits.append(key)
        # Log lines do not include post counts; unknown at drop time.
    return {
        "drop_no_shared_claim_count": len(drops),
        "dropped_planet_names": drops,
        "catchall_drops": catchall_hits,
        "posts_vanished_estimate": vanished_posts,
        "dropped_planets_40plus_posts": large_drops,
    }


def _parse_log(log_text: str) -> dict:
    out: dict = {}
    if m := SECTION_TIMING.search(log_text):
        out["section_label_wall_sec"] = float(m.group(3))
        out["section_planets_logged"] = int(m.group(2))
        out["section_systems_logged"] = int(m.group(1))
    if m := GLOBAL_TIMING.search(log_text):
        out["global_label_sec"] = float(m.group(2))
    if m := CLUSTER_TIMING.search(log_text):
        out["cluster_sec"] = float(m.group(3))
        out["claims_clustered"] = int(m.group(1))
    if m := JEV_CACHE.search(log_text):
        out["jev_cache_hits_log"] = int(m.group(1))
        out["jev_dedup_skips_log"] = int(m.group(2))
        out["jev_prefilter_skips_log"] = int(m.group(3))
    stance_fail = STANCE_FAIL.findall(log_text)
    stance_inc = STANCE_INCOHERENT.findall(log_text)
    out["stance_check_failed"] = int(stance_fail[-1]) if stance_fail else 0
    out["stance_check_incoherent"] = int(stance_inc[-1]) if stance_inc else 0
    out.update(_drops_from_log(log_text, {}))
    return out


def _cost_breakdown(payload: dict) -> dict:
    rows = payload.get("rows") or []
    jev = deep = other = Decimal(0)
    for row in rows:
        service = str(row.get("service") or "")
        amount = Decimal(str(row.get("cost_usd") or "0"))
        if service == SERVICE_JEV:
            jev += amount
        elif service == SERVICE_DEEPINFRA:
            deep += amount
        else:
            other += amount
    total = jev + deep + other
    cache_hits = int(payload.get("jev_cache_hits") or 0)
    dedup = int(payload.get("jev_dedup_skips") or 0)
    scored = 0
    for row in rows:
        if row.get("service") == SERVICE_JEV:
            scored = int(row.get("calls") or 0)
    denom = cache_hits + scored
    true_hit_rate = (cache_hits / denom) if denom else 0.0
    return {
        "cost_usd_total": format_usd(total),
        "cost_usd_jev": format_usd(jev),
        "cost_usd_labeling": format_usd(deep),
        "cost_usd_other": format_usd(other),
        "jev_cache_hits": cache_hits,
        "jev_dedup_skips": dedup,
        "jev_calls": scored,
        "jev_true_cache_hit_rate": round(true_hit_rate, 4),
        "jev_break_even_hit_rate": 0.05,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-json", type=Path, required=True)
    parser.add_argument("--cost-run", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--test-day", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.data_json.read_text(encoding="utf-8"))
    cost = json.loads(args.cost_run.read_text(encoding="utf-8"))
    log_text = args.log.read_text(encoding="utf-8", errors="replace")

    summary = {
        "github_run_id": str(args.run_id),
        "test_day": str(args.test_day),
        "total_posts": int(payload.get("total_posts") or 0),
        "face_quality": _face_quality(payload),
        "log_metrics": _parse_log(log_text),
        "cost": _cost_breakdown(cost),
    }
    section_sec = summary["log_metrics"].get("section_label_wall_sec")
    if section_sec is not None:
        summary["section_label_warning"] = section_sec >= 1000
        summary["section_label_over_limit"] = section_sec >= 1200

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
