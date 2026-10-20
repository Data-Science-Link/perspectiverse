#!/usr/bin/env python3
"""Dry-run replay of run 39260526877 Politics relocate + validate (#258).

No paid calls. ``PERSPECTIVERSE_ALLOW_PAID`` must stay unset.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.assemble import assemble_payload
from pipeline.schema import NOISE_POLICY, validate_payload
from pipeline.section_relocate import (
    RUN_39260526877_FIXTURE,
    apply_politics_post_label_relocate,
    minimal_global_topic_from_section,
    politics_topics_from_run_39260526877_fixture,
)


def main() -> int:
    if os.environ.get("PERSPECTIVERSE_ALLOW_PAID"):
        print("Refusing to run with PERSPECTIVERSE_ALLOW_PAID set.", file=sys.stderr)
        return 2
    data = json.loads(RUN_39260526877_FIXTURE.read_text(encoding="utf-8"))
    topics, posts = politics_topics_from_run_39260526877_fixture(data)
    stale_sections = apply_politics_post_label_relocate(topics, posts, renormalize=False)
    stale = sum(float(t["total_volume_percent"]) for t in stale_sections["Politics"])
    print(f"Without renormalize: Politics sum={stale:.1f} (expect 93.1)")
    try:
        validate_payload(
            {
                "last_updated": "2026-10-19",
                "total_posts": sum(int(r["post_count"]) for r in data["politics_post_counts"]),
                "window_hours": 168,
                "source": "fixture",
                "mode": "live",
                "noise_policy": NOISE_POLICY,
                "topics": [minimal_global_topic_from_section(stale_sections["Politics"][0])],
                "sections": stale_sections,
            }
        )
        print("ERROR: validate_payload should have failed on stale Politics volumes.")
        return 1
    except ValueError as exc:
        print(f"validate_payload failed as expected: {exc}")

    topics, posts = politics_topics_from_run_39260526877_fixture(data)
    fixed = apply_politics_post_label_relocate(topics, posts, renormalize=True)
    politics_sum = sum(float(t["total_volume_percent"]) for t in fixed["Politics"])
    culture_sum = sum(float(t["total_volume_percent"]) for t in fixed["Culture"])
    print(f"With renormalize: Politics={politics_sum:.1f} Culture={culture_sum:.1f}")
    payload = assemble_payload(
        [minimal_global_topic_from_section(fixed["Politics"][0])],
        mode="live",
        source="fixture",
        total_posts=sum(int(r["post_count"]) for r in data["politics_post_counts"]),
        last_updated="2026-10-19",
        sections=fixed,
    )
    validate_payload(payload)
    print("assemble_payload + validate_payload OK after renormalize.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
