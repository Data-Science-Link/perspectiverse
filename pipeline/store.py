"""SQLite store for raw posts and derived cluster membership.

``pipeline/data/posts.db`` stays gitignored scratch. The retained live window
is ``pipeline/data/live_corpus.db``. That file is tracked as a seed. When the
R2 secrets are set, the daily job downloads and uploads it instead of growing
the git blob. topic_membership and perspectives are derived and rebuilt each run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB = DATA_DIR / "posts.db"
LIVE_CORPUS_DB = DATA_DIR / "live_corpus.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    uri TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    likes INTEGER NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS topic_membership (
    uri TEXT PRIMARY KEY,
    topic_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS perspectives (
    uri TEXT PRIMARY KEY,
    topic_id INTEGER NOT NULL,
    face_index INTEGER NOT NULL,
    distance REAL
);
CREATE TABLE IF NOT EXISTS fetched_days (
    utc_date TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    kept INTEGER NOT NULL
);
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

_POST_COLUMNS = (
    ("section", "TEXT"),
    ("section_confidence", "REAL"),
    ("spam_score", "REAL"),
    ("is_claim", "INTEGER"),
)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else DEFAULT_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA)
    present = {row[1] for row in connection.execute("PRAGMA table_info(posts)")}
    for name, declaration in _POST_COLUMNS:
        if name not in present:
            connection.execute(f"ALTER TABLE posts ADD COLUMN {name} {declaration}")
    connection.commit()
    return connection


def replace_posts(connection: sqlite3.Connection, posts: list[dict]) -> None:
    """Replace the cleaned post table. Derived tables are cleared with it."""
    connection.execute("DELETE FROM perspectives")
    connection.execute("DELETE FROM topic_membership")
    connection.execute("DELETE FROM posts")
    connection.executemany(
        """
        INSERT INTO posts (
            uri, author, text, clean_text, likes, created_at,
            section, section_confidence, spam_score, is_claim
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                post["uri"],
                post["author"],
                post["text"],
                post["clean_text"],
                int(post["likes"]),
                post.get("created_at") or "",
                post.get("section") or None,
                post.get("section_confidence"),
                post.get("spam_score"),
                _claim_bit(post.get("is_claim")),
            )
            for post in posts
        ],
    )
    connection.commit()


def load_posts(connection: sqlite3.Connection) -> list[dict]:
    """Return cleaned posts currently in the store, oldest first."""
    rows = connection.execute(
        """
        SELECT uri, author, text, clean_text, likes, created_at,
               section, section_confidence, spam_score, is_claim
        FROM posts
        ORDER BY created_at ASC
        """
    ).fetchall()
    return [
        {
            "uri": row[0],
            "author": row[1],
            "text": row[2],
            "clean_text": row[3],
            "likes": int(row[4] or 0),
            "created_at": row[5] or "",
            "section": row[6] or "",
            "section_confidence": row[7],
            "spam_score": row[8],
            "is_claim": None if row[9] is None else bool(row[9]),
        }
        for row in rows
    ]


def _claim_bit(value) -> int | None:
    """Store a claim decision. ``None`` means Jev has not been asked."""
    if value is None or value == "":
        return None
    return 1 if value in (True, 1, "1") else 0


def fetched_day_set(connection: sqlite3.Connection) -> set[str]:
    """UTC dates that already have a successful public fetch."""
    rows = connection.execute("SELECT utc_date FROM fetched_days").fetchall()
    return {str(row[0]) for row in rows}


def record_fetched_days(connection: sqlite3.Connection, dates: list[str], *, fetched_at: str, kept: int) -> None:
    """Remember a successful public fetch so that UTC day is not searched again."""
    connection.executemany(
        """
        INSERT INTO fetched_days (utc_date, fetched_at, kept)
        VALUES (?, ?, ?)
        ON CONFLICT(utc_date) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            kept = excluded.kept
        """,
        [(day, fetched_at, int(kept)) for day in dates],
    )
    connection.commit()


# Verdicts older than this many days are deleted. A row dated today minus
# this many days is still inside the window.
JEV_VERDICT_TTL_DAYS = 14
RETAINED_VERDICT_MODEL = "retained"


def expire_jev_verdicts(connection: sqlite3.Connection, today: str, *, ttl_days: int = JEV_VERDICT_TTL_DAYS) -> int:
    """Drop verdicts older than the cache window. ``today`` is a UTC date."""
    from datetime import date, timedelta

    cutoff = (date.fromisoformat(today) - timedelta(days=int(ttl_days))).isoformat()
    cursor = connection.execute("DELETE FROM jev_verdicts WHERE scored_on < ?", (cutoff,))
    connection.commit()
    return int(cursor.rowcount)


def load_jev_verdicts(connection: sqlite3.Connection, uris: list[str]) -> dict[str, tuple]:
    """Return cache rows for these URIs. Missing URIs are absent."""
    found: dict[str, tuple] = {}
    unique = [uri for uri in dict.fromkeys(uris) if uri]
    if not unique:
        return found
    connection.execute("CREATE TEMP TABLE IF NOT EXISTS _jev_lookup (uri TEXT PRIMARY KEY)")
    connection.execute("DELETE FROM _jev_lookup")
    chunk = 400
    for start in range(0, len(unique), chunk):
        part = [(uri,) for uri in unique[start : start + chunk]]
        connection.executemany("INSERT OR IGNORE INTO _jev_lookup (uri) VALUES (?)", part)
    rows = connection.execute(
        """
        SELECT verdict.uri, verdict.spam_score, verdict.claim_score, verdict.section,
               verdict.model, verdict.scored_on, verdict.text_fp
        FROM jev_verdicts AS verdict
        JOIN _jev_lookup AS wanted ON wanted.uri = verdict.uri
        """
    ).fetchall()
    connection.execute("DELETE FROM _jev_lookup")
    for row in rows:
        found[str(row[0])] = row
    return found


def load_jev_fingerprints(connection: sqlite3.Connection) -> list[str]:
    """Simhashes of scored posts, for the near-duplicate index."""
    rows = connection.execute(
        "SELECT text_fp FROM jev_verdicts WHERE text_fp != ''"
    ).fetchall()
    return [str(row[0]) for row in rows]


def jev_verdict_uris(connection: sqlite3.Connection) -> set[str]:
    """Every URI still inside the cache window."""
    rows = connection.execute("SELECT uri FROM jev_verdicts").fetchall()
    return {str(row[0]) for row in rows}


def save_jev_verdicts(connection: sqlite3.Connection, rows: list[tuple]) -> None:
    """Insert Jev answers. A real answer replaces a retained-corpus backfill."""
    connection.executemany(
        """
        INSERT INTO jev_verdicts (
            uri, spam_score, claim_score, section, model, scored_on, text_fp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(uri) DO UPDATE SET
            spam_score = excluded.spam_score,
            claim_score = excluded.claim_score,
            section = excluded.section,
            model = excluded.model,
            scored_on = excluded.scored_on,
            text_fp = excluded.text_fp
        """,
        rows,
    )
    connection.commit()


def remember_retained_verdicts(connection: sqlite3.Connection, rows: list[tuple]) -> None:
    """Remember claims already in the corpus without a second Jev call.

    A row already scored by Jev is left alone. A backfill row's date is
    refreshed while the claim is still in the window, and it then expires
    ``JEV_VERDICT_TTL_DAYS`` after the claim leaves.
    """
    connection.executemany(
        """
        INSERT INTO jev_verdicts (
            uri, spam_score, claim_score, section, model, scored_on, text_fp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(uri) DO UPDATE SET
            scored_on = excluded.scored_on,
            text_fp = CASE
                WHEN jev_verdicts.text_fp = '' THEN excluded.text_fp
                ELSE jev_verdicts.text_fp
            END
        WHERE jev_verdicts.model = ?
        """,
        [(*row, RETAINED_VERDICT_MODEL) for row in rows],
    )
    connection.commit()


def write_clusters(
    connection: sqlite3.Connection,
    membership: list[tuple[str, int]],
    faces: list[tuple[str, int, int, float]],
) -> None:
    """Persist topic ids and face indexes for the posts that were kept."""
    connection.execute("DELETE FROM perspectives")
    connection.execute("DELETE FROM topic_membership")
    connection.executemany(
        "INSERT INTO topic_membership (uri, topic_id) VALUES (?, ?)",
        membership,
    )
    connection.executemany(
        """
        INSERT INTO perspectives (uri, topic_id, face_index, distance)
        VALUES (?, ?, ?, ?)
        """,
        faces,
    )
    connection.commit()
