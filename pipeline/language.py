"""Cheap local checks for posts that should not enter an English clustering.

No model and no network. A post is skipped when another language's function
words outnumber English ones, when the letters are mostly not Latin, or when
the text is only a link. Short English remarks are kept.
"""

from __future__ import annotations

import re
import unicodedata

from pipeline.cleaning import (
    HANDLE_RE,
    HASHTAG_RE,
    WHITESPACE_RE,
    _find_link_spans,
    _without_handles,
    has_link_host,
    strip_link_hosts,
)

_TOKEN = re.compile(r"[\w']{2,}", re.UNICODE)
_ALPHA_WORD = re.compile(r"[A-Za-zÀ-ÿ']+")
_PT_STRONG_ACCENT_RE = re.compile(r"[ãõç]", re.IGNORECASE)

_LINK_BOILERPLATE_RE = re.compile(
    r"\b(?:gift\s+link|free\s+(?:article\s+)?link|article\s+link|free\s+article|"
    r"read\s+more|watch\s*:?|full\s+story|link\s+in\s+bio|click\s+here|"
    r"subscribe\s+to|sign\s+up)\b",
    re.IGNORECASE,
)

# Function words that are ordinary English. A hit here is evidence for English.
_ENGLISH = frozenset(
    {
        "the",
        "and",
        "is",
        "to",
        "of",
        "in",
        "on",
        "it",
        "be",
        "as",
        "at",
        "by",
        "or",
        "we",
        "he",
        "if",
        "so",
        "do",
        "an",
        "my",
        "me",
        "us",
        "am",
        "no",
        "that",
        "this",
        "with",
        "from",
        "have",
        "about",
        "they",
        "them",
        "their",
        "what",
        "when",
        "where",
        "which",
        "would",
        "could",
        "should",
        "there",
        "your",
        "been",
        "were",
        "was",
        "are",
        "not",
        "but",
        "its",
        "our",
        "out",
        "you",
        "for",
        "youre",
        "into",
        "just",
        "like",
        "how",
        "who",
        "dont",
        "has",
        "can",
        "get",
        "got",
        "she",
        "his",
        "her",
        "him",
        "one",
        "must",
        "because",
        "people",
        "will",
        "theyre",
        "its",
        "than",
        "then",
        "also",
        "some",
        "any",
        "all",
        "more",
        "been",
        "being",
        "over",
        "after",
        "before",
        "why",
        "yes",
        "here",
        "weve",
        "ive",
        "im",
        "dont",
        "didnt",
        "isnt",
        "wasnt",
        "arent",
        "cant",
        "wont",
    }
)

_FOREIGN_RAW = frozenset(
    {
        # Dutch
        "niet",
        "het",
        "een",
        "van",
        "dat",
        "hij",
        "zij",
        "wij",
        "naar",
        "geen",
        "wordt",
        "deze",
        "omdat",
        "tussen",
        "voor",
        "bij",
        "uit",
        "dan",
        "wat",
        "ook",
        "maar",
        "heb",
        "hebben",
        "zijn",
        "jullie",
        # German
        "und",
        "nicht",
        "eine",
        "der",
        "das",
        "den",
        "dem",
        "ein",
        "sich",
        "dass",
        "auch",
        "ist",
        "mit",
        "auf",
        "fuer",
        "nach",
        "wenn",
        "oder",
        "werden",
        # French
        "les",
        "des",
        "une",
        "est",
        "pas",
        "dans",
        "pour",
        "avec",
        "sont",
        "nous",
        "vous",
        "elle",
        "aux",
        "cette",
        "mais",
        "qui",
        # Spanish / Portuguese (shared and PT-specific)
        "los",
        "las",
        "una",
        "por",
        "para",
        "como",
        "pero",
        "esta",
        "este",
        "hay",
        "del",
        "porque",
        "tambien",
        "também",
        "nao",
        "não",
        "sao",
        "são",
        "mais",
        "foi",
        "pelo",
        "pela",
        "que",
        "con",
        "sus",
        "de",
        "da",
        "do",
        "dos",
        "das",
        "em",
        "um",
        "uma",
        "os",
        "seu",
        "sua",
        "seus",
        "suas",
        "está",
        "estao",
        "estão",
        "ser",
        "ter",
        "veja",
        "desta",
        "deste",
        "terça",
        "terca",
        "feira",
        "brasil",
        "governo",
        "anunciou",
        "medidas",
        "economicas",
        "econômicas",
        "fetiches",
        "populares",
        "acho",
        "isso",
        "voce",
        "você",
    }
)

# Portuguese cues that are not ordinary English function words.
_PORTUGUESE_ONLY_RAW = frozenset(
    {
        "nao",
        "não",
        "que",
        "para",
        "uma",
        "com",
        "está",
        "estao",
        "estão",
        "voce",
        "você",
        "tambem",
        "também",
        "mais",
        "isso",
        "brasil",
        "governo",
        "anunciou",
        "medidas",
        "economicas",
        "econômicas",
        "fetiches",
        "populares",
        "acho",
        "veja",
        "desta",
        "deste",
        "sao",
        "são",
        "pelo",
        "pela",
        "terça",
        "terca",
        "feira",
        "ser",
        "ter",
        "foi",
        "porque",
        "tambien",
    }
)


def _fold_token(token: str) -> str:
    lowered = token.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


_FOREIGN = frozenset(_fold_token(word) for word in _FOREIGN_RAW)
_PORTUGUESE_ONLY = frozenset(
    _fold_token(word) for word in _PORTUGUESE_ONLY_RAW if _fold_token(word) not in _ENGLISH
)


def post_raw_text(post: dict) -> str:
    """Prefer stored raw text so filters match ingest and clustering (#219)."""
    return str(post.get("text") or post.get("clean_text") or "")


def _strip_for_language(text: str) -> str:
    body = HANDLE_RE.sub(" ", text or "")
    body = strip_link_hosts(body)
    body = HASHTAG_RE.sub(" ", body)
    return body


def _strip_for_link_check(text: str) -> str:
    body = HANDLE_RE.sub(" ", text or "")
    body = strip_link_hosts(body)
    body = HASHTAG_RE.sub(" ", body)
    return WHITESPACE_RE.sub(" ", body).strip()


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


def _portuguese_signal(body: str, tokens: list[str]) -> bool:
    folded = [_fold_token(token) for token in tokens]
    pt_hits = sum(1 for token in folded if token in _PORTUGUESE_ONLY)
    if _PT_STRONG_ACCENT_RE.search(body) and pt_hits >= 2:
        return True
    if pt_hits >= 4:
        return True
    return False


def looks_english(text: str) -> bool:
    """True unless the post is clearly not English."""
    body = str(text or "")
    if _non_latin_ratio(body) >= 0.2:
        return False
    stripped = _strip_for_language(body)
    tokens = [_fold_token(token) for token in _TOKEN.findall(stripped)]
    if len(tokens) < 4:
        return True
    if _portuguese_signal(body, tokens):
        return False
    english = sum(1 for token in tokens if token in _ENGLISH)
    foreign = sum(1 for token in tokens if token in _FOREIGN and token not in _ENGLISH)
    if foreign >= 2 and foreign >= english:
        return False
    return True


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
