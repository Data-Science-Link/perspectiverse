"""Compact helpers for the synthetic face catalog."""

from __future__ import annotations

from typing import Any


def faces(*entries: tuple[str, str, tuple[str, ...], tuple[tuple[str, str], ...]]) -> list[dict[str, Any]]:
    """Expand (title, summary, arguments, posts) tuples into schema-shaped briefs."""
    out: list[dict[str, Any]] = []
    for title, summary, arguments, posts in entries:
        if len(arguments) < 2:
            raise ValueError(f"{title} needs at least two core arguments")
        if len(posts) < 2:
            raise ValueError(f"{title} needs at least two posts")
        out.append(
            {
                "title": title,
                "summary": summary,
                "arguments": list(arguments),
                "posts": [{"author": author, "text": text} for author, text in posts],
            }
        )
    return out
