#!/usr/bin/env python3
"""Print duplicate/unsupported face-title counts before and after offline repair."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.face_titles import count_duplicate_title_faces, repair_payload_face_titles
from scripts.baseline_metrics import posts_unsupported_title

LIVE_URL = "https://data-science-link.github.io/perspectiverse/data.json"


def _load_snapshot() -> dict:
    raw = subprocess.check_output(
        ["git", "show", "origin/data-snapshot:public/data.json"],
        text=True,
    )
    return json.loads(raw)


def _report(label: str, data: dict) -> dict:
    before_dup = count_duplicate_title_faces(data)
    before_unsup = posts_unsupported_title(data)
    payload = copy.deepcopy(data)
    stats = repair_payload_face_titles(payload)
    after_dup = count_duplicate_title_faces(payload)
    after_unsup = posts_unsupported_title(payload)
    print(f"{label} duplicate_title_faces: {before_dup} -> {after_dup}")
    print(
        f"{label} unsupported_title_faces: {before_unsup[1]} -> {after_unsup[1]} "
        f"(posts {before_unsup[0]} -> {after_unsup[0]})"
    )
    print(f"{label} repair_stats: {stats}")
    print(f"{label} renames ({len(stats['renames'])}):")
    for row in stats["renames"]:
        print(f"  {row['planet']}: {row['old']} -> {row['new']} ({row['reason']})")
    print(f"{label} still_unsupported ({len(stats['still_unsupported'])}):")
    for row in stats["still_unsupported"]:
        print(f"  {row['planet']}: {row['title']}")
    return stats


def main() -> int:
    with urllib.request.urlopen(LIVE_URL) as response:
        live = json.loads(response.read().decode())
    _report("live", live)
    try:
        _report("data-snapshot", _load_snapshot())
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"data-snapshot: skipped ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
