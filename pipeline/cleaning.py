"""Normalize post text before clustering."""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HANDLE_RE = re.compile(r"@[A-Za-z0-9._-]+")
WHITESPACE_RE = re.compile(r"\s+")
REPEAT_RE = re.compile(r"(.)\1{7,}")


def clean_text(text: str) -> str:
    """Strip URLs and handles and collapse whitespace."""
    without_urls = URL_RE.sub(" ", text or "")
    without_handles = HANDLE_RE.sub(" ", without_urls)
    return WHITESPACE_RE.sub(" ", without_handles).strip()


def is_spam(text: str) -> bool:
    """Drop scraps and obvious junk. Real argument can be short; this is conservative."""
    if len(text) < 24:
        return True
    if REPEAT_RE.search(text):
        return True
    if text.count("#") > 6:
        return True
    if text.lower().count("buy followers") >= 2:
        return True
    return False


def clean_posts(posts: list[dict]) -> list[dict]:
    """Return posts that survived cleaning, preserving likes and identity."""
    cleaned: list[dict] = []
    seen: set[str] = set()
    for post in posts:
        uri = str(post.get("uri") or "")
        if not uri or uri in seen:
            continue
        text = clean_text(str(post.get("text") or ""))
        if is_spam(text):
            continue
        seen.add(uri)
        cleaned.append(
            {
                "uri": uri,
                "author": str(post.get("author") or "unknown"),
                "text": str(post.get("text") or ""),
                "clean_text": text,
                "likes": int(post.get("likes") or 0),
                "created_at": str(post.get("created_at") or ""),
            }
        )
    return cleaned
