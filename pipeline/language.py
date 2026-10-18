"""Local checks for link-only posts and non-English language (#221–#223).

Link-only rules are lexical. Language uses the pinned ``langid`` model on text
with URLs, handles, and hashtags stripped, after normalizing strikethrough and
letter-spacing. English-framed sentences with foreign names are kept.
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
# Min share of English frame words among non-name tokens to keep.
_MIN_FRAME_RATIO = 0.35
_MIN_FRAME_HITS = 2

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


# English function / sports-bot frame words (not Portuguese de/para/que).
_FRAME_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "by",
        "to",
        "of",
        "in",
        "on",
        "at",
        "from",
        "with",
        "after",
        "before",
        "just",
        "seen",
        "scores",
        "score",
        "goal",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "can",
        "may",
        "might",
        "not",
        "no",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "what",
        "when",
        "where",
        "who",
        "how",
        "why",
        "all",
        "any",
        "some",
        "as",
        "if",
        "so",
        "than",
        "then",
        "there",
        "here",
        "they",
        "them",
        "their",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "my",
        "me",
        "i",
        "banned",
        "timeout",
        "ban",
        "live",
        "follow",
        "against",
        "penalty",
        "agg",
        "minute",
        "min",
        "sign",
        "up",
        "free",
        "speech",
        "platform",
        "show",
        "dutch",
    }
)

_FRAME_WORDS_FOLDED = frozenset(_fold_token(w) for w in _FRAME_WORDS)


def post_raw_text(post: dict) -> str:
    """Prefer stored raw text so filters match ingest and clustering (#219)."""
    return str(post.get("text") or post.get("clean_text") or "")


def _strip_combining_marks(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _collapse_spaced_letters(text: str) -> str:
    """Join letter-spaced obfuscation: ``S i g n u p`` → ``Signup``."""
    parts = (text or "").split()
    if not parts:
        return ""
    out: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        alpha = re.sub(r"[^A-Za-zÀ-ÿ]", "", token)
        if len(alpha) == 1 and alpha.isalpha():
            end = index
            letters: list[str] = []
            while end < len(parts):
                piece = re.sub(r"[^A-Za-zÀ-ÿ]", "", parts[end])
                if len(piece) == 1 and piece.isalpha():
                    letters.append(piece)
                    end += 1
                else:
                    break
            if len(letters) >= 4:
                out.append("".join(letters))
                index = end
                continue
        out.append(token)
        index += 1
    return " ".join(out)


def _normalize_for_language(text: str) -> str:
    body = _strip_combining_marks(text)
    body = _collapse_spaced_letters(body)
    return body


def _strip_for_language(text: str) -> str:
    body = _normalize_for_language(text or "")
    body = HANDLE_RE.sub(" ", body)
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


def _token_is_name_like(word: str) -> bool:
    """Proper nouns and team names — skip when measuring English frame share."""
    bare = word.strip("'")
    if not bare.isalpha():
        return False
    fold = _fold_token(bare)
    if fold in _FRAME_WORDS_FOLDED:
        return False
    if bare.isupper() and len(bare) > 1 and fold not in _FRAME_WORDS_FOLDED:
        return True
    if len(bare) >= 2 and bare[0].isupper() and bare[1:].islower():
        return True
    if len(bare) >= 2 and bare[0].isupper() and any(ch.isupper() for ch in bare[1:]):
        return True
    return False


def _english_frame_keeps(lang_input: str) -> bool:
    words = _ALPHA_WORD.findall(lang_input)
    frame_hits = 0
    eligible = 0
    for word in words:
        if _token_is_name_like(word):
            continue
        fold = _fold_token(word)
        if not fold:
            continue
        eligible += 1
        if fold in _FRAME_WORDS_FOLDED:
            frame_hits += 1
    if eligible < _MIN_FRAME_HITS:
        return False
    return frame_hits >= _MIN_FRAME_HITS and (frame_hits / eligible) >= _MIN_FRAME_RATIO


def _without_name_tokens(lang_input: str) -> str:
    kept: list[str] = []
    for word in _ALPHA_WORD.findall(lang_input):
        if _token_is_name_like(word):
            continue
        kept.append(_fold_token(word))
    return " ".join(kept)


def _langid_confidently_not_english(text: str) -> bool:
    if not text.strip():
        return False
    ranked = langid.rank(text)
    if not ranked:
        return False
    top_lang, top_score = ranked[0]
    if top_lang == "en":
        return False
    en_score = next((score for lang, score in ranked if lang == "en"), None)
    if en_score is None:
        return True
    margin = top_score - en_score
    return margin >= _LANGID_MARGIN


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
    body = _normalize_for_language(str(text or ""))
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
    if _english_frame_keeps(lang_input):
        return True
    name_stripped = _without_name_tokens(lang_input)
    if name_stripped and not _langid_confidently_not_english(name_stripped):
        return True
    if not _langid_confidently_not_english(lang_input):
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
