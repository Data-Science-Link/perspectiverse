"""Bounded Jev verdict cache that survives a fresh Actions runner.

The retained corpus already stores ``jev_verdicts`` inside ``live_corpus.db``
(R2). That table is not a separate Actions cache: a runner that starts from a
corpus without the table scores every post again. This module copies the
table to ``pipeline/data/jev_verdict_cache.sqlite``, which the daily workflow
restores with ``actions/cache``. The file is capped so the saved object stays
small enough for that cache.

Rows are still dropped after 14 days by ``expire_jev_verdicts``. The cap here
is the size bound on top of that window: oldest ``scored_on`` first.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from pipeline.store import DATA_DIR, RETAINED_VERDICT_MODEL

# Newest verdicts kept. At ~250 bytes a row this is about 80 MB, under the
# GitHub Actions cache comfort zone and under GitHub's 100 MB file limit if a
# copy is ever committed. 320k rows covers a 100k-claim window plus several
# days of top-up non-claims; older rows fall off before the 14-day TTL does
# only when the day scores more than this cap.
JEV_CACHE_MAX_ROWS = 320_000
JEV_CACHE_MAX_BYTES = 80 * 1024 * 1024
CACHE_FILENAME = "jev_verdict_cache.sqlite"
_ENV_PATH = "JEV_VERDICT_CACHE"

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS jev_verdicts (
    uri TEXT PRIMARY KEY,
    spam_score REAL,
    claim_score REAL,
    section TEXT,
    model TEXT NOT NULL,
    scored_on TEXT NOT NULL,
    text_fp TEXT NOT NULL DEFAULT ''
);
"""


def default_cache_path() -> Path:
    return DATA_DIR / CACHE_FILENAME


def active_cache_path() -> Path | None:
    """Where this process reads and writes the cross-run file.

    Pytest leaves the file off unless ``JEV_VERDICT_CACHE`` is set, so a
    leftover file cannot change call counts. Production uses the default path.
    """
    raw = (os.getenv(_ENV_PATH) or "").strip()
    if raw:
        return Path(raw)
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    return default_cache_path()


def enforce_jev_cache_bound(connection: sqlite3.Connection, *, max_rows: int = JEV_CACHE_MAX_ROWS) -> int:
    """Delete the oldest verdicts until the table is within ``max_rows``."""
    limit = max(0, int(max_rows))
    total = int(connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0])
    extra = total - limit
    if extra <= 0:
        return 0
    connection.execute(
        """
        DELETE FROM jev_verdicts
        WHERE uri IN (
            SELECT uri FROM jev_verdicts
            ORDER BY scored_on ASC, uri ASC
            LIMIT ?
        )
        """,
        (extra,),
    )
    connection.commit()
    return extra


def import_persistent_cache(connection: sqlite3.Connection, path: Path | None = None) -> int:
    """Copy rows from the cross-run file into ``connection``.

    A newer ``scored_on`` replaces an older row. A real Jev answer replaces a
    retained backfill on the same day. Returns how many URIs were inserted or
    updated. Never raises.
    """
    cache = path if path is not None else active_cache_path()
    if cache is None or not cache.is_file():
        return 0
    try:
        connection.execute("ATTACH DATABASE ? AS jev_cache", (str(cache),))
        try:
            present = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM jev_cache.sqlite_master WHERE type = 'table'"
                )
            }
            if "jev_verdicts" not in present:
                return 0
            before = int(connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0])
            cursor = connection.execute(
                """
                INSERT INTO jev_verdicts (
                    uri, spam_score, claim_score, section, model, scored_on, text_fp
                )
                SELECT uri, spam_score, claim_score, section, model, scored_on, text_fp
                FROM jev_cache.jev_verdicts
                WHERE uri != ''
                ON CONFLICT(uri) DO UPDATE SET
                    spam_score = excluded.spam_score,
                    claim_score = excluded.claim_score,
                    section = excluded.section,
                    model = excluded.model,
                    scored_on = excluded.scored_on,
                    text_fp = excluded.text_fp
                WHERE excluded.scored_on > jev_verdicts.scored_on
                   OR (
                        excluded.scored_on = jev_verdicts.scored_on
                        AND jev_verdicts.model = ?
                        AND excluded.model != ?
                   )
                """,
                (RETAINED_VERDICT_MODEL, RETAINED_VERDICT_MODEL),
            )
            connection.commit()
            return int(cursor.rowcount) if cursor.rowcount and cursor.rowcount > 0 else max(
                0,
                int(connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0]) - before,
            )
        finally:
            connection.execute("DETACH DATABASE jev_cache")
    except Exception as exc:
        sys.stderr.write(f"WARNING: Jev verdict cache file was not read: {exc}\n")
        try:
            connection.execute("DETACH DATABASE jev_cache")
        except sqlite3.Error:
            pass
        return 0


def export_persistent_cache(
    connection: sqlite3.Connection,
    path: Path | None = None,
    *,
    max_rows: int = JEV_CACHE_MAX_ROWS,
    max_bytes: int = JEV_CACHE_MAX_BYTES,
) -> Path | None:
    """Write a bounded snapshot of ``jev_verdicts``. Never raises.

    The row cap is applied to ``connection`` as well, so the corpus and the
    file agree. The byte cap only shrinks the snapshot (and then the corpus)
    when the file would exceed ``max_bytes``.
    """
    cache = path if path is not None else active_cache_path()
    if cache is None:
        return None
    try:
        enforce_jev_cache_bound(connection, max_rows=max_rows)
        cache.parent.mkdir(parents=True, exist_ok=True)
        _write_snapshot(connection, cache)
        guard = 0
        previous = None
        while cache.is_file() and cache.stat().st_size > max_bytes and guard < 24:
            size = cache.stat().st_size
            # An empty SQLite file is still a few pages. Stop once shrinking
            # the table no longer shrinks the file.
            if previous is not None and size >= previous:
                break
            previous = size
            guard += 1
            total = int(connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0])
            if total <= 0:
                break
            drop = max(1, total // 2)
            enforce_jev_cache_bound(connection, max_rows=total - drop)
            _write_snapshot(connection, cache)
        return cache
    except Exception as exc:
        sys.stderr.write(f"WARNING: Jev verdict cache file was not written: {exc}\n")
        return None


def _write_snapshot(connection: sqlite3.Connection, cache: Path) -> None:
    temporary = cache.with_suffix(cache.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    snapshot = sqlite3.connect(temporary)
    try:
        snapshot.executescript(_CACHE_SCHEMA)
        rows = connection.execute(
            """
            SELECT uri, spam_score, claim_score, section, model, scored_on, text_fp
            FROM jev_verdicts
            """
        ).fetchall()
        snapshot.executemany(
            """
            INSERT INTO jev_verdicts (
                uri, spam_score, claim_score, section, model, scored_on, text_fp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        snapshot.commit()
    finally:
        snapshot.close()
    temporary.replace(cache)


def replay_same_posts(directory: Path) -> dict:
    """Score one fixed post list twice. The second pass reopens the database.

    Run 2 must reuse run 1's verdicts (no paid calls). A third pass opens a
    brand-new database and reads only the cache file, which is what a fresh
    Actions runner does when the corpus file does not yet hold the table.
    """
    from pipeline.costs import get_meter, jev_cache_log_line, jev_filter_counts, reset_meter
    from pipeline.jev import apply_jev, reset_jev_state
    from pipeline.store import connect

    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "corpus.db"
    cache_file = directory / CACHE_FILENAME
    saved = {
        "TYPESAFE_API_KEY": os.environ.get("TYPESAFE_API_KEY"),
        _ENV_PATH: os.environ.get(_ENV_PATH),
    }
    calls = {"n": 0}
    call_lock = __import__("threading").Lock()

    def fake(url, **kwargs):
        del url, kwargs
        with call_lock:
            calls["n"] += 1
        return {
            "model": "jev-replay",
            "answers": {
                "spam": {"type": "noul", "noul": 0.05},
                "section": {
                    "type": "choice",
                    "choice": "Politics",
                    "confidence": 0.8,
                    "probabilities": {"Politics": 0.8, "Other": 0.2},
                },
                "claim": {"type": "noul", "noul": 0.91},
            },
            "usage": {"input_tokens": 600, "output_tokens": 12},
        }

    posts = [_replay_post(uri, text) for uri, text in _REPLAY_POSTS]
    try:
        os.environ["TYPESAFE_API_KEY"] = "replay-test-key"
        os.environ[_ENV_PATH] = str(cache_file)
        import pipeline.jev as jev_module

        original = jev_module.read_json
        jev_module.read_json = fake
        try:
            run1 = _one_pass(apply_jev, connect, reset_meter, reset_jev_state, database, posts, calls)
            run1["line"] = jev_cache_log_line()
            run1["hits"] = jev_filter_counts()["cache_hits"]
            run1["lookups"] = jev_filter_counts()["lookups"]
            run1["paid_calls"] = sum(1 for attempt in get_meter().attempts() if attempt.service == "typesafe-jev")
            run1["cost_usd"] = str(sum((attempt.cost_usd for attempt in get_meter().attempts() if attempt.service == "typesafe-jev"), start=_zero()))

            calls["n"] = 0
            run2 = _one_pass(apply_jev, connect, reset_meter, reset_jev_state, database, posts, calls)
            run2["line"] = jev_cache_log_line()
            run2["hits"] = jev_filter_counts()["cache_hits"]
            run2["lookups"] = jev_filter_counts()["lookups"]
            run2["paid_calls"] = sum(1 for attempt in get_meter().attempts() if attempt.service == "typesafe-jev")
            run2["cost_usd"] = str(sum((attempt.cost_usd for attempt in get_meter().attempts() if attempt.service == "typesafe-jev"), start=_zero()))

            fresh = directory / "fresh.db"
            calls["n"] = 0
            file_only = _one_pass(apply_jev, connect, reset_meter, reset_jev_state, fresh, posts, calls)
            file_only["line"] = jev_cache_log_line()
            file_only["hits"] = jev_filter_counts()["cache_hits"]
            file_only["lookups"] = jev_filter_counts()["lookups"]
            file_only["paid_calls"] = sum(1 for attempt in get_meter().attempts() if attempt.service == "typesafe-jev")
            file_only["cost_usd"] = str(sum((attempt.cost_usd for attempt in get_meter().attempts() if attempt.service == "typesafe-jev"), start=_zero()))
        finally:
            jev_module.read_json = original
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return {"posts": len(posts), "run1": run1, "run2": run2, "file_only": file_only}


def _zero():
    from decimal import Decimal

    return Decimal("0")


def _one_pass(apply_jev, connect, reset_meter, reset_jev_state, database: Path, posts: list[dict], calls: dict) -> dict:
    reset_meter()
    reset_jev_state()
    before = calls["n"]
    connection = connect(database)
    try:
        # Drop sections so this pass looks like a new fetch, not retained-corpus dedup.
        fresh = [{key: value for key, value in post.items() if key != "section"} for post in posts]
        apply_jev(fresh, connection=connection)
    finally:
        connection.close()
    return {"http_calls": calls["n"] - before}


def _replay_post(uri: str, text: str) -> dict:
    return {
        "uri": uri,
        "author": "ada",
        "text": text,
        "clean_text": text,
        "likes": 1,
        "created_at": "2026-10-12T00:00:00Z",
    }


_REPLAY_POSTS = (
    (
        "at://replay/ballot",
        "Congress should publish the mail ballot rules before November arrives.",
    ),
    (
        "at://replay/housing",
        "The city should build public housing near the train station this year.",
    ),
    (
        "at://replay/nurses",
        "Hospitals need more nurses before the winter flu season begins again.",
    ),
    (
        "at://replay/tuition",
        "Universities should cut tuition for students who work while they study.",
    ),
)
