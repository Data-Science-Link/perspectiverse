"""Normalize post text before clustering and drop obvious junk."""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HANDLE_RE = re.compile(r"@[A-Za-z0-9._-]+")
WHITESPACE_RE = re.compile(r"\s+")
REPEAT_RE = re.compile(r"(.)\1{7,}")
GM_RE = re.compile(r"^(gm|gn|good morning|good night|hello|hi|hey)[\s!.]*$", re.IGNORECASE)
EMOJI_ONLY_RE = re.compile(r"^[\W_0-9]+$", re.UNICODE)
HASHTAG_RE = re.compile(r"#\w+")

SPAM_PHRASES = (
    "buy followers",
    "follow for follow",
    "follow back",
    "followback",
    "onlyfans",
    "crypto giveaway",
    "nft giveaway",
    "airdrop",
    "dm me for",
    "check my pinned",
    "click the link",
    "limited offer",
    "guaranteed profit",
    "join my telegram",
    "whatsapp me",
)


def clean_text(text: str) -> str:
    """Strip URLs and handles and collapse whitespace."""
    without_urls = URL_RE.sub(" ", text or "")
    without_handles = HANDLE_RE.sub(" ", without_urls)
    return WHITESPACE_RE.sub(" ", without_handles).strip()


def _dedupe_key(text: str) -> str:
    return WHITESPACE_RE.sub(" ", (text or "").lower()).strip()


def is_spam(text: str) -> bool:
    """Drop scraps, bait, and copy-paste junk. Conservative on real argument."""
    if len(text) < 24:
        return True
    if REPEAT_RE.search(text):
        return True
    if text.count("#") > 6:
        return True
    lowered = text.lower()
    if any(phrase in lowered for phrase in SPAM_PHRASES):
        return True
    if GM_RE.match(text.strip()):
        return True
    stripped = HASHTAG_RE.sub("", URL_RE.sub("", text)).strip()
    if len(stripped) < 20:
        return True
    tokens = [part for part in WHITESPACE_RE.split(stripped) if part]
    if tokens and (len(HASHTAG_RE.findall(text)) / max(len(tokens), 1)) > 0.45:
        return True
    if EMOJI_ONLY_RE.match(stripped):
        return True
    return False


def drop_near_duplicates(posts: list[dict]) -> list[dict]:
    """Drop copy-paste text that survived URI dedup. Safe for the live window."""
    kept: list[dict] = []
    seen_text: set[str] = set()
    for post in posts:
        key = _dedupe_key(str(post.get("clean_text") or post.get("text") or ""))
        if not key or key in seen_text:
            continue
        seen_text.add(key)
        kept.append(post)
    return kept


def clean_posts(posts: list[dict]) -> list[dict]:
    """Return posts that survived cleaning, preserving likes and identity."""
    cleaned: list[dict] = []
    seen_uris: set[str] = set()
    for post in posts:
        uri = str(post.get("uri") or "")
        if not uri or uri in seen_uris:
            continue
        text = clean_text(str(post.get("text") or ""))
        if is_spam(text):
            continue
        seen_uris.add(uri)
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
