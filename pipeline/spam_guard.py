"""Free spam guard. Deterministic. No network and no model call.

This is not the production cleaner. ``pipeline.cleaning.is_spam`` still drops
short remarks and greetings on the default path. This guard only marks promo,
bots, and solicitations. A short human remark is not spam. Non-claims are not
spam. The live pipeline uses it only when ``free_ingest`` is on.
"""

from __future__ import annotations

import re

from pipeline.cleaning import HASHTAG_RE, REPEAT_RE, URL_RE

# Phrases that showed up as Jev spam (score >= 0.8) and are rare in ordinary
# remarks. Political speech, a single news link, and short replies are absent
# on purpose: Jev's non-spam set is full of those.
_PROMO_PHRASES = (
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
    "link in bio",
    "link in my bio",
    "don't scroll",
    "dont scroll",
    "pre-order",
    "preorder",
    "free books",
    "shop now",
    "venmo only",
    "buy followers",
    "follow for follow",
    "followback",
    "follow back",
    "promo code",
    "use code",
    "adult-dating",
    "findomme",
    "findom",
    "smart money",
    "tune in now",
    "now playing on",
    "get that book",
    "hot gameplay highlight",
    "check it out here",
    "cashapp",
    "guaranteed returns",
)

_AGGREGATOR_RE = re.compile(r"more on \".+\" at \S+", re.IGNORECASE)
_STORE_RELEASE_RE = re.compile(r"new release\s*\[", re.IGNORECASE)
_CRYPTO_PRICE_RE = re.compile(
    r"(?:price\s*:\s*\$|accumulated\s+\$|\b(?:15m|1h|4h|24h)\s+chart\b)",
    re.IGNORECASE,
)
_AD_TAG_RE = re.compile(r"(?:^|\s)#ad\b", re.IGNORECASE)
# Solicitations and store bots. Word boundaries, so "Center Now" is not
# "enter now" and a news URL is not a store link. "giveaways" (plural) is
# left alone: that shows up in news about a promotion, not the promo itself.
_COMMERCE_RE = re.compile(
    r"(?:"
    r"\benter\s+to\s+win\b"
    r"|\bdm\s+to\s+claim\b"
    r"|\bamazon\.com/dp/"
    r"|\bamzn\.to/"
    r"|\bebay\.com/itm/"
    r"|\bgumroad\.com\b"
    r"|\bfree\s+trial\b"
    r"|\bon\s+sale\s+now\b"
    r"|\bsee\s+what\s+you\s+qualify\b"
    r"|\border\s+yours\b"
    r"|\bkindle\s+unlimited\b"
    r"|\breview\s+cop(?:y|ies)\b"
    r"|\bdownload\s*&\s*listen\b"
    r"|\brare\s+item\s+alert\b"
    r"|\bmarket\s+size\b"
    r"|\bcagr\b"
    r"|\bcontestreminder\b"
    r"|\bsweepstakes\b"
    r"|#giveaway\b"
    r"|\bgiveaway\b.{0,60}\b(?:enter|win|contest|ends)\b"
    r"|\b(?:enter|win|contest)\b.{0,60}\bgiveaway\b"
    r"|\bdiscount\s+code\b"
    r"|\bcoupon\s+code\b"
    r"|\bflash\s+sale\b"
    r"|\bfree\s+shipping\b"
    r"|\badd\s+to\s+cart\b"
    r"|\bmint\s+now\b"
    r"|\bseed\s+phrase\b"
    r"|\bwallet\s+connect\b"
    r"|\bfansly\b"
    r"|\bpaypal\.me/"
    r"|\broundtrip,\s+including\s+all\s+taxes\b"
    r"|\[ad\]"
    r"|\baffiliate\s+link\b"
    r"|\bsponsored\s+post\b"
    r"|\bnow\s+playing\b"
    r")",
    re.IGNORECASE,
)
# Clock-stamped headline bots: "The news at 04:37:57 is:".
_NEWSBOT_RE = re.compile(r"\bthe news at \d{2}:\d{2}:\d{2} is:", re.IGNORECASE)
# Hashtag stuffing. Ordinary posts use one or two tags.
_HASHTAG_CAP = 6


def post_body(post: dict) -> str:
    return str(post.get("text") or post.get("clean_text") or "")


def guard_reason(post: dict) -> str | None:
    """Why this post is spam, or None to let it through.

    None means keep. A reason means block. Claim versus not-claim is not a
    reason: a non-spam aside is kept.
    """
    text = post_body(post)
    if not text.strip():
        return "empty"
    lowered = text.lower()
    if any(phrase in lowered for phrase in _PROMO_PHRASES):
        return "promo"
    if _COMMERCE_RE.search(text):
        return "promo"
    if _NEWSBOT_RE.search(text):
        return "bot"
    if _AD_TAG_RE.search(text):
        return "ad"
    if _AGGREGATOR_RE.search(text):
        return "aggregator"
    if _STORE_RELEASE_RE.search(text):
        return "storebot"
    if _CRYPTO_PRICE_RE.search(text):
        return "crypto"
    if REPEAT_RE.search(text):
        return "repeat"
    if len(HASHTAG_RE.findall(text)) > _HASHTAG_CAP:
        return "hashtags"
    stripped = HASHTAG_RE.sub(" ", URL_RE.sub(" ", text))
    tokens = [part for part in stripped.split() if part]
    tags = HASHTAG_RE.findall(text)
    if tokens and len(tags) / len(tokens) > 0.45 and len(tags) >= 4:
        return "hashtags"
    return None


def is_blocked(post: dict) -> bool:
    return guard_reason(post) is not None


def partition_guard(posts: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split posts into (kept, blocked-with-reason). Order is preserved."""
    kept: list[dict] = []
    blocked: list[tuple[dict, str]] = []
    for post in posts:
        reason = guard_reason(post)
        if reason is None:
            kept.append(post)
        else:
            blocked.append((post, reason))
    return kept, blocked
