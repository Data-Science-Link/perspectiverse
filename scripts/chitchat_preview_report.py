#!/usr/bin/env python3
"""Offline report: chit-chat removed at ingest and planets dropped by content.

Reads a free-ingest-preview artifact (data.json + optional chitchat_removed.json).
The planet decision uses representative posts. The planet title is not an input.
No network and no paid calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.chitchat_guard import planet_chitchat_reason, pleasantry_share


def _members(topic: dict) -> list[dict]:
    return [
        {"text": str(post.get("text") or "")}
        for face in topic.get("perspectives") or []
        for post in face.get("representative_posts") or []
        if str(post.get("text") or "").strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize chit-chat filtering on a preview artifact")
    parser.add_argument("--data", type=Path, required=True, help="Path to data.json")
    parser.add_argument("--chitchat", type=Path, help="Path to chitchat_removed.json from a new run")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    print(f"Edition total_posts in data.json: {data.get('total_posts')}")
    print("Representative posts only. Full post texts are not in the preview artifact.")
    if args.chitchat and args.chitchat.is_file():
        report = json.loads(args.chitchat.read_text(encoding="utf-8"))
        print(json.dumps(report, indent=2))
    else:
        print("No chitchat_removed.json (artifact from before #208).")
    flagged = []
    for scope, topics in (("global", data.get("topics") or []),):
        del scope
        for topic in topics:
            name = str(topic.get("name") or "")
            members = _members(topic)
            if not members:
                continue
            reason = planet_chitchat_reason(members, [], name=None)
            if reason:
                flagged.append(f"{name} ({pleasantry_share(members):.0%} of representatives): {reason}")
    if flagged:
        print("Global planets whose representatives are chit-chat:")
        for line in flagged:
            print(f"  {line}")
    else:
        print("No global planet is dropped from its representative posts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
