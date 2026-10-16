"""Persist paid ingest work when the daily spend cap halts before publish.

A stop still must not replace ``public/data.json``. The retained SQLite corpus
(and R2 when configured) is updated so the next run reuses Jev verdicts
instead of paying again.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pipeline.store import connect, replace_posts


def persist_paid_corpus(
    connection,
    posts: list[dict] | None,
    *,
    db_path: Path,
) -> None:
    """Write scored posts and the Jev cache file. Optionally upload to R2.

    Never raises: a persistence failure must not hide the spend-cap stop.
    """
    try:
        if posts:
            replace_posts(connection, posts)
        from pipeline.jev_cache import export_persistent_cache

        export_persistent_cache(connection)
        connection.commit()
    except Exception as exc:
        print(
            f"WARNING: Could not save the retained corpus after a spend-cap stop: {exc}",
            file=sys.stderr,
        )
        return
    try:
        from pipeline.r2 import upload_corpus

        status = upload_corpus(Path(db_path))
        if status == "uploaded":
            print(f"Spend cap stop: uploaded retained corpus to R2 ({db_path}).")
        elif status == "unconfigured":
            print("Spend cap stop: R2 unconfigured; corpus saved locally only.")
    except Exception as exc:
        print(
            f"WARNING: R2 upload skipped after a spend-cap stop: {exc}",
            file=sys.stderr,
        )


def reopen_and_persist(posts: list[dict] | None, db_path: Path) -> None:
    """Open ``db_path``, persist, and close. For callers that already closed."""
    connection = connect(db_path)
    try:
        persist_paid_corpus(connection, posts, db_path=db_path)
    finally:
        connection.close()
