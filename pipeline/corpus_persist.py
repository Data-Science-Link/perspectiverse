"""Persist paid ingest work when the daily spend cap halts before publish.

A stop still must not replace ``public/data.json``. The retained SQLite corpus
is staged outside the git worktree and uploaded to R2 from the workflow so
``hold-edition`` cannot delete it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

from pipeline.store import connect, replace_posts

MARKER_FILENAME = "halt_corpus.sha256"
CORPUS_FILENAME = "live_corpus.db"
JEV_CACHE_FILENAME = "jev_verdict_cache.sqlite"
ENV_STAGING = "PERSPECTIVERSE_HALT_STAGING"


def staging_root() -> Path:
    raw = (os.getenv(ENV_STAGING) or "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "perspectiverse-halt-corpus"


def marker_path(db_dir: Path | None = None) -> Path:
    if db_dir is not None:
        return Path(db_dir) / MARKER_FILENAME
    return staging_root() / MARKER_FILENAME


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_corpus_marker(db_path: Path, *, also_staging: bool = True) -> str:
    """Write the corpus digest beside the db and in the halt staging dir."""
    digest = sha256_file(db_path)
    marker_path(db_path.parent).write_text(digest + "\n", encoding="utf-8")
    if also_staging:
        root = staging_root()
        root.mkdir(parents=True, exist_ok=True)
        (root / MARKER_FILENAME).write_text(digest + "\n", encoding="utf-8")
    return digest


def stage_halted_corpus(db_path: Path) -> Path | None:
    """Copy the corpus and Jev cache outside the repo. Never raises."""
    database = Path(db_path)
    if not database.is_file():
        print(f"Halt staging: no corpus at {database}", file=sys.stderr)
        return None
    try:
        root = staging_root()
        root.mkdir(parents=True, exist_ok=True)
        staged_db = root / CORPUS_FILENAME
        shutil.copy2(database, staged_db)
        write_corpus_marker(staged_db, also_staging=True)
        write_corpus_marker(database, also_staging=False)
        from pipeline.jev_cache import active_cache_path

        cache = active_cache_path()
        if cache is not None and cache.is_file():
            shutil.copy2(cache, root / JEV_CACHE_FILENAME)
        print(f"Halt staging: copied corpus to {staged_db}")
        return staged_db
    except Exception as exc:
        print(f"WARNING: Halt corpus staging skipped: {exc}", file=sys.stderr)
        return None


def verify_staged_corpus(staged_db: Path, marker_file: Path | None = None) -> bool:
    """True when the staged file exists and matches its marker."""
    if not staged_db.is_file():
        return False
    marker = marker_file if marker_file is not None else marker_path(staging_root())
    if not marker.is_file():
        return False
    expected = marker.read_text(encoding="utf-8").strip()
    if not expected:
        return False
    return sha256_file(staged_db) == expected


def upload_staged_corpus() -> int:
    """Upload the staged corpus when the marker matches. Never uploads a missing file."""
    root = staging_root()
    staged_db = root / CORPUS_FILENAME
    if not verify_staged_corpus(staged_db):
        print("Halt R2 upload: staged corpus missing or marker mismatch; not uploading.", file=sys.stderr)
        return 1
    try:
        from pipeline.r2 import upload_corpus

        status = upload_corpus(staged_db)
        if status == "uploaded":
            print(f"Halt R2 upload: uploaded {staged_db}")
            return 0
        if status == "unconfigured":
            print("Halt R2 upload: R2 unconfigured.", file=sys.stderr)
            return 0
        print(f"Halt R2 upload: unexpected status {status}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"::error::Halt R2 upload failed: {exc}", file=sys.stderr)
        return 1


def persist_paid_corpus(
    connection,
    posts: list[dict] | None,
    *,
    db_path: Path,
) -> None:
    """Write scored posts and the Jev cache file. Stage for R2 in the workflow.

    Never raises: a persistence failure must not hide the spend-cap stop.
    """
    try:
        if posts:
            replace_posts(connection, posts)
        from pipeline.jev_cache import export_persistent_cache

        export_persistent_cache(connection)
        connection.commit()
        stage_halted_corpus(db_path)
    except Exception as exc:
        print(
            f"WARNING: Could not save the retained corpus after a spend-cap stop: {exc}",
            file=sys.stderr,
        )


def reopen_and_persist(posts: list[dict] | None, db_path: Path) -> None:
    """Open ``db_path``, persist, and close. For callers that already closed."""
    connection = connect(db_path)
    try:
        persist_paid_corpus(connection, posts, db_path=db_path)
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage or upload the corpus after a halted pipeline run")
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage-for-halt", help="Copy live_corpus.db outside the git worktree")
    stage.add_argument("--db", type=Path, required=True)
    upload = sub.add_parser("upload-staged", help="Upload the staged corpus when the marker matches")
    args = parser.parse_args(argv)
    if args.command == "stage-for-halt":
        return 0 if stage_halted_corpus(args.db) is not None else 1
    if args.command == "upload-staged":
        return upload_staged_corpus()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
