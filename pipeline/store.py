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
"""

_POST_COLUMNS = (
    ("section", "TEXT"),
    ("section_confidence", "REAL"),
    ("spam_score", "REAL"),
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
            section, section_confidence, spam_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
               section, section_confidence, spam_score
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
        }
        for row in rows
    ]


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
