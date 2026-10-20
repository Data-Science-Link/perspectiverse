"""Offline replay of the local stance gate on a published data.json.

No model call. Reads a snapshot, runs ``gate_published_perspectives`` on every
planet, and prints planets whose face count or titles change, then the planets
that still have two or more faces.

This replay sees representative posts only, plus each face's post count. The
live gate (``apply_local_stance_gate``) uses the full face membership, so a
planet can fold or stay on different evidence in the two paths.

The Oct 19 snapshot this replay was checked against is edition commit
44a537b (``44a537b834acb2ac421f1ebfb33b6bd68ef44744``, "Update discourse
snapshot and cost ledger").

    python scripts/replay_stance_gate.py path/to/data.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.stance import gate_published_perspectives

# Pinned edition for the Oct 19 discourse snapshot. Representative posts only.
EDITION_COMMIT = "44a537b"


def iter_planets(data: dict):
    for planet in data.get("topics") or []:
        yield "global", planet
    for scope, planets in (data.get("sections") or {}).items():
        for planet in planets:
            yield str(scope), planet


def face_titles(faces: list[dict]) -> list[str]:
    return [str(face.get("title") or "") for face in faces]


def replay(data: dict) -> dict:
    """Return changed planets and the planets that still have two or more faces."""
    changed = []
    still_multi = []
    for scope, planet in iter_planets(data):
        before = list(planet.get("perspectives") or [])
        if not before:
            continue
        after = gate_published_perspectives(before)
        before_titles = face_titles(before)
        after_titles = face_titles(after)
        row = {
            "scope": scope,
            "planet": str(planet.get("name") or ""),
            "before_count": len(before),
            "after_count": len(after),
            "before_titles": before_titles,
            "after_titles": after_titles,
        }
        if before_titles != after_titles or len(before) != len(after):
            changed.append(row)
        if len(after) >= 2:
            still_multi.append(row)
    return {"changed": changed, "still_multi": still_multi}


def _format_titles(titles: list[str]) -> str:
    return "; ".join(titles)


def render(report: dict) -> str:
    lines = [
        "Replay uses representative posts only. Live apply_local_stance_gate uses full membership.",
        f"Edition commit pinned for the Oct 19 snapshot: {EDITION_COMMIT}.",
        "",
        "| Scope | Planet | Faces before | Titles before | Faces after | Titles after |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in report["changed"]:
        lines.append(
            "| {scope} | {planet} | {before_count} | {before} | {after_count} | {after} |".format(
                scope=row["scope"],
                planet=row["planet"],
                before_count=row["before_count"],
                before=_format_titles(row["before_titles"]),
                after_count=row["after_count"],
                after=_format_titles(row["after_titles"]),
            )
        )
    if len(report["changed"]) == 0:
        lines.append("| | none | | | | |")
    lines.append("")
    lines.append("Planets that still have two or more faces:")
    lines.append("")
    lines.append("| Scope | Planet | Faces | Titles |")
    lines.append("| --- | --- | ---: | --- |")
    for row in report["still_multi"]:
        lines.append(
            "| {scope} | {planet} | {count} | {titles} |".format(
                scope=row["scope"],
                planet=row["planet"],
                count=row["after_count"],
                titles=_format_titles(row["after_titles"]),
            )
        )
    if not report["still_multi"]:
        lines.append("| | none | | |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/replay_stance_gate.py path/to/data.json", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[1]).read_text())
    print(render(replay(data)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
