"""Wider fetch and planet-only Jev. Off unless ``free_ingest`` is set.

When the setting is on, three things change:

* The free spam guard replaces per-post Jev spam and claim checks. Every
  post the guard lets through is stored, including non-claims.
* Jev runs once per candidate planet, and only to pick a newspaper category.
  Member posts inherit that category. Section solar systems then use the
  category the way they use a per-post section today.
* Search walks the last 7 UTC days with a longer query list and up to the
  search page cap, and stops a day at 14,300 non-spam posts. It backs off
  on HTTP 429 and 403. It does not walk the fill lookback past 7 days.

The default pipeline does not import this module's fetch. ``run_live``
calls it only when the setting is on.
"""

from __future__ import annotations

import copy
import time
from datetime import datetime, timedelta, timezone

from pipeline.cleaning import clean_text
from pipeline.corpus import parse_created, retire_oldest
from pipeline.data_sources.extract_bluesky import (
    MAX_SEARCH_PAGES,
    _default_fetch,
    extract_posts,
    format_search_time,
)
from pipeline.schema import CATEGORIES
from pipeline.spam_guard import guard_reason

# One seventh of a 100,000-post week, the #192 availability bar.
NON_SPAM_PER_DAY = 14_300
FREE_INGEST_DAYS = 7
# High-frequency English tokens. The first six match the default neutral list.
# The rest widen coverage without naming a beat.
WIDE_QUERIES = (
    "the",
    "and",
    "to",
    "of",
    "in",
    "for",
    "a",
    "is",
    "it",
    "you",
    "that",
    "on",
    "with",
    "this",
    "be",
    "as",
    "at",
    "by",
    "from",
    "or",
    "not",
    "are",
    "was",
    "have",
    "but",
    "they",
    "we",
    "just",
    "like",
    "so",
    "if",
    "about",
    "what",
    "when",
    "who",
    "how",
    "all",
    "can",
    "will",
    "people",
    "time",
    "new",
    "now",
    "day",
)


def free_ingest_enabled(settings: dict) -> bool:
    """True only when the operator turned the switch on. Default is off."""
    return bool(settings.get("free_ingest"))


def wide_queries(override: list[str] | None = None) -> list[str]:
    chosen = [item for item in (override or []) if item]
    if chosen:
        return chosen
    return list(WIDE_QUERIES)


def day_windows(moment: datetime, days: int = FREE_INGEST_DAYS) -> list[tuple[datetime, datetime]]:
    """UTC midnights, today first, then older days. ``days`` is 7."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    start = datetime(moment.year, moment.month, moment.day, tzinfo=timezone.utc)
    windows = []
    for offset in range(max(1, int(days))):
        since = start - timedelta(days=offset)
        windows.append((since, since + timedelta(days=1)))
    return windows


def paced_fetch(query, cursor, limit, since=None, until=None):
    """Search fetch with backoff on rate-limit and datacenter 403 responses."""
    delay = 1.0
    last: Exception | None = None
    for attempt in range(5):
        try:
            return _default_fetch(query, cursor, limit, since=since, until=until)
        except RuntimeError as exc:
            last = exc
            message = str(exc)
            if "HTTP 429" not in message and "HTTP 403" not in message:
                raise
            print(f"Bluesky search backoff {attempt + 1} ({message[:80]}).")
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    assert last is not None
    raise last


def prepare_post(post: dict) -> dict:
    """Attach cleaned text. Does not drop the post."""
    text = str(post.get("text") or "")
    prepared = dict(post)
    prepared["text"] = text
    prepared["clean_text"] = clean_text(text) or text
    prepared["author"] = str(post.get("author") or "unknown")
    prepared["likes"] = int(post.get("likes") or 0)
    prepared["created_at"] = str(post.get("created_at") or "")
    # The guard replaces per-post Jev. A stored row is not a claim verdict
    # and has no section until the planet call assigns one.
    prepared["is_claim"] = None
    prepared["spam_score"] = None
    prepared["section"] = ""
    prepared["section_confidence"] = None
    return prepared


def keep_non_spam(posts: list[dict]) -> tuple[list[dict], int]:
    """Return prepared posts the guard lets through, and how many it blocked."""
    kept: list[dict] = []
    blocked = 0
    for post in posts:
        prepared = prepare_post(post)
        if guard_reason(prepared) is not None:
            blocked += 1
            continue
        kept.append(prepared)
    return kept, blocked


def _in_window(post: dict, cutoff: datetime) -> bool:
    return parse_created(post.get("created_at") or "") >= cutoff


def ingest_free(
    existing: list[dict],
    settings: dict,
    queries: list[str] | None = None,
    *,
    target: int,
    now: datetime | None = None,
    extract=None,
    days: int = FREE_INGEST_DAYS,
) -> list[dict]:
    """Fetch the last 7 UTC days and keep every non-spam post.

    Does not call Jev. A search failure keeps the posts already collected.
    The retained list is cut to the rolling window and ``target``.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    fetch = extract or extract_posts
    chosen = wide_queries(queries if queries is not None else None)
    # An explicit --query list replaces the wide list. An omitted list uses it.
    if queries:
        chosen = [item for item in queries if item] or list(WIDE_QUERIES)
    window_hours = int(settings.get("window_hours") or 168)
    cutoff = moment - timedelta(hours=window_hours)
    seen = {str(post.get("uri") or "") for post in existing if post.get("uri")}
    kept: list[dict] = []
    for post in existing:
        if not post.get("uri") or not _in_window(post, cutoff):
            continue
        prepared = prepare_post(post)
        if guard_reason(prepared) is not None:
            continue
        kept.append(prepared)
    per_day = int(settings.get("free_ingest_per_day") or NON_SPAM_PER_DAY)
    for since, until in day_windows(moment, days):
        if len(kept) >= target:
            break
        day_new = 0
        day_blocked = 0
        for query in chosen:
            if day_new >= per_day or len(kept) >= target:
                break
            try:
                incoming = fetch(
                    sample_size=max(per_day, 1),
                    window_hours=window_hours,
                    queries=[query],
                    now=moment,
                    since=since,
                    until=until,
                    pages=MAX_SEARCH_PAGES,
                    subsample=False,
                    skip_uris=seen,
                    fetch=paced_fetch,
                )
            except RuntimeError as exc:
                print(
                    f"Free ingest {format_search_time(since)} query {query!r} failed ({exc})."
                )
                continue
            fresh, blocked = keep_non_spam(incoming)
            day_blocked += blocked
            for post in fresh:
                uri = str(post.get("uri") or "")
                if not uri or uri in seen:
                    continue
                seen.add(uri)
                kept.append(post)
                day_new += 1
                if day_new >= per_day or len(kept) >= target:
                    break
        print(
            f"Free ingest {since.date().isoformat()}: {day_new} new non-spam, "
            f"{day_blocked} blocked, {len(kept)} kept."
        )
    return retire_oldest(
        kept,
        now=moment,
        window_hours=window_hours,
        target=target,
    )


def stamp_candidate_sections(posts: list[dict], clustered: dict, classify) -> int:
    """One Jev category call per candidate planet. Members inherit it.

    ``classify(summary, arguments)`` returns a section name or None. A miss
    leaves the post's section blank so the keyword map can still name the
    planet. Returns how many classify calls were made. A spend-cap stop
    still aborts the run. Any other classify error keeps the keyword map.
    """
    from pipeline.spend_cap import SpendCapExceeded

    calls = 0
    for topic in clustered.get("topics") or []:
        indices = [int(index) for index in (topic.get("member_indices") or [])]
        if not indices:
            continue
        sample = [posts[index] for index in indices[:12] if 0 <= index < len(posts)]
        terms = " ".join(str(term) for term in (topic.get("terms") or []))
        arguments = "\n".join(
            str(post.get("text") or post.get("clean_text") or "") for post in sample
        )[:1500]
        calls += 1
        try:
            section = classify(terms or "planet", arguments)
        except SpendCapExceeded:
            raise
        except Exception as exc:
            print(f"Planet section call failed ({type(exc).__name__}).")
            continue
        if section not in CATEGORIES:
            continue
        for index in indices:
            if 0 <= index < len(posts):
                posts[index]["section"] = section
    if calls:
        print(f"Jev planet categories: {calls} call(s), one per candidate planet.")
    return calls


def section_copies(topics: list[dict]) -> dict[str, list[dict]]:
    """Bucket published planets by category without a second Jev call.

    Copies, so renaming a section id does not change the global planet id.
    Unused when member sections already drive ``_cluster_sections``. Tests
    use it to show one category is enough to file the planet.
    """
    grouped: dict[str, list[dict]] = {}
    for topic in topics:
        category = str(topic.get("category") or "")
        if category not in CATEGORIES:
            category = "Other"
        grouped.setdefault(category, []).append(copy.deepcopy(topic))
    return grouped
