"""Speed test with no Jev: search, a short Jetstream count, planet-build time.

Strips paid API keys before doing any work. Search uses the widened query
list and the last 7 UTC days, and backs off on HTTP 429 and 403.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.free_ingest import NON_SPAM_PER_DAY, WIDE_QUERIES, day_windows, keep_non_spam, paced_fetch
from pipeline.data_sources.extract_bluesky import MAX_SEARCH_PAGES, extract_posts

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "issue-192"
JETSTREAM_URL = (
    "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
)
# Measured Jev cost per call from the issue. Not a live price lookup.
JEV_USD_PER_CALL = 0.0000278
JETSTREAM_SECONDS = 180


def _disable_paid_keys() -> None:
    os.environ.pop("TYPESAFE_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)


async def _jetstream_count(seconds: int) -> dict:
    import websockets

    started = time.monotonic()
    creates = 0
    other = 0
    deadline = started + seconds
    async with websockets.connect(JETSTREAM_URL, open_timeout=20, max_size=2**22) as socket:
        while time.monotonic() < deadline:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=timeout)
            except TimeoutError:
                # The deadline expired during recv. That is the end of the count.
                break
            event = json.loads(raw)
            commit = event.get("commit") or {}
            if (
                event.get("kind") == "commit"
                and commit.get("collection") == "app.bsky.feed.post"
                and commit.get("operation") == "create"
            ):
                creates += 1
            else:
                other += 1
    elapsed = time.monotonic() - started
    per_hour = creates / elapsed * 3600 if elapsed else 0
    return {
        "seconds": round(elapsed, 1),
        "post_creates": creates,
        "other_events": other,
        "posts_per_hour": round(per_hour, 1),
    }


def search_last_seven_days(now: datetime) -> dict:
    started = time.monotonic()
    raw_posts = 0
    requests = 0
    days = []
    seen: set[str] = set()
    texts: list[str] = []
    for since, until in day_windows(now, 7):
        day_raw = 0
        day_kept = 0
        day_blocked = 0
        for query in WIDE_QUERIES:
            if day_kept >= NON_SPAM_PER_DAY:
                break
            before = time.monotonic()
            try:
                incoming = extract_posts(
                    sample_size=NON_SPAM_PER_DAY,
                    window_hours=168,
                    queries=[query],
                    now=now,
                    since=since,
                    until=until,
                    pages=MAX_SEARCH_PAGES,
                    subsample=False,
                    skip_uris=seen,
                    fetch=paced_fetch,
                )
            except RuntimeError as exc:
                print(f"{since.date().isoformat()} {query!r} failed ({exc}).")
                incoming = []
            requests += 1
            kept, blocked = keep_non_spam(incoming)
            day_raw += len(incoming)
            day_blocked += blocked
            raw_posts += len(incoming)
            for post in kept:
                uri = str(post.get("uri") or "")
                if not uri or uri in seen:
                    continue
                seen.add(uri)
                day_kept += 1
                body = str(post.get("clean_text") or post.get("text") or "")
                if body:
                    texts.append(body)
                if day_kept >= NON_SPAM_PER_DAY:
                    break
            print(
                f"{since.date().isoformat()} {query!r}: "
                f"+{len(incoming)} raw in {time.monotonic() - before:.1f}s, "
                f"day non-spam {day_kept}."
            )
        days.append(
            {
                "date": since.date().isoformat(),
                "raw_posts": day_raw,
                "non_spam": day_kept,
                "blocked": day_blocked,
                "hit_14300": day_kept >= NON_SPAM_PER_DAY,
            }
        )
        print(f"Day {since.date().isoformat()}: {day_kept} non-spam, {day_raw} raw.")
    elapsed = time.monotonic() - started
    hours = elapsed / 3600 if elapsed else 0
    non_spam_total = sum(day["non_spam"] for day in days)
    return {
        "elapsed_seconds": round(elapsed, 1),
        "raw_posts": raw_posts,
        "unique_non_spam": non_spam_total,
        "posts_fetched_per_hour": round(raw_posts / hours, 1) if hours else 0,
        "non_spam_per_hour": round(non_spam_total / hours, 1) if hours else 0,
        "query_rounds": requests,
        "queries": len(WIDE_QUERIES),
        "max_pages_per_query": MAX_SEARCH_PAGES,
        "days": days,
        "texts": texts,
    }


def time_planet_build(texts: list[str]) -> dict:
    from pipeline.topics import CANDIDATE_POOL, cluster_texts

    distinct = list(texts)
    padded = list(distinct)
    if padded:
        index = 0
        while len(padded) < 100_000:
            padded.append(distinct[index % len(distinct)])
            index += 1
    target = padded[:100_000]
    started = time.perf_counter()
    clustered = cluster_texts(
        target,
        min_cluster_size=5,
        cluster_backend="embedding",
        embedding_model="all-MiniLM-L6-v2",
        seed=0,
        catalog_size=CANDIDATE_POOL,
    )
    elapsed = time.perf_counter() - started
    planets = len(clustered["topics"])
    return {
        "posts": len(target),
        "distinct_posts": len(distinct),
        "duplicated_to_fill": len(target) > len(distinct),
        "seconds": round(elapsed, 1),
        "candidate_planets": planets,
        "noise_posts": int(clustered.get("noise_count") or 0),
        "jev_usd_at_measured_call_cost": round(planets * JEV_USD_PER_CALL, 6),
        "usd_per_call": JEV_USD_PER_CALL,
    }


def main() -> None:
    _disable_paid_keys()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    async def _both():
        jetstream_task = asyncio.create_task(_jetstream_count(JETSTREAM_SECONDS))
        search = await asyncio.to_thread(search_last_seven_days, now)
        try:
            jetstream = await jetstream_task
        except Exception as exc:
            jetstream = {"error": type(exc).__name__}
            print(f"Jetstream count failed ({type(exc).__name__}).")
        return search, jetstream

    search, jetstream = asyncio.run(_both())
    texts = search.pop("texts")
    print(f"Timing planet build on {min(100_000, max(len(texts), 1))} posts.")
    planets = time_planet_build(texts) if texts else {"error": "no texts"}
    non_spam_days = [day["non_spam"] for day in search["days"]]
    min_day = min(non_spam_days) if non_spam_days else 0
    fetch_hours_for_100k = None
    if search["non_spam_per_hour"]:
        fetch_hours_for_100k = round(100_000 / search["non_spam_per_hour"], 2)
    payload = {
        "generated_at": now.isoformat(),
        "search": search,
        "jetstream": jetstream,
        "planet_build": planets,
        "targets": {
            "non_spam_per_day_min": min_day,
            "non_spam_per_day_bar": NON_SPAM_PER_DAY,
            "hours_to_fetch_100k_non_spam": fetch_hours_for_100k,
            "planet_build_seconds": planets.get("seconds") if isinstance(planets, dict) else None,
        },
    }
    path = EVIDENCE / "speed_test.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in payload if key != "search"}, indent=2))
    print(json.dumps(search, indent=2))


if __name__ == "__main__":
    main()
