"""Free local filter for greeting and chit-chat posts (#208).

No network and no model calls. A post is chit-chat when its text is a social
gesture — a thank-you or compliment reply, a birthday or holiday wish, a
live-now self-promotion, or a one-word agreement — and it does not carry a
public topic. Planet titles are not an input. Used at free ingest before the
daily cap, and as a planet guard after labeling.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.cleaning import HASHTAG_RE, URL_RE
from pipeline.language import is_link_only, looks_english
from pipeline.spam_guard import guard_reason, post_body

# Majority of member posts. Titles are not consulted.
PLEASANTRY_SHARE_DROP = 0.55
# A model "yes" needs the posts to agree. In the preview fixture every
# real-topic planet is 0% pleasantry (97 of the 100 non-target planets).
# The only planets under 55% that contain any pleasantry are at 50%
# (one of two representatives). 30% is the empty gap between those.
MODEL_CHITCHAT_SHARE_FLOOR = 0.30

# Social and function words. A token here is not a public topic.
_FILLER = frozenset(
    {
        "that", "this", "with", "from", "they", "them", "their", "there", "these", "those",
        "have", "been", "were", "will", "would", "could", "should", "about", "after", "before",
        "because", "while", "where", "which", "what", "when", "your", "youre", "youve", "yours",
        "just", "like", "really", "very", "much", "some", "more", "than", "then", "into", "over",
        "also", "only", "even", "still", "back", "here", "going", "gonna", "wanna", "gotta",
        "want", "wants", "wanted", "know", "knew", "think", "thinking", "make", "made", "makes",
        "doing", "does", "dont", "didnt", "cant", "wont", "isnt", "arent", "wasnt", "being",
        "having", "other", "people", "thing", "things", "something", "someone", "anyone",
        "everyone", "everything", "nothing", "please", "today", "tonight", "tomorrow", "always",
        "again", "never", "little", "super", "totally", "literally", "actually", "maybe",
        "probably", "already", "another", "first", "time", "times", "week", "weeks", "month",
        "year", "years", "days", "look", "looks", "looking", "seen", "seeing", "gets", "getting",
        "yeah", "yep", "yup", "sure", "well", "hope", "hopes", "hoping", "love", "loved", "loving",
        "good", "great", "nice", "best", "many", "most", "thank", "thanks", "thankyou",
        "happy", "hello", "morning", "night", "evening", "afternoon", "birthday", "bday",
        "birthdays", "anniversary", "weekend", "weekends", "luck", "late", "wishing", "wish",
        "wishes", "fun", "course", "count", "absolutely", "exactly", "agreed", "same", "true",
        "said", "says", "live", "stream", "streams", "streaming", "twitch", "starting", "soon",
        "come", "came", "hang", "hop", "tune", "watch", "watching", "pretty", "gorgeous",
        "beautiful", "stunning", "amazing", "wonderful", "awesome", "congrats", "congratulations",
        "appreciate", "appreciated", "appreciation", "sharing", "share", "shared", "enjoy",
        "enjoyed", "aww", "omg", "lol", "haha", "hehe", "yay", "wow", "yes", "okay",
        "friend", "friends", "bestie", "dude", "dear", "honey", "baby", "babe", "folks", "guys",
        "yall", "girl", "boy", "mom", "mum", "dad", "cute", "lovely", "sweet", "sexy", "hot",
        "adorable", "delightful", "perfect", "incredible", "kind", "glad", "feeling", "feelings",
        "feel", "feels", "felt", "photo", "photos", "pic", "pics", "piece", "pieces", "work",
        "works", "art", "arts", "content", "community", "support", "supportive", "honor",
        "inspired", "inspiration", "reaction", "reactions", "hugs", "hug", "purrs", "purr",
        "safe", "take", "care", "saturday", "sunday", "friday", "monday", "thursday",
        "wednesday", "tuesday", "fabulous", "peaceful", "smashing", "better", "recovered",
        "sorry", "both", "rest", "existence", "celebration", "cause", "treat", "couple",
        "endeavor", "welcome", "thankful", "warm", "special", "gift", "gifts", "present",
        "presents", "damn", "open", "means", "list", "moments", "moment", "confidence",
        "pack", "starter", "adding", "shading", "mood", "shape", "specimen", "exotic",
        "colors", "color", "colours", "colour", "bright", "warn", "warning", "beauty",
        "including", "outstanding", "helping", "scary", "generous", "aroused", "polite",
        "exciting", "excitingly", "extremely", "truly", "recent", "quick", "real", "less",
        "helped", "play", "next", "comforted", "encouraging", "post", "posts", "around",
        "through", "under", "down", "away", "right", "left", "long", "full", "part", "last",
        "lots", "need", "keep", "give", "gave", "tell", "told", "gone", "ours", "mine",
        "youll", "youd", "theyre", "theyve", "lets", "theres", "heres", "whats", "thats",
        "met", "way", "woman", "much", "will", "know", "make", "best", "day", "evening",
        "always", "today", "again", "dear", "friend",
    }
)

# A public topic keeps the post even when a social word is in it.
_NEWS_RE = re.compile(
    r"\b(?:veterans?|congress|senate|senators?|court|rulings?|laws?|bills?|council|"
    r"votes?|voting|voters?|polic(?:y|ies)|wages?|reports?|invasion|ukrain\w*|housing|"
    r"gambling|elections?|presidents?|tax(?:es)?|tariffs?|military|police|hospitals?|"
    r"vaccines?|climate|schools?|students?|universit\w*|inflation|strikes?|unions?|"
    r"protests?|refugees?|treat(?:y|ies)|sanctions?|parliament|ministers?|governors?|"
    r"mayors?|rights|amendments?|constitution|judges?|trials?|crimes?|workers?|"
    r"medicare|medicaid|insurance|immigration|abortion|healthcare|borders?|lawsuits?|"
    r"indictments?|verdicts?|prisons?|ceasefire|missiles?|nato|gaza|israel\w*|russia\w*|"
    r"china|chinese|legislation|regulations?|federal|emissions|wildfires?|hurricanes?|"
    r"cancers?|doctors?|patients?|teachers?|tuition|curriculum|algebra|calculus|"
    r"prerequisites?|statistics|injur(?:y|ed|ies)|championships?|leagues?|tournaments?|"
    r"playoffs?|measles|covid|pandemic|outbreaks?|prevention|diseases?|diagnos\w*|"
    r"overdoses?|fentanyl|economy|nasdaq|diesel|embargo|nuclear|shootings?|genocide|"
    r"apartheid|fascis\w*|ballots?|renters?|seized|charms?|moderation|governments?|"
    r"contracts?|citizenship|investigations?|administration|supreme|scotus|flu|"
    r"symptoms?|lessons?|vaccines?|ndp|canadians?|pope|popes|troops|trump|putin|musk)\b",
    re.IGNORECASE,
)

_WORK_RE = re.compile(
    r"\b(?:songs?|albums?|movies?|films?|books?|novels?|poems?|goals?|scored|assists?|podcasts?)\b",
    re.IGNORECASE,
)

_STREAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitch\.tv/|kick\.com/|youtube\.com/live/)",
    re.IGNORECASE,
)
_STREAM_PHRASE_RE = re.compile(
    r"\b(?:live now|going live|go live|im live|i am live|were live|we are live|"
    r"stream is starting|stream starting|streams starting|stream starts|streams start|stream time|streaming now|"
    r"now live|bonus stream|come hop in|hop in|live right now)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_AGREEMENT_EXACT = frozenset(
    {
        "of course",
        "for sure",
        "count me in",
        "absolutely",
        "exactly",
        "agreed",
        "yes",
        "yeah",
        "yep",
        "yup",
        "same",
        "sure",
        "in",
        "im in",
        "i am in",
        "this",
        "so true",
        "well said",
        "same here",
        "me too",
        "facts",
        "true",
        "ok",
        "okay",
        "k",
        "in you",
        "get in",
        "count me in im there",
        "im in yay",
        "well i am in",
        "yeah just got in you",
        "oooo ill try to be there",
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


def _plain(raw: str) -> str:
    """Lowercase words with URLs, hashtags, and punctuation removed.

    Apostrophes are removed so ``you're`` and ``you're`` compare as ``youre``.
    Stream hosts are detected on the original text before this runs.
    """
    text = raw or ""
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", " ")
        .replace("\u201d", " ")
    )
    text = HASHTAG_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = re.sub(r"(?:https?://)?(?:www\.)?(?:twitch\.tv|kick\.com)/\S+", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9'\s]", " ", text)
    text = text.replace("'", "")
    return " ".join(text.lower().split())


def _tokens(plain: str) -> list[str]:
    return _TOKEN_RE.findall(plain or "")


def _substance(plain: str) -> list[str]:
    """Content words that are not social filler. These are what a topic post has."""
    return [token for token in _tokens(plain) if len(token) >= 4 and token not in _FILLER]


def _news(plain: str) -> bool:
    return bool(_NEWS_RE.search(plain or ""))


def _work_topic(plain: str) -> bool:
    return bool(_WORK_RE.search(plain or ""))


def _sports_play(raw: str) -> bool:
    """A named play or goal, not a compliment aimed at a person."""
    text = raw or ""
    if re.search(r"\bcross from\b", text, flags=re.I):
        return True
    if re.search(r"#\d{1,3}\b", text) and re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text):
        return True
    if re.search(r"\b(?:goal|scored|assist|hat trick|hat-trick)\b", text, flags=re.I) and re.search(
        r"\b[A-Z]{3,}\b|\b[A-Z][a-z]+ [A-Z][a-z]+\b",
        text,
    ):
        return True
    return False


def _word_count(plain: str) -> int:
    return len((plain or "").split())


def _agreement(plain: str) -> bool:
    text = re.sub(
        r"^(?:(?:aww+|omg+|lol+|haha+|hehe+|yes+|but|and|so|well|yeah|yep|ok|okay)\s+)+",
        "",
        plain or "",
    ).strip()
    text = re.sub(r"(?:\s+lol)+$", "", text).strip()
    if text in _AGREEMENT_EXACT:
        return True
    if _news(plain):
        return False
    if _word_count(plain) <= 10 and re.search(
        r"\b(?:count me in|im in|i am in|checking in|join in|tap in|get in|goin in|going in|dive in|got in|be there)\b",
        plain or "",
    ):
        # "I'm in!" is agreement. "I'm in Spain" names a place and stays.
        return len(_substance(plain)) <= 1
    return False


def _stream_promo(raw: str, plain: str) -> bool:
    url = bool(_STREAM_URL_RE.search(raw or ""))
    phrase = bool(_STREAM_PHRASE_RE.search(plain or ""))
    mentions = bool(re.search(r"\b(?:stream|streams|streaming|twitch)\b", plain or ""))
    invite = bool(
        re.search(
            r"\b(?:im|ive|we|my|our|come|join|hop|hang|tonight|today|tomorrow|live|ill|lets)\b",
            plain or "",
        )
    )
    if not (url or phrase or (mentions and invite)):
        return False
    # A hearing, a vote, or a bill signing that says "live now" is coverage.
    # Once a civic or government topic is present, the live phrase does not
    # count. A channel URL is still a self-promotion.
    if _news(plain) and not url:
        return False
    return True


def _person_directed(plain: str) -> bool:
    return bool(
        re.search(r"\b(?:you|your|youre|youve)\b", plain or "")
        or re.search(r"\blove (?:her|him|them)\b", plain or "")
    )


def _thanks(plain: str) -> bool:
    if not (
        re.search(r"\b(?:thank you|thanks|thankyou|thx)\b", plain or "")
        or plain in {"ty", "thx"}
        or re.search(r"\byoure welcome\b", plain or "")
    ):
        return False
    if _news(plain) or _work_topic(plain) or _sports_play(plain):
        return False
    return len(_substance(plain)) <= 1


def _compliment(raw: str, plain: str) -> bool:
    if not re.search(
        r"\b(?:cute|beautiful|gorgeous|stunning|lovely|sexy|adorable|delightful|"
        r"so pretty|love this|love it|love her|love him|love you|love that you|so hot)\b",
        plain or "",
    ):
        return False
    if _news(plain) or _work_topic(plain) or _sports_play(raw):
        return False
    subs = _substance(plain)
    if _person_directed(plain):
        return len(subs) <= 2 and _word_count(plain) <= 40
    # A bare "so cute" / "beautiful!" with no topic noun. One real noun keeps it.
    return len(subs) == 0 and _word_count(plain) <= 24


def _wish(plain: str) -> str | None:
    if _news(plain):
        return None
    if re.search(r"\bgood luck charms?\b", plain or ""):
        pass
    elif re.search(r"\b(?:good luck|best of luck)\b", plain or "") and len(_substance(plain)) <= 4:
        return "luck"
    if re.search(r"\bhappy anniversary\b", plain or "") and not re.search(r"\banniversary of\b", plain or ""):
        if len(_substance(plain)) <= 6:
            return "wish"
    if re.search(r"\bhappy\s+(?:\w+\s+){0,3}(?:birthday|bday)\b", plain or "") or re.search(
        r"\b(?:happy bday|bday)\b", plain or ""
    ):
        if len(_substance(plain)) <= 8:
            return "wish"
    if re.search(r"\bmy birthday\b", plain or "") and len(_substance(plain)) <= 6 and _word_count(plain) <= 36:
        return "wish"
    if re.search(r"\bbirthday\b", plain or "") and len(_substance(plain)) <= 2 and _word_count(plain) <= 24:
        return "wish"
    if re.search(r"\bhope\b.{0,40}\bbirthday\b", plain or "") and len(_substance(plain)) <= 4:
        return "wish"
    if re.search(r"\bweekends?\b", plain or ""):
        short = len(_substance(plain)) <= 2 and _word_count(plain) <= 18
        wished = bool(
            re.search(
                r"\b(?:have a|wishing|hope|happy|great|good|nice|fun|fabulous|peaceful|smashing|wonderful|lovely)\b",
                plain or "",
            )
        ) and len(_substance(plain)) <= 6 and _word_count(plain) <= 36
        if short or wished:
            return "weekend"
    if re.search(
        r"\b(?:happy thanksgiving|merry christmas|happy new year|happy holidays|happy hanukkah|eid mubarak)\b",
        plain or "",
    ):
        if len(_substance(plain)) <= 4:
            return "wish"
    if re.search(r"\b(?:congrats|congratulations|best wishes)\b", plain or "") and len(_substance(plain)) <= 4:
        if _word_count(plain) <= 30:
            return "wish"
    return None


def _greeting(plain: str) -> bool:
    return plain in {
        "gm",
        "gn",
        "hello",
        "hi",
        "hey",
        "howdy",
        "good morning",
        "good night",
        "good evening",
        "good afternoon",
    }


def pleasantry_reason(post: dict) -> str | None:
    """Why this post is chit-chat, or None to keep it.

    The decision is the post text. A public-topic word (a law, a war, a team
    result, a song, a place) keeps a post that merely uses a social word.
    """
    raw = post_body(post)
    if not raw.strip():
        return None
    plain = _plain(raw)
    if not plain:
        return None
    if _agreement(plain):
        return "agreement"
    if _stream_promo(raw, plain):
        return "stream_announce"
    kind = _wish(plain)
    if kind:
        return kind
    if _thanks(plain):
        return "thanks"
    if _compliment(raw, plain):
        return "compliment"
    if _greeting(plain):
        return "greeting"
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
    model_chitchat: bool | None = None,
) -> str | None:
    """Drop a planet from its posts, never from its title.

    ``name`` and ``terms`` are ignored. Callers still pass the label so logs
    can name the planet; a rename cannot keep or drop it. ``model_chitchat``
    is the yes/no field on the existing planet-naming response. Yes alone
    does not drop a planet. The posts have to be at least 55% chit-chat, or
    the model has to say yes and at least 30% of the posts agree.
    """
    del terms, name
    if not members:
        return None
    share = pleasantry_share(members)
    if share >= PLEASANTRY_SHARE_DROP:
        return f"{share:.0%} of the posts are chit-chat"
    if model_chitchat is True and share >= MODEL_CHITCHAT_SHARE_FLOOR:
        return f"naming prompt marked the posts as chit-chat and {share:.0%} of the posts agree"
    return None
