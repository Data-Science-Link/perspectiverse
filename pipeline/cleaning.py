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

# Login walls, paywalls, and bot checks copied from scraped pages — not claims.
_BOILERPLATE_PHRASES = (
    "sign in to view",
    "sign in to read",
    "sign in to continue",
    "sign in to access",
    "sign in to see",
    "log in to view",
    "log in to read",
    "log in to continue",
    "log in to access",
    "login to view",
    "login to continue",
    "please log in to",
    "please sign in to",
    "you must log in",
    "you must sign in",
    "must be logged in to",
    "must be signed in to",
    "verify you are human",
    "verify that you are human",
    "confirm you are human",
    "prove you are human",
    "checking your browser before accessing",
    "checking your browser",
    "enable cookies to continue",
    "cookies must be enabled",
    "please enable cookies",
    "javascript is required",
    "enable javascript to",
    "javascript must be enabled",
    "subscribe to read",
    "subscribe to continue",
    "subscribe to view",
    "subscription required",
    "create an account to view",
    "create an account to read",
    "create an account to continue",
    "register to view",
    "register to read",
    "registration required",
    "unlock this article",
    "already a subscriber? sign in",
    "complete the captcha",
    "security check to continue",
    "access to this page has been denied",
    "attention required! | cloudflare",
    "attention required",
    "ddos protection by cloudflare",
)
# Longer scraped pages can still be mostly chrome; residue check uses this ceiling.
_BOILERPLATE_MAX_LEN = 320
_BOILERPLATE_MAX_RESIDUE_WORDS = 4
_BOILERPLATE_RESIDUE_STOP = frozenset(
    """
    a an the this that these those our your their its here there please just
    page post posts story article content site forum thread link more rest
    """.split()
)

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


def _normalize_for_boilerplate(text: str) -> str:
    folded = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    return WHITESPACE_RE.sub(" ", folded).strip()


def _boilerplate_residue_words(lowered: str, phrase: str) -> list[str]:
    residue = lowered.replace(phrase, " ")
    residue = re.sub(r"[^a-z0-9']+", " ", residue)
    return [
        part
        for part in residue.split()
        if part and part not in _BOILERPLATE_RESIDUE_STOP
    ]


def is_login_wall_boilerplate(text: str) -> bool:
    """True when the post is page chrome, not someone arguing about access."""
    lowered = _normalize_for_boilerplate(text)
    if not lowered:
        return False
    for phrase in _BOILERPLATE_PHRASES:
        if phrase not in lowered:
            continue
        residue = _boilerplate_residue_words(lowered, phrase)
        if len(residue) <= _BOILERPLATE_MAX_RESIDUE_WORDS and len(lowered) <= _BOILERPLATE_MAX_LEN:
            return True
    return False


def clean_text(text: str) -> str:
    """Strip URLs and handles and collapse whitespace."""
    without_urls = URL_RE.sub(" ", text or "")
    without_handles = HANDLE_RE.sub(" ", without_urls)
    return WHITESPACE_RE.sub(" ", without_handles).strip()


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
        raw_text = str(post.get("text") or "")
        text = clean_text(raw_text)
        if is_login_wall_boilerplate(raw_text) or is_login_wall_boilerplate(text):
            try:
                from pipeline.costs import note_jev_prefilter

                note_jev_prefilter("boilerplate")
            except Exception:
                pass
            continue
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
