#!/usr/bin/env python3
"""Measure chit-chat filtering against a free-ingest-preview ``data.json``.

No network and no paid calls. The preview artifact stores representative
posts, not the full edition. Share on a planet is the representative drop
rate. Estimated posts removed is that rate times ``post_count``. A planet
does not survive when that share is at least 55 percent, under any title.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from pipeline.chitchat_guard import PLEASANTRY_SHARE_DROP, pleasantry_reason, planet_chitchat_reason

TARGETS = (
    ("global", "Art Appreciation"),
    ("global", "Twitch Stream"),
    ("Business", "Count"),
    ("Sports", "Good Luck"),
    ("Sports", "Happy Anniversary"),
    ("Education", "Course"),
    ("Education", "Full Agreement"),
    ("Other", "Art Appreciation"),
    ("Other", "the weekend"),
    ("Other", "Happy Birthday"),
)


def _iter_planets(data: dict):
    yield "global", data.get("topics") or []
    for section, topics in sorted((data.get("sections") or {}).items()):
        yield section, topics or []


def _members(topic: dict) -> list[dict]:
    return [
        {"text": str(post.get("text") or "")}
        for face in topic.get("perspectives") or []
        for post in face.get("representative_posts") or []
        if str(post.get("text") or "").strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate chit-chat rules on preview data.json")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--sample", type=int, default=100)
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    print(
        "Full post texts are not in this artifact. "
        f"total_posts={data.get('total_posts')}. Measuring representative posts only."
    )
    all_texts: list[tuple[str, str]] = []
    index: dict[tuple[str, str], dict] = {}
    for scope, topics in _iter_planets(data):
        for topic in topics:
            name = str(topic.get("name") or "")
            index[(scope, name)] = topic
            for member in _members(topic):
                all_texts.append((f"{scope}:{name}", member["text"]))

    removed = [(where, text) for where, text in all_texts if pleasantry_reason({"text": text})]
    kept = [(where, text) for where, text in all_texts if not pleasantry_reason({"text": text})]
    share = len(removed) / len(all_texts) if all_texts else 0.0
    print(f"Representative posts: {len(all_texts)}")
    print(f"Content-rule drops: {len(removed)} ({share:.2%} of representatives)")
    print(f"Kept: {len(kept)}")

    print("\nTarget clusters. Guard ignores the title (checked as Kind Words and with no name).")
    print(f"{'cluster':<32} {'reps':>8} {'share':>8} {'est remain':>12} floor guard")
    for scope, name in TARGETS:
        topic = index.get((scope, name))
        if topic is None:
            print(f"  MISSING {scope}:{name}")
            continue
        members = _members(topic)
        hits = sum(1 for member in members if pleasantry_reason(member))
        rep_share = hits / len(members) if members else 0.0
        post_count = int(topic.get("post_count") or len(members))
        remain = int(round(post_count * (1 - rep_share)))
        renamed = planet_chitchat_reason(members, [], name="Kind Words")
        unnamed = planet_chitchat_reason(members, [], name=None)
        titled = planet_chitchat_reason(members, [], name=name)
        same = renamed == unnamed == titled and renamed is not None
        below = remain < 5
        label = f"{scope}:{name}"
        print(
            f"{label:<32} {hits:>3}/{len(members):<3} {rep_share:>7.1%} "
            f"{remain:>12} {'yes' if below else 'no':>5} "
            f"{'DROP' if same and rep_share >= PLEASANTRY_SHARE_DROP else 'KEEP'}"
        )

    random.seed(args.seed)
    removed_sample = removed if len(removed) <= args.sample else random.sample(removed, args.sample)
    random.seed(args.seed)
    kept_sample = kept if len(kept) <= args.sample else random.sample(kept, args.sample)
    print(f"\nRemoved sample seed={args.seed} n={len(removed_sample)}")
    for index_no, (where, text) in enumerate(removed_sample, start=1):
        print(f"R{index_no:03d} [{where}] {text[:220]}")
    print(f"\nKept sample seed={args.seed} n={len(kept_sample)}")
    for index_no, (where, text) in enumerate(kept_sample, start=1):
        print(f"K{index_no:03d} [{where}] {text[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
