"""Fetch an English Bluesky sample from a rolling window.

With no app password this uses the public AppView search. GitHub-hosted
runners sometimes get 403 on one host and not the other, so we try
``public.api.bsky.app`` then ``api.bsky.app`` with short retries.

Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD to search as that account
instead. Callers can pass ``fetch`` so tests never touch the network.
"""

from __future__ import annotations

import math
import os
import random
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from pipeline.http_json import read_json

PUBLIC_SEARCH_URLS = (
    "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
    "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
)
USER_AGENT = "perspectiverse-pipeline/0.2"
# Bluesky search stops returning new pages around this depth. A fill run
# starts a fresh cursor per UTC day instead of asking for page 41.
MAX_SEARCH_PAGES = 40


def page_budget(sample_size: int, query_count: int, per_query: int = 100) -> int:
    """Pages per query so a large claim window can be inspected.

    The extractor overscans to twice ``sample_size`` before it subsamples.
    A fixed 8-page loop stops near 4,800 posts across the neutral queries.
    """
    queries = max(int(query_count), 1)
    per = max(int(per_query), 1)
    needed = math.ceil((max(int(sample_size), 1) * 2) / (queries * per))
    return min(MAX_SEARCH_PAGES, max(8, needed))


def format_search_time(moment: datetime) -> str:
    """UTC timestamp for Bluesky ``since`` / ``until`` (until is exclusive)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_posts(
    *,
    sample_size: int,
    window_hours: int,
    queries: list[str],
    fetch=None,
    now: datetime | None = None,
    rng: random.Random | None = None,
    per_query: int = 100,
    skip_uris: set[str] | None = None,
    cache_uris: set[str] | None = None,
    cache_reused: set[str] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    pages: int | None = None,
    subsample: bool = True,
) -> list[dict]:
    """Return up to ``sample_size`` normalized posts inside the rolling window.

    ``since`` / ``until`` bound one search (until is exclusive). Fill runs pass
    one UTC day at a time so each query gets its own page budget. Scheduled
    runs leave both unset. ``pages`` overrides the size-based page budget.
    ``subsample=False`` keeps every post the pages returned.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(hours=window_hours)
    lower, upper = _search_bounds(cutoff, moment, since, until)
    getter = fetch or _default_fetch
    chooser = rng or random.Random()
    collected: list[dict] = []
    seen: set[str] = set(skip_uris or ())
    if pages is None:
        budget = page_budget(sample_size, len(queries), per_query)
    else:
        budget = min(MAX_SEARCH_PAGES, max(1, int(pages)))

    for query in queries:
        cursor = None
        for _page in range(budget):
            try:
                page = _invoke_fetch(getter, query, cursor, per_query, since, until)
            except RuntimeError as exc:
                print(f"Skipping Bluesky query {query!r}: {exc}")
                break
            for raw in page.get("posts") or []:
                post = normalize_post(raw)
                if post is None:
                    continue
                if post["uri"] in seen:
                    # A URI already scored, and not already in the retained
                    # corpus, is a cache hit. The caller puts those URIs in
                    # both ``skip_uris`` and ``cache_uris``. Corpus URIs are
                    # dedup, not hits, so they stay out of ``cache_uris``.
                    if cache_reused is not None and cache_uris is not None and post["uri"] in cache_uris:
                        cache_reused.add(post["uri"])
                    continue
                created = _parse_time(post["created_at"])
                if since is None and until is None:
                    outside = created < lower or created > moment + timedelta(hours=1)
                else:
                    outside = created < lower or created >= upper or created > moment + timedelta(hours=1)
                if outside:
                    continue
                seen.add(post["uri"])
                collected.append(post)
            cursor = page.get("cursor")
            if not cursor or (subsample and len(collected) >= sample_size * 2):
                break
            time.sleep(0.35)
        if subsample and len(collected) >= sample_size * 2:
            break
        time.sleep(0.2)

    if subsample and len(collected) > sample_size:
        collected = chooser.sample(collected, sample_size)
    return collected


def _search_bounds(
    cutoff: datetime,
    moment: datetime,
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    """Inclusive lower bound and exclusive upper bound for one extract."""
    if since is None and until is None:
        return cutoff, moment + timedelta(hours=1)
    lower = _as_utc(since) if since is not None else cutoff
    upper = _as_utc(until) if until is not None else moment + timedelta(hours=1)
    return lower, upper


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _invoke_fetch(getter, query: str, cursor: str | None, limit: int, since: datetime | None, until: datetime | None):
    """Call a 3-argument fetch unless this search is bounded by a date window."""
    if since is None and until is None:
        return getter(query, cursor, limit)
    return getter(query, cursor, limit, since=since, until=until)


def extract_grouped_posts(
    *,
    quotas: dict[str, int],
    query_groups: dict[str, list[str]],
    window_hours: int,
    fetch=None,
    now: datetime | None = None,
    rng: random.Random | None = None,
    per_query: int = 100,
) -> list[dict]:
    """Pull one quota per named query group.

    The public live job does not call this. It searches neutral tokens instead.
    """
    chooser = rng or random.Random()
    collected: list[dict] = []
    seen: set[str] = set()
    for group, quota in quotas.items():
        queries = [item for item in query_groups.get(group, []) if item]
        if not queries or quota <= 0:
            continue
        try:
            batch = extract_posts(
                sample_size=max(quota, 10),
                window_hours=window_hours,
                queries=queries,
                fetch=fetch,
                now=now,
                rng=chooser,
                per_query=per_query,
            )
        except RuntimeError as exc:
            print(f"Skipping Bluesky group {group!r}: {exc}")
            continue
        for post in batch:
            if post["uri"] in seen:
                continue
            seen.add(post["uri"])
            collected.append(post)
        time.sleep(0.2)
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


def _default_fetch(
    query: str,
    cursor: str | None,
    limit: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    handle = (os.getenv("BLUESKY_HANDLE") or "").strip()
    password = os.getenv("BLUESKY_APP_PASSWORD") or ""
    if handle and password.strip():
        try:
            return _fetch_authenticated(query, cursor, limit, since=since, until=until)
        except RuntimeError as exc:
            print(
                f"Authenticated Bluesky search failed ({exc}). "
                "Falling back to public AppView search."
            )
    return _fetch_public(query, cursor, limit, since=since, until=until)


def _search_params(
    query: str,
    cursor: str | None,
    limit: int,
    since: datetime | None,
    until: datetime | None,
    *,
    limit_as_str: bool,
) -> dict:
    capped = min(limit, 100)
    params: dict = {
        "q": query,
        "limit": str(capped) if limit_as_str else capped,
        "sort": "latest",
        "lang": "en",
    }
    if cursor:
        params["cursor"] = cursor
    if since is not None:
        params["since"] = format_search_time(since)
    if until is not None:
        params["until"] = format_search_time(until)
    return params


def _fetch_public(
    query: str,
    cursor: str | None,
    limit: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    params = _search_params(query, cursor, limit, since, until, limit_as_str=True)
    query_string = urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for base in PUBLIC_SEARCH_URLS:
        url = f"{base}?{query_string}"
        host = urllib.parse.urlparse(base).hostname or base
        try:
            return read_json(
                url,
                timeout=20,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
        except RuntimeError as exc:
            last_error = exc
            message = str(exc)
            if "HTTP 403" in message:
                print(f"Public Bluesky search HTTP 403 from {host} (anonymous GET).")
                time.sleep(1.0)
                try:
                    return read_json(
                        url,
                        timeout=20,
                        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                    )
                except RuntimeError as retry_exc:
                    last_error = retry_exc
                    continue
            if "HTTP 401" in message or "HTTP 404" in message:
                continue
            time.sleep(0.4)
            try:
                return read_json(
                    url,
                    timeout=20,
                    headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                )
            except RuntimeError as retry_exc:
                last_error = retry_exc
                continue
    raise RuntimeError(f"Bluesky public search failed: {last_error}") from last_error


_AUTH_CLIENT = None
_AUTH_LOGIN_STATE = "untried"


def reset_auth_state() -> None:
    """Test seam so cached login does not leak across cases."""
    global _AUTH_CLIENT, _AUTH_LOGIN_STATE
    _AUTH_CLIENT = None
    _AUTH_LOGIN_STATE = "untried"


def _redact(text: str) -> str:
    password = os.getenv("BLUESKY_APP_PASSWORD") or ""
    if password and password in text:
        text = text.replace(password, "***")
    return text[:240]


def _authenticated_client():
    """Log in once per process. Never prints the app password."""
    global _AUTH_CLIENT, _AUTH_LOGIN_STATE
    if _AUTH_CLIENT is not None:
        return _AUTH_CLIENT
    if _AUTH_LOGIN_STATE.startswith("failed"):
        raise RuntimeError(f"Bluesky login already failed ({_AUTH_LOGIN_STATE})")
    try:
        from atproto import Client
    except ImportError as exc:
        _AUTH_LOGIN_STATE = "failed (atproto missing)"
        raise RuntimeError(
            "BLUESKY_HANDLE is set but the atproto package is not installed. "
            "The daily job must `uv pip install atproto` (see pipeline.yml)."
        ) from exc
    handle = (os.getenv("BLUESKY_HANDLE") or "").strip()
    password = os.getenv("BLUESKY_APP_PASSWORD") or ""
    client = Client()
    try:
        client.login(handle, password)
    except Exception as exc:  # noqa: BLE001 — atproto raises several types
        _AUTH_LOGIN_STATE = f"failed ({type(exc).__name__})"
        print(f"Bluesky login failed for {handle}: {type(exc).__name__}.")
        raise RuntimeError(
            f"Bluesky login failed for {handle}: {type(exc).__name__}: {_redact(str(exc))}"
        ) from exc
    _AUTH_CLIENT = client
    _AUTH_LOGIN_STATE = "ok"
    print(f"Bluesky authenticated search as {handle} (login ok)")
    return client


def _fetch_authenticated(
    query: str,
    cursor: str | None,
    limit: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    handle = (os.getenv("BLUESKY_HANDLE") or "").strip()
    client = _authenticated_client()
    params = _search_params(query, cursor, limit, since, until, limit_as_str=False)
    try:
        response = client.app.bsky.feed.search_posts(params)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Authenticated Bluesky search failed after login "
            f"({_AUTH_LOGIN_STATE}) as {handle}: {type(exc).__name__}: {_redact(str(exc))}"
        ) from exc
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
