#!/usr/bin/env python3
"""Print duplicate-title counts before/after offline repair.

Reads a local data.json. Does not fetch the live site and does not call a model.
Pass a path, or omit it to use tests/fixtures/face_titles_snapshot.json.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.face_titles import (
    count_duplicate_title_faces,
    face_title_changes,
    iter_all_planets,
    repair_payload_face_titles,
)

FIXTURE = ROOT / "tests" / "fixtures" / "face_titles_snapshot.json"


def _report(label: str, data: dict) -> int:
    planets = list(iter_all_planets(data))
    print(f"{label} planets: {len(planets)}")
    if not planets:
        print(f"{label}: no planets in this file", file=sys.stderr)
        return 1
    before_dup = count_duplicate_title_faces(data)
    payload = copy.deepcopy(data)
    stats = repair_payload_face_titles(payload)
    after_dup = count_duplicate_title_faces(payload)
    print(f"{label} duplicate_title_faces: {before_dup} -> {after_dup}")
    print(f"{label} merged_exact_duplicates: {stats.get('merged')}")
    print(f"{label} unsupported_faces_reported: {len(stats.get('unsupported_faces') or [])}")
    title_changes = face_title_changes(data, payload)
    if title_changes:
        print(f"{label} face_title_changes:")
        for row in title_changes:
            print(f"  - {row['planet']}: {row['before']} -> {row['after']}")
    else:
        print(f"{label} face_title_changes: (none)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    paths = [Path(arg) for arg in args if not arg.startswith("-")]
    if not paths:
        paths = [FIXTURE]
    status = 0
    for path in paths:
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            status = 1
            continue
        status = max(status, _report(path.name, json.loads(path.read_text(encoding="utf-8"))))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
