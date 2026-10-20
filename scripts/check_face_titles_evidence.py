#!/usr/bin/env python3
"""Print duplicate-title and unsupported-face counts before/after offline repair."""

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

from pipeline.face_titles import (
    count_duplicate_title_faces,
    face_title_changes,
    repair_payload_face_titles,
)
from scripts.baseline_metrics import posts_unsupported_title

LIVE_URL = "https://data-science-link.github.io/perspectiverse/data.json"
FIXTURE = ROOT / "tests" / "fixtures" / "face_titles_snapshot.json"


def _load_snapshot() -> dict:
    raw = subprocess.check_output(
        ["git", "show", "origin/data-snapshot:public/data.json"],
        text=True,
    )
    return json.loads(raw)


def _report(label: str, data: dict) -> None:
    before_dup = count_duplicate_title_faces(data)
    before_unsup = posts_unsupported_title(data)
    payload = copy.deepcopy(data)
    stats = repair_payload_face_titles(payload)
    after_dup = count_duplicate_title_faces(payload)
    after_unsup = posts_unsupported_title(payload)
    print(f"{label} duplicate_title_faces: {before_dup} -> {after_dup}")
    print(
        f"{label} unsupported_title_faces (baseline_metrics): "
        f"{before_unsup[1]} -> {after_unsup[1]} (posts {before_unsup[0]} -> {after_unsup[0]})"
    )
    print(f"{label} unsupported_faces_reported: {len(stats.get('unsupported_faces') or [])}")
    print(f"{label} merged_exact_duplicates: {stats.get('merged')}")
    title_changes = face_title_changes(data, payload)
    if title_changes:
        print(f"{label} face_title_changes:")
        for row in title_changes:
            print(f"  - {row['planet']}: {row['before']} -> {row['after']}")
    else:
        print(f"{label} face_title_changes: (none)")


def main() -> int:
    if FIXTURE.is_file():
        _report("fixture", json.loads(FIXTURE.read_text(encoding="utf-8")))
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
