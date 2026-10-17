"""Compare the free spam guard to stored Jev spam verdicts. No paid calls.

Restores the corpus the way the daily job does (R2 download, then the
cross-run verdict cache if that file is present). Post text is not in
``jev_verdicts``. Texts are read from the posts table when the row is still
there, and otherwise from the public Bluesky getPosts API, which is free.

Claim versus non-claim is ignored. Spam is ``spam_score >= 0.8`` on a real
Jev model row (not the retained backfill and not a pre-filter row).
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline.jev import SPAM_THRESHOLD
from pipeline.jev_cache import import_persistent_cache
from pipeline.r2 import restore_corpus
from pipeline.spam_guard import guard_reason
from pipeline.store import connect

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "issue-192"
DEFAULT_DB = Path(os.environ.get("PERSPECTIVERSE_CORPUS_DB", "/tmp/perspectiverse-live-corpus/live_corpus.db"))
GET_POSTS = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts"
JEV_MODEL_PREFIX = "jev-"
TEXT_CACHE = Path("/tmp/jev-text-cache.jsonl")


def _disable_paid_keys() -> None:
    os.environ.pop("TYPESAFE_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)


def restore_verdict_db(path: Path) -> sqlite3.Connection:
    """R2 restore, then import the Actions-style cache file when it exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        status = restore_corpus(path)
        print(f"R2 restore: {status}")
    else:
        print(f"Using corpus already at {path} ({path.stat().st_size} bytes).")
    connection = connect(path)
    imported = import_persistent_cache(connection)
    print(f"Imported {imported} verdict row(s) from the cross-run cache file.")
    return connection


def verdict_mix(connection: sqlite3.Connection) -> dict:
    rows = connection.execute(
        """
        SELECT model,
               COUNT(*) AS n,
               SUM(CASE WHEN spam_score IS NULL THEN 1 ELSE 0 END) AS missing,
               SUM(CASE WHEN spam_score >= ? THEN 1 ELSE 0 END) AS spam,
               SUM(CASE WHEN spam_score < ? THEN 1 ELSE 0 END) AS not_spam
        FROM jev_verdicts
        GROUP BY model
        ORDER BY n DESC
        """,
        (SPAM_THRESHOLD, SPAM_THRESHOLD),
    ).fetchall()
    by_model = [
        {"model": model, "rows": n, "spam_score_missing": missing or 0, "spam": spam or 0, "not_spam": not_spam or 0}
        for model, n, missing, spam, not_spam in rows
    ]
    jev_rows = [item for item in by_model if str(item["model"]).startswith(JEV_MODEL_PREFIX)]
    spam = sum(item["spam"] for item in jev_rows)
    not_spam = sum(item["not_spam"] for item in jev_rows)
    posts = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    posts_spam = connection.execute(
        "SELECT COUNT(*) FROM posts WHERE spam_score >= ?",
        (SPAM_THRESHOLD,),
    ).fetchone()[0]
    joined_spam = connection.execute(
        """
        SELECT COUNT(*) FROM jev_verdicts v
        JOIN posts p ON p.uri = v.uri
        WHERE v.model LIKE 'jev-%' AND v.spam_score >= ?
        """,
        (SPAM_THRESHOLD,),
    ).fetchone()[0]
    return {
        "rows": sum(item["rows"] for item in by_model),
        "by_model": by_model,
        "jev_spam": spam,
        "jev_not_spam": not_spam,
        "jev_spam_share": round(spam / (spam + not_spam), 4) if spam + not_spam else None,
        "posts_table_rows": posts,
        "posts_table_spam": posts_spam,
        "jev_spam_rows_still_in_posts_table": joined_spam,
        "bias": (
            "The posts table keeps claims Jev did not call spam, so it cannot "
            "measure spam leaks. Spam texts are hydrated from Bluesky by the stored URI. "
            "Posts Bluesky no longer returns are missing from the confusion matrix."
        ),
    }


def _load_text_cache() -> dict[str, str]:
    found: dict[str, str] = {}
    if not TEXT_CACHE.is_file():
        return found
    for line in TEXT_CACHE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        uri = str(row.get("uri") or "")
        text = str(row.get("text") or "")
        if uri and text:
            found[uri] = text
    return found


def _append_text_cache(rows: dict[str, str]) -> None:
    if not rows:
        return
    with TEXT_CACHE.open("a", encoding="utf-8") as handle:
        for uri, text in rows.items():
            handle.write(json.dumps({"uri": uri, "text": text}, ensure_ascii=False) + "\n")


def _fetch_texts(uris: list[str]) -> dict[str, str]:
    found = _load_text_cache()
    pending = [uri for uri in uris if uri not in found]
    print(f"Text cache has {len(found)}. Fetching {len(pending)}.")
    for start in range(0, len(pending), 15):
        chunk = pending[start : start + 15]
        query = "&".join("uris=" + urllib.parse.quote(uri, safe="") for uri in chunk)
        request = urllib.request.Request(
            f"{GET_POSTS}?{query}",
            headers={"Accept": "application/json", "User-Agent": "perspectiverse-pipeline/0.2"},
        )
        delay = 1.0
        payload: dict = {}
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except Exception as exc:
                message = str(exc)
                if "429" not in message and "403" not in message and attempt == 4:
                    print(f"getPosts failed: {message[:120]}")
                    payload = {}
                    break
                if "429" not in message and "403" not in message:
                    print(f"getPosts failed: {message[:120]}")
                    payload = {}
                    break
                time.sleep(delay)
                delay = min(delay * 2, 30)
        else:
            payload = {}
        batch: dict[str, str] = {}
        for post in payload.get("posts") or []:
            uri = str(post.get("uri") or "")
            text = str((post.get("record") or {}).get("text") or "")
            if uri and text:
                batch[uri] = text
                found[uri] = text
        _append_text_cache(batch)
        if start and start % 1500 == 0:
            print(f"Hydrated {start} of {len(pending)}.")
        time.sleep(0.12)
    return found


def confusion(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs are (jev_spam, guard_blocked)."""
    matrix = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for jev_spam, blocked in pairs:
        if jev_spam and blocked:
            matrix["tp"] += 1
        elif jev_spam and not blocked:
            matrix["fn"] += 1
        elif not jev_spam and blocked:
            matrix["fp"] += 1
        else:
            matrix["tn"] += 1
    spam = matrix["tp"] + matrix["fn"]
    not_spam = matrix["fp"] + matrix["tn"]
    blocked = matrix["tp"] + matrix["fp"]
    return {
        "true_positive_blocked_spam": matrix["tp"],
        "false_negative_spam_leaked": matrix["fn"],
        "false_positive_non_spam_blocked": matrix["fp"],
        "true_negative_non_spam_passed": matrix["tn"],
        "jev_spam_evaluated": spam,
        "jev_not_spam_evaluated": not_spam,
        "spam_leak_rate_among_jev_spam": round(matrix["fn"] / spam, 4) if spam else None,
        "wrongly_blocked_rate_among_jev_not_spam": round(matrix["fp"] / not_spam, 4) if not_spam else None,
        "blocked": blocked,
    }


def evaluate(connection: sqlite3.Connection, *, not_spam_sample: int, seed: int) -> dict:
    jev_spam = [
        row[0]
        for row in connection.execute(
            """
            SELECT uri FROM jev_verdicts
            WHERE model LIKE 'jev-%' AND spam_score >= ?
            """,
            (SPAM_THRESHOLD,),
        )
    ]
    jev_ok = [
        row[0]
        for row in connection.execute(
            """
            SELECT uri FROM jev_verdicts
            WHERE model LIKE 'jev-%' AND spam_score < ?
            """,
            (SPAM_THRESHOLD,),
        )
    ]
    rng = random.Random(seed)
    ok_sample = jev_ok if len(jev_ok) <= not_spam_sample else rng.sample(jev_ok, not_spam_sample)
    stored_text = {
        uri: text
        for uri, text in connection.execute("SELECT uri, text FROM posts")
        if uri and text
    }
    need = [uri for uri in jev_spam + ok_sample if uri not in stored_text]
    print(f"Hydrating {len(need)} post texts ({len(jev_spam)} spam URIs, {len(ok_sample)} non-spam URIs).")
    hydrated = _fetch_texts(need)
    texts = dict(stored_text)
    texts.update(hydrated)
    pairs = []
    missing_spam = 0
    missing_ok = 0
    for uri in jev_spam:
        text = texts.get(uri)
        if not text:
            missing_spam += 1
            continue
        pairs.append((True, guard_reason({"text": text}) is not None))
    for uri in ok_sample:
        text = texts.get(uri)
        if not text:
            missing_ok += 1
            continue
        pairs.append((False, guard_reason({"text": text}) is not None))
    report = confusion(pairs)
    report["spam_uris"] = len(jev_spam)
    report["not_spam_uris_sampled"] = len(ok_sample)
    report["not_spam_uris_in_cache"] = len(jev_ok)
    report["spam_texts_missing"] = missing_spam
    report["not_spam_texts_missing"] = missing_ok
    report["not_spam_sample_is_full_cache"] = len(ok_sample) == len(jev_ok)
    return report


def fresh_passed_posts(*, queries: list[str], pages: int, per_query: int, want: int, seed: int) -> list[dict]:
    """Unfiltered search, then the guard. Returns guard-passed posts, shuffled."""
    from pipeline.data_sources.extract_bluesky import extract_posts

    collected: list[dict] = []
    seen: set[str] = set()
    for query in queries:
        batch = extract_posts(
            sample_size=per_query * pages,
            window_hours=168,
            queries=[query],
            pages=pages,
            per_query=per_query,
            subsample=False,
            skip_uris=seen,
        )
        for post in batch:
            uri = str(post.get("uri") or "")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            collected.append(post)
        if len(collected) >= want * 3:
            break
    passed = [post for post in collected if guard_reason(post) is None]
    rng = random.Random(seed)
    rng.shuffle(passed)
    print(f"Fresh search {len(collected)} posts, {len(passed)} passed the guard.")
    return passed[:want]


def main() -> None:
    _disable_paid_keys()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    connection = restore_verdict_db(DEFAULT_DB)
    try:
        mix = verdict_mix(connection)
        matrix = evaluate(connection, not_spam_sample=8000, seed=192)
    finally:
        connection.close()
    sample = fresh_passed_posts(
        queries=["the", "and", "to", "of", "in", "for", "you", "it", "is", "this"],
        pages=3,
        per_query=100,
        want=200,
        seed=192,
    )
    sample_path = EVIDENCE / "agent_check_sample.json"
    sample_path.write_text(
        json.dumps(
            [
                {
                    "n": index + 1,
                    "uri": post.get("uri"),
                    "created_at": post.get("created_at"),
                    "author": post.get("author"),
                    "text": post.get("text"),
                }
                for index, post in enumerate(sample)
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = {"mix": mix, "confusion": matrix, "fresh_passed_sample": len(sample), "sample_file": str(sample_path)}
    out = EVIDENCE / "jev_comparison.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
