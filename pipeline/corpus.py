"""Retain a rolling window of Bluesky posts.

Posts older than the window fall off only after a successful fetch. An empty
incoming batch leaves the retained posts untouched, including ones that are
now past the window, so a 403 cannot erase yesterday's sample. The public
sample is random within the fetch, not ranked by likes.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

TARGET_POSTS = 1000
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


def cap_sample(posts: list[dict], limit: int, rng: random.Random) -> list[dict]:
    """Keep up to ``limit`` posts at random. Does not rank by likes."""
    if limit <= 0:
        return []
    if len(posts) <= limit:
        return list(posts)
    return rng.sample(list(posts), limit)


def retain_window(
    existing: list[dict],
    incoming: list[dict],
    *,
    now: datetime,
    window_hours: int,
    target: int,
    rng: random.Random,
) -> list[dict]:
    """Expire posts outside the window and top up toward ``target``.

    An empty ``incoming`` list returns ``existing`` unchanged. In-window posts
    are never dropped to make room, and likes are not a rank.
    """
    if not incoming:
        return list(existing)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=window_hours)
    survivors = [post for post in existing if parse_created(post.get("created_at") or "") >= cutoff]
    seen = {post["uri"] for post in survivors if post.get("uri")}
    fresh = [post for post in incoming if post.get("uri") and post["uri"] not in seen]
    need = max(0, target - len(survivors))
    return survivors + cap_sample(fresh, need, rng)


def posts_on_utc_date(posts: list[dict], utc_date: str) -> bool:
    """True when any post was created on ``utc_date`` (``YYYY-MM-DD``)."""
    for post in posts:
        if parse_created(post.get("created_at") or "").date().isoformat() == utc_date:
            return True
    return False


def window_utc_dates(now: datetime, days: int = 7) -> list[str]:
    """UTC dates covered by a first fill, newest first."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    moment = now.astimezone(timezone.utc).date()
    return [(moment - timedelta(days=offset)).isoformat() for offset in range(days)]


def scale_quotas(sample_size: int, quotas: dict[str, int] | None = None) -> dict[str, int]:
    """Stretch the default group mix to ``sample_size`` while keeping a 10-post floor."""
    base = dict(quotas or GROUP_QUOTAS)
    total = sum(base.values()) or 1
    scaled = {name: max(MIN_GROUP_POSTS, int(round(sample_size * share / total))) for name, share in base.items()}
    drift = sample_size - sum(scaled.values())
    head = "general" if "general" in scaled else next(iter(scaled))
    scaled[head] = max(MIN_GROUP_POSTS, scaled[head] + drift)
    return scaled
