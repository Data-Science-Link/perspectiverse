"""Free checks that section planets match their member posts (#228).

Moves clearly non-political Politics planets to Culture or Other after
labeling. Real tax-policy and civic posts stay in Politics.
"""

from __future__ import annotations

import re

from pipeline.chitchat_guard import pleasantry_reason
from pipeline.cleaning import HASHTAG_RE, URL_RE
from pipeline.schema import CATEGORY_KEYWORDS
from pipeline.spam_guard import post_body

_POLITICS_WORDS = frozenset(CATEGORY_KEYWORDS["Politics"]) | frozenset(
    {
        "trump",
        "biden",
        "democrat",
        "democrats",
        "republican",
        "republicans",
        "gop",
        "senator",
        "governor",
        "mayor",
        "campaign",
        "ballot",
        "impeach",
        "scotus",
        "supreme",
        "immigration",
        "abortion",
        "trans",
        "lgbt",
        "maga",
        "labour",
        "tory",
        "parliament",
        "minister",
        "irs",
        "bracket",
        "deduction",
        "legislation",
        "filibuster",
    }
)

_TAX_MEME_RE = re.compile(r"\bfor\s+tax\s+purposes\b", re.IGNORECASE)
_POLICY_TAX_RE = re.compile(
    r"\b(?:irs|tax\s+(?:bill|policy|code|reform|cut|hike|credit)|bracket|deduction|withholding)\b",
    re.IGNORECASE,
)
_MUSIC_LINK_RE = re.compile(r"\byoutu\.be/|(?:^|\s)youtube\.com/|#musicsky\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _post_supports_politics(text: str) -> bool:
    if _TAX_MEME_RE.search(text) and not _POLICY_TAX_RE.search(text):
        return False
    if _MUSIC_LINK_RE.search(text):
        stripped = URL_RE.sub(" ", HASHTAG_RE.sub(" ", text))
        words = [part for part in stripped.split() if part]
        if len(words) <= 10:
            return False
    tokens = _tokens(text)
    if tokens & _POLITICS_WORDS:
        return True
    if _POLICY_TAX_RE.search(text):
        return True
    return False


def members_support_politics(members: list[dict], *, name: str = "") -> bool:
    """True when member posts look like civic or policy discourse."""
    if not members:
        return True
    texts = [post_body(post) for post in members]
    supporting = sum(1 for text in texts if _post_supports_politics(text))
    share = supporting / len(texts)
    if share >= 0.35:
        return True
    pleasant = sum(1 for post in members if pleasantry_reason(post))
    if pleasant / len(members) >= 0.45 and share < 0.15:
        return False
    music = sum(1 for text in texts if _MUSIC_LINK_RE.search(text))
    if music / len(members) >= 0.5 and share < 0.2:
        return False
    meme = sum(1 for text in texts if _TAX_MEME_RE.search(text) and not _POLICY_TAX_RE.search(text))
    if meme / len(members) >= 0.4:
        return False
    lowered_name = (name or "").lower()
    if "music" in lowered_name and "video" in lowered_name:
        return False
    if lowered_name in {"thank you", "thank"} and share < 0.2:
        return False
    if share >= 0.2:
        return True
    return supporting >= 2


def politics_planet_destination(name: str, members: list[dict]) -> str | None:
    """Return Culture or Other when a Politics planet should move; else None."""
    if members_support_politics(members, name=name):
        return None
    texts = [post_body(post) for post in members]
    music = sum(1 for text in texts if _MUSIC_LINK_RE.search(text))
    meme = sum(1 for text in texts if _TAX_MEME_RE.search(text) and not _POLICY_TAX_RE.search(text))
    if music >= max(2, len(members) // 3) or meme >= max(2, len(members) // 3):
        return "Culture"
    lowered = (name or "").lower()
    if "music" in lowered or "video" in lowered or "tax movie" in lowered:
        return "Culture"
    return "Other"


def partition_politics_planets(
    topics: list[dict],
    posts: list[dict],
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Split Politics planets into keep vs relocate buckets."""
    by_uri = {str(post.get("uri") or ""): post for post in posts}
    kept: list[dict] = []
    moved: dict[str, list[dict]] = {}
    for topic in topics:
        uris = [str(uri) for uri in (topic.get("_member_uris") or []) if uri]
        members = [by_uri[uri] for uri in uris if uri in by_uri]
        if not members:
            for face in topic.get("perspectives") or []:
                for rep in face.get("representative_posts") or []:
                    members.append({"text": rep.get("text"), "author": rep.get("author")})
        dest = politics_planet_destination(str(topic.get("name") or ""), members)
        if dest is None:
            kept.append(topic)
            continue
        topic = dict(topic)
        topic["category"] = dest
        moved.setdefault(dest, []).append(topic)
    return kept, moved
