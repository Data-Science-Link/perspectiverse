"""Retain and rotate the live Bluesky corpus.

The first fill keeps ``target`` quality posts. Each later run drops the oldest
seventh and adds a seventh of new posts from the prior day. A failed fetch
must not shrink the retained window — the daily job still has to publish.
"""

from __future__ import annotations

from datetime import datetime, timezone

TARGET_POSTS = 1000
REFRESH_FRACTION = 1.0 / 7.0
MIN_GROUP_POSTS = 10

GROUP_QUOTAS = {
    "general": 400,
    "sports": 200,
    "geopolitics": 200,
    "ai": 200,
}


def parse_created(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def quality_score(post: dict) -> float:
    """Prefer posts that look like an argument, not a bump."""
    text = str(post.get("clean_text") or post.get("text") or "")
    likes = max(int(post.get("likes") or 0), 0)
    length = len(text)
    length_score = min(length, 280) / 20.0
    if 40 <= length <= 400:
        length_score += 4.0
    return likes * 2.0 + length_score


def select_quality(posts: list[dict], limit: int) -> list[dict]:
    """Keep the best ``limit`` posts. Input should already be de-spammed."""
    ranked = sorted(
        posts,
        key=lambda post: (-quality_score(post), -parse_created(post.get("created_at") or "").timestamp()),
    )
    return ranked[: max(limit, 0)]


def rotate_corpus(
    existing: list[dict],
    incoming: list[dict],
    *,
    target: int = TARGET_POSTS,
    drop_fraction: float = REFRESH_FRACTION,
) -> list[dict]:
    """Merge incoming posts into a ~target window.

    If ``incoming`` is empty, ``existing`` is returned unchanged so a 403
    cannot erase yesterday's sample. First fill (no existing rows) keeps the
    best ``target`` incoming posts.
    """
    if not incoming:
        return list(existing)
    if not existing:
        return select_quality(incoming, target)

    drop_count = max(1, int(round(len(existing) * drop_fraction)))
    add_count = max(drop_count, int(round(target * drop_fraction)))
    survivors = sorted(existing, key=lambda post: parse_created(post.get("created_at") or ""))[drop_count:]
    seen = {post["uri"] for post in survivors}
    fresh = [post for post in incoming if post.get("uri") and post["uri"] not in seen]
    fresh = select_quality(fresh, add_count)
    merged = survivors + fresh
    if len(merged) > target:
        merged = select_quality(merged, target)
    return merged


def scale_quotas(sample_size: int, quotas: dict[str, int] | None = None) -> dict[str, int]:
    """Stretch the default group mix to ``sample_size`` while keeping a 10-post floor."""
    base = dict(quotas or GROUP_QUOTAS)
    total = sum(base.values()) or 1
    scaled = {name: max(MIN_GROUP_POSTS, int(round(sample_size * share / total))) for name, share in base.items()}
    drift = sample_size - sum(scaled.values())
    head = "general" if "general" in scaled else next(iter(scaled))
    scaled[head] = max(MIN_GROUP_POSTS, scaled[head] + drift)
    return scaled
