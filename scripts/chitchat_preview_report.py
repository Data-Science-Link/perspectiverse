#!/usr/bin/env python3
"""Offline report: chit-chat removed at ingest and planets dropped by label guard.

Reads a free-ingest-preview artifact (data.json + optional chitchat_removed.json).
No network and no paid calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.assemble import topic_name
from pipeline.chitchat_guard import planet_chitchat_reason


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize chit-chat filtering on a preview artifact")
    parser.add_argument("--data", type=Path, required=True, help="Path to data.json")
    parser.add_argument("--chitchat", type=Path, help="Path to chitchat_removed.json from a new run")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    print(f"Edition total_posts in data.json: {data.get('total_posts')}")
    if args.chitchat and args.chitchat.is_file():
        report = json.loads(args.chitchat.read_text(encoding="utf-8"))
        print(json.dumps(report, indent=2))
    else:
        print("No chitchat_removed.json (artifact from before #208).")
    flagged = []
    for topic in data.get("topics") or []:
        name = str(topic.get("name") or "")
        if planet_chitchat_reason(
            [{"text": name}],
            [w.lower() for w in name.split()],
            name=name,
        ):
            flagged.append(name)
    if flagged:
        print("Published planets that still match chit-chat label heuristics:", flagged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
