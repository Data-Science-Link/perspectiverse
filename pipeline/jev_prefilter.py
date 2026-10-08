"""Free checks that run before a post is sent to Jev.

The word floor is 6, not 8. On the 10,000 Jev-approved claims from the
2026-10-08 corpus (Actions run 37789244791), ``measure_claim_loss`` with
these same checks dropped 465 claims at a floor of 8 (4.65%) and 357 at a
floor of 7 (3.57%). The quality bar is 3%. The shipped floor of 6 dropped
269 of 10,000 (2.69%): 185 short, 75 language, 1 link, and 8 near-duplicates.
"""

from __future__ import annotations

import hashlib
import re

from pipeline.cleaning import URL_RE

# Fewer than this many whitespace-separated words on the cleaned text.
# Tuned on the retained corpus so the whole pre-filter stays within 3%.
MIN_WORDS = 6
# A post that is only a link has fewer alphabetic words than this after URLs go.
_LINK_WORD_MAX = 3
# Near-duplicate simhash distance. Used only when both texts have enough tokens
# that a random collision is not the short-post case.
_NEAR_DUP_TOKENS = 8
_NEAR_DUP_DISTANCE = 3
_BANDS = 4
_BAND_BITS = 16

_ENGLISH_WORDS = frozenset(
    """
    a an the and or but if then of to in on for with at by from as is are was were
    be been being it this that these those i you he she we they me him her us them
    my your his its our their not no nor so than too very can could should would
    will just about into over after before up down out off what when who how why
    which there do did does have has had all any some other such only also more
    most same own
    """.split()
)

# Function words that are rare in English claims. A hit or two is not enough;
# the post has to lean on these more than on English function words.
_FOREIGN_WORDS = frozenset(
    """
    het een niet voor zijn aan ook maar naar bij nog wel geen deze dit wij zij
    jullie wordt werd und der das eine für den dem des sich von zu im dass oder
    wie aber nach bei aus nur noch wenn sind wird wurde haben über zum zur ich
    le les des une est pas que dans pour sur avec par plus nous vous ils elle
    aux du au cette ces qui dont ne ou mais comme sont été los las por como más
    pero sus del está hay porque cuando también muy sin sobre entre och att är
    inte som på för av ett till jag ska från eller när också efter mellan og
    ikke não uma para com os as do da dos das um se mais foi são está ve bir
    için ile çok daha olan olarak ama gibi kadar sonra önce değil gli che non
    per della dei delle anche più questo questa de het
    """.split()
) - _ENGLISH_WORDS


def post_text(post: dict) -> str:
    """Text Jev would see. Cleaning has already stripped URLs and handles."""
    return str(post.get("clean_text") or post.get("text") or "")


def post_raw(post: dict) -> str:
    return str(post.get("text") or post.get("clean_text") or "")


def word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", (text or "").strip()) if part])


def normalized_tokens(text: str) -> list[str]:
    """Case, URL, and punctuation folded. Used for the near-duplicate fingerprint."""
    folded = URL_RE.sub(" ", text or "").lower()
    folded = re.sub(r"[^a-z0-9\s]", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    return folded.split()


def text_fingerprint(text: str) -> str:
    """64-bit simhash of normalized tokens, as 16 hex chars. Empty when there are none."""
    tokens = normalized_tokens(text)
    if not tokens:
        return ""
    weights = [0] * 64
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, "big")
        for bit in range(64):
            weights[bit] += 1 if (hashed >> bit) & 1 else -1
    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight > 0:
            fingerprint |= 1 << bit
    return f"{fingerprint:016x}"


def _band_keys(fingerprint: int) -> list[int]:
    return [(fingerprint >> (band * _BAND_BITS)) & 0xFFFF for band in range(_BANDS)]


class DuplicateIndex:
    """Near-exact duplicates of posts that were already scored.

    The index stores simhashes, not text, so a non-claim can leave the corpus
    and still suppress a later copy. Hamming distance is the near-exact test
    once a post has enough tokens; shorter posts match only an identical hash.
    """

    def __init__(self) -> None:
        self._bands: list[dict[int, list[int]]] = [{} for _ in range(_BANDS)]

    def add_fingerprint(self, fingerprint: str) -> None:
        if not fingerprint:
            return
        value = int(fingerprint, 16)
        for band, key in enumerate(_band_keys(value)):
            self._bands[band].setdefault(key, []).append(value)

    def add_text(self, text: str) -> None:
        self.add_fingerprint(text_fingerprint(text))

    def is_duplicate(self, text: str) -> bool:
        fingerprint = text_fingerprint(text)
        if not fingerprint:
            return False
        value = int(fingerprint, 16)
        limit = _NEAR_DUP_DISTANCE if len(normalized_tokens(text)) >= _NEAR_DUP_TOKENS else 0
        seen: set[int] = set()
        for band, key in enumerate(_band_keys(value)):
            for other in self._bands[band].get(key, ()):
                if other in seen:
                    continue
                seen.add(other)
                if (value ^ other).bit_count() <= limit:
                    return True
        return False


def declared_non_english(post: dict) -> bool:
    """True when the post names languages and English is not one of them.

    Jetstream carries ``langs``. Search posts usually do not, and then the
    local check below decides.
    """
    raw = post.get("langs")
    if raw is None or raw == "":
        raw = post.get("lang")
    if raw is None or raw == "":
        return False
    if isinstance(raw, str):
        codes = [part.strip().lower() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        codes = [str(part).strip().lower() for part in raw if str(part).strip()]
    else:
        return False
    if not codes:
        return False
    return not any(code == "en" or code.startswith("en-") for code in codes)


def _styled_latin(code: int) -> bool:
    """Mathematical and fullwidth Latin still read as English."""
    return 0x1D400 <= code <= 0x1D7FF or 0xFF21 <= code <= 0xFF5A


def _non_latin_share(text: str) -> tuple[int, int]:
    other = 0
    total = 0
    for char in text or "":
        if not char.isalpha():
            continue
        total += 1
        code = ord(char)
        if code < 128 or 0x00C0 <= code <= 0x024F or _styled_latin(code):
            continue
        other += 1
    return other, total


def _alpha_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿĀ-ž']+", text or "")


def looks_non_english(text: str) -> bool:
    """Cheap local check. Headlines with no function words stay English."""
    other, total = _non_latin_share(text)
    if total >= 8 and other >= 8 and other / total >= 0.25:
        return True
    tokens = [token.lower().strip("'") for token in _alpha_tokens(text)]
    if len(tokens) < 5:
        return False
    english_hits = sum(1 for token in tokens if token in _ENGLISH_WORDS)
    foreign_hits = sum(1 for token in tokens if token in _FOREIGN_WORDS)
    return foreign_hits >= 2 and foreign_hits > english_hits


def _link_only(post: dict) -> bool:
    """A post whose words disappear once the URL is removed."""
    raw = post_raw(post)
    if not URL_RE.search(raw):
        return False
    stripped = URL_RE.sub(" ", post_text(post))
    return len(_alpha_tokens(stripped)) < _LINK_WORD_MAX


def prefilter_reason(post: dict, duplicates: DuplicateIndex | None = None) -> str | None:
    """Why this post should not be sent to Jev, or None to score it.

    ``duplicate`` is a near-exact copy of a post already passed to ``duplicates``.
    The caller adds a post to that index only after this returns None, so the
    first copy is scored and the later copies are skipped.
    """
    if _link_only(post):
        return "link"
    if word_count(post_text(post)) < MIN_WORDS:
        return "short"
    if declared_non_english(post) or looks_non_english(post_text(post)):
        return "language"
    if duplicates is not None and duplicates.is_duplicate(post_text(post)):
        return "duplicate"
    return None


def measure_claim_loss(posts: list[dict]) -> dict[str, int]:
    """How many posts the pre-filter would drop, counted once each.

    Walks posts in order. A kept post becomes an already-scored fingerprint,
    which is how a later near-copy is judged.
    """
    counts = {"short": 0, "language": 0, "link": 0, "duplicate": 0, "kept": 0}
    index = DuplicateIndex()
    for post in posts:
        reason = prefilter_reason(post, index)
        if reason is None:
            counts["kept"] += 1
            index.add_text(post_text(post))
        else:
            counts[reason] += 1
    counts["dropped"] = len(posts) - counts["kept"]
    return counts
