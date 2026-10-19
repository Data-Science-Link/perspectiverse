"""Free local filter for greeting and chit-chat posts (#208).

No network and no model calls. A post is chit-chat when its text is a social
gesture — a thank-you or compliment reply, a birthday, holiday, or get-well
wish, a live-now self-promotion, or a one-word agreement — and it does not carry a
public topic. A personal health update is the author's own illness, surgery,
or recovery journal. Health news and public-health or policy posts stay.
Planet titles are not an input. Used at free ingest before the daily cap, and
as a planet guard after labeling.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pipeline.cleaning import HANDLE_RE, HASHTAG_RE, URL_RE
from pipeline.language import edition_filter_reason, is_link_only, partition_posts
from pipeline.spam_guard import guard_reason, post_body
from pipeline.weather_guard import weather_bot_reason

# Majority of member posts. Titles are not consulted.
PLEASANTRY_SHARE_DROP = 0.55
# A model "yes" needs the posts to agree. In the preview fixture every
# real-topic planet is 0% pleasantry (97 of the 100 non-target planets).
# The only planets under 55% that contain any pleasantry are at 50%
# (one of two representatives). 30% is the empty gap between those.
MODEL_CHITCHAT_SHARE_FLOOR = 0.30

# Link-only and non-English filtering before clustering is ``partition_posts``.
# That call is on main (pre-#209), in live.py since 322b12f. Main's free ingest
# stored those posts: ``keep_non_spam`` dropped only spam, so they counted
# toward the corpus, and ``partition_posts`` then kept them out of clustering.
#
# This flag is the #209 ingest drop, added in d721778. It does not turn the
# main clustering filter off.
# True (default): ingest refuses them, so they do not count toward the 100K,
# and clustering still skips any that are already stored.
# False, or ``DROP_LINK_AND_LANGUAGE_AT_INGEST=0``: main's behavior. They
# count toward the stored corpus, and ``edition_posts_for_clustering`` still
# removes them before clustering. They are not clustered in either setting.
DROP_LINK_AND_LANGUAGE_AT_INGEST = True

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
    r"\b(?:veterans?|congress|senate|senators?|court|rulings?|(?<!\bin )laws?|bills?|council|"
    r"impeach(?:ed|ment|ments)?|"
    r"votes?|voting|voters?|voted|polic(?:y|ies)|wages?|reports?|invasion|ukrain\w*|housing|"
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

# Political or argumentative posts that open with thanks or “great”.
_DISCUSSION_RE = re.compile(
    r"\b(?:nazis?|fascists?|never forget|scumbag|stolen|destroying|communities|"
    r"environment|screenplay|studios?|webtoon|comicfury|itch|tumblr|organizations?|"
    r"audience|ebooks?|treatments?|hires?|industry|platforms?)\b",
    re.IGNORECASE,
)

_CIVIC_TAG_RE = re.compile(
    r"#(?:ivoted|voteblue|votered|nokings|resist|fbr|vote)\b",
    re.IGNORECASE,
)

_GESTURE_WIPE_RE = re.compile(
    r"\b(?:thank you|thanks|thankyou|thx|ty|my pleasure|youre welcome|you are welcome|"
    r"happy to help|glad to help|no problem|dont mention it|of course|"
    r"incredible|awesome|amazing|beautiful|gorgeous|stunning|lovely|fantastic|wonderful|"
    r"great|best|photogenic|cute|hot|sexy|adorable|delightful|so good|so pretty|"
    r"love it|love this|love you|thankful|grateful|appreciate|pleasure|welcome|"
    r"photogenic|wonderful design|lovely work|nice work|amazing work|great work)\b",
    re.IGNORECASE,
)

# Thanks-heavy courtesy clusters (#227). Independent of a single anchor post.
THANK_PLANET_MIN_MEMBERS = 15
THANK_PLANET_SHARE_DROP = 0.25
THANK_PLANET_MIN_THANKS = 5
# Mention-based thanks balls can be mostly long-form gratitude, not ingest thanks.
THANK_PLANET_MENTION_SHARE_DROP = 0.30
# Reaction / stream balls sized like published chit-chat planets.
GESTURE_CLUSTER_MIN_MEMBERS = 40
GESTURE_CLUSTER_SHARE_DROP = 0.38
STREAM_CLUSTER_MIN_MEMBERS = 50
STREAM_CLUSTER_SHARE_DROP = 0.30

_STREAMING_PLATFORM_SALIENT_TERMS = frozenset(
    {
        "twitch",
        "kick",
        "youtube",
        "youtu",
        "rumble",
        "mixer",
        "joystick",
    }
)
_STREAM_PLATFORM_DROP_REASON = "Mostly about a streaming platform, not a topic"

_WORK_RE = re.compile(
    r"\b(?:songs?|albums?|movies?|films?|books?|novels?|poems?|goals?|scored|assists?|podcasts?)\b",
    re.IGNORECASE,
)

# A YouTube live URL is a news or podcast link unless the words are a promo.
_STREAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitch\.tv/|kick\.com/)",
    re.IGNORECASE,
)
# Stream hosts for planet stream-share (includes subdomains and YouTube /live).
_STREAM_DOMAIN_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)*twitch\.tv(?:/\S*)?|"
    r"(?:https?://)?(?:[\w-]+\.)*kick\.com(?:/\S*)?|"
    r"(?:https?://)?(?:www\.)?youtube\.com/live(?:/\S*)?",
    re.IGNORECASE,
)
_STREAM_PHRASE_RE = re.compile(
    r"\b(?:live now|going live|go live|im live|i am live|were live|we are live|"
    r"stream is starting|stream starting|streams starting|stream starts|streams start|stream time|"
    r"time to stream|its time to stream|streaming now|"
    r"im streaming|i am streaming|ill be streaming|live on twitch|"
    r"come watch|come join|come hang out|starting now|surprise stream|"
    r"we are streaming|were streaming|ready to stream|impromptu stream|"
    r"gonna start stream|start stream|final stream|"
    r"karaoke stream|"
    r"now live(?!\s+in\b)|bonus stream|come hop in|hop in|live right now)\b",
    re.IGNORECASE,
)
# Cues that count only next to a Twitch or Kick URL. "I live with my parents"
# has no channel URL and stays.
_STREAM_WITH_URL_RE = re.compile(
    r"\b(?:time to|watch now|come through|come hang|hop in|swing on by|be back|live with)\b",
    re.IGNORECASE,
)
_GET_WELL_RE = re.compile(
    r"\b(?:speedy recovery|quick recovery|full recovery|get well(?: soon)?|"
    r"feel better soon|feeling better soon|"
    r"hope(?: \w+){0,3} you(?:re|r)?(?: \w+){0,5} (?:feel better|heal|recover)|"
    r"you heal up|hope your(?: \w+){0,6} recovery|"
    r"prayers? for you|praying for you|wishing you|"
    r"sending (?:healing|prayers)|healing purrs|"
    r"my condolences|sorry for your loss)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_RECOVERY_RE = re.compile(
    r"\b(?:i am|im|ive|i have|i feel|i felt|ive been|i will)\b.{0,40}\b(?:better|recovered|recovery)\b",
    re.IGNORECASE,
)
# A system, law, or outbreak. Not "hospital", "doctor", or "flu": those words
# also appear in someone's own illness journal.
_PUBLIC_HEALTH_RE = re.compile(
    r"\b(?:healthcare|health care|health insurance|medicare|medicaid|"
    r"single payer|universal coverage|premiums?|copays?|"
    r"congress|senate|senators?|governors?|outbreaks?|pandemic|"
    r"vaccines?|staffing|public health|policies|policy)\b",
    re.IGNORECASE,
)
# The phrase already names the author. "sick of" is removed before this runs.
_PERSONAL_HEALTH_AUTHOR_RE = re.compile(
    r"(?:"
    r"\b(?:ive|i have) been (?:so |really |very |pretty |extremely |just |home )?(?:sick|ill)\b"
    r"|\b(?:im|i am) (?:so |really |very |too |just |home )?(?:sick|ill)\b"
    r"|\b(?:i feel|im feeling|ive been feeling|i have been feeling) "
    r"(?:so |really |very |too |extremely )?(?:sick|ill)\b"
    r"|\bfeeling (?:so |really |very )?too ill\b|\bfeeling too ill\b"
    r"|\bfeel(?:ing)? so sick\b"
    r"|\b(?:so |really |very )?sick and ill\b"
    r"|\bgetting sick\b"
    r"|\bnot feeling well\b"
    r"|\bsickly\b"
    r"|\b(?:back|home) from (?:the )?hospital\b"
    r"|\b(?:had|have) to go to (?:the )?hospital\b"
    r"|\b(?:i |ive |im ).{0,50}\b(?:went|going) to (?:the )?hospital\b"
    r"|\bmy (?:surgery|migraine|fever|chemo|chemotherapy|diagnosis|illness|infection|meds)\b"
    r"|\b(?:i had|i have|ive had|ive got|i got|im having) "
    r"(?:a |the |another |massive |bad |really |little ){0,4}(?:migraine|fever|surgery)\b"
    r"|\bmedicated up\b|\b(?:im|i am) medicated\b"
    r"|\bfully recovered from chemo\b|\brecovered from chemo\b"
    r")",
    re.IGNORECASE,
)
# A condition word. It counts only when the author is also in the post.
_PERSONAL_HEALTH_CONDITION_RE = re.compile(
    r"\b(?:migraines?|chemo(?:therapy)?|bedridden|health issues|weak immune|"
    r"threw up|thrown up|vomited|from coughing|my fever|stomach ache|"
    r"fainting)\b",
    re.IGNORECASE,
)
_PERSONAL_HEALTH_AUTHOR_TOKEN_RE = re.compile(r"\b(?:i|im|ive|id|my|me)\b")
_SPORTS_RESULT_RE = re.compile(
    r"\b(?:games?|seasons?|innings?|quarters?|overtime|playoffs?|touchdowns?|goals?|scored|defeated)\b",
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
        self.near_duplicate_blocked = 0
        self.other_blocked = 0
        self.new_stored = 0
        self.already_stored = 0
        self.over_daily_cap = 0
        self.over_target_cap = 0
        self.over_max_new_posts = 0
        self.missing_uri = 0
        self._chitchat_samples: list[dict] = []

    def reset(self) -> None:
        self.fetched = 0
        self.spam_blocked = 0
        self.chitchat_blocked = 0
        self.language_blocked = 0
        self.link_blocked = 0
        self.near_duplicate_blocked = 0
        self.other_blocked = 0
        self.new_stored = 0
        self.already_stored = 0
        self.over_daily_cap = 0
        self.over_target_cap = 0
        self.over_max_new_posts = 0
        self.missing_uri = 0
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
        else:
            self.other_blocked += 1

    def removal_total(self) -> int:
        return (
            self.spam_blocked
            + self.chitchat_blocked
            + self.language_blocked
            + self.link_blocked
            + self.near_duplicate_blocked
            + self.other_blocked
        )

    def accounted_total(self) -> int:
        return (
            self.removal_total()
            + self.new_stored
            + self.already_stored
            + self.over_daily_cap
            + self.over_target_cap
            + self.over_max_new_posts
            + self.missing_uri
        )

    def buckets_reconcile(self) -> bool:
        return self.fetched == self.accounted_total()

    def chitchat_share_of_fetched(self) -> float:
        if self.fetched <= 0:
            return 0.0
        return self.chitchat_blocked / self.fetched

    def to_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "new_stored": self.new_stored,
            "spam_blocked": self.spam_blocked,
            "chitchat_blocked": self.chitchat_blocked,
            "language_blocked": self.language_blocked,
            "link_blocked": self.link_blocked,
            "near_duplicate_blocked": self.near_duplicate_blocked,
            "other_blocked": self.other_blocked,
            "already_stored": self.already_stored,
            "over_daily_cap": self.over_daily_cap,
            "over_target_cap": self.over_target_cap,
            "over_max_new_posts": self.over_max_new_posts,
            "missing_uri": self.missing_uri,
            "accounted_total": self.accounted_total(),
            "buckets_reconcile": self.buckets_reconcile(),
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
    text = HANDLE_RE.sub(" ", text)
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


def _discussion_topic(raw: str, plain: str) -> bool:
    if _CIVIC_TAG_RE.search(raw or ""):
        return True
    return bool(_DISCUSSION_RE.search(plain or ""))


def _gesture_remainder_substance(plain: str) -> list[str]:
    text = _GESTURE_WIPE_RE.sub(" ", plain or "")
    text = re.sub(r"[^\w\s]", " ", text)
    return _substance(" ".join(text.split()))


def _gesture_is_the_post(raw: str, plain: str, *, creator: bool = False) -> bool:
    """True when gratitude or praise is the whole post, not a lead-in to a topic."""
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain):
        return False
    subs = _gesture_remainder_substance(plain)
    if re.search(r"^(?:thank you|thanks|ty|thx)\b", plain or ""):
        return len(subs) <= 3 and _word_count(plain) <= 60
    if creator:
        return len(subs) <= 2 and _word_count(plain) <= 55
    return len(subs) <= 1 and _word_count(" ".join(subs)) <= 6


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
    """A go-live announcement, not a sentence that merely says streaming.

    A strong phrase ("I'm live", "time to stream", "come hop in") is enough.
    A Twitch or Kick URL counts when the post is a short plug or has a go-live
    cue. Mentioning streaming services, a release window, or a channel URL at
    the end of a longer post does not.
    """
    url = bool(_STREAM_URL_RE.search(raw or ""))
    phrase = bool(_STREAM_PHRASE_RE.search(plain or ""))
    # "streaming" in a film-revenue sentence is not a channel announcement.
    if (
        not url
        and not phrase
        and re.search(r"\bstreaming\b", plain or "")
        and not re.search(r"\b(?:stream|streams|twitch)\b", plain or "")
        and re.search(r"\b(?:films?|movies?|revenue|merch|box office)\b", plain or "")
    ):
        return False
    # A hearing, a vote, or a bill signing that says "live now" is coverage.
    # Once a civic or government topic is present, the live phrase does not
    # count. A Twitch or Kick URL with an announcement phrase still is.
    if _news(plain) and not (url and phrase):
        return False
    if phrase:
        return True
    if (
        re.search(r"\bjoin me\b", plain or "")
        and re.search(r"\b(?:stream|streams|karaoke|twitch|live)\b", plain or "")
        and not _news(plain)
        and _word_count(plain) <= 24
    ):
        return True
    if (
        re.search(r"\b(?:karaoke|bonus|surprise) stream\b", plain or "")
        and not _news(plain)
        and _word_count(plain) <= 20
    ):
        return True
    if not url or _news(plain):
        return False
    if _word_count(plain) <= 30:
        return True
    return bool(_STREAM_WITH_URL_RE.search(plain or ""))


def _person_directed(plain: str) -> bool:
    return bool(
        re.search(r"\b(?:you|your|youre|youve)\b", plain or "")
        or re.search(r"\blove (?:her|him|them|his|hers)\b", plain or "")
    )


def _courtesy_reply(raw: str, plain: str) -> bool:
    """Short “my pleasure” / “happy to help” replies, not policy."""
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain):
        return False
    if not re.search(
        r"\b(?:my pleasure|youre welcome|you are welcome|happy to help|glad to help|"
        r"no problem|dont mention it|do not mention it)\b",
        plain or "",
    ):
        return False
    subs = _gesture_remainder_substance(plain)
    return _word_count(plain) <= 40 and len(subs) <= 3


def _creator_compliment(raw: str, plain: str) -> bool:
    """Praise for someone's art, WIP pics, shirt, etc."""
    if re.search(r"^great\s*[-–—]", plain or ""):
        return False
    if _discussion_topic(raw, plain) or _news(plain) or _sports_play(plain):
        return False
    if not re.search(r"\byour\b", plain or ""):
        return False
    if not re.search(
        r"\b(?:work|wip|progress|pics?|art|shirt|photo|photos|drawing|sketch|rendering|"
        r"piece|creation|design|comic|animation|video|stream|channel)\b",
        plain or "",
    ):
        return False
    if not re.search(
        r"\b(?:incredible|awesome|amazing|beautiful|stunning|gorgeous|lovely|fantastic|"
        r"wonderful|great|best|favorite|favourite|talented|skilled)\b",
        plain or "",
    ):
        return False
    return _word_count(plain) <= 55 and _gesture_is_the_post(raw, plain, creator=True)


def _thanks(raw: str, plain: str) -> bool:
    if _courtesy_reply(raw, plain):
        return True
    thanked = bool(
        re.search(r"\b(?:thank you|thanks|thankyou|thx)\b", plain or "")
        or plain in {"ty", "thx"}
        or re.search(r"\byoure welcome\b", plain or "")
    )
    grateful = bool(
        re.search(r"\b(?:appreciate|grateful|thankful)\b", plain or "")
        and _word_count(plain) <= 28
        and len(_substance(plain)) <= 3
    )
    if not (thanked or grateful):
        return False
    if HASHTAG_RE.search(raw or ""):
        tag_plain = _plain(" ".join(HASHTAG_RE.findall(raw or "")))
        if _news(tag_plain) or _discussion_topic(raw, tag_plain) or len(_substance(tag_plain)) >= 1:
            return False
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain) or _sports_play(plain):
        return False
    return _gesture_is_the_post(raw, plain)


def _enthusiasm_reaction(raw: str, plain: str) -> bool:
    """Short “so good” reactions, not a sports or policy argument."""
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain):
        return False
    if re.search(r"\bso good at\b", plain or ""):
        return False
    if re.search(r"\b(?:comment section|press conference|hearing|vote|voted|bill)\b", plain or ""):
        return False
    if not re.search(
        r"\b(?:(?:this|that|it) is )?so good\b|^(?:this|that) is so good\b|\blooks so good\b",
        plain or "",
    ):
        return False
    if not _word_count(plain) <= 14:
        return False
    return _gesture_is_the_post(raw, plain)


def _art_praise(raw: str, plain: str) -> bool:
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain):
        return False
    if re.search(r"\bhow can i\b", plain or ""):
        return False
    if not re.search(
        r"\b(?:look how cute|how cute (?:this|it)|wonderful design|lovely work|"
        r"nice work|amazing work|beautiful (?:design|rendering|art))\b",
        plain or "",
    ):
        return False
    subs = _gesture_remainder_substance(plain)
    return _word_count(plain) <= 48 and len(subs) <= 4


def _compliment(raw: str, plain: str) -> bool:
    if _enthusiasm_reaction(raw, plain) or _art_praise(raw, plain) or _creator_compliment(raw, plain):
        return True
    if not re.search(
        r"\b(?:cute|beautiful|gorgeous|stunning|lovely|sexy|adorable|delightful|"
        r"so pretty|love this|love it|love her|love him|love you|love that you|so hot|"
        r"extremely cute|incredibly cute|incredible|awesome|photogenic)\b",
        plain or "",
    ):
        return False
    if _discussion_topic(raw, plain) or _news(plain) or _work_topic(plain) or _sports_play(raw):
        return False
    subs = _gesture_remainder_substance(plain)
    if _person_directed(plain):
        return _word_count(plain) <= 48 and len(subs) <= 5
    return _word_count(plain) <= 24 and len(subs) <= 1


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
        # A result ("last 10 games") is a sports jab, not a greeting card.
        if _word_count(plain) <= 30 and not _SPORTS_RESULT_RE.search(plain or ""):
            return "wish"
    return None


def _reaction_only(raw: str) -> bool:
    """Emoji or punctuation left after links, tags, and handles are removed.

    A bare URL is left for the link-only check. A gift emoji on a news link
    is a reaction, not the article. A hashtag is a topic marker: ``#NoKings``
    with an emoji is not a reaction-only post.
    """
    if HASHTAG_RE.search(raw or ""):
        return False
    text = URL_RE.sub(" ", raw or "")
    text = HASHTAG_RE.sub(" ", text)
    text = HANDLE_RE.sub(" ", text)
    if re.search(r"[A-Za-z0-9]", text):
        return False
    return bool(re.search(r"\S", text))


def _short_reply(plain: str) -> bool:
    """One or two words with no public topic. "Senate votes" stays."""
    words = (plain or "").split()
    if not 1 <= len(words) <= 2:
        return False
    if _news(plain) or _work_topic(plain):
        return False
    subs = _substance(plain)
    if not subs:
        return True
    return len(subs) == 1 and len(subs[0]) <= 4


def _personal_status(plain: str) -> bool:
    """A ride arriving, with no public topic. An Uber strike stays."""
    if _news(plain) or _work_topic(plain):
        return False
    return bool(
        re.search(r"\b(?:my|our) (?:uber|lyft|cab|taxi|ride) is here\b", plain or "")
    )


def _birthday(raw: str, plain: str) -> bool:
    """A first-person birthday or a birthday party, not a news mention.

    A question that argues about a birthday ("why ... child's birthday?") stays.
    """
    if not re.search(r"\bbirthdays?\b", plain or ""):
        return False
    if _news(plain) or _work_topic(plain):
        return False
    if "?" in (raw or "") and re.search(r"\bwhy\b", plain or ""):
        return False
    return True


def _personal_health(plain: str) -> bool:
    """The author's own illness, surgery, or recovery journal.

    Directed wishes are handled by ``_get_well``. A public-health or policy
    post stays, including one that mentions a hospital, a vaccine, or a bill.
    "Sick of" a politician is a complaint, not a fever.
    """
    if not plain or _PUBLIC_HEALTH_RE.search(plain):
        return False
    text = re.sub(r"\bsick and tired of\b", " ", plain)
    text = re.sub(r"\bsick of\b", " ", text)
    text = re.sub(r"\bmakes me sick\b", " ", text)
    text = re.sub(r"\b(?:feel|feeling|felt) (?:so |really |very )?sick about\b", " ", text)
    text = re.sub(r"\bsick about\b", " ", text)
    if _PERSONAL_HEALTH_AUTHOR_RE.search(text):
        return True
    if _PERSONAL_HEALTH_CONDITION_RE.search(text) and _PERSONAL_HEALTH_AUTHOR_TOKEN_RE.search(text):
        return True
    return False


def _get_well(plain: str) -> bool:
    """A directed get-well, condolence, or recovery wish.

    The author's own illness journal is ``_personal_health``, not a wish.
    A news report of an illness stays in both checks.
    """
    if _news(plain) or _work_topic(plain):
        return False
    if not _GET_WELL_RE.search(plain or ""):
        return False
    if _FIRST_PERSON_RECOVERY_RE.search(plain or "") and not re.search(
        r"\b(?:hope you|wishing you|prayers for you|praying for you|get well|"
        r"speedy recovery|quick recovery|sending healing|healing purrs)\b",
        plain or "",
    ):
        return False
    return True


_EVERY_MORNING_PLATITUDE_RE = re.compile(
    r"\bevery\s+morning\s+is\s+a\s+good\s+morning\b",
    re.IGNORECASE,
)
_LEADING_HAIL_RE = re.compile(
    r"^(?:hiya|hey|hello|hi)\s+[a-z]{2,}\s+"
    r"(?=good\s+(?:morning|afternoon|evening|night)|goodmorning|goodnight|morning\b)",
    re.IGNORECASE,
)
_DAYPART_OPEN_RE = re.compile(
    r"^good\s+(?:morning|afternoon|evening|night)\b|"
    r"^goodmorning\b|"
    r"^goodnight\b|"
    r"^(?:gm|gn)\b",
    re.IGNORECASE,
)
_MORNING_ONLY_OPEN_RE = re.compile(r"^morning\b", re.IGNORECASE)
_MORNING_NAME_OPEN_RE = re.compile(
    r"^morning\s+([a-z]{2,})(.*)$",
    re.IGNORECASE,
)
_GOOD_MORNING_TOPIC_TAIL = frozenset(
    {
        "america",
        "world",
        "news",
        "run",
        "routine",
    }
)
_MORNING_FALSE_SECOND = frozenset(
    {
        "after",
        "commute",
        "joe",
        "show",
        "news",
        "run",
        "routine",
        "america",
        "game",
        "the",
        "pill",
    }
)
_GREETING_VOCATIVE = frozenset(
    {
        "everyone",
        "everybody",
        "all",
        "folks",
        "friends",
        "friend",
        "world",
        "yall",
        "beautiful",
        "gorgeous",
        "lovely",
        "dear",
        "buddy",
    }
)
_GREETING_PLEASANTRY_RE = re.compile(
    r"\b(?:"
    r"to you(?:\s+too)?|to ya|"
    r"make it a good day|have a (?:good|great|magnificent|wonderful|nice|relaxing|lazy) day|"
    r"how are you|hope you|i hope you|wishing you|"
    r"have a great day|happy (?:sunday|saturday|monday|tuesday|wednesday|thursday|friday)|"
    r"thats the spirit|that s the spirit|"
    r"xx|xxx|chaggiful"
    r")\b",
    re.IGNORECASE,
)
_GREETING_SIGNOFF_TAIL_RE = re.compile(
    r"\bhave a good (?:evening|night|afternoon|day)\s*\.?\s*$",
    re.IGNORECASE,
)
_GREETING_TOPIC_VERB = frozenset(
    {
        "said",
        "won",
        "held",
        "resigned",
        "stalled",
        "expands",
        "ban",
        "loved",
        "opens",
        "interview",
        "matter",
        "access",
        "brutal",
        "runs",
        "run",
        "talks",
    }
)
_GREETING_WISH_TAIL_RE = re.compile(
    r"\b(?:"
    r"happy\s+(?:sun)?day|happy\s+(?:sunday|saturday|monday|tuesday|wednesday|thursday|friday)|"
    r"happy\s+chilly\s+sunday|"
    r"hope you|i hope you|i hope this day|i hope everyone|i hope your day|hope this day|hope and pray|"
    r"hope you have|hope you enjoy|hope you thoroughly|hope you are all doing great|"
    r"have a (?:good|great|wonderful|magnificent|nice|relaxing|lazy|easy) day|"
    r"make it a good day|thats the spirit|that s the spirit|"
    r"peaceful easy feeling|peaceful vibes|easy feeling|relaxing day|nice relaxing day|"
    r"going to be a relaxing day|nice day|great day|wonderful day|blessed day|"
    r"my dear friend|my friend(?!\s+the\b)|nice relaxing|chilly sunday|lazy sunday|sinful sunday|"
    r"awesome sunday|safe travels|have a magnificent day|enjoy your lazy sunday|"
    r"enjoy your coffee|enjoy the matches|pray everyone|"
    r"sleep well|sweet dreams|stay warm|coffee is on"
    r")\b",
    re.IGNORECASE,
)
_GREETING_TAIL_PLEASANTRY_TOKENS = frozenset(
    {
        "sleep",
        "sleeps",
        "slept",
        "sleeping",
        "dream",
        "dreams",
        "well",
        "warm",
        "warmer",
        "stay",
        "safe",
        "cozy",
        "coffee",
        "tea",
        "vibes",
        "easy",
        "kind",
        "rest",
        "blessed",
        "sweet",
        "today",
        "tonight",
        "dear",
        "folks",
        "friends",
        "friend",
        "everyone",
        "all",
    }
)
_DIRECTED_HOPE_RE = re.compile(
    r"\bi hope (?:you|this day|your day|everyone|your)\b",
    re.IGNORECASE,
)
_GREETING_HARD_TOPIC_RE = re.compile(
    r"\b(?:"
    r"won|held|resigned|stalled|said|interview|ban|expands|access|brutal|"
    r"lakers|yankees|fed|museum|marathon|rally|pill|coach|exhibit|talks|"
    r"protect\s+trans|black\s+lives\s+matter|free\s+palestine|"
    r"see you at the rally"
    r")\b",
    re.IGNORECASE,
)
_GREETING_WIPE_RE = re.compile(
    r"\b(?:"
    r"good\s+morning|goodmorning|good\s+(?:afternoon|evening|night)|goodnight|"
    r"gm|gn|morning|afternoon|evening|night|"
    r"to you(?:\s+too)?|to ya|from|dear|"
    r"everyone|everybody|all|folks|friends|friend|world|yall|"
    r"make it a good day|have a (?:good|great|magnificent|wonderful|nice|relaxing|lazy) day|"
    r"how are you|hope you|i hope you|wishing you|have a great day|"
    r"happy (?:sunday|saturday|monday|tuesday|wednesday|thursday|friday)|"
    r"thats the spirit|that s the spirit|"
    r"beautiful|wonderful|lovely|gorgeous|great|nice|happy|the|a|my|"
    r"xx|xxx|chaggiful|kinmo|cat|kinmo the cat"
    r")\b",
    re.IGNORECASE,
)


def _greeting_remainder_tokens(remainder: str) -> list[str]:
    text = _GREETING_PLEASANTRY_RE.sub(" ", remainder or "")
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if t]


def _greeting_remainder_substance(remainder: str) -> list[str]:
    return _substance(" ".join(_greeting_remainder_tokens(remainder)))


def _greeting_tail_substance(remainder: str) -> list[str]:
    """Content words in a greeting tail minus ordinary wish vocabulary."""
    return [
        token
        for token in _greeting_remainder_substance(remainder)
        if token not in _GREETING_TAIL_PLEASANTRY_TOKENS
    ]


def _strip_greeting_addressee(remainder: str) -> str:
    text = (remainder or "").strip()
    text = re.sub(r"^and\s+", "", text)
    match = re.match(r"^([a-z]{2,})\s*(?:,|!\.)\s*(.*)$", text)
    if match and match.group(2).strip():
        name, tail = match.group(1), match.group(2).strip()
        if name not in _GREETING_VOCATIVE and name not in _MORNING_FALSE_SECOND:
            if _GREETING_WISH_TAIL_RE.search(tail) or _GREETING_PLEASANTRY_RE.search(tail):
                return tail
    match = re.match(r"^([a-z]{2,})\s+(.+)$", text)
    if match:
        name, tail = match.group(1), match.group(2).strip()
        if name not in _GREETING_VOCATIVE and name not in _MORNING_FALSE_SECOND:
            if re.match(r"^(?:make it|hope|have a|happy|my)\b", tail):
                return tail
    return text


def _greeting_remainder_is_topic(remainder: str) -> bool:
    """True when the tail is more than a name, vocative, or pleasantry."""
    if not (remainder or "").strip():
        return False
    text = _strip_greeting_addressee(remainder)
    if _news(text) or _work_topic(text):
        return True
    if re.search(r"\bi hope\b", text) and not _DIRECTED_HOPE_RE.search(text):
        return True
    if _DIRECTED_HOPE_RE.search(text) and not _greeting_tail_substance(text):
        return False
    if re.search(r",\s*the\s+\w+", text):
        return True
    if re.search(r"\bthe\s+\w+\s+(?:won|held|resigned|opens|stalled)\b", text):
        return True
    if _GREETING_HARD_TOPIC_RE.search(text):
        return True
    if re.search(r":\s*\S", text):
        return True
    tokens = _greeting_remainder_tokens(text)
    if any(token in _GREETING_TOPIC_VERB for token in tokens):
        return True
    if _GREETING_WISH_TAIL_RE.search(text) and not (_news(text) or _work_topic(text)):
        return False
    subs = _greeting_tail_substance(text)
    if len(subs) >= 2:
        return True
    if len(subs) == 1:
        if subs[0] == "kinmo" or re.match(r"^\s*from\s+", text or ""):
            return False
        if _GREETING_WISH_TAIL_RE.search(text):
            return False
        return True
    return False


def _morning_name_greeting_tail(rest: str) -> bool:
    rest = (rest or "").strip()
    if not rest:
        return True
    if rest.startswith(","):
        rest = rest[1:].strip()
    if not rest:
        return True
    return not _greeting_remainder_is_topic(rest)


def _greeting_wish_body(plain: str) -> bool:
    text = plain or ""
    if _news(text) or _work_topic(text):
        return False
    if _EVERY_MORNING_PLATITUDE_RE.search(text) and _word_count(text) <= 40:
        tail = _EVERY_MORNING_PLATITUDE_RE.sub(" ", text).strip()
        return not _greeting_remainder_is_topic(tail)

    if _GREETING_SIGNOFF_TAIL_RE.search(text):
        before = text[: _GREETING_SIGNOFF_TAIL_RE.search(text).start()].strip()
        if before and (_word_count(before) > 6 or len(_substance(before)) >= 2):
            return False

    text = _LEADING_HAIL_RE.sub("", text).strip()
    if not text:
        return False

    if re.search(r"\bgood\s+night\s+at\s+the\b", text):
        return False
    if re.match(r"^a\s+good\s+morning\b", text):
        return False

    if not _DAYPART_OPEN_RE.match(text) and not _MORNING_ONLY_OPEN_RE.match(text):
        lead = re.search(r"\bgood\s+(?:morning|afternoon|evening|night)\b", text)
        if lead and lead.start() <= 10 and _word_count(text[: lead.start()]) <= 2:
            text = text[lead.start() :].strip()

    remainder = ""
    if _DAYPART_OPEN_RE.match(text):
        m = re.match(
            r"^(?:good\s+(?:morning|afternoon|evening|night)|goodmorning|goodnight|gm|gn)\s*"
            r"(?:[!.,:]\s*)?(.*)$",
            text,
            flags=re.I,
        )
        if not m:
            return False
        remainder = (m.group(1) or "").strip()
        head = text[: m.start(1)].lower()
        if "good morning" in head or "goodmorning" in head.replace(" ", ""):
            first = remainder.split(None, 1)[0] if remainder else ""
            if first in _GOOD_MORNING_TOPIC_TAIL:
                return False
    elif _MORNING_ONLY_OPEN_RE.match(text):
        m = re.match(r"^morning\s*(?:[!.,]\s*)?(.*)$", text, flags=re.I)
        remainder = (m.group(1) or "").strip() if m else ""
        if not remainder:
            return _word_count(text) <= 4
        mname = _MORNING_NAME_OPEN_RE.match(text)
        if not mname:
            return False
        second = mname.group(1).lower()
        if second in _MORNING_FALSE_SECOND:
            return False
        return _morning_name_greeting_tail(mname.group(2) or "")
    else:
        return False

    if _greeting_remainder_is_topic(remainder):
        return False

    if re.match(r"^to you(?:\s+too)?\s*$", remainder.strip()):
        return True

    if _GREETING_WISH_TAIL_RE.search(_strip_greeting_addressee(remainder)):
        return True

    rem_tokens = _greeting_remainder_tokens(remainder)
    if not rem_tokens:
        return True

    if rem_tokens[0] == "from":
        return not _greeting_remainder_is_topic(remainder)

    # Optional vocative then pleasantries only.
    idx = 0
    if rem_tokens[0] in _GREETING_VOCATIVE or (
        len(rem_tokens[0]) >= 2
        and rem_tokens[0] not in _MORNING_FALSE_SECOND
        and rem_tokens[0] != "from"
    ):
        if rem_tokens[0] in _MORNING_FALSE_SECOND:
            return False
        idx = 1
        if idx < len(rem_tokens) and rem_tokens[idx] in _GREETING_VOCATIVE:
            idx += 1
    tail = " ".join(rem_tokens[idx:])
    if not tail:
        return True
    if tail.startswith("from"):
        return not _greeting_remainder_is_topic(tail)
    if _GREETING_PLEASANTRY_RE.search(tail):
        return not _greeting_remainder_is_topic(tail)
    # A single addressee name (Susan, Richard, Jim) then pleasantry clause.
    if idx >= 1 and _GREETING_PLEASANTRY_RE.search(remainder):
        return not _greeting_remainder_is_topic(remainder)
    return False


def _greeting(plain: str) -> bool:
    exact = {
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
        "morning",
    }
    if plain in exact:
        return True
    if _news(plain) or _work_topic(plain):
        return False
    if _word_count(plain) > 60:
        return False
    return _greeting_wish_body(plain)


def pleasantry_reason(post: dict) -> str | None:
    """Why this post is chit-chat, or None to keep it.

    The decision is the post text. A public-topic word (a law, a war, a team
    result, a song, a place) keeps a post that merely uses a social word.
    """
    raw = post_body(post)
    if not raw.strip():
        return None
    if _reaction_only(raw):
        return "reaction"
    plain = _plain(raw)
    if not plain:
        return None
    if _short_reply(plain):
        return "reply"
    if _personal_status(plain):
        return "status"
    if _agreement(plain):
        return "agreement"
    if _stream_promo(raw, plain):
        return "stream_announce"
    if _birthday(raw, plain):
        return "wish"
    if _get_well(plain):
        return "wish"
    if _personal_health(plain):
        return "health_update"
    kind = _wish(plain)
    if kind:
        return kind
    if _thanks(raw, plain):
        return "thanks"
    if _creator_compliment(raw, plain):
        return "compliment"
    if _compliment(raw, plain):
        return "compliment"
    if _greeting(plain):
        return "greeting"
    return None


# Public alias used across the pipeline.
chitchat_reason = pleasantry_reason


def drop_link_and_language_at_ingest() -> bool:
    """Whether ingest refuses link-only and non-English posts.

    The environment variable wins when it is set. ``0`` reproduces main:
    those posts count toward the stored corpus. It does not let them into
    clustering. ``edition_posts_for_clustering`` still removes them, which
    is what main's ``partition_posts`` already did. The default is on, so
    ingest refuses them and they do not count toward the 100K.
    """
    raw = os.environ.get("DROP_LINK_AND_LANGUAGE_AT_INGEST")
    if raw is None or not str(raw).strip():
        return DROP_LINK_AND_LANGUAGE_AT_INGEST
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def ingest_block_reason(post: dict) -> str | None:
    """Spam, chit-chat, personal health updates, and optionally link-only or non-English.

    None means edition-quality. A personal health update is a chit-chat reason
    (``health_update``), so it is removed before the daily cap and does not
    count toward the 100K. Link-only and language are the d721778 ingest step
    and follow ``drop_link_and_language_at_ingest``.
    """
    spam = guard_reason(post)
    if spam:
        return f"spam:{spam}"
    # Always refuse new bot wires. Stored-row deletion is opt-in via
    # ``PERSPECTIVERSE_PURGE_STORED_REASONS`` (include ``weather_bot``).
    weather = weather_bot_reason(post)
    if weather:
        return weather
    chit = pleasantry_reason(post)
    if chit:
        return f"chitchat:{chit}"
    if not drop_link_and_language_at_ingest():
        return None
    reason = edition_filter_reason(post)
    if reason:
        return reason
    return None


def edition_posts_for_clustering(
    posts: list[dict],
    *,
    carried_uris: set[str] | None = None,
    carried_skips: dict[str, int] | None = None,
) -> tuple[list[dict], int, int, int]:
    """Posts that enter clustering, plus language, link, and chit-chat skips.

    Link-only and non-English posts are always removed. That is
    ``partition_posts``, which main already ran before #209. Free ingest on
    main counted those posts in the stored corpus and then skipped them
    here. ``DROP_LINK_AND_LANGUAGE_AT_INGEST=0`` restores that split: ingest
    keeps them, and this function still removes them. The switch does not
    let them into a planet.

    Chit-chat is always removed here too. That part is #208.

    When ``carried_uris`` and ``carried_skips`` are set, counts how many
    skipped posts came from an earlier run's stored corpus (#217).
    """
    carried = carried_uris or set()
    kept: list[dict] = []
    language = 0
    links = 0
    for post in posts:
        uri = str(post.get("uri") or "")
        if weather_bot_reason(post):
            if carried_skips is not None and uri in carried:
                carried_skips["weather_bot"] = carried_skips.get("weather_bot", 0) + 1
            continue
        reason = edition_filter_reason(post)
        if reason == "link_only":
            links += 1
            if carried_skips is not None and uri in carried:
                carried_skips["link_only"] = carried_skips.get("link_only", 0) + 1
            continue
        if reason == "language":
            language += 1
            if carried_skips is not None and uri in carried:
                carried_skips["language"] = carried_skips.get("language", 0) + 1
            continue
        kept.append(post)
    kept, chitchat = filter_chitchat_posts(
        kept,
        carried_uris=carried if carried_skips is not None else None,
        carried_skips=carried_skips,
    )
    return kept, language, links, chitchat


def clustering_topup_shortfall(
    target: int,
    clustered: int,
    skipped_language: int,
    skipped_links: int,
) -> int:
    """How many more posts to fetch so the edition can fill ``target``.

    With the ingest switch on, link-only and non-English posts do not count
    toward the 100K, so a clustering gap is a shortfall. With the switch off,
    those posts already counted in the stored corpus, which is main's
    behavior, and removing them before clustering is not a reason to fetch
    more. Chit-chat skips still are.
    """
    excluded = 0
    if not drop_link_and_language_at_ingest():
        excluded = int(skipped_language) + int(skipped_links)
    return max(0, int(target) - int(clustered) - excluded)


def filter_chitchat_posts(
    posts: list[dict],
    *,
    carried_uris: set[str] | None = None,
    carried_skips: dict[str, int] | None = None,
) -> tuple[list[dict], int]:
    """Drop chit-chat posts that reached clustering. Returns (kept, dropped)."""
    carried = carried_uris or set()
    kept: list[dict] = []
    dropped = 0
    for post in posts:
        if pleasantry_reason(post) is None:
            kept.append(post)
            continue
        dropped += 1
        uri = str(post.get("uri") or "")
        if carried_skips is not None and uri in carried:
            carried_skips["chitchat"] = carried_skips.get("chitchat", 0) + 1
        _LOG.record_block(post, "chitchat:late")
    return kept, dropped


def pleasantry_share(members: list[dict]) -> float:
    if not members:
        return 0.0
    hits = sum(1 for member in members if pleasantry_reason(member))
    return hits / len(members)


def _post_text_surfaces(post: dict) -> str:
    """Text and clean_text combined. Link cards often leave ``text`` blank."""
    return " ".join(
        part.strip()
        for part in (str(post.get("text") or ""), str(post.get("clean_text") or ""))
        if part and part.strip()
    )


def is_bare_stream_domain_link(post: dict) -> bool:
    """A Twitch, Kick, or YouTube /live URL with almost no other words."""
    raw = _post_text_surfaces(post)
    if not _STREAM_DOMAIN_URL_RE.search(raw):
        return False
    text = HASHTAG_RE.sub(" ", raw)
    text = HANDLE_RE.sub(" ", text)
    text = _STREAM_DOMAIN_URL_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    words = re.findall(r"[A-Za-z]{3,}", text)
    return len(words) < 4


def is_bare_link_post(post: dict) -> bool:
    """A URL, including youtu.be, with fewer than four words left.

    Planet share counts these. Ingest uses the same ``is_link_only`` rule.
    """
    return is_link_only(post_body(post))


def planet_content_share(members: list[dict]) -> float:
    """Pleasantry posts plus bare-link posts, over the members given."""
    if not members:
        return 0.0
    hits = sum(
        1
        for member in members
        if pleasantry_reason(member) or is_bare_link_post(member)
    )
    return hits / len(members)


_GESTURE_KINDS = frozenset(
    {
        "thanks",
        "compliment",
        "wish",
        "greeting",
        "stream_announce",
        "agreement",
        "reply",
        "reaction",
        "luck",
        "weekend",
    }
)


def _streaming_platform_salient_reason(members: list[dict]) -> str | None:
    """Drop when salient terms are only streaming-platform tokens (#227)."""
    from pipeline.cluster_math import salient_terms, tokenize

    texts = [
        (_post_text_surfaces(member) or post_body(member)).strip()
        for member in members
        if (_post_text_surfaces(member) or post_body(member)).strip()
    ]
    if not texts:
        return None
    counts: dict[str, int] = {}
    for text in texts:
        for token in set(tokenize(text)):
            counts[token] = counts.get(token, 0) + 1
    if not counts:
        return None
    threshold = max(2, int(len(texts) * 0.3))
    top_terms = salient_terms(texts, limit=1)
    if not top_terms:
        return None
    top = top_terms[0]
    if top not in _STREAMING_PLATFORM_SALIENT_TERMS:
        return None
    for term, weight in counts.items():
        if weight >= threshold and term not in _STREAMING_PLATFORM_SALIENT_TERMS:
            return None
    return _STREAM_PLATFORM_DROP_REASON


def _gesture_share(members: list[dict]) -> float:
    if not members:
        return 0.0
    hits = sum(
        1
        for member in members
        if (pleasantry_reason(member) or "") in _GESTURE_KINDS
    )
    return hits / len(members)


def planet_chitchat_reason(
    members: list[dict],
    terms: list[str],
    *,
    name: str | None = None,
    model_chitchat: bool | None = None,
) -> str | None:
    """Drop a planet from its posts, never from its title.

    ``name`` is ignored. Callers still pass the label so logs can name the
    planet; a rename cannot keep or drop it. ``terms`` is unused except for
    API compatibility with the labeler. ``model_chitchat``
    is the yes/no field on the existing planet-naming response. Yes alone
    does not drop a planet. The posts have to be at least 55% chit-chat, or
    the model has to say yes and at least 30% of the posts agree, or at least
    35% are thanks / compliments / wishes with no topical anchor post. Bare
    video links count toward that share. The planet title does not.
    """
    del name, terms
    if not members:
        return None
    platform = _streaming_platform_salient_reason(members)
    if platform:
        return platform
    share = planet_content_share(members)
    if share >= PLEASANTRY_SHARE_DROP:
        return f"{share:.0%} of the posts are chit-chat"
    if model_chitchat is True and share >= MODEL_CHITCHAT_SHARE_FLOOR:
        return f"naming prompt marked the posts as chit-chat and {share:.0%} of the posts agree"
    thanks_count = sum(1 for member in members if pleasantry_reason(member) == "thanks")
    thanks_share = thanks_count / len(members)
    if (
        len(members) >= THANK_PLANET_MIN_MEMBERS
        and thanks_share >= THANK_PLANET_SHARE_DROP
        and thanks_count >= THANK_PLANET_MIN_THANKS
    ):
        return f"{thanks_share:.0%} of the posts are thanks ({thanks_count} posts)"
    thanks_mentions = sum(
        1
        for member in members
        if re.search(r"\b(?:thank you|thanks|thank)\b", _plain(post_body(member)) or "")
    )
    mention_share = thanks_mentions / len(members)
    if (
        len(members) >= THANK_PLANET_MIN_MEMBERS
        and thanks_mentions >= THANK_PLANET_MIN_THANKS
        and mention_share >= THANK_PLANET_MENTION_SHARE_DROP
    ):
        return f"{mention_share:.0%} of the posts mention thanks ({thanks_mentions} posts)"
    gesture = _gesture_share(members)
    if len(members) >= GESTURE_CLUSTER_MIN_MEMBERS and gesture >= GESTURE_CLUSTER_SHARE_DROP:
        return f"{gesture:.0%} of the posts are social gestures in a large cluster"
    streamish = 0
    for member in members:
        surfaces = _post_text_surfaces(member)
        plain = _plain(surfaces or post_body(member))
        if pleasantry_reason(member) == "stream_announce":
            streamish += 1
        elif is_bare_stream_domain_link(member):
            streamish += 1
        elif _STREAM_URL_RE.search(surfaces or ""):
            streamish += 1
        elif _STREAM_URL_RE.search(plain or ""):
            streamish += 1
        elif re.search(r"\b(?:twitch|kick)\b", plain or "") and _word_count(plain) <= 40:
            streamish += 1
    stream_share = streamish / len(members)
    if len(members) >= STREAM_CLUSTER_MIN_MEMBERS and stream_share >= STREAM_CLUSTER_SHARE_DROP:
        return f"{stream_share:.0%} of the posts are stream promos or Twitch plugs"
    return None
