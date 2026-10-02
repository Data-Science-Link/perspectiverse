"""Label planets and faces, and synthesize a short steelman per face.

Default order: Ollama if it answers, else an OpenAI-compatible API when
OPENAI_API_KEY is set, else a heuristic built from top terms and posts.
One retry, then the heuristic. This module labels clusters, not each post.
"""

from __future__ import annotations

import json
import os
import re
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
        "These posts are meant to be one perspective. Name that view.\n"
        "Return JSON only, with no markdown: "
        '{"title": "2-3 words", "summary": "one sentence", '
        '"arguments": ["steelman 1", "steelman 2", "steelman 3"]}\n'
        "The title is 2 to 3 words naming the specific claim these posts share. "
        "The summary is one sentence of that claim. "
        "Do not invent an opposing camp, and do not call the posts various opinions. "
        "Each argument must paraphrase one of the posts below, in that view's own voice. "
        "Do not add a fact, number, or proper noun that is not in those posts. "
        "If the posts do not share a claim, use title \"Mixed remarks\", say so in one clause, "
        "and return an empty arguments list.\n"
        f"Posts:\n{body}\n"
    )


def build_topic_prompt(posts: list[dict], terms: list[str]) -> str:
    shown = ", ".join(terms[:6]) if terms else "unknown"
    body = _post_lines(posts, limit=16)
    return (
        "Name one public-conversation topic clustered from social posts.\n"
        "Return JSON only, with no markdown: "
        '{"name": "2-4 words", "summary": "one sentence"}\n'
        "The name should sound like a newsbeat or civic issue, not a keyword dump. "
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
    ranked = sorted(posts or [], key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        text = str(post.get("text") or post.get("clean_text") or "").strip()
        if len(text) < 24:
            continue
        sentence = text.split(". ")[0].strip()
        if len(sentence) > 180:
            sentence = sentence[:177].rsplit(" ", 1)[0] + "…"
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
    """Extractive steelman: the strongest distinct posts, trimmed."""
    arguments: list[str] = []
    seen: set[str] = set()
    ranked = sorted(posts, key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        text = str(post.get("text") or post.get("clean_text") or "").strip()
        if len(text) < 32:
            continue
        key = text.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        if len(text) > 180:
            text = text[:177].rsplit(" ", 1)[0] + "…"
        arguments.append(text)
        if len(arguments) >= 3:
            break
    if len(arguments) < 2 and terms:
        shown = ", ".join(terms[:4])
        arguments.append(f"The conversation keeps returning to {shown}.")
        arguments.append(f"Readers are treating {shown} as the live issue this week.")
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


def ground_perspective(labeled: dict, posts: list[dict], terms: list[str]) -> dict:
    """Drop steelmans that invent a fact or do not paraphrase a shown post."""
    source = _source_text(posts, terms)
    titled = dict(labeled)
    if invented_entities(str(titled.get("title") or ""), source, title=True):
        fallback = heuristic_label(terms, posts)
        titled["title"] = fallback["title"]
        titled["label_source"] = "heuristic"
    if invented_entities(str(titled.get("summary") or ""), source):
        titled["summary"] = heuristic_label(terms, posts)["summary"]
        titled["label_source"] = "heuristic"
    arguments = _grounded_arguments(titled.get("arguments") or [], posts, source)
    if len(arguments) < 2:
        for extra in heuristic_arguments(posts):
            if extra in arguments:
                continue
            arguments.extend(_grounded_arguments([extra], posts, source))
            if len(arguments) >= 2:
                break
    if len(arguments) >= 2:
        titled["arguments"] = arguments[:6]
    else:
        titled.pop("arguments", None)
    return titled


def ground_topic(labeled: dict, posts: list[dict], terms: list[str]) -> dict:
    """Reject a planet name that names something the posts do not mention."""
    source = _source_text(posts, terms)
    titled = dict(labeled)
    name = str(titled.get("name") or titled.get("title") or "").strip()
    if not name or invented_entities(name, source, title=True):
        name = heuristic_topic_label(terms, posts)["name"]
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
        kept.append(text)
    return kept


def _source_text(posts: list[dict], terms: list[str]) -> str:
    parts = [str(term) for term in terms]
    for post in posts:
        parts.append(str(post.get("text") or ""))
        parts.append(str(post.get("clean_text") or ""))
    return " ".join(parts)


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
        if "arguments" not in labeled:
            labeled["arguments"] = heuristic_arguments(posts, terms)
        return ground_perspective(labeled, posts, terms)

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return ground_perspective(heuristic_label(terms, posts), posts, terms)
    return ground_perspective(_via_model(chosen, build_perspective_prompt(posts), terms, posts, model), posts, terms)


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


def _openai_generate(prompt: str, model: str) -> str:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = resolve_openai_base_url()
    payload = read_json(
        f"{base}/chat/completions",
        timeout=60,
        data=json.dumps(
            {
                "model": model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    return str(payload["choices"][0]["message"]["content"])
