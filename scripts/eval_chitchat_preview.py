#!/usr/bin/env python3
"""Measure chit-chat filtering against a free-ingest-preview ``data.json``.

No network and no paid calls. Representative posts under-count pleasantry
share on large planets; planet-guard title rules use ``post_count`` from the
edition when member texts are not available.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from pipeline.chitchat_guard import pleasantry_reason, planet_chitchat_reason

TARGETS = frozenset(
    {
        "Art Appreciation",
        "Twitch Stream",
        "Happy Birthday",
        "the weekend",
        "Happy Anniversary",
        "Good Luck",
        "Count",
        "Course",
        "Full Agreement",
    }
)

_DISCOURSE_MARKERS = (
    "council",
    "ukraine",
    "veteran",
    "congress",
    "invasion",
    "housing",
    "bill",
    "wages",
    "ruling",
    "gambling",
    "charms",
    "samuel",
    "fomin",
    "policy",
    "platform",
)


def _iter_planets(data: dict):
    yield "global", data.get("topics") or []
    for section, topics in sorted((data.get("sections") or {}).items()):
        yield section, topics or []


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate chit-chat rules on preview data.json")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    all_texts: list[str] = []
    for _scope, topics in _iter_planets(data):
        for topic in topics:
            for face in topic.get("perspectives") or []:
                for post in face.get("representative_posts") or []:
                    text = str(post.get("text") or "").strip()
                    if text:
                        all_texts.append(text)

    removed = [text for text in all_texts if pleasantry_reason({"text": text})]
    share = len(removed) / len(all_texts) if all_texts else 0.0
    print(f"Representative posts: {len(all_texts)}")
    print(f"Ingest pleasantry drops: {len(removed)} ({share:.2%} of representatives)")

    print("\nTarget planets (#208):")
    for scope, topics in _iter_planets(data):
        for topic in topics:
            name = str(topic.get("name") or "")
            if name not in TARGETS:
                continue
            members = [
                {"text": str(post.get("text") or "")}
                for face in topic.get("perspectives") or []
                for post in face.get("representative_posts") or []
            ]
            post_count = int(topic.get("post_count") or len(members))
            rep_hits = sum(1 for member in members if pleasantry_reason(member))
            expanded = members * max(1, post_count // max(len(members), 1))
            guard = planet_chitchat_reason(expanded[:post_count], [], name=name)
            est = int(post_count * (rep_hits / len(members))) if members else 0
            print(
                f"  {scope}:{name} posts={post_count} "
                f"rep_ingest_drops={rep_hits}/{len(members)} est_ingest~{est} "
                f"planet_guard={'yes' if guard else 'no'}"
            )

    random.seed(args.seed)
    sample = removed if len(removed) <= 100 else random.sample(removed, 100)
    obvious_fp = [text for text in sample if any(marker in text.lower() for marker in _DISCOURSE_MARKERS)]
    fp_rate = len(obvious_fp) / len(sample) if sample else 0.0
    print(f"\nRemoved-post sample (n={len(sample)}): obvious discourse markers in {len(obvious_fp)} ({fp_rate:.1%})")
    for text in obvious_fp[:10]:
        print(f"  FP? {text[:120]}")
    print(f"\nEdition total_posts field: {data.get('total_posts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
