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
from pipeline.language import edition_filter_reason, is_link_only, partition_posts, post_raw_text
from pipeline.spam_guard import guard_reason, post_body

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

# A YouTube live URL is a news or podcast link unless the words are a promo.
_STREAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitch\.tv/|kick\.com/)",
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
    if not url or _news(plain):
        return False
    if _word_count(plain) <= 30:
        return True
    return bool(_STREAM_WITH_URL_RE.search(plain or ""))


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
    if _thanks(plain):
        return "thanks"
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
    chit = pleasantry_reason(post)
    if chit:
        return f"chitchat:{chit}"
    if not drop_link_and_language_at_ingest():
        return None
    reason = edition_filter_reason(post_raw_text(post))
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
        text = str(post.get("clean_text") or post.get("text") or "")
        if is_link_only(text):
            links += 1
            if carried_skips is not None and uri in carried:
                carried_skips["link_only"] = carried_skips.get("link_only", 0) + 1
            continue
        if not looks_english(text):
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
    the model has to say yes and at least 30% of the posts agree. Bare video
    links count toward that share. The planet title does not.
    """
    del terms, name
    if not members:
        return None
    share = planet_content_share(members)
    if share >= PLEASANTRY_SHARE_DROP:
        return f"{share:.0%} of the posts are chit-chat"
    if model_chitchat is True and share >= MODEL_CHITCHAT_SHARE_FLOOR:
        return f"naming prompt marked the posts as chit-chat and {share:.0%} of the posts agree"
    return None
