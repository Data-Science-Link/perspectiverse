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

# Bare hosts allowed without a scheme (short links and common social hosts).
_BARE_LINK_ALLOWLIST_RE = re.compile(
    r"\b(?:"
    r"youtu\.be|(?:www\.)?youtube\.com|m\.youtube\.com|"
    r"bsky\.app|t\.co|"
    r"(?:www\.)?tiktok\.com|vm\.tiktok\.com|"
    r"twitch\.tv|kick\.com|picarto\.tv"
    r")(?:/[^\s]*)?",
    re.IGNORECASE,
)

# ``host.tld/rest`` — not ``README.md`` or ``sicko.jpg`` (no slash).
_PATH_LINK_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,63})/([^\s]+)",
    re.IGNORECASE,
)

_FILE_TLDS = frozenset(
    {
        "jpg",
        "jpeg",
        "gif",
        "png",
        "webp",
        "svg",
        "bmp",
        "md",
        "js",
        "jsx",
        "ts",
        "tsx",
        "mjs",
        "cjs",
        "pdf",
        "doc",
        "docx",
        "ppt",
        "xls",
        "csv",
        "json",
        "xml",
        "txt",
        "micro",
        "yes",
    }
)


def _without_handles(text: str) -> str:
    return HANDLE_RE.sub(" ", text or "")


def _path_link_is_real(match: re.Match[str]) -> bool:
    tld = (match.group(1) or "").lower()
    return tld not in _FILE_TLDS


def _find_link_spans(body: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (URL_RE, _BARE_LINK_ALLOWLIST_RE):
        for match in pattern.finditer(body):
            spans.append((match.start(), match.end()))
    for match in _PATH_LINK_RE.finditer(body):
        if _path_link_is_real(match):
            spans.append((match.start(), match.end()))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def strip_link_hosts(text: str) -> str:
    """Remove scheme URLs, www links, and bare link hosts (handles stripped first)."""
    body = _without_handles(text)
    spans = _find_link_spans(body)
    if not spans:
        return body
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(body[cursor:start])
        parts.append(" ")
        cursor = end
    parts.append(body[cursor:])
    return "".join(parts)


def has_link_host(text: str) -> bool:
    """True when handle-stripped text still contains a real URL or bare link."""
    body = _without_handles(text or "")
    return bool(_find_link_spans(body))


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
    """Strip URLs, bare link hosts, and handles; collapse whitespace."""
    without_urls = strip_link_hosts(text)
    return WHITESPACE_RE.sub(" ", without_urls).strip()


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


def dedupe_key(post: dict) -> str:
    """Normalized text key for copy-paste dedup across URIs."""
    return _dedupe_key(str(post.get("clean_text") or post.get("text") or ""))


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
