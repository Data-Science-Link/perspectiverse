"""Cheap local checks for posts that should not enter an English clustering.

No model and no network. A post is skipped when another language's function
words outnumber English ones, when the letters are mostly not Latin, or when
the text is only a link. Short English remarks are kept.
"""

from __future__ import annotations

import re

_URL = re.compile(
    r"https?://\S+|www\.\S+|\b[\w.-]+\.(?:com|org|net|io|co)(?:/|\b)\S*",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[a-z']{2,}")

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

# Function words that are not English. Two of these, and more of them than
# English function words, is enough to skip the post.
_FOREIGN = frozenset(
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
        "dans",
        "qui",
        # Spanish / Portuguese
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
        "nao",
        "sao",
        "mais",
        "foi",
        "pelo",
        "pela",
        "que",
        "con",
        "sus",
    }
)


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


def is_link_only(text: str) -> bool:
    """True when removing URLs leaves fewer than four words."""
    if not _URL.search(text or ""):
        return False
    stripped = _URL.sub(" ", text or "")
    words = re.findall(r"[A-Za-z]{3,}", stripped)
    return len(words) < 4


def looks_english(text: str) -> bool:
    """True unless the post is clearly not English."""
    body = str(text or "")
    if _non_latin_ratio(body) >= 0.2:
        return False
    tokens = _TOKEN.findall(body.lower())
    if len(tokens) < 4:
        return True
    english = sum(1 for token in tokens if token in _ENGLISH)
    foreign = sum(1 for token in tokens if token in _FOREIGN and token not in _ENGLISH)
    if foreign >= 2 and foreign > english:
        return False
    return True


def partition_posts(posts: list[dict]) -> tuple[list[dict], int, int]:
    """Return posts to cluster, plus how many were non-English or link-only."""
    kept: list[dict] = []
    language = 0
    links = 0
    for post in posts:
        text = str(post.get("clean_text") or post.get("text") or "")
        if is_link_only(text):
            links += 1
            continue
        if not looks_english(text):
            language += 1
            continue
        kept.append(post)
    return kept, language, links
