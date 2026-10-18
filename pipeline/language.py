"""Local checks for link-only posts and non-English language (#221–#223).

Link-only rules are lexical. Language uses the pinned ``langid`` model on text
with URLs, handles, and hashtags stripped. Short or ambiguous text is kept.
"""

from __future__ import annotations

import re
import unicodedata

import langid

from pipeline.cleaning import (
    HANDLE_RE,
    HASHTAG_RE,
    WHITESPACE_RE,
    _find_link_spans,
    _without_handles,
    has_link_host,
    strip_link_hosts,
)

# langid log-probability gap (top language vs English) required to drop a post.
_LANGID_MARGIN = 25.0
# Fewer letters than this after stripping → keep (too short to ID reliably).
_MIN_LANGID_LETTERS = 24
# Fewer distinct words → keep (repetitive / synthetic blurbs).
_MIN_LANGID_UNIQUE_WORDS = 4

_ALPHA_WORD = re.compile(r"[A-Za-zÀ-ÿ']+")

_LINK_BOILERPLATE_RE = re.compile(
    r"\b(?:gift\s+link|free\s+(?:article\s+)?link|article\s+link|free\s+article|"
    r"read\s+more|watch\s*:?|full\s+story|link\s+in\s+bio|click\s+here|"
    r"subscribe\s+to|sign\s+up)\b",
    re.IGNORECASE,
)


def _fold_token(token: str) -> str:
    lowered = token.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def post_raw_text(post: dict) -> str:
    """Prefer stored raw text so filters match ingest and clustering (#219)."""
    return str(post.get("text") or post.get("clean_text") or "")


def _strip_for_language(text: str) -> str:
    body = HANDLE_RE.sub(" ", text or "")
    body = strip_link_hosts(body)
    body = HASHTAG_RE.sub(" ", body)
    return WHITESPACE_RE.sub(" ", body).strip()


def _strip_for_link_check(text: str) -> str:
    body = HANDLE_RE.sub(" ", text or "")
    body = strip_link_hosts(body)
    body = HASHTAG_RE.sub(" ", body)
    return WHITESPACE_RE.sub(" ", body).strip()


def _latin_letters_for_langid(stripped: str) -> str:
    """Latin script for langid; drop emoji and non-Latin letters (names stay in the post)."""
    chunks: list[str] = []
    for char in stripped:
        if char.isalpha():
            if char.isascii() or ord(char) <= 0x024F:
                chunks.append(char)
            else:
                chunks.append(" ")
        elif char in {"'", "-"}:
            chunks.append(char)
        else:
            chunks.append(" ")
    return WHITESPACE_RE.sub(" ", "".join(chunks)).strip()


def _non_latin_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 8:
        return 0.0
    foreign = 0
    for char in letters:
        code = ord(char)
        if code > 0x024F:
            foreign += 1
    return foreign / len(letters)


def _boilerplate_only(remaining: str) -> bool:
    cleaned = _LINK_BOILERPLATE_RE.sub(" ", remaining)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    return not _ALPHA_WORD.findall(cleaned)


def _link_slug_words(body: str) -> set[str]:
    handle_stripped = _without_handles(body)
    words: set[str] = set()
    for start, end in _find_link_spans(handle_stripped):
        chunk = handle_stripped[start:end].lower()
        for token in re.findall(r"[a-z]{3,}", chunk):
            words.add(token)
    return words


def _looks_like_link_preview_title(remaining: str, body: str) -> bool:
    """Cheap check: pasted headline words mostly repeat the URL path."""
    poster = [_fold_token(word) for word in _ALPHA_WORD.findall(remaining) if len(word) >= 3]
    if len(poster) < 4:
        return False
    slugs = _link_slug_words(body)
    if not slugs:
        return False
    overlap = sum(1 for word in poster if word in slugs)
    return overlap / len(poster) >= 0.6


def is_link_only(text: str) -> bool:
    """True when the post is only a URL, boilerplate, or a pasted link title."""
    body = str(text or "")
    if not has_link_host(body):
        return False
    remaining = _strip_for_link_check(body)
    if not _ALPHA_WORD.findall(remaining):
        return True
    if _boilerplate_only(remaining):
        return True
    if _looks_like_link_preview_title(remaining, body):
        return True
    return False


def looks_english(text: str) -> bool:
    """True unless langid is confidently non-English on stripped text."""
    body = str(text or "")
    if _non_latin_ratio(body) >= 0.2:
        return False
    stripped = _strip_for_language(body)
    lang_input = _latin_letters_for_langid(stripped)
    letters = sum(1 for char in lang_input if char.isalpha())
    if letters < _MIN_LANGID_LETTERS:
        return True
    if len(set(_ALPHA_WORD.findall(lang_input))) < _MIN_LANGID_UNIQUE_WORDS:
        return True
    if not lang_input:
        return True
    ranked = langid.rank(lang_input)
    if not ranked:
        return True
    top_lang, top_score = ranked[0]
    if top_lang == "en":
        return True
    en_score = next((score for lang, score in ranked if lang == "en"), None)
    if en_score is None:
        return False
    margin = top_score - en_score
    if margin < _LANGID_MARGIN:
        return True
    return False


def edition_filter_reason(post: dict) -> str | None:
    """Single public check for ingest, clustering, and #219 stored-row cleanup."""
    body = post_raw_text(post)
    if is_link_only(body):
        return "link_only"
    if not looks_english(body):
        return "language"
    return None


def partition_posts(posts: list[dict]) -> tuple[list[dict], int, int]:
    """Return posts to cluster, plus how many were non-English or link-only."""
    kept: list[dict] = []
    language = 0
    links = 0
    for post in posts:
        reason = edition_filter_reason(post)
        if reason == "link_only":
            links += 1
            continue
        if reason == "language":
            language += 1
            continue
        kept.append(post)
    return kept, language, links
