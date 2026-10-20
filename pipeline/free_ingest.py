"""Wider fetch and planet-only Jev.

On for a scheduled run and a normal dispatch. The workflow sets
``PERSPECTIVERSE_FREE_INGEST=1``, and ``pipeline.example.yaml`` says
``free_ingest: true``. ``legacy_jev`` and a fill dispatch set the variable
to ``0``. A config that omits the key stays off (``DEFAULTS``).

When the setting is on, three things change:

* The free spam guard and chit-chat filter replace per-post Jev spam and
  claim checks. Edition-quality posts (not spam, chit-chat, link-only, or
  non-English) are stored, including non-claims.
* Jev runs once per candidate planet, and only to pick a newspaper category.
  Member posts inherit that category. Section solar systems then use the
  category the way they use a per-post section today.
* Search walks the last 7 UTC days with a longer query list and up to the
  search page cap, and stops a day at 14,300 non-spam posts. It backs off
  on HTTP 429 and 403. It does not walk the fill lookback past 7 days.

``run_live`` calls this fetch only when the setting is on. The old path
does not.
"""

from __future__ import annotations

import copy
import time
from datetime import datetime, timedelta, timezone

from pipeline.cleaning import clean_text, dedupe_key
from pipeline.corpus import parse_created, retire_oldest
from pipeline.data_sources.extract_bluesky import (
    MAX_SEARCH_PAGES,
    _default_fetch,
    extract_posts,
    format_search_time,
)
from pipeline.chitchat_guard import get_chitchat_log, ingest_block_reason, reset_chitchat_log
from pipeline.schema import CATEGORIES

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
    """True when this run should skip per-post Jev.

    Production turns that on. A config that omits the key does not.
    """
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
    text = str(post.get("text") or post.get("clean_text") or "")
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


def keep_edition_quality(
    posts: list[dict],
    *,
    seen_text: set[str] | None = None,
) -> tuple[list[dict], int, int]:
    """Return posts that pass spam, chit-chat, language, and link-only checks.

    The daily non-spam cap counts only posts returned here, so chit-chat never
    fills a 14,300 slot and ingest can top up until ``target`` quality posts.
    When ``seen_text`` is set, copy-paste text already in the corpus or an
    earlier fetch in this run is counted as ``near_duplicate_blocked``.
    """
    log = get_chitchat_log()
    kept: list[dict] = []
    blocked_spam = 0
    blocked_other = 0
    for post in posts:
        log.record_fetch(1)
        prepared = prepare_post(post)
        reason = ingest_block_reason(prepared)
        if reason is not None:
            log.record_block(prepared, reason)
            if reason.startswith("spam:"):
                blocked_spam += 1
            else:
                blocked_other += 1
            continue
        if seen_text is not None:
            key = dedupe_key(prepared)
            if key and key in seen_text:
                log.near_duplicate_blocked += 1
                continue
            if key:
                seen_text.add(key)
        kept.append(prepared)
    return kept, blocked_spam, blocked_other


def _seed_seen_text(posts: list[dict]) -> set[str]:
    keys: set[str] = set()
    for post in posts:
        key = dedupe_key(post)
        if key:
            keys.add(key)
    return keys


def _accept_fresh_posts(
    fresh: list[dict],
    kept: list[dict],
    seen: set[str],
    *,
    per_day: int,
    day_new: int,
    target: int,
    new_cap: int | None,
    fetch_added: int,
) -> tuple[int, int]:
    """Append edition-quality fetches. Count cap and duplicate exits in the log."""
    log = get_chitchat_log()
    for post in fresh:
        uri = str(post.get("uri") or "")
        if not uri:
            log.missing_uri += 1
            continue
        if uri in seen:
            log.already_stored += 1
            continue
        if len(kept) >= target:
            log.over_target_cap += 1
            continue
        if day_new >= per_day:
            log.over_daily_cap += 1
            continue
        if new_cap is not None and fetch_added >= new_cap:
            log.over_max_new_posts += 1
            continue
        seen.add(uri)
        kept.append(post)
        day_new += 1
        fetch_added += 1
        log.new_stored += 1
    return day_new, fetch_added


def log_fetch_bucket_summary() -> None:
    log = get_chitchat_log()
    print(
        "Free ingest fetch buckets: "
        f"fetched={log.fetched}, new={log.new_stored}, "
        f"spam={log.spam_blocked}, chitchat={log.chitchat_blocked}, "
        f"health_update={log.health_update_blocked}, "
        f"link_only={log.link_blocked}, language={log.language_blocked}, "
        f"near_duplicate={log.near_duplicate_blocked}, other={log.other_blocked}, "
        f"already_stored={log.already_stored}, over_daily_cap={log.over_daily_cap}, "
        f"over_target_cap={log.over_target_cap}, over_max_new_posts={log.over_max_new_posts}, "
        f"missing_uri={log.missing_uri}, "
        f"accounted={log.accounted_total()}, "
        f"reconcile={'ok' if log.buckets_reconcile() else 'MISMATCH'}."
    )


def keep_non_spam(posts: list[dict]) -> tuple[list[dict], int]:
    """Backward-compatible wrapper. Prefer ``keep_edition_quality``."""
    kept, blocked_spam, blocked_other = keep_edition_quality(posts)
    return kept, blocked_spam + blocked_other


def _in_window(post: dict, cutoff: datetime) -> bool:
    return parse_created(post.get("created_at") or "") >= cutoff


def _classify_block_reason(reason: str) -> str:
    if reason.startswith("spam:"):
        return "spam"
    if reason == "chitchat:health_update":
        return "health_update"
    if reason.startswith("chitchat:"):
        return "chitchat"
    if reason == "link_only":
        return "link_only"
    if reason == "language":
        return "language"
    return "other"


def refresh_carried_posts(
    existing: list[dict],
    cutoff: datetime,
) -> tuple[list[dict], dict[str, int]]:
    """Re-run edition filters on rows already in the corpus."""
    stats = {
        "carried_seen": 0,
        "carried_kept": 0,
        "carried_spam": 0,
        "carried_chitchat": 0,
        "carried_health_update": 0,
        "carried_link_only": 0,
        "carried_language": 0,
        "carried_other": 0,
    }
    kept: list[dict] = []
    for post in existing:
        if not post.get("uri") or not _in_window(post, cutoff):
            continue
        stats["carried_seen"] += 1
        prepared = prepare_post(post)
        reason = ingest_block_reason(prepared)
        if reason is not None:
            bucket = _classify_block_reason(reason)
            key = f"carried_{bucket}"
            if bucket == "other":
                stats["carried_other"] += 1
            else:
                stats[key] = stats.get(key, 0) + 1
            continue
        kept.append(prepared)
        stats["carried_kept"] += 1
    return kept, stats


def ingest_free(
    existing: list[dict],
    settings: dict,
    queries: list[str] | None = None,
    *,
    target: int,
    now: datetime | None = None,
    extract=None,
    days: int = FREE_INGEST_DAYS,
    reset_log: bool = True,
    max_new_posts: int | None = None,
) -> tuple[list[dict], bool, int]:
    """Fetch the last 7 UTC days and keep edition-quality posts.

    Spam, chit-chat, and personal health updates are always dropped before the
    daily cap and ``target``.
    Link-only and non-English posts are dropped there only when
    ``drop_link_and_language_at_ingest`` is on. When it is off they count
    toward the stored edition, which is what main did before #209, and
    clustering still skips them. Does not call Jev. A search failure keeps
    the posts already collected. The retained list is cut to the rolling
    window and ``target``.
    """
    if reset_log:
        reset_chitchat_log()
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
    kept, carried_stats = refresh_carried_posts(existing, cutoff)
    seen_text = _seed_seen_text(kept)
    if carried_stats["carried_seen"]:
        print(
            "Carried-over corpus filters: "
            f"seen={carried_stats['carried_seen']}, "
            f"kept={carried_stats['carried_kept']}, "
            f"spam={carried_stats['carried_spam']}, "
            f"chitchat={carried_stats['carried_chitchat']}, "
            f"health_update={carried_stats['carried_health_update']}, "
            f"link_only={carried_stats['carried_link_only']}, "
            f"language={carried_stats['carried_language']}, "
            f"other={carried_stats['carried_other']}."
        )
    per_day = int(settings.get("free_ingest_per_day") or NON_SPAM_PER_DAY)
    fetch_added = 0
    near_dup_before = get_chitchat_log().near_duplicate_blocked
    new_cap = max(int(max_new_posts), 0) if max_new_posts is not None else None
    for since, until in day_windows(moment, days):
        if len(kept) >= target:
            break
        if new_cap is not None and fetch_added >= new_cap:
            break
        day_new = 0
        day_blocked_spam = 0
        day_blocked_other = 0
        for query in chosen:
            if day_new >= per_day or len(kept) >= target:
                break
            if new_cap is not None and fetch_added >= new_cap:
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
            fresh, blocked_spam, blocked_other = keep_edition_quality(
                incoming,
                seen_text=seen_text,
            )
            day_blocked_spam += blocked_spam
            day_blocked_other += blocked_other
            day_new, fetch_added = _accept_fresh_posts(
                fresh,
                kept,
                seen,
                per_day=per_day,
                day_new=day_new,
                target=target,
                new_cap=new_cap,
                fetch_added=fetch_added,
            )
        log = get_chitchat_log()
        print(
            f"Free ingest {since.date().isoformat()}: {day_new} new edition-quality, "
            f"{day_blocked_spam} spam, {day_blocked_other} other filtered "
            f"(chitchat {log.chitchat_blocked}, health_update {log.health_update_blocked}), "
            f"{len(kept)} kept."
        )
    log_fetch_bucket_summary()
    retired = retire_oldest(
        kept,
        now=moment,
        window_hours=window_hours,
        target=target,
    )
    fetch_exhausted = len(retired) < int(target) and fetch_added == 0
    near_duplicate_dropped = get_chitchat_log().near_duplicate_blocked - near_dup_before
    return retired, fetch_exhausted, near_duplicate_dropped


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
