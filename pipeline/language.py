"""Cheap local checks for posts that should not enter an English clustering.

No model and no network. A post is skipped when another language's function
words outnumber English ones, when the letters are mostly not Latin, or when
the text is only a link. Short English remarks are kept.
"""

from __future__ import annotations

import re
import unicodedata

from pipeline.cleaning import HANDLE_RE, HASHTAG_RE, has_link_host, strip_link_hosts

_TOKEN = re.compile(r"[\w']{2,}", re.UNICODE)
_WORD_3 = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

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
        "as",
        "com",
        "seu",
        "sua",
        "seus",
        "suas",
        "está",
        "esta",
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
    }
)


def _fold_token(token: str) -> str:
    lowered = token.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


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


def _strip_for_link_check(text: str) -> str:
    body = HANDLE_RE.sub(" ", text or "")
    body = strip_link_hosts(body)
    body = HASHTAG_RE.sub(" ", body)
    return body


def is_link_only(text: str) -> bool:
    """True when removing URLs and hashtags leaves fewer than four real words."""
    body = str(text or "")
    if not has_link_host(body):
        return False
    stripped = _strip_for_link_check(body)
    return len(_WORD_3.findall(stripped)) < 4


def looks_english(text: str) -> bool:
    """True unless the post is clearly not English."""
    body = str(text or "")
    if _non_latin_ratio(body) >= 0.2:
        return False
    tokens = [_fold_token(token) for token in _TOKEN.findall(body)]
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
        text = str(post.get("text") or post.get("clean_text") or "")
        if is_link_only(text):
            links += 1
            continue
        if not looks_english(text):
            language += 1
            continue
        kept.append(post)
    return kept, language, links
