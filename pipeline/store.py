"""SQLite store for raw posts and derived cluster membership.

pipeline/data/ is gitignored. posts are the cleaned extract. topic_membership
and perspectives are derived and can be rebuilt by re-running the pipeline.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB = DATA_DIR / "posts.db"

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
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else DEFAULT_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA)
    return connection


def replace_posts(connection: sqlite3.Connection, posts: list[dict]) -> None:
    """Replace the cleaned post table. Derived tables are cleared with it."""
    connection.execute("DELETE FROM perspectives")
    connection.execute("DELETE FROM topic_membership")
    connection.execute("DELETE FROM posts")
    connection.executemany(
        """
        INSERT INTO posts (uri, author, text, clean_text, likes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                post["uri"],
                post["author"],
                post["text"],
                post["clean_text"],
                int(post["likes"]),
                post.get("created_at") or "",
            )
            for post in posts
        ],
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
