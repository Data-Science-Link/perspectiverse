"""Free local filter for greeting and chit-chat posts (#208).

No network and no model calls. Used at free ingest (before the daily non-spam
cap) and as a planet-level guard when a chit-chat cluster slips through.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.cleaning import HASHTAG_RE, URL_RE
from pipeline.language import is_link_only, looks_english
from pipeline.spam_guard import guard_reason, post_body

_GREETING_RE = re.compile(
    r"^(?:gm|gn|good\s+(?:morning|afternoon|evening|night)|hello|hi|hey|howdy|sup)[\s!.?]*$",
    re.IGNORECASE,
)
_THANKS_ONLY_RE = re.compile(
    r"^(?:thank\s+you(?:\s+so\s+much)?|thanks(?:\s+you)?(?:\s+so\s+much)?|ty|thx|"
    r"much\s+appreciated|appreciate\s+(?:it|you|this))[\s!.?]*$",
    re.IGNORECASE,
)
_AGREEMENT_RE = re.compile(
    r"^(?:of\s+course|count\s+me\s+in|absolutely|exactly|agreed|yes|yep|yeah|this|same|"
    r"so\s+true|well\s+said|couldn'?t\s+agree\s+more)[\s!.?]*$",
    re.IGNORECASE,
)
_WISH_RE = re.compile(
    r"\bhappy\s+(?:birthday|bday|anniversary)\b",
    re.IGNORECASE,
)
_LUCK_RE = re.compile(
    r"\b(?:good\s+luck|best\s+of\s+luck)\b",
    re.IGNORECASE,
)
_WEEKEND_RE = re.compile(
    r"^(?:have\s+a\s+)?(?:great|good|nice|happy)\s+weekend[\s!.?]*$",
    re.IGNORECASE,
)
_STREAM_ANNOUNCE_RE = re.compile(
    r"\b(?:"
    r"live\s+now|going\s+live|we(?:'re| are)\s+live|streaming\s+now|stream\s+now|"
    r"tune\s+in\s+now|watch\s+live|twitch\.tv/"
    r")\b",
    re.IGNORECASE,
)
_COMPLIMENT_RE = re.compile(
    r"\b(?:beautiful|gorgeous|stunning|amazing|wonderful|well\s+done|great\s+work|"
    r"love\s+this|so\s+pretty|thank\s+you\s+for\s+sharing)\b",
    re.IGNORECASE,
)

# When these appear with enough words, the post is discourse not chit-chat.
_DISCOURSE_HINTS = frozenset(
    {
        "veteran",
        "veterans",
        "policy",
        "policies",
        "regulation",
        "congress",
        "senate",
        "election",
        "war",
        "ukraine",
        "gaza",
        "court",
        "bill",
        "law",
        "laws",
        "platform",
        "streaming",
        "twitch",
        "youtube",
        "news",
        "report",
        "government",
        "president",
        "minister",
    }
)

_PLANET_LABEL_PHRASES = (
    "happy birthday",
    "happy anniversary",
    "good luck",
    "full agreement",
    "art appreciation",
    "twitch stream",
    "the weekend",
)

_PLANET_LABEL_WORDS = frozenset(
    {
        "birthday",
        "anniversary",
        "weekend",
        "luck",
        "agreement",
        "appreciation",
        "twitch",
        "count",
        "course",
    }
)

_SAMPLE_CAP = 100


class ChitchatRemovalLog:
    """Counts ingest blocks and keeps a sample for review."""

    def __init__(self) -> None:
        self.fetched = 0
        self.spam_blocked = 0
        self.chitchat_blocked = 0
        self.language_blocked = 0
        self.link_blocked = 0
        self._samples: list[dict] = []

    def reset(self) -> None:
        self.fetched = 0
        self.spam_blocked = 0
        self.chitchat_blocked = 0
        self.language_blocked = 0
        self.link_blocked = 0
        self._samples.clear()

    def record_fetch(self, count: int = 1) -> None:
        self.fetched += max(0, int(count))

    def record_block(self, post: dict, reason: str) -> None:
        if reason.startswith("spam:"):
            self.spam_blocked += 1
            return
        if reason.startswith("chitchat:"):
            self.chitchat_blocked += 1
            kind = reason.split(":", 1)[1]
        elif reason == "language":
            self.language_blocked += 1
            kind = reason
        elif reason == "link_only":
            self.link_blocked += 1
            kind = reason
        else:
            return
        if len(self._samples) >= _SAMPLE_CAP:
            return
        text = " ".join(str(post_body(post)).split())
        self._samples.append(
            {
                "reason": kind,
                "uri": str(post.get("uri") or ""),
                "text": text[:280],
            }
        )

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
            "removed_sample": list(self._samples),
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


def _has_discourse_anchor(lowered: str, word_count: int) -> bool:
    if word_count >= 24:
        return True
    hits = sum(1 for hint in _DISCOURSE_HINTS if hint in lowered)
    if hits >= 2:
        return True
    if "veteran" in lowered and word_count >= 9:
        return True
    if ("policy" in lowered or "regulation" in lowered) and word_count >= 10:
        return True
    if "platform" in lowered and word_count >= 12:
        return True
    if "streaming" in lowered and word_count >= 14 and "live now" not in lowered:
        return True
    return False


def _social_text(text: str) -> str:
    """Drop URLs, hashtags, and emoji so short thanks still match."""
    stripped = HASHTAG_RE.sub(" ", URL_RE.sub(" ", text or ""))
    stripped = re.sub(r"[^\w\s'!?.,]", " ", stripped, flags=re.UNICODE)
    return " ".join(stripped.split())


def chitchat_reason(post: dict) -> str | None:
    """Why this post is chit-chat, or None when it should stay."""
    text = post_body(post)
    if not text.strip():
        return None
    social = _social_text(text)
    lowered = social.lower()
    wc = _word_count(social)
    if _has_discourse_anchor(lowered, wc):
        return None
    stripped = " ".join(lowered.split())
    if _GREETING_RE.match(stripped):
        return "greeting"
    if _THANKS_ONLY_RE.match(stripped):
        return "thanks"
    if _AGREEMENT_RE.match(stripped):
        return "agreement"
    if _WEEKEND_RE.match(stripped):
        return "weekend"
    if _WISH_RE.search(lowered) and wc <= 22:
        return "wish"
    if _LUCK_RE.search(lowered) and wc <= 16:
        return "luck"
    if _STREAM_ANNOUNCE_RE.search(lowered) and wc <= 20:
        return "stream_announce"
    if wc <= 14 and _COMPLIMENT_RE.search(lowered):
        return "compliment"
    if wc <= 6 and stripped in {"of course", "count me in", "this", "same", "yes", "yep", "agreed"}:
        return "agreement"
    return None


def ingest_block_reason(post: dict) -> str | None:
    """Spam, chit-chat, link-only, or non-English. None means edition-quality."""
    spam = guard_reason(post)
    if spam:
        return f"spam:{spam}"
    chit = chitchat_reason(post)
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
        if chitchat_reason(post) is None:
            kept.append(post)
            continue
        dropped += 1
        _LOG.record_block(post, "chitchat:late")
    return kept, dropped


def _planet_label_chitchat(label: str, terms: list[str]) -> tuple[str, str] | None:
    """Return (kind, detail) where kind is ``phrase`` or ``weak_stem``."""
    lowered = label.lower()
    for phrase in _PLANET_LABEL_PHRASES:
        if phrase in lowered:
            return ("phrase", phrase)
    term_keys = {str(term).lower() for term in terms}
    if len(term_keys) == 1 and next(iter(term_keys)) in _PLANET_LABEL_WORDS:
        return ("weak_stem", next(iter(term_keys)))
    if lowered in {"full agreement", "good luck", "happy birthday", "happy anniversary", "the weekend"}:
        return ("phrase", lowered)
    return None


def _member_has_discourse(post: dict) -> bool:
    text = _social_text(post_body(post))
    return _has_discourse_anchor(text.lower(), _word_count(text))


def planet_chitchat_reason(
    members: list[dict],
    terms: list[str],
    *,
    name: str | None = None,
) -> str | None:
    """True when a cluster is mostly chit-chat and the label agrees."""
    if not members:
        return None
    reasons = [chitchat_reason(member) for member in members]
    share = sum(1 for item in reasons if item) / len(members)
    discourse = sum(1 for member in members if _member_has_discourse(member))
    if discourse >= max(2, int(len(members) * 0.12)):
        return None
    label = str(name or "").strip()
    label_signal = _planet_label_chitchat(label, terms) if label else None
    if label_signal:
        kind, detail = label_signal
        floor = 0.25 if kind == "phrase" else 0.65
        if share >= floor:
            return f"{share:.0%} chitchat posts; label {kind} {detail!r}"
    weak = _planet_label_chitchat(" ".join(terms), terms)
    if weak:
        kind, detail = weak
        floor = 0.25 if kind == "phrase" else 0.65
        if share >= floor:
            return f"{share:.0%} chitchat posts; terms {kind} {detail!r}"
    if share >= 0.88:
        return f"{share:.0%} chitchat posts; no discourse topic"
    return None
