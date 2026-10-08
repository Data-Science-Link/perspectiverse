#!/usr/bin/env python3
"""Offline estimate of extra labeling input tokens from wider MMR prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pipeline.label import build_perspective_prompt, build_topic_prompt
from pipeline.perspectives import select_representatives
from pipeline.prompt_sample import select_prompt_posts


def _chars(prompt: str) -> int:
    return len(prompt)


def _estimate_tokens(chars: int) -> int:
    return int(chars / 3.6)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests" / "fixtures" / "tiny_posts.json"
    posts = json.loads(fixture.read_text(encoding="utf-8"))
    # Synthetic large face: repeat tiny texts with varied suffixes.
    large: list[dict] = []
    for i in range(199):
        base = posts[i % len(posts)]
        large.append(
            {
                **base,
                "text": f"{base.get('text', '')} variant {i}",
                "clean_text": f"{base.get('clean_text') or base.get('text', '')} variant {i}",
                "likes": int(base.get("likes") or 0) + (i % 7),
            }
        )
    cosines = [0.99 - 0.002 * (i % 20) for i in range(len(large))]
    before_posts = select_representatives(large, [0.0] * len(large), limit=12, matches=cosines)
    after_posts = select_prompt_posts(large, cosines, limit=40)
    before_prompt = build_perspective_prompt(before_posts, post_limit=12)
    after_prompt = build_perspective_prompt(after_posts, post_limit=len(after_posts))
    delta_chars = _chars(after_prompt) - _chars(before_prompt)
    delta_tokens = _estimate_tokens(delta_chars)
    # Scale: 52 faces over 12 posts on a 220-face snapshot (issue #86).
    scaled_tokens = delta_tokens * 52
    cost_per_million_in = 0.10
    added_usd = scaled_tokens / 1_000_000 * cost_per_million_in
    print("Large face example (199 posts):")
    print(f"  Before (12 centroid): {len(before_posts)} posts, ~{_estimate_tokens(_chars(before_prompt))} tokens")
    print(f"  After (40 MMR):       {len(after_posts)} posts, ~{_estimate_tokens(_chars(after_prompt))} tokens")
    print(f"  Delta this face: ~{delta_tokens} input tokens")
    print(f"  Scaled (52 wide faces): ~{scaled_tokens} input tokens (~${added_usd:.4f} at $0.10/M in)")
    topic_before = build_topic_prompt(large[:16], ["war", "gaza"], post_limit=16)
    topic_after = build_topic_prompt(
        select_prompt_posts(large, cosines, limit=20),
        ["war", "gaza"],
        post_limit=20,
    )
    print(
        f"  Planet topic prompt delta (16 oldest vs 20 MMR): "
        f"~{_estimate_tokens(_chars(topic_after) - _chars(topic_before))} tokens"
    )
    print("\nBefore prompt post indices (centroid-closest 12):")
    for i, post in enumerate(before_posts):
        print(f"  {i + 1}. likes={post.get('likes')} match={post.get('match')} text={post['text'][:72]}...")
    print("\nAfter prompt post indices (MMR 40):")
    for i, post in enumerate(after_posts):
        print(f"  {i + 1}. likes={post.get('likes')} match={post.get('match')} text={post['text'][:72]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
