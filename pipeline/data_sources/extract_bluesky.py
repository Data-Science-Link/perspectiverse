"""Fetch a small English Bluesky sample from the last 168 hours.

With no app password this uses the public AppView search. Set BLUESKY_HANDLE
and BLUESKY_APP_PASSWORD to search as that account instead. Callers can pass
`fetch` so tests never touch the network.
"""

from __future__ import annotations

import os
import random
import urllib.parse
from datetime import datetime, timedelta, timezone

from pipeline.http_json import read_json

PUBLIC_SEARCH = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def extract_posts(
    *,
    sample_size: int,
    window_hours: int,
    queries: list[str],
    fetch=None,
    now: datetime | None = None,
    rng: random.Random | None = None,
    per_query: int = 25,
) -> list[dict]:
    """Return up to `sample_size` normalized posts inside the rolling window."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(hours=window_hours)
    getter = fetch or _default_fetch
    chooser = rng or random.Random()
    collected: list[dict] = []
    seen: set[str] = set()

    for query in queries:
        cursor = None
        for _page in range(8):
            page = getter(query, cursor, per_query)
            for raw in page.get("posts") or []:
                post = normalize_post(raw)
                if post is None or post["uri"] in seen:
                    continue
                created = _parse_time(post["created_at"])
                if created < cutoff or created > moment + timedelta(hours=1):
                    continue
                seen.add(post["uri"])
                collected.append(post)
            cursor = page.get("cursor")
            if not cursor or len(collected) >= sample_size * 2:
                break
        if len(collected) >= sample_size * 2:
            break

    if len(collected) > sample_size:
        collected = chooser.sample(collected, sample_size)
    return collected


def normalize_post(raw: dict) -> dict | None:
    record = raw.get("record") if isinstance(raw.get("record"), dict) else {}
    text = record.get("text") or raw.get("text") or ""
    uri = raw.get("uri") or ""
    author = raw.get("author") or {}
    if isinstance(author, dict):
        handle = author.get("handle") or "unknown"
    else:
        handle = str(author or "unknown")
    created = record.get("createdAt") or raw.get("created_at") or raw.get("indexedAt")
    if not uri or not text or not created:
        return None
    likes = raw.get("likeCount", raw.get("likes", 0)) or 0
    return {
        "uri": str(uri),
        "author": str(handle),
        "text": str(text),
        "likes": int(likes),
        "created_at": str(created),
    }


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_fetch(query: str, cursor: str | None, limit: int) -> dict:
    if os.getenv("BLUESKY_HANDLE") and os.getenv("BLUESKY_APP_PASSWORD"):
        return _fetch_authenticated(query, cursor, limit)
    return _fetch_public(query, cursor, limit)


def _fetch_public(query: str, cursor: str | None, limit: int) -> dict:
    params = {"q": query, "limit": str(min(limit, 100)), "sort": "latest", "lang": "en"}
    if cursor:
        params["cursor"] = cursor
    url = PUBLIC_SEARCH + "?" + urllib.parse.urlencode(params)
    return read_json(url, timeout=20, headers={"Accept": "application/json", "User-Agent": "perspectiverse-pipeline/0.1"})


def _fetch_authenticated(query: str, cursor: str | None, limit: int) -> dict:
    try:
        from atproto import Client
    except ImportError as exc:
        raise RuntimeError(
            "BLUESKY_HANDLE is set but the atproto package is not installed. Run uv sync."
        ) from exc
    client = Client()
    client.login(os.environ["BLUESKY_HANDLE"], os.environ["BLUESKY_APP_PASSWORD"])
    params = {"q": query, "limit": min(limit, 100), "sort": "latest", "lang": "en"}
    if cursor:
        params["cursor"] = cursor
    response = client.app.bsky.feed.search_posts(params)
    posts = []
    for post in getattr(response, "posts", []) or []:
        record = getattr(post, "record", None)
        author = getattr(post, "author", None)
        posts.append(
            {
                "uri": getattr(post, "uri", ""),
                "author": {"handle": getattr(author, "handle", "unknown")},
                "record": {
                    "text": getattr(record, "text", ""),
                    "createdAt": getattr(record, "created_at", None) or getattr(record, "createdAt", ""),
                },
                "likeCount": getattr(post, "like_count", 0) or 0,
                "indexedAt": getattr(post, "indexed_at", "") or "",
            }
        )
    return {"posts": posts, "cursor": getattr(response, "cursor", None)}
