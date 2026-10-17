#!/usr/bin/env python3
"""Replay the planet guard on saved preview planets.

No network and no paid calls. Artifacts store representative posts, not every
member. The share is that representative mix. A planet drops at 55 percent.
The title is ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.chitchat_guard import planet_chitchat_reason, planet_content_share


def representative_texts(topic: dict) -> list[str]:
    texts: list[str] = []
    for face in topic.get("perspectives") or []:
        for post in face.get("representative_posts") or []:
            text = str(post.get("text") or post.get("clean_text") or "").strip()
            if text:
                texts.append(text)
    return texts


def iter_published_planets(data: dict):
    for topic in data.get("topics") or []:
        yield "global", topic
    sections = data.get("sections") or {}
    if isinstance(sections, dict):
        items = sections.items()
    else:
        items = []
    for section, body in items:
        topics = body if isinstance(body, list) else (body or {}).get("topics") or []
        for topic in topics:
            yield str(section), topic


def classify_planet(section: str, name: str, texts: list[str], post_count: int) -> dict:
    members = [{"text": text} for text in texts]
    share = planet_content_share(members)
    reason = planet_chitchat_reason(members, [], name=name)
    return {
        "section": section,
        "name": name,
        "post_count": int(post_count),
        "reps": len(members),
        "share": share,
        "decision": "DROP" if reason else "KEEP",
        "reason": reason or "",
    }


def classify_artifact(data: dict) -> list[dict]:
    rows = []
    for section, topic in iter_published_planets(data):
        name = str(topic.get("name") or "")
        texts = representative_texts(topic)
        post_count = int(topic.get("post_count") or len(texts))
        rows.append(classify_planet(section, name, texts, post_count))
    return rows


def format_table(rows: list[dict], *, heading: str) -> str:
    lines = [
        heading,
        "Full member texts are not in the artifact. Share is the representative mix.",
        f"{'decision':<8} {'section':<12} {'name':<32} {'posts':>6} {'reps':>5} {'share':>7}",
    ]
    for row in rows:
        lines.append(
            f"{row['decision']:<8} {row['section']:<12} {row['name'][:32]:<32} "
            f"{row['post_count']:>6} {row['reps']:>5} {row['share']:>6.0%}"
        )
    dropped = [row for row in rows if row["decision"] == "DROP"]
    lines.append(
        f"Dropped {len(dropped)} of {len(rows)}: "
        + (", ".join(f"{row['section']}:{row['name']}" for row in dropped) or "(none)")
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay the planet chit-chat guard")
    parser.add_argument("data", type=Path, help="Preview data.json")
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated planet names to print from this file",
    )
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    rows = classify_artifact(data)
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    if only:
        rows = [row for row in rows if row["name"] in only]
    print(format_table(rows, heading=f"Replay {args.data}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
