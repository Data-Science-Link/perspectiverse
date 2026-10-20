"""Label planets and faces, and synthesize a short steelman per face.

Default order: Ollama if it answers, else an OpenAI-compatible API when
OPENAI_API_KEY is set, else a heuristic built from top terms and posts.
One retry, then the heuristic. This module labels clusters, not each post.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable

from pipeline.cluster_math import salient_terms
from pipeline.http_json import read_json
from pipeline.settings import MAX_PROMPT_POSTS

FALLBACK_TITLE = "Untitled cluster"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_DEEPINFRA_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def build_prompt(posts: list[dict]) -> str:
    return build_perspective_prompt(posts)


def build_perspective_prompt(posts: list[dict], *, post_limit: int | None = None) -> str:
    body = _post_lines(posts, limit=post_limit)
    return (
        "These posts are meant to be one perspective. Name the claim they share.\n"
        "Return JSON only, with no markdown: "
        '{"title": "2-3 words", "summary": "one sentence", '
        '"arguments": ["steelman 1", "steelman 2", "steelman 3"]}\n'
        "The title is 2 to 3 words naming the specific event, policy, or claim. "
        "Do not name a camp or a bare slogan. Titles like \"Anti Republican\", \"Pro Ukraine\", "
        "\"AI Criticism\", \"Art World Criticized\", or \"Stop AI\" are not allowed. "
        "Do not use an insult or a criminal accusation as the title. "
        "The summary is one complete sentence of that same claim, at most 22 words, written in your own words. "
        "Do not paste a post, and do not end the sentence with an ellipsis. "
        "Do not add a second camp, a motive, or a \"but\" or \", and some\" that joins a different claim. "
        "Do not call the posts various opinions. "
        "If the posts name different events, different people, or different policies, they do not share a claim. "
        "Each argument paraphrases a different post below, in that view's own voice, "
        "and states a claim rather than a name-call. "
        "Do not add a fact, number, or proper noun that is not in those posts. "
        "If the posts do not share a claim, use title \"Mixed remarks\", say so in one clause, "
        "and return an empty arguments list.\n"
        f"Posts:\n{body}\n"
    )


def build_repair_prompt(posts: list[dict], draft: dict, *, post_limit: int | None = None) -> str:
    body = _post_lines(posts, limit=post_limit)
    title = str(draft.get("title") or "")
    summary = str(draft.get("summary") or "")
    return (
        "Rewrite this perspective label. The draft is not publishable.\n"
        f"Draft title: {title}\n"
        f"Draft summary: {summary}\n"
        "Return JSON only, with no markdown: "
        '{"title": "2-3 words", "summary": "one sentence", '
        '"arguments": ["steelman 1", "steelman 2"]}\n'
        "The title is a grammatical phrase a person could say. "
        "Good titles: \"Halt Executions\", \"Artists Reject AI\", \"Diesel Export Ban\", \"Cornell Rape Case\". "
        "Bad titles: \"Evangelists Unequipped\", \"Detrimental Undermines\", \"AI Criticism\", \"Anti Trump\", \"Stop AI\", \"Art World Criticized\". "
        "The summary is one complete sentence of the single claim most of these posts make, at most 22 words. "
        "Do not join a second claim with \"but\" or \", and some\". Do not say various. Do not copy a post. "
        "Do not end the summary with an ellipsis. "
        "Each argument paraphrases a different post and states a claim, not a name-call. "
        "Do not add a fact, number, or proper noun that is not in the posts. "
        "If the posts do not share one claim, use title \"Mixed remarks\", "
        "summary \"These posts do not share a claim.\", and an empty arguments list.\n"
        f"Posts:\n{body}\n"
    )


def build_same_subject_prompt(faces: list[dict]) -> str:
    lines = []
    for face in faces:
        lines.append(f"- {face.get('title')}: {face.get('summary')}")
    shown = "\n".join(lines)
    return (
        "Do these perspectives belong on one page because they are about the same event, case, or policy?\n"
        "Return JSON only: {\"same\": true} or {\"same\": false}.\n"
        "Same: \"Halt the death penalty\" and \"Lethal injection causes suffering\" about one execution. "
        "Same: \"Artists reject generative AI\" and \"AI evangelists are unfit to govern it\". "
        "Same: battlefield updates and calls to defend that country, about one war. "
        "Same: a criminal case and argument about how that case was decided.\n"
        "Same: a diesel export ban and a release of diesel stockpiles.\n"
        "Not the same: a Pentagon religion office and a church's alliance with artists. "
        "Not the same: one candidate's campaign and a different politician's bribery case. "
        "Not the same: posts about one politician and posts about a different politician. "
        "Not the same: a government office and an unrelated program that only share a topic word.\n"
        f"Perspectives:\n{shown}\n"
    )


def build_planet_name_prompt(
    posts: list[dict],
    faces: list[dict],
    *,
    post_limit: int | None = None,
) -> str:
    lines = [f"- {face.get('title')}: {face.get('summary')}" for face in faces]
    body = _post_lines(posts, limit=post_limit if post_limit is not None else 10)
    return (
        "Name the one subject these perspectives share.\n"
        "Return JSON only: {\"name\": \"2-4 words\", \"chitchat\": \"yes or no\"}.\n"
        "chitchat is yes only for greetings, thanks, compliments, birthday or holiday wishes, "
        "live-now self-promotion, or one-word agreement, and no when the posts discuss a public topic "
        "even if those words appear.\n"
        "The name is a newsbeat: a specific event, case, or policy. "
        "Every word must appear in the posts. Do not invent a movement, bill, or person. "
        "If the perspectives are different stories, name the largest one.\n"
        f"Perspectives:\n{chr(10).join(lines)}\n"
        f"Posts:\n{body}\n"
    )


def build_topic_prompt(posts: list[dict], terms: list[str], *, post_limit: int | None = None) -> str:
    shown = ", ".join(terms[:6]) if terms else "unknown"
    body = _post_lines(posts, limit=post_limit if post_limit is not None else 16)
    return (
        "Name one public-conversation topic clustered from social posts.\n"
        "Return JSON only, with no markdown: "
        '{"name": "2-4 words", "summary": "one sentence", "chitchat": "yes or no"}\n'
        "chitchat is yes only for greetings, thanks, compliments, birthday or holiday wishes, "
        "live-now self-promotion, or one-word agreement, and no when the posts discuss a public topic "
        "even if those words appear.\n"
        "The name should sound like a newsbeat: a specific event, case, or policy, "
        "not a mood, a party, or a keyword dump. "
        "Use only entities that appear in the posts or the salient terms. "
        f"Salient terms: {shown}.\n"
        f"Posts:\n{body}\n"
    )


def _post_lines(posts: list[dict], limit: int | None = 12) -> str:
    """At most ``MAX_PROMPT_POSTS`` lines, even when ``limit`` is the whole planet."""
    if limit is None:
        cap = MAX_PROMPT_POSTS
    else:
        cap = max(0, min(int(limit), MAX_PROMPT_POSTS))
    lines = []
    shown = posts[:cap]
    for post in shown:
        likes = int(post.get("likes") or 0)
        text = str(post.get("text") or post.get("clean_text") or "")[:280]
        lines.append(f"- ({likes} likes) {text}")
    return "\n".join(lines)


def _relax_unescaped_quotes(text: str) -> str:
    """Escape double quotes a model dropped inside a JSON string.

    A quote ends the string only when the next non-space character is a
    comma, colon, closing brace, or closing bracket. Anything else is
    content, which strict json.loads rejects.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if not in_string:
            out.append(char)
            if char == '"':
                in_string = True
            continue
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\":
            out.append(char)
            escaped = True
            continue
        if char != '"':
            out.append(char)
            continue
        follower = index + 1
        while follower < len(text) and text[follower] in " \t\r\n":
            follower += 1
        if follower >= len(text) or text[follower] in ",}]:":
            out.append(char)
            in_string = False
        else:
            out.append('\\"')
    return "".join(out)


def _load_label_json(blob: str):
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        try:
            return json.loads(_relax_unescaped_quotes(blob))
        except json.JSONDecodeError:
            return None


def parse_label(text: str) -> dict | None:
    """Pull the first JSON object that has a title/name and a summary."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    data = _load_label_json(text[start : end + 1])
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    title = str(data.get("title") or data.get("name") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not title or not summary:
        return None
    parsed: dict = {"title": title[:48], "summary": summary[:280]}
    if data.get("name"):
        parsed["name"] = str(data["name"]).strip()[:48]
    flag = chitchat_flag(data)
    if flag is not None:
        parsed["chitchat"] = flag
    arguments = _clean_arguments(data.get("arguments"))
    if arguments:
        parsed["arguments"] = arguments
    return parsed


def _clean_arguments(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    items = [str(item).strip() for item in raw if str(item).strip()]
    return items[:6]


def fallback_label(terms: list[str]) -> dict:
    shown = ", ".join(terms[:5]) if terms else "no stable terms"
    return {
        "title": FALLBACK_TITLE,
        "summary": f"Automatic label unavailable; top terms: {shown}.",
        "label_source": "fallback",
    }


def _shown_sentence(posts: list[dict] | None) -> str:
    """A finished sentence from a shown post, never a clipped fragment."""
    ranked = sorted(posts or [], key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        text = str(post.get("text") or post.get("clean_text") or "").strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip()
            words = sentence.split()
            if len(words) < 4 or len(words) > 32:
                continue
            if sentence.endswith("…") or sentence.endswith("..."):
                continue
            if sentence[-1:] not in ".!?":
                continue
            return sentence
    return ""


def heuristic_label(terms: list[str], posts: list[dict] | None = None) -> dict:
    words = [term.capitalize() for term in terms[:3]]
    title = " ".join(words) if words else FALLBACK_TITLE
    shown = ", ".join(terms[:5]) if terms else "these posts"
    summary = _shown_sentence(posts) or f"A live remark about {shown}."
    labeled = {
        "title": title[:48],
        "summary": summary[:280],
        "label_source": "heuristic",
        "arguments": heuristic_arguments(posts or [], terms),
    }
    return labeled


def heuristic_topic_label(terms: list[str], posts: list[dict] | None = None) -> dict:
    words = [term.capitalize() for term in terms[:3]]
    name = " ".join(words) if words else "Untitled topic"
    shown = ", ".join(terms[:5]) if terms else "this cluster"
    return {
        "name": name[:48],
        "title": name[:48],
        "summary": f"A live cluster around {shown}.",
        "label_source": "heuristic",
        "arguments": heuristic_arguments(posts or [], terms),
    }


def heuristic_arguments(posts: list[dict], terms: list[str] | None = None) -> list[str]:
    """A short claim from one post's own words, not a pasted post."""
    del terms
    arguments: list[str] = []
    seen: set[str] = set()
    ranked = sorted(posts, key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        tokens = sorted(
            content_tokens(str(post.get("text") or post.get("clean_text") or "")),
            key=len,
            reverse=True,
        )
        if len(tokens) < 2:
            continue
        primary = f"The claim centers on {tokens[0]} and {tokens[1]}."
        secondary = f"Readers are treating {tokens[0]} and {tokens[1]} as the live issue."
        for sentence in (primary, secondary):
            if sentence in seen:
                continue
            seen.add(sentence)
            arguments.append(sentence)
        if len(arguments) >= 2:
            break
    return arguments[:4]


def content_tokens(text: str) -> set[str]:
    """Words long enough to show that a sentence is about the same post."""
    return {token for token in _TOKEN.findall(text.lower()) if len(token) >= 4 and token not in _GROUND_STOP}


def titles_alike(left: str | None, right: str | None) -> bool:
    """True when two face titles are the same stance, including a numbered copy."""
    from difflib import SequenceMatcher

    def normalize(value: str | None) -> str:
        words = re.findall(r"[a-z0-9]+", str(value or "").lower())
        while words and words[-1].isdigit():
            words.pop()
        return " ".join(words)

    a = normalize(left)
    b = normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if SequenceMatcher(None, a, b).ratio() >= 0.8:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if len(a_tokens) >= 2 and len(b_tokens) >= 2:
        overlap = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
        if overlap >= 0.67:
            return True
        small, large = (a_tokens, b_tokens) if len(a_tokens) <= len(b_tokens) else (b_tokens, a_tokens)
        if small <= large:
            return True
    shared = a_tokens & b_tokens
    only_a = a_tokens - b_tokens
    only_b = b_tokens - a_tokens
    if shared and len(only_a) == 1 and len(only_b) == 1:
        left = next(iter(only_a))
        right = next(iter(only_b))
        if len(left) >= 4 and len(right) >= 4 and left[:4] == right[:4]:
            return True
    return False


def unique_label(name: str, seen: set[str]) -> str:
    """Keep planet and face titles distinct inside one snapshot."""
    base = " ".join((name or "").split()) or "Untitled"
    candidate = base
    number = 2
    while candidate.lower() in seen:
        candidate = f"{base} {number}"
        number += 1
    seen.add(candidate.lower())
    return candidate


def invented_entities(text: str, source: str, *, title: bool = False) -> list[str]:
    """Names, acronyms, and numbers the posts never said.

    A title is title case, so ordinary words there are not treated as entities.
    Inside a sentence, a capitalized word that is not the first word is.
    """
    lexicon = set(_TOKEN.findall((source or "").lower()))
    found: list[str] = []
    source_numbers = set(_NUMBER.findall(source or ""))
    for number in _NUMBER.findall(text or ""):
        if number not in source_numbers:
            found.append(number)
    for match in _CAMEL.findall(text or ""):
        if match.lower() not in lexicon:
            found.append(match)
    for match in _ACRONYM.findall(text or ""):
        if match.lower() not in lexicon:
            found.append(match)
    if title:
        return found
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text or "")
    for index, word in enumerate(words):
        if index == 0 or word.lower() in lexicon or word.lower() in _TITLE_WORDS:
            continue
        if re.fullmatch(r"[A-Z][a-z]{2,}", word):
            found.append(word)
    return found


def perspective_needs_repair(labeled: dict, posts: list[dict] | None = None) -> bool:
    """A publishable face has a grammatical title and one complete sentence."""
    summary = str(labeled.get("summary") or "")
    if _title_needs_repair(str(labeled.get("title") or "")) or _summary_needs_repair(summary):
        return True
    return bool(posts and _copies_post(summary, posts))


def _title_needs_repair(title: str) -> bool:
    words = str(title or "").split()
    if not words or len(words) > 4:
        return True
    if _is_camp_title(title) or _is_insult_title(title) or _title_is_weak(title):
        return True
    if any(word.lower().strip(".,") in _FRAGMENT_WORDS for word in words):
        return True
    if _SLOGAN_TITLE.search(str(title or "").strip()):
        return True
    if _MOOD_ENDING.search(words[-1]):
        return True
    stems = [subject_stem(word.lower()) for word in words if len(word) >= 4]
    if len(stems) != len(set(stems)):
        return True
    if len(words) == 2 and _BROKEN_TITLE_ENDING.search(words[-1]):
        return True
    return False


def _summary_needs_repair(summary: str) -> bool:
    text = str(summary or "").strip()
    if not text or text.endswith("…") or text.endswith("..."):
        return True
    if len(text.split()) < 4:
        return True
    lowered = text.lower()
    if _hedged(text) or " but " in f" {lowered} " or _SECOND_SUBJECT.search(text):
        return True
    if len(text.split()) > 28:
        return True
    return False


def ground_perspective(labeled: dict, posts: list[dict], terms: list[str]) -> dict:
    """Drop steelmans that invent a fact or do not paraphrase a shown post."""
    source = _source_text(posts, terms)
    titled = dict(labeled)
    title = str(titled.get("title") or "")
    if invented_entities(title, source, title=True) or _title_needs_repair(title):
        fallback = _claim_title(posts, terms)
        if fallback and not _title_needs_repair(fallback):
            titled["title"] = fallback
            titled["label_source"] = "heuristic"
    summary = str(titled.get("summary") or "")
    if invented_entities(summary, source):
        sentence = _shown_sentence(posts)
        if (
            sentence
            and not _summary_needs_repair(sentence)
            and not invented_entities(sentence, source)
            and not _copies_post(sentence, posts)
        ):
            titled["summary"] = sentence
            titled["label_source"] = "heuristic"
    arguments = _grounded_arguments(titled.get("arguments") or [], posts, source)
    arguments = _arguments_about_the_title(arguments, str(titled.get("title") or ""))
    if len(arguments) < 2 and str(titled.get("label_source") or "") == "heuristic":
        for extra in heuristic_arguments(posts, terms):
            if extra in arguments:
                continue
            arguments.extend(_grounded_arguments([extra], posts, source))
            if len(arguments) >= 2:
                break
    if arguments:
        titled["arguments"] = arguments[:6]
    else:
        titled.pop("arguments", None)
    return titled


def ground_topic(labeled: dict, posts: list[dict], terms: list[str]) -> dict:
    """Reject a planet name that names something the posts do not mention."""
    source = _source_text(posts, terms)
    titled = dict(labeled)
    name = str(titled.get("name") or titled.get("title") or "").strip()
    if (
        not name
        or invented_entities(name, source, title=True)
        or _is_camp_title(name)
        or _is_insult_title(name)
        or _name_adds_words(name, source)
    ):
        replacement = _claim_title(posts, terms) or heuristic_topic_label(terms, posts)["name"]
        if replacement and not _title_is_weak(replacement):
            name = replacement
            titled["label_source"] = "heuristic"
    titled["name"] = name
    titled["title"] = name
    if invented_entities(str(titled.get("summary") or ""), source):
        titled["summary"] = heuristic_topic_label(terms, posts)["summary"]
        titled["label_source"] = "heuristic"
    return titled


def _grounded_arguments(items: list, posts: list[dict], source: str) -> list[str]:
    kept: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or invented_entities(text, source) or not _paraphrases(text, posts):
            continue
        if _copies_post(text, posts):
            continue
        kept.append(text)
    return kept


def _copies_post(text: str, posts: list[dict]) -> bool:
    """A steelman that pastes a post is not a summary of the claim."""
    snippet = " ".join(text.lower().split())
    if len(snippet) < 48:
        return False
    for post in posts:
        body = " ".join(str(post.get("text") or post.get("clean_text") or "").lower().split())
        if snippet[:72] in body:
            return True
    return False


def _arguments_about_the_title(arguments: list[str], title: str) -> list[str]:
    """Drop steelmans that wandered into a different claim when the title is specific."""
    if not content_tokens(title):
        return arguments
    matched = [item for item in arguments if shares_claim_word(item, title)]
    if matched:
        return matched
    return arguments


def shares_claim_word(text: str, focus: str) -> bool:
    """True when a sentence uses a word from the claim, including a close plural."""
    focus_tokens = content_tokens(focus)
    text_tokens = content_tokens(text)
    for left in text_tokens:
        for right in focus_tokens:
            if left == right:
                return True
            short, long = (left, right) if len(left) <= len(right) else (right, left)
            if len(short) >= 5 and long.startswith(short):
                return True
            if len(short) >= 4 and long.startswith(short) and len(long) - len(short) <= 3:
                return True
    return False


_PERSON_GLUE = frozenset(
    {
        "trump",
        "donald",
        "biden",
        "harris",
        "kamala",
        "president",
        "republican",
        "democrat",
        "america",
        "american",
        "americans",
    }
)


def _post_word_glue() -> frozenset[str]:
    return _GROUND_STOP | frozenset(
        {
            "actually",
            "think",
            "thinking",
            "anything",
            "through",
            "against",
            "certain",
            "support",
            "understand",
            "agree",
            "better",
            "every",
            "small",
            "without",
            "large",
            "really",
            "something",
            "someone",
            "because",
            "another",
            "before",
            "after",
        }
    )


def subject_stem(token: str) -> str:
    """Fold rape/rapists and export/exports onto one subject stem."""
    word = token
    for suffix in ("ists", "ist", "ings", "ing", "ers", "er", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word.rstrip("e")


_VERB_STEMS = frozenset(
    {
        "know",
        "want",
        "lik",
        "need",
        "said",
        "mak",
        "think",
        "look",
        "com",
        "tak",
        "hav",
        "get",
        "say",
        "just",
        "also",
        "even",
        "very",
    }
)


_TOPIC_GLUE = frozenset(
    {
        "christian",
        "church",
        "religion",
        "religious",
        "religiou",
        "catholic",
        "faith",
    }
)


# A job title is not a case. "Prosecutor" glues a border-wall ruling to a campaign ad.
_OFFICE_GLUE = frozenset(
    {
        "attorney",
        "counsel",
        "court",
        "general",
        "judg",
        "judge",
        "justice",
        "lawyer",
        "prosecut",
        "prosecution",
        "prosecutor",
    }
)


def _stem_bag(text: str, glue: frozenset[str]) -> set[str]:
    stems = set()
    for token in content_tokens(text):
        if len(token) < 4 or token in glue:
            continue
        stem = subject_stem(token)
        if len(stem) < 3 or stem in _VERB_STEMS:
            continue
        stems.add(stem)
    return stems


def _face_subject_words(face: dict) -> set[str]:
    """Stems this face repeats. A one-off aside does not make two stories one."""
    glue = _post_word_glue() | _PERSON_GLUE
    posts = (face.get("representative_posts") or [])[:6]
    if len(posts) <= 1:
        return _stem_bag(" ".join(str(post.get("text") or "") for post in posts), glue)
    counts: dict[str, int] = {}
    for post in posts:
        for stem in _stem_bag(str(post.get("text") or ""), glue):
            counts[stem] = counts.get(stem, 0) + 1
    title_stems = _stem_bag(
        " ".join([str(face.get("title") or ""), str(face.get("summary") or "")]),
        glue,
    )
    kept: set[str] = set()
    for stem, count in counts.items():
        if len(stem) >= 5:
            kept.add(stem)
        elif len(stem) == 4 and (count >= 2 or stem in title_stems):
            kept.add(stem)
        elif count >= 2 and count * 2 >= len(posts):
            kept.add(stem)
    return kept


def _shared_post_words(faces: list[dict]) -> set[str]:
    """Subject words every face's posts use, ignoring a bare politician name."""
    bags = [_face_subject_words(face) for face in faces]
    if len(bags) < 2 or any(not bag for bag in bags):
        return set()
    shared = set.intersection(*bags)
    return shared


def _is_specific_subject_word(word: str) -> bool:
    """Same filters as ``specific_shared_words``: not a person, creed, verb, or office."""
    return (
        len(word) >= 3
        and word not in _PERSON_GLUE
        and word not in _TOPIC_GLUE
        and word not in _VERB_STEMS
        and word not in _OFFICE_GLUE
    )


def specific_subject_words(face: dict) -> set[str]:
    """Specific subject stems one face repeats. Empty when the face has none."""
    return {word for word in _face_subject_words(face) if _is_specific_subject_word(word)}


def specific_shared_words(faces: list[dict]) -> set[str]:
    """Subject words the faces' posts share, ignoring a bare politician or creed."""
    return {word for word in _shared_post_words(faces) if _is_specific_subject_word(word)}


def story_groups(faces: list[dict]) -> list[list[int]]:
    """Partition faces into stories that still share a specific subject word.

    A group stays together only while the intersection of its subject words
    is non-empty. That is the same signal as ``specific_shared_words``: an
    empty intersection is different stories, not one planet. A face with no
    specific subject word is its own story. Groups come back largest first,
    then by the earliest face index. At most a handful of faces, so the
    merge is a direct search.
    """
    count = len(faces)
    if count == 0:
        return []
    bags = [specific_subject_words(face) for face in faces]
    members: list[list[int]] = [[index] for index in range(count)]
    active = set(range(count))
    while True:
        best: tuple[tuple[int, int, int], int, int, set[str]] | None = None
        ids = sorted(active)
        for left_at, left in enumerate(ids):
            if not bags[left]:
                continue
            for right in ids[left_at + 1 :]:
                if not bags[right]:
                    continue
                overlap = bags[left] & bags[right]
                if not overlap:
                    continue
                rank = (len(overlap), -left, -right)
                if best is None or rank > best[0]:
                    best = (rank, left, right, overlap)
        if best is None:
            break
        _rank, left, right, overlap = best
        members[left].extend(members[right])
        bags[left] = overlap
        active.remove(right)
    groups = [sorted(members[index]) for index in sorted(active)]
    groups.sort(key=lambda indexes: (-len(indexes), indexes[0]))
    return groups


# A smaller face stays on the planet only when at least this share of its
# posts contain the largest face's top stem.
_MAJORITY_STEM_COVERAGE = 0.5


def _face_story_texts(face: dict) -> list[str]:
    """Posts the stem check reads. A title is used only when the face has no posts."""
    rows = face.get("member_texts")
    if rows:
        return [str(text) for text in rows if str(text).strip()]
    posts = [
        str(post.get("text") or "")
        for post in (face.get("representative_posts") or [])
        if str(post.get("text") or "").strip()
    ]
    if posts:
        return posts
    title = " ".join(
        part
        for part in (str(face.get("title") or "").strip(), str(face.get("summary") or "").strip())
        if part
    )
    return [title] if title else []


def _face_story_size(face: dict) -> int:
    if face.get("post_count"):
        return int(face["post_count"])
    return len(_face_story_texts(face))


def _name_stem_bag(text: str) -> list[str]:
    """Subject stems, including a person's name. Repeats are kept.

    ``specific_shared_words`` drops names so "Trump" cannot glue two stories.
    This check is the opposite question: does the smaller face still talk
    about the largest face's subject, which may be a person.
    """
    glue = _post_word_glue() | _TOPIC_GLUE | _OFFICE_GLUE
    stems: list[str] = []
    # Findall, not the set in content_tokens, so a repeated word counts twice.
    for token in _TOKEN.findall(str(text or "").lower()):
        if len(token) < 4 or token in _GROUND_STOP or token in glue:
            continue
        stem = subject_stem(token)
        if len(stem) < 3 or stem in _VERB_STEMS or stem in glue:
            continue
        stems.append(stem)
    return stems


def face_top_stem(texts: list[str]) -> str | None:
    """Most common stem. A tie goes to the stem used more often, then the longer one."""
    coverage: dict[str, int] = {}
    frequency: dict[str, int] = {}
    for text in texts:
        bag = _name_stem_bag(text)
        for stem in bag:
            frequency[stem] = frequency.get(stem, 0) + 1
        for stem in set(bag):
            coverage[stem] = coverage.get(stem, 0) + 1
    if not coverage:
        return None
    return max(coverage, key=lambda stem: (coverage[stem], frequency[stem], len(stem), stem))


def _text_has_stem(text: str, stem: str) -> bool:
    for other in _name_stem_bag(text):
        if other == stem:
            return True
        short, long = (other, stem) if len(other) <= len(stem) else (stem, other)
        if len(short) >= 5 and long.startswith(short):
            return True
    return False


def majority_story_groups(faces: list[dict]) -> list[list[int]] | None:
    """Face indexes that are one story, largest face first.

    None when the largest face has no stem, so the caller can fall back to
    ``story_groups``. A smaller face is its own story when fewer than half
    of its posts contain the largest face's top stem. Sharing "data" or
    "canada" does not keep it.
    """
    count = len(faces)
    if count == 0:
        return []
    if count == 1:
        return [[0]]
    order = sorted(range(count), key=lambda index: (-_face_story_size(faces[index]), index))
    anchor = order[0]
    stem = face_top_stem(_face_story_texts(faces[anchor]))
    if stem is None:
        return None
    together = [anchor]
    apart: list[list[int]] = []
    for index in order[1:]:
        rows = _face_story_texts(faces[index])
        if not rows:
            apart.append([index])
            continue
        covered = sum(1 for text in rows if _text_has_stem(text, stem))
        if covered / len(rows) >= _MAJORITY_STEM_COVERAGE:
            together.append(index)
        else:
            apart.append([index])
    if not apart:
        return [sorted(together)]
    return [sorted(together), *apart]


def faces_are_different_stories(faces: list[dict]) -> bool:
    """True when the faces should not stay on one planet."""
    groups = majority_story_groups(faces)
    if groups is not None and len(groups) >= 2:
        return True
    return len(faces) >= 2 and not specific_shared_words(faces)


# A planet label whose top word is in fewer than this share of posts is a
# mislabeled catch-all ("Companies" on an AI blob, "Think" on another).
CATCHALL_LABEL_COVERAGE = 0.30
# A stem in at least this share of the cluster is the blob's glue, not a
# story inside it. "ai" never reaches this function (it is two letters).
_CATCHALL_GLUE_SHARE = 0.70
# A catch-all bucket under this size, named by a generic stem, is a fragment.
# It is held out of the catalog. It is not glued onto another planet.
# This is stricter than the 5-post planet floor from #79. Specific stems still
# publish at 5 posts.
_THIN_FRAGMENT_POSTS = 8
_SHORT_SUBJECTS = frozenset({"ai", "eu", "gop", "ice", "uk", "un", "us"})
# Attitude words and the weak keys that produced AI Concerns/Use/Dangers/Rights
# ("already", "full", "first", "both"). Not the title-fragment list below.
_GENERIC_BUCKET_WORDS = frozenset(
    {
        "already",
        "another",
        "anything",
        "both",
        "break",
        "call",
        "calling",
        "concern",
        "concerns",
        "criticism",
        "danger",
        "dangers",
        "doing",
        "drawback",
        "drawbacks",
        "fear",
        "first",
        "flaw",
        "flaws",
        "full",
        "gen",
        "going",
        "harm",
        "issue",
        "issues",
        "made",
        "major",
        "make",
        "mean",
        "means",
        "might",
        "model",
        "models",
        "need",
        "nothing",
        "other",
        "problem",
        "problems",
        "really",
        "right",
        "rights",
        "risk",
        "risks",
        "saying",
        "something",
        "stuff",
        "thing",
        "things",
        "think",
        "threat",
        "threats",
        "use",
        "used",
        "using",
        "want",
        "way",
        "while",
        "worry",
    }
)


def label_top_term(label: str) -> str:
    """The label's primary word, including a weak word such as "think".

    Stopwords and bare numbers are skipped. A two-letter acronym that names
    a subject (AI, US) is kept. The first remaining word is the term the
    coverage test measures.
    """
    for word in re.findall(r"[A-Za-z0-9']+", label or ""):
        lower = word.lower()
        if lower in _TITLE_WORDS or lower.isdigit():
            continue
        if len(lower) <= 2 and lower not in _SHORT_SUBJECTS:
            continue
        return lower
    return ""


def _stem_key(stem: str) -> str:
    """Fold company/companies and factory/factories onto one key."""
    trimmed = stem.rstrip("iye")
    return trimmed if len(trimmed) >= 4 else stem


def _same_label_stem(left: str, right: str) -> bool:
    if left == right or _stem_key(left) == _stem_key(right):
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    return len(short) >= 4 and long.startswith(short)


def _label_term_in_text(term: str, text: str) -> bool:
    """True when ``term`` shows up, folding company/companies onto one stem."""
    if not term:
        return False
    if term in _SHORT_SUBJECTS and re.search(rf"\b{re.escape(term)}\b", text.lower()):
        return True
    term_stem = subject_stem(term)
    for token in _TOKEN.findall(text.lower()):
        if token == term or _same_label_stem(subject_stem(token), term_stem):
            return True
    return False


def label_term_coverage(label: str, posts: list[dict]) -> float:
    """Share of posts that use the label's top term. 0 when the label has none."""
    term = label_top_term(label)
    if not term or not posts:
        return 0.0
    hits = 0
    for post in posts:
        text = str(post.get("text") or post.get("clean_text") or "")
        if _label_term_in_text(term, text):
            hits += 1
    return hits / len(posts)


def catchall_reasons(faces: list[dict], posts: list[dict], label: str) -> list[str]:
    """Why this cluster is not one specific story. Empty means coherent.

    The three signals from issue #104, any one of which is enough:

    - more than one ``story_groups`` bucket (the faces are not one story)
    - empty ``specific_shared_words`` (no shared claim across the faces)
    - the label's top term appears in under 30% of member posts
    """
    reasons: list[str] = []
    if len(faces) >= 2:
        if len(story_groups(faces)) > 1:
            reasons.append("more than one story")
        if not specific_shared_words(faces):
            reasons.append("no shared claim")
    if posts and label_term_coverage(label, posts) < CATCHALL_LABEL_COVERAGE:
        reasons.append("label term in under 30% of posts")
    return reasons


def _collapse_stem_roots(stems: set[str]) -> dict[str, str]:
    """Map company/companies-style stems onto the shorter shared root."""
    ordered = sorted(stems, key=lambda stem: (len(stem), stem))
    root_of: dict[str, str] = {}
    for stem in ordered:
        root = stem
        for earlier in ordered:
            if earlier == stem:
                break
            if len(earlier) >= 5 and stem.startswith(earlier):
                root = root_of[earlier]
                break
        root_of[stem] = root
    return root_of


def _generic_stem_keys() -> set[str]:
    """Stems of attitude words and weak title words, including use→us and make→mak."""
    keys: set[str] = set()
    for word in _GENERIC_BUCKET_WORDS | _WEAK_TITLE_WORDS:
        keys.add(word)
        stemmed = subject_stem(word)
        keys.add(stemmed)
        keys.add(_stem_key(stemmed))
    return keys


def _fragment_stem(stem: str) -> bool:
    """True when a bucket key is an attitude or a weak word, not a story.

    "use" stems to "us" and "make" stems to "mak". A short specific subject
    such as "book" is not a fragment.
    """
    key = _stem_key(stem)
    generic = _generic_stem_keys()
    return key in generic or stem in generic


def _surface_fragment(term: str) -> bool:
    """True when a salient word would not name a specific story."""
    word = str(term or "").lower()
    if len(word) <= 3:
        return True
    if word in _GENERIC_BUCKET_WORDS or word in _WEAK_TITLE_WORDS:
        return True
    return _fragment_stem(subject_stem(word))


def _fragment_bucket(posts: list[dict], stem: str, indexes: list[int]) -> bool:
    """A thin bucket is a fragment when its key, or every salient word, is generic."""
    if _fragment_stem(stem):
        return True
    texts = [
        str(posts[index].get("clean_text") or posts[index].get("text") or "") for index in indexes
    ]
    terms = salient_terms(texts, limit=6)
    if not terms:
        return True
    return all(_surface_fragment(term) for term in terms)


def _collapse_thin_fragments(
    posts: list[dict],
    keyed: list[tuple[str, list[int]]],
    *,
    notes: list[str] | None = None,
    held_buckets: list[list[int]] | None = None,
) -> list[list[int]]:
    """Hold a thin generic bucket. Do not glue it onto a different story.

    A specific stem (copyright, book, psychosis) stays its own bucket even at
    the planet floor. A generic bucket under 8 posts (concern, use, danger,
    right) is left out. Joining it to another planet would glue two stories.
    """
    kept: list[list[int]] = []
    held_fragments = 0
    held_posts = 0
    for stem, indexes in keyed:
        if len(indexes) >= _THIN_FRAGMENT_POSTS or not _fragment_bucket(posts, stem, indexes):
            kept.append(indexes)
            continue
        held_fragments += 1
        held_posts += len(indexes)
        if held_buckets is not None:
            held_buckets.append(list(indexes))
    if notes is not None and held_fragments:
        notes.append(
            f"held {held_fragments} thin fragments ({held_posts} posts) "
            f"below {_THIN_FRAGMENT_POSTS} posts."
        )
    return kept


def split_catchall_posts(
    posts: list[dict],
    *,
    floor: int,
    notes: list[str] | None = None,
    held_buckets: list[list[int]] | None = None,
) -> list[list[int]]:
    """Index groups of specific stories inside one catch-all cluster.

    A stem in 70% or more of the posts is the blob's glue and is not a
    story. Each remaining stem that covers at least ``floor`` posts can name
    a planet. A post joins its rarest such stem. A thin generic bucket is
    held out instead of glued onto a different story. One bucket that still
    holds almost every post is not a split. Groups come back largest first.
    """
    floor = max(int(floor), 2)
    count = len(posts)
    if count < floor:
        return []
    glue_words = _post_word_glue() | _PERSON_GLUE
    raw_bags = [
        _stem_bag(str(post.get("clean_text") or post.get("text") or ""), glue_words) for post in posts
    ]
    keyed = [{_stem_key(stem) for stem in bag} for bag in raw_bags]
    roots = _collapse_stem_roots({stem for bag in keyed for stem in bag})
    bags = [{roots[stem] for stem in bag} for bag in keyed]
    counts: dict[str, int] = {}
    for bag in bags:
        for stem in bag:
            counts[stem] = counts.get(stem, 0) + 1
    glue = {stem for stem, seen in counts.items() if seen >= _CATCHALL_GLUE_SHARE * count}
    keys = {
        stem
        for stem, seen in counts.items()
        if stem not in glue and stem not in _TOPIC_GLUE and stem not in _OFFICE_GLUE and seen >= floor
    }
    if not keys:
        return []
    groups: dict[str, list[int]] = {}
    for index, bag in enumerate(bags):
        options = [stem for stem in bag if stem in keys]
        if not options:
            continue
        chosen = min(options, key=lambda stem: (counts[stem], stem))
        groups.setdefault(chosen, []).append(index)
    keyed_buckets = [(stem, indexes) for stem, indexes in groups.items() if len(indexes) >= floor]
    buckets = _collapse_thin_fragments(
        posts, keyed_buckets, notes=notes, held_buckets=held_buckets
    )
    if len(buckets) == 1 and len(buckets[0]) >= int(0.85 * count):
        return []
    buckets.sort(key=lambda indexes: (-len(indexes), indexes[0] if indexes else 0))
    return buckets


def repeated_stems_below_floor(posts: list[dict], floor: int) -> int:
    """Stems that repeat and still miss the planet floor.

    Two or more means the cluster is several stories that are each too small
    to publish, not one story the splitter failed to cut.
    """
    floor = max(int(floor), 2)
    count = len(posts)
    if count < 2:
        return 0
    glue_words = _post_word_glue() | _PERSON_GLUE
    raw_bags = [
        _stem_bag(str(post.get("clean_text") or post.get("text") or ""), glue_words) for post in posts
    ]
    keyed = [{_stem_key(stem) for stem in bag} for bag in raw_bags]
    roots = _collapse_stem_roots({stem for bag in keyed for stem in bag})
    bags = [{roots[stem] for stem in bag} for bag in keyed]
    counts: dict[str, int] = {}
    for bag in bags:
        for stem in bag:
            counts[stem] = counts.get(stem, 0) + 1
    return sum(
        1
        for stem, seen in counts.items()
        if 2 <= seen < floor and stem not in _TOPIC_GLUE and stem not in _OFFICE_GLUE
    )


def faces_share_vocabulary(faces: list[dict]) -> bool:
    """False when representative posts share no subject word.

    Titles are ignored on purpose: a label can glue two stories with one verb.
    A face with no usable words does not, by itself, prove the stories differ.
    """
    if len(faces) < 2:
        return True
    glue = _post_word_glue()
    bags: list[set[str]] = []
    for face in faces:
        posts = face.get("representative_posts") or []
        text = " ".join(str(post.get("text") or "") for post in posts[:6])
        tokens = {token for token in content_tokens(text) if len(token) >= 5 and token not in glue}
        if not tokens:
            return True
        bags.append(tokens)
    return bool(set.intersection(*bags))


def _source_text(posts: list[dict], terms: list[str]) -> str:
    parts = [str(term) for term in terms]
    for post in posts:
        parts.append(str(post.get("text") or ""))
        parts.append(str(post.get("clean_text") or ""))
    return " ".join(parts)


_CAMP_TITLE = re.compile(
    r"^(anti|pro)\b|\b(criticism|critique|criticized)$",
    re.IGNORECASE,
)
_SLOGAN_TITLE = re.compile(r"^(stop|ban|end)\s+[A-Za-z0-9]{2,3}$", re.IGNORECASE)
_SECOND_SUBJECT = re.compile(r", and (some|many|other|women|men)\b", re.IGNORECASE)
_INSULT_TITLE = re.compile(r"\b(rapists?|fascists?|nazis?|morons?|scum)\b", re.IGNORECASE)


def _is_camp_title(title: str) -> bool:
    """A camp label hides the claim. 'Tax the Rich' is a claim; 'Anti Republican' is not."""
    return bool(_CAMP_TITLE.search(str(title or "").strip()))


def _is_insult_title(title: str) -> bool:
    return bool(_INSULT_TITLE.search(str(title or "")))


def _term_title(terms: list[str]) -> str:
    words = [_display_word(str(term).strip()) for term in terms[:3] if str(term).strip()]
    return " ".join(words)[:48]


_WEAK_TITLE_WORDS = frozenset(
    {
        "most",
        "use",
        "used",
        "using",
        "think",
        "thing",
        "things",
        "stuff",
        "other",
        "others",
        "really",
        "very",
        "just",
        "like",
        "make",
        "made",
        "want",
        "need",
        "take",
        "going",
        "says",
        "said",
        "much",
        "many",
        "well",
        "something",
        "someone",
        "anything",
        "everything",
        "nothing",
    }
)
_ACRONYM_CASE = {
    "ai": "AI",
    "us": "US",
    "uk": "UK",
    "g7": "G7",
    "lgbtq": "LGBTQ",
    "fbi": "FBI",
    "doj": "DOJ",
}
_HEDGE_PHRASES = (
    "various opinions",
    "various issues",
    "various concerns",
    "various forms",
    "no shared claim",
    "do not share a claim",
)


def _display_word(token: str) -> str:
    lower = token.lower()
    if lower in _ACRONYM_CASE:
        return _ACRONYM_CASE[lower]
    return token[:1].upper() + token[1:]


def _title_is_weak(title: str) -> bool:
    words = re.findall(r"[A-Za-z0-9']+", title or "")
    if not words:
        return True
    return len(words) == 1 and (words[0].lower() in _WEAK_TITLE_WORDS or len(words[0]) <= 3)


def _hedged(summary: str) -> bool:
    text = str(summary or "").lower()
    return any(phrase in text for phrase in _HEDGE_PHRASES)


def _specific_terms(terms: list[str]) -> list[str]:
    kept = []
    for term in terms:
        token = str(term).strip()
        if not token:
            continue
        if token.lower() in _WEAK_TITLE_WORDS or token.lower() in _TITLE_WORDS:
            continue
        if len(token) <= 3 and token.lower() not in _ACRONYM_CASE:
            continue
        kept.append(_display_word(token))
    return kept


def _claim_title(posts: list[dict], terms: list[str]) -> str:
    """Use salient terms only when they already name a claim, such as Rent Increase."""
    del posts
    from_terms = _specific_terms(terms)
    if len(from_terms) >= 2 and any(len(word) >= 6 for word in from_terms):
        return " ".join(from_terms[:3])[:48]
    return ""


_BROKEN_TITLE_ENDING = re.compile(
    r"(equipped|undermines|questionable|exists)$",
    re.IGNORECASE,
)
_MOOD_ENDING = re.compile(
    r"(harmful|flawed|discourse|views|opinions|outrage|toxic)$",
    re.IGNORECASE,
)


_FRAGMENT_WORDS = frozenset(
    {
        "doesn",
        "doesnt",
        "isn",
        "isnt",
        "wasn",
        "wasnt",
        "weren",
        "werent",
        "couldn",
        "couldnt",
        "wouldn",
        "wouldnt",
        "shouldn",
        "shouldnt",
        "dont",
        "cant",
        "wont",
        "happen",
        "happens",
        "happened",
    }
)


def _lead_text(posts: list[dict] | None) -> str:
    ranked = sorted(posts or [], key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        text = str(post.get("text") or post.get("clean_text") or "").strip()
        if len(text.split()) >= 8:
            return text
    return ""


def _concrete_title(text: str) -> str:
    """Two specific words from a sentence, longest first, written in reading order."""
    words = []
    for raw in re.findall(r"[A-Za-z][A-Za-z']+", text or ""):
        token = raw.lower().replace("'", "").replace("’", "")
        if token.endswith("ly") and len(token) > 4:
            continue
        if token in _TITLE_WORDS or token in _WEAK_TITLE_WORDS or token in _GROUND_STOP or token in _FRAGMENT_WORDS:
            continue
        if len(token) < 5:
            continue
        words.append(_display_word(token))
    pool = [word for word in words if len(word) >= 8]
    if len(pool) < 2:
        pool = [word for word in words if len(word) >= 6]
    if len(pool) < 2:
        return ""
    chosen = sorted(pool, key=len, reverse=True)[:2]
    chosen.sort(key=words.index)
    return " ".join(chosen)[:48]


def _word_in_source(word: str, lexicon: set[str]) -> bool:
    """True when the posts use this word, including a simple plural."""
    token = word.lower()
    if token in lexicon:
        return True
    candidates = {token}
    if token.endswith("es") and len(token) > 5:
        candidates.add(token[:-2])
    if token.endswith("s") and len(token) > 4:
        candidates.add(token[:-1])
    for item in lexicon:
        if item in candidates:
            return True
        stem = item
        if item.endswith("es") and len(item) > 5:
            stem = item[:-2]
        elif item.endswith("s") and len(item) > 4:
            stem = item[:-1]
        if stem == token:
            return True
    return False


def _name_adds_words(name: str, source: str) -> bool:
    """True when a name word of five letters or more never appears in the posts."""
    lexicon = set(_TOKEN.findall((source or "").lower()))
    missing = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z']*", name or "")
        if len(word) >= 5 and word.lower() not in _TITLE_WORDS and not _word_in_source(word, lexicon)
    ]
    return len(missing) >= 1


def topic_name_is_weak(name: str, posts: list[dict], terms: list[str]) -> bool:
    """A planet name that invents a story or dumps keywords should be rewritten."""
    source = _source_text(posts, terms)
    cleaned = str(name or "").strip()
    return (
        not cleaned
        or _title_needs_repair(cleaned)
        or _is_camp_title(cleaned)
        or _is_insult_title(cleaned)
        or _name_adds_words(cleaned, source)
    )


def _paraphrases(argument: str, posts: list[dict]) -> bool:
    argument_tokens = content_tokens(argument)
    if len(argument_tokens) < 2:
        return False
    for post in posts:
        post_tokens = content_tokens(str(post.get("text") or post.get("clean_text") or ""))
        if len(argument_tokens & post_tokens) >= 2:
            return True
    return False


_TOKEN = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b")
_TITLE_WORDS = frozenset(
    {
        "the",
        "this",
        "that",
        "some",
        "many",
        "people",
        "posts",
        "public",
        "social",
        "media",
        "when",
        "what",
        "with",
        "from",
        "they",
        "their",
        "there",
        "these",
        "those",
        "other",
        "about",
        "after",
        "before",
        "because",
        "would",
        "could",
        "should",
        "still",
        "just",
        "more",
        "most",
        "also",
        "only",
        "into",
        "over",
        "under",
        "such",
        "than",
        "then",
        "them",
        "been",
        "have",
        "were",
        "will",
        "your",
        "here",
        "even",
        "very",
        "really",
        "today",
        "world",
        "news",
        "mixed",
        "remarks",
        "untitled",
        "cluster",
        "topic",
    }
)
_GROUND_STOP = _TITLE_WORDS | frozenset(
    {
        "post",
        "posts",
        "face",
        "concentrate",
        "around",
        "live",
        "cluster",
        "these",
        "those",
        "their",
        "there",
        "about",
        "which",
        "where",
        "while",
        "being",
        "having",
    }
)


def label_perspective(
    posts: list[dict],
    terms: list[str],
    *,
    backend: str = "auto",
    generate: Callable[[str], str] | None = None,
    model: str | None = None,
    post_limit: int | None = None,
) -> dict:
    """Return title, summary, arguments, and label_source."""
    prompt_limit = post_limit if post_limit is not None else min(len(posts), 12)
    if generate is not None:
        labeled = _from_generator(
            generate, build_perspective_prompt(posts, post_limit=prompt_limit), terms, posts
        )
        labeled = _repair_perspective(labeled, posts, terms, generate, post_limit=prompt_limit)
        return _finish_perspective(labeled, posts, terms, drop_if_unrepaired=True)

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return _finish_perspective(heuristic_label(terms, posts), posts, terms, drop_if_unrepaired=False)
    generator = _generator_for(chosen, model)
    labeled = _from_generator(
        generator, build_perspective_prompt(posts, post_limit=prompt_limit), terms, posts
    )
    if labeled["label_source"] != "fallback":
        labeled["label_source"] = chosen
    labeled = _repair_perspective(labeled, posts, terms, generator, post_limit=prompt_limit)
    return _finish_perspective(labeled, posts, terms, drop_if_unrepaired=True)


def _repair_perspective(
    labeled: dict,
    posts: list[dict],
    terms: list[str],
    generate: Callable[[str], str],
    *,
    post_limit: int | None = None,
) -> dict:
    if not perspective_needs_repair(labeled, posts):
        return labeled
    repaired = _from_generator(
        generate, build_repair_prompt(posts, labeled, post_limit=post_limit), terms, posts
    )
    if repaired.get("label_source") == "fallback":
        return labeled
    merged = dict(labeled)
    if not _title_needs_repair(str(repaired.get("title") or "")):
        merged["title"] = repaired["title"]
    if not _summary_needs_repair(str(repaired.get("summary") or "")):
        merged["summary"] = repaired["summary"]
    if repaired.get("arguments"):
        merged["arguments"] = repaired["arguments"]
    merged["label_source"] = repaired.get("label_source") or merged.get("label_source")
    return merged


def _finish_perspective(
    labeled: dict,
    posts: list[dict],
    terms: list[str],
    *,
    drop_if_unrepaired: bool,
) -> dict:
    grounded = ground_perspective(labeled, posts, terms)
    if drop_if_unrepaired and perspective_needs_repair(grounded, posts):
        grounded["title"] = "Mixed remarks"
        grounded["summary"] = "These posts do not share a claim."
        grounded.pop("arguments", None)
        grounded["label_source"] = "heuristic"
    return grounded


def perspectives_share_subject(
    faces: list[dict],
    *,
    backend: str = "auto",
    generate: Callable[[str], str] | None = None,
    model: str | None = None,
) -> bool:
    """False when the faces are different stories glued into one planet."""
    if len(faces) < 2:
        return True
    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return True
    try:
        if generate is not None:
            raw = generate(build_same_subject_prompt(faces)) or ""
        else:
            raw = _generator_for(chosen, model)(build_same_subject_prompt(faces)) or ""
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError):
        return True
    parsed = _load_object(raw)
    if not isinstance(parsed, dict) or "same" not in parsed:
        return True
    return bool(parsed.get("same"))


def chitchat_flag(data: dict | None) -> bool | None:
    """Yes/no from the existing naming response. Missing means do not drop."""
    if not isinstance(data, dict) or "chitchat" not in data:
        return None
    raw = data.get("chitchat")
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"yes", "true", "y"}:
        return True
    if text in {"no", "false", "n"}:
        return False
    return None


def name_from_perspectives(
    posts: list[dict],
    faces: list[dict],
    terms: list[str],
    *,
    backend: str = "auto",
    model: str | None = None,
    post_limit: int | None = None,
) -> tuple[str | None, bool | None]:
    """A newsbeat name the posts use, plus the naming response's chit-chat flag.

    The flag is read from the same call. Heuristic naming makes no call and
    returns no flag. A rejected name still returns the flag.
    """
    if not faces:
        return None, None
    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return None, None
    try:
        raw = _generator_for(chosen, model)(
            build_planet_name_prompt(posts, faces, post_limit=post_limit)
        ) or ""
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError):
        return None, None
    parsed = parse_label(raw) or _load_object(raw)
    if not isinstance(parsed, dict):
        return None, None
    flag = chitchat_flag(parsed)
    name = str(parsed.get("name") or parsed.get("title") or "").strip()
    if not name:
        return None, flag
    grounded = ground_topic(
        {"name": name, "summary": str(faces[0].get("summary") or name), "chitchat": flag},
        posts,
        terms,
    )
    if grounded.get("label_source") == "heuristic":
        return None, flag
    cleaned = str(grounded.get("name") or "").strip()
    if not cleaned or _title_needs_repair(cleaned) or _is_camp_title(cleaned):
        return None, flag
    return cleaned, flag


def _generator_for(chosen: str, model: str | None) -> Callable[..., str]:
    if chosen == "ollama":
        chosen_model = model or (os.getenv("OLLAMA_MODEL") or "llama3.2")

        def _ollama(text: str, seed: int | None = None) -> str:
            del seed
            return _ollama_generate(text, chosen_model)

        return _ollama
    if chosen == "openai":
        chosen_model = resolve_openai_model(model)

        def _openai(text: str, seed: int | None = None) -> str:
            return _openai_generate(text, chosen_model, seed=seed)

        return _openai
    raise ValueError(f"Unknown label_backend {chosen}")


def _load_object(text: str) -> dict | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    data = _load_label_json(text[start : end + 1])
    return data if isinstance(data, dict) else None


def label_topic(
    posts: list[dict],
    terms: list[str],
    *,
    backend: str = "auto",
    generate: Callable[[str], str] | None = None,
    model: str | None = None,
    post_limit: int | None = None,
) -> dict:
    """Return a planet name and one-sentence summary."""
    if generate is not None:
        labeled = _from_generator(
            generate, build_topic_prompt(posts, terms, post_limit=post_limit), terms, posts
        )
        if "name" not in labeled:
            labeled["name"] = labeled.get("title") or heuristic_topic_label(terms, posts)["name"]
        return ground_topic(labeled, posts, terms)

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return ground_topic(heuristic_topic_label(terms, posts), posts, terms)
    labeled = _via_model(
        chosen, build_topic_prompt(posts, terms, post_limit=post_limit), terms, posts, model
    )
    if "name" not in labeled:
        labeled["name"] = labeled.get("title") or heuristic_topic_label(terms, posts)["name"]
    return ground_topic(labeled, posts, terms)


def _resolve_backend(backend: str) -> str:
    if backend == "heuristic":
        return "heuristic"
    if backend != "auto":
        return backend
    if ollama_reachable():
        return "ollama"
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return "openai"
    return "heuristic"


def _via_model(chosen: str, prompt: str, terms: list[str], posts: list[dict], model: str | None) -> dict:
    if chosen == "ollama":
        generator = lambda text: _ollama_generate(text, model or (os.getenv("OLLAMA_MODEL") or "llama3.2"))  # noqa: E731
        labeled = _from_generator(generator, prompt, terms, posts)
        if labeled["label_source"] != "fallback":
            labeled["label_source"] = "ollama"
        if "arguments" not in labeled:
            labeled["arguments"] = heuristic_arguments(posts, terms)
        return labeled
    if chosen == "openai":
        generator = lambda text: _openai_generate(text, resolve_openai_model(model))  # noqa: E731
        labeled = _from_generator(generator, prompt, terms, posts)
        if labeled["label_source"] != "fallback":
            labeled["label_source"] = "openai"
        if "arguments" not in labeled:
            labeled["arguments"] = heuristic_arguments(posts, terms)
        return labeled
    if chosen == "heuristic":
        return heuristic_label(terms, posts)
    raise ValueError(f"Unknown label_backend {chosen}")


def _from_generator(
    generate: Callable[[str], str],
    prompt: str,
    terms: list[str],
    posts: list[dict],
) -> dict:
    for _attempt in range(2):
        try:
            raw = generate(prompt) or ""
        except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError):
            raw = ""
        parsed = parse_label(raw)
        if parsed:
            parsed["label_source"] = "model"
            if "arguments" not in parsed:
                parsed["arguments"] = heuristic_arguments(posts, terms)
            return parsed
    failed = fallback_label(terms)
    failed["arguments"] = heuristic_arguments(posts, terms)
    return failed


_OLLAMA_CACHE: bool | None = None


def ollama_reachable(timeout: float = 0.4) -> bool:
    global _OLLAMA_CACHE
    if _OLLAMA_CACHE is not None:
        return _OLLAMA_CACHE
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        read_json(f"{host}/api/tags", timeout=timeout)
    except (RuntimeError, json.JSONDecodeError):
        _OLLAMA_CACHE = False
        return False
    _OLLAMA_CACHE = True
    return True


def _ollama_generate(prompt: str, model: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = read_json(
        f"{host}/api/chat",
        timeout=60,
        data=json.dumps(
            {
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return str(payload.get("message", {}).get("content") or "")


def resolve_openai_base_url() -> str:
    """OPENAI_BASE_URL, treating empty GitHub secret values as unset."""
    return (os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).strip().rstrip("/")


def resolve_openai_model(explicit: str | None = None) -> str:
    """Prefer an explicit model, then OPENAI_MODEL, then a host-specific default."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    env = (os.getenv("OPENAI_MODEL") or "").strip()
    if env:
        return env
    if "deepinfra.com" in resolve_openai_base_url():
        return DEFAULT_DEEPINFRA_MODEL
    return DEFAULT_OPENAI_MODEL


# Planets are labeled concurrently (pipeline.live), so a rate limit, a
# gateway blip, or a timeout is retried with a short bounded backoff instead
# of becoming a fallback label (which drops the face). 429 and 5xx get two
# retries, 2s then 6s. A timeout gets one retry: run 39038944044's second
# timeout retry of the same read never succeeded, and each one held a worker
# for the full request timeout. A retry that would run past the section
# deadline is not started. A timeout retry needs another full request timeout
# still inside the ceiling. 90s: prompts are capped at 40 posts. The old 120s
# timeout was for a 100-post stance sample that took 83s and, under 12-way
# concurrency, still read-timed out.
OPENAI_REQUEST_TIMEOUT = 90.0
_RETRY_CLASSES = frozenset({"429", "5xx", "timeout"})
_RETRY_DELAYS = (2.0, 6.0)
_TIMEOUT_RETRY_DELAYS = (2.0,)

_label_deadline_lock = threading.Lock()
_label_deadline_monotonic: float | None = None


def set_label_deadline(deadline: float | None) -> None:
    """Section ceiling (``time.monotonic``) shared with label worker threads.

    ``None`` clears it. Global labeling has no ceiling. The value is a module
    global, not a context var: pool threads are created before the deadline
    is known, so they would not see a context copied at thread start.
    """
    global _label_deadline_monotonic
    with _label_deadline_lock:
        _label_deadline_monotonic = deadline


def get_label_deadline() -> float | None:
    with _label_deadline_lock:
        return _label_deadline_monotonic


def classify_label_error(exc: BaseException) -> str:
    """Map a labeling transport error to 429, 5xx, timeout, or other."""
    message = str(exc)
    if message.startswith("HTTP 429"):
        return "429"
    if message.startswith("HTTP "):
        code_text = message.split(" ", 2)[1]
        if code_text.isdigit():
            code = int(code_text)
            if code == 408:
                return "timeout"
            if 500 <= code <= 599:
                return "5xx"
            return "other"
    if _looks_like_timeout(exc):
        return "timeout"
    return "other"


def _looks_like_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    cause = exc.__cause__
    if isinstance(cause, TimeoutError):
        return True
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        return True
    if cause is not None:
        cause_text = str(cause).lower()
        if "timed out" in cause_text or "timeout" in cause_text:
            return True
    return False


def _retry_fits_budget(delay: float, error_class: str) -> tuple[bool, str]:
    """A retry must finish inside the section ceiling when one is set."""
    deadline = get_label_deadline()
    if deadline is None:
        return True, ""
    remaining = deadline - time.monotonic()
    needed = float(delay)
    if error_class == "timeout":
        needed += OPENAI_REQUEST_TIMEOUT
    if remaining >= needed:
        return True, ""
    return False, (
        f"retry skipped; {remaining:.1f}s left in the section time budget, need {needed:.1f}s"
    )


def _log_label_error(exc: BaseException, error_class: str, *, retried: bool, skip_reason: str) -> None:
    kind = "retried attempt" if retried else "final failure"
    extra = f" ({skip_reason})" if skip_reason else ""
    print(f"DeepInfra {error_class} {kind}{extra}: {exc}", file=sys.stderr)


def _openai_generate(prompt: str, model: str, *, seed: int | None = None) -> str:
    from pipeline.spend_cap import guard_before_paid_call

    guard_before_paid_call("labeling")
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = resolve_openai_base_url()
    request: dict = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if seed is not None:
        request["seed"] = int(seed)
    body = json.dumps(request).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload: dict | None = None
    timeout_retries = 0
    other_retries = 0
    while True:
        try:
            payload = read_json(
                f"{base}/chat/completions",
                timeout=OPENAI_REQUEST_TIMEOUT,
                data=body,
                headers=headers,
            )
        except RuntimeError as exc:
            error_class = classify_label_error(exc)
            if error_class == "timeout":
                delays = _TIMEOUT_RETRY_DELAYS
                used = timeout_retries
            elif error_class in _RETRY_CLASSES:
                delays = _RETRY_DELAYS
                used = other_retries
            else:
                delays = ()
                used = 0
            delay = delays[used] if used < len(delays) else None
            fits = False
            skip_reason = ""
            if delay is not None:
                fits, skip_reason = _retry_fits_budget(delay, error_class)
            will_retry = delay is not None and fits
            _remember_label_cost(
                model,
                getattr(exc, "payload", None),
                "retry" if will_retry else "failure",
                error_class=error_class,
            )
            _log_label_error(exc, error_class, retried=will_retry, skip_reason="" if will_retry else skip_reason)
            if not will_retry:
                raise
            if error_class == "timeout":
                timeout_retries += 1
            else:
                other_retries += 1
            time.sleep(float(delay))
            continue
        _remember_label_cost(model, payload, "success")
        break
    assert payload is not None
    return str(payload["choices"][0]["message"]["content"])


def _remember_label_cost(
    model: str,
    payload: dict | None,
    status: str,
    error_class: str = "",
) -> None:
    """Best effort. A metering error must not change the label result.

    ``SpendCapExceeded`` still stops the run. A swallowed cap would publish.
    """
    from pipeline.spend_cap import SpendCapExceeded

    try:
        from pipeline.costs import llm_service_for_base_url, record_llm_attempt

        record_llm_attempt(
            service=llm_service_for_base_url(resolve_openai_base_url()),
            requested_model=model,
            payload=payload,
            status=status,
            error_class="" if status == "success" else error_class,
        )
    except SpendCapExceeded:
        raise
    except Exception as exc:
        sys.stderr.write(f"WARNING: Cost log skipped for a labeling call: {exc}\n")
