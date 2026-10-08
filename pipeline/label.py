"""Label planets and faces, and synthesize a short steelman per face.

Default order: Ollama if it answers, else an OpenAI-compatible API when
OPENAI_API_KEY is set, else a heuristic built from top terms and posts.
One retry, then the heuristic. This module labels clusters, not each post.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable

from pipeline.http_json import read_json

FALLBACK_TITLE = "Untitled cluster"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_DEEPINFRA_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def build_prompt(posts: list[dict]) -> str:
    return build_perspective_prompt(posts)


def build_perspective_prompt(posts: list[dict]) -> str:
    body = _post_lines(posts)
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


def build_repair_prompt(posts: list[dict], draft: dict) -> str:
    body = _post_lines(posts)
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


def build_planet_name_prompt(posts: list[dict], faces: list[dict]) -> str:
    lines = [f"- {face.get('title')}: {face.get('summary')}" for face in faces]
    body = _post_lines(posts, limit=10)
    return (
        "Name the one subject these perspectives share.\n"
        "Return JSON only: {\"name\": \"2-4 words\"}.\n"
        "The name is a newsbeat: a specific event, case, or policy. "
        "Every word must appear in the posts. Do not invent a movement, bill, or person. "
        "If the perspectives are different stories, name the largest one.\n"
        f"Perspectives:\n{chr(10).join(lines)}\n"
        f"Posts:\n{body}\n"
    )


def build_topic_prompt(posts: list[dict], terms: list[str]) -> str:
    shown = ", ".join(terms[:6]) if terms else "unknown"
    body = _post_lines(posts, limit=16)
    return (
        "Name one public-conversation topic clustered from social posts.\n"
        "Return JSON only, with no markdown: "
        '{"name": "2-4 words", "summary": "one sentence"}\n'
        "The name should sound like a newsbeat: a specific event, case, or policy, "
        "not a mood, a party, or a keyword dump. "
        "Use only entities that appear in the posts or the salient terms. "
        f"Salient terms: {shown}.\n"
        f"Posts:\n{body}\n"
    )


def _post_lines(posts: list[dict], limit: int = 12) -> str:
    lines = []
    for post in posts[:limit]:
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
) -> dict:
    """Return title, summary, arguments, and label_source."""
    if generate is not None:
        labeled = _from_generator(generate, build_perspective_prompt(posts), terms, posts)
        labeled = _repair_perspective(labeled, posts, terms, generate)
        return _finish_perspective(labeled, posts, terms, drop_if_unrepaired=True)

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return _finish_perspective(heuristic_label(terms, posts), posts, terms, drop_if_unrepaired=False)
    generator = _generator_for(chosen, model)
    labeled = _from_generator(generator, build_perspective_prompt(posts), terms, posts)
    if labeled["label_source"] != "fallback":
        labeled["label_source"] = chosen
    labeled = _repair_perspective(labeled, posts, terms, generator)
    return _finish_perspective(labeled, posts, terms, drop_if_unrepaired=True)


def _repair_perspective(
    labeled: dict,
    posts: list[dict],
    terms: list[str],
    generate: Callable[[str], str],
) -> dict:
    if not perspective_needs_repair(labeled, posts):
        return labeled
    repaired = _from_generator(generate, build_repair_prompt(posts, labeled), terms, posts)
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


def name_from_perspectives(
    posts: list[dict],
    faces: list[dict],
    terms: list[str],
    *,
    backend: str = "auto",
    model: str | None = None,
) -> str | None:
    """A newsbeat name that the posts actually use."""
    if not faces:
        return None
    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return None
    try:
        raw = _generator_for(chosen, model)(build_planet_name_prompt(posts, faces)) or ""
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError):
        return None
    parsed = parse_label(raw) or _load_object(raw)
    if not isinstance(parsed, dict):
        return None
    name = str(parsed.get("name") or parsed.get("title") or "").strip()
    if not name:
        return None
    grounded = ground_topic({"name": name, "summary": str(faces[0].get("summary") or name)}, posts, terms)
    if grounded.get("label_source") == "heuristic":
        return None
    cleaned = str(grounded.get("name") or "").strip()
    if not cleaned or _title_needs_repair(cleaned) or _is_camp_title(cleaned):
        return None
    return cleaned


def _generator_for(chosen: str, model: str | None) -> Callable[[str], str]:
    if chosen == "ollama":
        chosen_model = model or (os.getenv("OLLAMA_MODEL") or "llama3.2")
        return lambda text: _ollama_generate(text, chosen_model)
    if chosen == "openai":
        chosen_model = resolve_openai_model(model)
        return lambda text: _openai_generate(text, chosen_model)
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
) -> dict:
    """Return a planet name and one-sentence summary."""
    if generate is not None:
        labeled = _from_generator(generate, build_topic_prompt(posts, terms), terms, posts)
        if "name" not in labeled:
            labeled["name"] = labeled.get("title") or heuristic_topic_label(terms, posts)["name"]
        return ground_topic(labeled, posts, terms)

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return ground_topic(heuristic_topic_label(terms, posts), posts, terms)
    labeled = _via_model(chosen, build_topic_prompt(posts, terms), terms, posts, model)
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


# Planets are labeled concurrently (pipeline.live), so a rate limit or a
# gateway blip is retried with a short backoff instead of becoming a fallback
# label (which drops the face). Timeouts are not retried; they already cost 60s.
_RETRY_STATUSES = ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")
_RETRY_DELAYS = (2.0, 6.0)


def _openai_generate(prompt: str, model: str) -> str:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = resolve_openai_base_url()
    body = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            payload = read_json(f"{base}/chat/completions", timeout=60, data=body, headers=headers)
            break
        except RuntimeError as exc:
            if attempt >= len(_RETRY_DELAYS) or not str(exc).startswith(_RETRY_STATUSES):
                raise
            time.sleep(_RETRY_DELAYS[attempt])
    return str(payload["choices"][0]["message"]["content"])
