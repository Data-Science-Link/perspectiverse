"""Free local filter for greeting and chit-chat posts (#208).

No network and no model calls. A post is chit-chat only when it is short and
its whole content is a pleasantry (greeting, thanks, praise, agreement, a
social wish, or a stream announcement) with no topic noun or claim. Used at
free ingest before the daily cap and as a planet guard after labeling.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.cleaning import HASHTAG_RE, URL_RE
from pipeline.label import content_tokens
from pipeline.language import is_link_only, looks_english
from pipeline.spam_guard import guard_reason, post_body

# Words that may appear in a pleasantry-only post. Anything else (len >= 4) is substance.
_PLEASANTRY_WORDS = frozenset(
    {
        "thank",
        "thanks",
        "thankyou",
        "much",
        "love",
        "hello",
        "good",
        "morning",
        "night",
        "evening",
        "afternoon",
        "happy",
        "birthday",
        "bday",
        "anniversary",
        "weekend",
        "luck",
        "late",
        "wishing",
        "everyone",
        "fun",
        "great",
        "nice",
        "course",
        "sure",
        "count",
        "absolutely",
        "exactly",
        "agreed",
        "yeah",
        "yep",
        "same",
        "true",
        "said",
        "well",
        "couldnt",
        "live",
        "stream",
        "streaming",
        "twitch",
        "starting",
        "soon",
        "come",
        "hang",
        "hop",
        "tune",
        "watch",
        "now",
        "going",
        "here",
        "please",
        "pretty",
        "gorgeous",
        "beautiful",
        "stunning",
        "amazing",
        "wonderful",
        "awesome",
        "congrats",
        "congratulations",
        "appreciate",
        "appreciated",
        "sharing",
        "song",
        "songs",
        "this",
        "that",
        "your",
        "you",
        "yours",
        "best",
        "have",
        "hope",
        "enjoy",
        "wonderful",
        "late",
        "aww",
        "omg",
        "lol",
        "haha",
        "yes",
        "for",
        "but",
        "and",
        "the",
        "a",
        "an",
        "to",
        "in",
        "on",
        "at",
        "it",
        "is",
        "are",
        "be",
        "my",
        "so",
        "very",
        "really",
        "just",
        "all",
        "day",
        "today",
        "tonight",
    }
)

_MAX_PLEASANTRY_WORDS = 22

_STREAM_HOST_RE = re.compile(
    r"(?:twitch\.tv|kick\.com|youtube\.com/live|youtu\.be/)",
    re.IGNORECASE,
)

_CHITCHAT_TITLES = frozenset(
    {
        "art appreciation",
        "twitch stream",
        "happy birthday",
        "the weekend",
        "happy anniversary",
        "good luck",
        "full agreement",
        "count",
        "course",
    }
)

_WEAK_SOCIAL_TITLES = frozenset(
    {
        "count",
        "course",
        "good luck",
        "full agreement",
        "happy anniversary",
    }
)

_BIRTHDAY_FILLERS = frozenset(
    {
        "birthday",
        "happy",
        "late",
        "hope",
        "great",
        "day",
        "days",
        "lovely",
        "you",
        "your",
        "both",
        "rest",
        "better",
        "tomorrow",
        "treat",
        "wonderful",
        "love",
        "existence",
        "celebration",
        "cause",
        "wonderful",
        "birthdays",
    }
)

_SAMPLE_CAP = 100


class ChitchatRemovalLog:
    """Counts ingest blocks and keeps a chit-chat-only sample for review."""

    def __init__(self) -> None:
        self.fetched = 0
        self.spam_blocked = 0
        self.chitchat_blocked = 0
        self.language_blocked = 0
        self.link_blocked = 0
        self._chitchat_samples: list[dict] = []

    def reset(self) -> None:
        self.fetched = 0
        self.spam_blocked = 0
        self.chitchat_blocked = 0
        self.language_blocked = 0
        self.link_blocked = 0
        self._chitchat_samples.clear()

    def record_fetch(self, count: int = 1) -> None:
        self.fetched += max(0, int(count))

    def record_block(self, post: dict, reason: str) -> None:
        if reason.startswith("spam:"):
            self.spam_blocked += 1
            return
        if reason.startswith("chitchat:"):
            self.chitchat_blocked += 1
            kind = reason.split(":", 1)[1]
            if len(self._chitchat_samples) < _SAMPLE_CAP:
                text = " ".join(str(post_body(post)).split())
                self._chitchat_samples.append(
                    {
                        "reason": kind,
                        "uri": str(post.get("uri") or ""),
                        "text": text[:280],
                    }
                )
            return
        if reason == "language":
            self.language_blocked += 1
        elif reason == "link_only":
            self.link_blocked += 1

    def chitchat_share_of_fetched(self) -> float:
        if self.fetched <= 0:
            return 0.0
        return self.chitchat_blocked / self.fetched

    def to_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "spam_blocked": self.spam_blocked,
            "chitchat_blocked": self.chitchat_blocked,
            "language_blocked": self.language_blocked,
            "link_blocked": self.link_blocked,
            "chitchat_share_of_fetched": round(self.chitchat_share_of_fetched(), 6),
            "removed_sample": list(self._chitchat_samples),
        }


_LOG = ChitchatRemovalLog()


def reset_chitchat_log() -> None:
    _LOG.reset()


def get_chitchat_log() -> ChitchatRemovalLog:
    return _LOG


def write_chitchat_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_LOG.to_dict(), indent=2) + "\n", encoding="utf-8")


def _word_count(text: str) -> int:
    stripped = HASHTAG_RE.sub(" ", URL_RE.sub(" ", text or ""))
    return len([part for part in stripped.split() if part])


def _social_text(text: str) -> str:
    stripped = HASHTAG_RE.sub(" ", URL_RE.sub(" ", text or ""))
    stripped = re.sub(r"[^\w\s'!?.,]", " ", stripped, flags=re.UNICODE)
    return " ".join(stripped.split())


def _strip_leading_fillers(lowered: str) -> str:
    return re.sub(
        r"^(?:(?:aww+|omg+|lol+|haha+|yes+|but|and|so|well)\s+)+",
        "",
        lowered,
        flags=re.IGNORECASE,
    ).strip()


def substantive_tokens(text: str) -> set[str]:
    """Topic or claim words; empty means the post may be pleasantry-only."""
    raw = text or ""
    social = _social_text(raw)
    tokens = content_tokens(social)
    tokens -= _stream_username_tokens(raw)
    return {token for token in tokens if token not in _PLEASANTRY_WORDS and not token.isdigit()}


def _has_capitalized_name(raw: str) -> bool:
    """Mid-sentence proper name (Title Case), not shouty stream titles."""
    skip = {
        "I",
        "The",
        "A",
        "An",
        "But",
        "And",
        "So",
        "Yes",
        "No",
        "Live",
        "Happy",
        "Good",
        "Come",
        "Stream",
        "Twitch",
        "Kick",
        "Youtube",
        "Aww",
        "Omg",
        "Wishing",
        "Thanks",
        "Thank",
        "Congrats",
        "Congratulations",
    }
    without_tags = HASHTAG_RE.sub(" ", raw or "")
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", without_tags):
        word = match.group(0)
        if word in skip:
            continue
        return True
    return False


def _stream_username_tokens(raw: str) -> set[str]:
    """Usernames in stream URLs are not topic nouns."""
    lowered = (raw or "").lower()
    tokens: set[str] = set()
    for match in re.finditer(r"(?:twitch\.tv|kick\.com)/([a-z0-9_]+)", lowered):
        handle = match.group(1)
        if len(handle) >= 4:
            tokens.add(handle)
    return tokens


def pleasantry_reason(post: dict) -> str | None:
    """Why this post is pleasantry-only chit-chat, or None to keep it."""
    raw = post_body(post)
    if not raw.strip():
        return None
    if _word_count(raw) > _MAX_PLEASANTRY_WORDS:
        return None
    if _has_capitalized_name(raw):
        return None
    subs = substantive_tokens(raw)
    lower = _strip_leading_fillers(_social_text(raw).lower())
    if re.search(r"\bhappy\s+(?:\w+\s+){0,3}birthday\b", lower):
        subs -= _BIRTHDAY_FILLERS
    if subs:
        return None
    if not lower:
        return None
    raw_lower = raw.lower()

    if re.fullmatch(r"(?:gm|gn|hello|hi|hey|howdy|sup)[\s!.?]*", lower, flags=re.IGNORECASE):
        return "greeting"
    if re.search(r"\bthank(s| you)\b", lower) or lower in {"ty", "thx"}:
        return "thanks"
    if re.search(r"\bhappy\s+(?:\w+\s+){0,2}birthday\b", lower) or re.search(r"\bhappy\s+bday\b", lower):
        return "wish"
    if re.search(r"\b(?:good\s+luck|best\s+of\s+luck)\b", lower) and "charm" not in lower:
        return "luck"
    if re.search(r"\bhappy\s+anniversary\b", lower):
        return "wish"
    if re.search(r"\b(?:have\s+a\s+)?(?:great|good|nice|fun|happy)\s+weekend\b", lower) or re.search(
        r"\bwishing\s+everyone\s+a\s+fun\s+weekend\b", lower
    ):
        return "weekend"
    if (
        re.search(r"\b(?:live\s+now|going\s+live|we(?:'re| are)\s+live|stream(?:ing)?\s+now|stream\s+is\s+starting)\b", lower)
        or _STREAM_HOST_RE.search(raw_lower)
    ):
        return "stream_announce"
    if re.fullmatch(
        r"(?:of\s+course|for\s+sure|count\s+me\s+in|absolutely|exactly|agreed|yes|yep|yeah|same|this|so\s+true|well\s+said)(?:\s+lol)?[\s!.?]*",
        lower,
    ):
        return "agreement"
    if re.search(r"\bcount\s+me\s+in\b", lower) and _word_count(raw) <= 10:
        return "agreement"
    if re.search(r"\b(?:i'?m\s+in|get\s+in)\b", lower) and _word_count(raw) <= 12:
        return "agreement"
    if re.fullmatch(r"(?:beautiful|gorgeous|stunning|amazing|wonderful|awesome|love\s+this|so\s+pretty)[\s!.?]*", lower):
        return "compliment"
    if re.fullmatch(r"(?:congrats|congratulations)[\s!.?]*", lower):
        return "compliment"
    return None


# Public alias used across the pipeline.
chitchat_reason = pleasantry_reason


def ingest_block_reason(post: dict) -> str | None:
    """Spam, chit-chat, link-only, or non-English. None means edition-quality."""
    spam = guard_reason(post)
    if spam:
        return f"spam:{spam}"
    chit = pleasantry_reason(post)
    if chit:
        return f"chitchat:{chit}"
    text = str(post.get("clean_text") or post.get("text") or "")
    if is_link_only(text):
        return "link_only"
    if not looks_english(text):
        return "language"
    return None


def filter_chitchat_posts(posts: list[dict]) -> tuple[list[dict], int]:
    """Drop chit-chat posts that reached clustering. Returns (kept, dropped)."""
    kept: list[dict] = []
    dropped = 0
    for post in posts:
        if pleasantry_reason(post) is None:
            kept.append(post)
            continue
        dropped += 1
        _LOG.record_block(post, "chitchat:late")
    return kept, dropped


def _title_is_chitchat(name: str) -> bool:
    lowered = " ".join(str(name or "").lower().split())
    if lowered in _CHITCHAT_TITLES:
        return True
    for title in _CHITCHAT_TITLES:
        if title in lowered and len(lowered.split()) <= 4:
            return True
    return False


def pleasantry_share(members: list[dict]) -> float:
    if not members:
        return 0.0
    hits = sum(1 for member in members if pleasantry_reason(member))
    return hits / len(members)


def planet_chitchat_reason(
    members: list[dict],
    terms: list[str],
    *,
    name: str | None = None,
) -> str | None:
    """After labeling: drop when most member posts are pleasantries."""
    if not members:
        return None
    share = pleasantry_share(members)
    label = str(name or "").strip()
    avg_words = sum(_word_count(post_body(member)) for member in members) / len(members)
    lowered_title = " ".join(label.lower().split())
    if share >= 0.55:
        detail = f"label {label!r}" if label else "no label"
        return f"{share:.0%} pleasantry posts; {detail}"
    if lowered_title in _CHITCHAT_TITLES and len(members) >= 50:
        return f"chit-chat title {label!r} ({len(members)} posts, {share:.0%} pleasantry in sample)"
    if lowered_title in _WEAK_SOCIAL_TITLES and len(members) >= 8:
        return f"chit-chat title {label!r} ({len(members)} posts)"
    if _title_is_chitchat(label) and share >= 0.30 and avg_words <= 14:
        return f"{share:.0%} pleasantry posts; chit-chat title {label!r}"
    if _title_is_chitchat(label) and share >= 0.20 and avg_words <= 8:
        return f"{share:.0%} pleasantry posts; short chit-chat title {label!r}"
    return None
