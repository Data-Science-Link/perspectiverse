"""Label planets and faces, and synthesize a short steelman per face.

Default order: Ollama if it answers, else an OpenAI-compatible API when
OPENAI_API_KEY is set, else a heuristic built from top terms and posts.
One retry, then the heuristic. This module labels clusters, not each post.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from pipeline.http_json import read_json

FALLBACK_TITLE = "Untitled cluster"


def build_prompt(posts: list[dict]) -> str:
    return build_perspective_prompt(posts)


def build_perspective_prompt(posts: list[dict]) -> str:
    body = _post_lines(posts)
    return (
        "Label one perspective cluster from public social posts.\n"
        "Return JSON only, with no markdown: "
        '{"title": "2-3 words", "summary": "one sentence", '
        '"arguments": ["steelman 1", "steelman 2", "steelman 3"]}\n'
        "The title is 2 to 3 words. The summary is one sentence. "
        "Give 2 to 4 short steelman arguments in that view's own voice.\n"
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


def parse_label(text: str) -> dict | None:
    """Pull the first JSON object that has a title/name and a summary."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
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


def heuristic_label(terms: list[str], posts: list[dict] | None = None) -> dict:
    words = [term.capitalize() for term in terms[:3]]
    title = " ".join(words) if words else FALLBACK_TITLE
    shown = ", ".join(terms[:5]) if terms else "these posts"
    summary = f"Posts in this face concentrate on {shown}."
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
        return labeled

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return heuristic_label(terms, posts)
    return _via_model(chosen, build_perspective_prompt(posts), terms, posts, model)


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
        return labeled

    chosen = _resolve_backend(backend)
    if chosen == "heuristic":
        return heuristic_topic_label(terms, posts)
    labeled = _via_model(chosen, build_topic_prompt(posts, terms), terms, posts, model)
    if "name" not in labeled:
        labeled["name"] = labeled.get("title") or heuristic_topic_label(terms, posts)["name"]
    return labeled


def _resolve_backend(backend: str) -> str:
    if backend == "heuristic":
        return "heuristic"
    if backend != "auto":
        return backend
    if ollama_reachable():
        return "ollama"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "heuristic"


def _via_model(chosen: str, prompt: str, terms: list[str], posts: list[dict], model: str | None) -> dict:
    if chosen == "ollama":
        generator = lambda text: _ollama_generate(text, model or os.getenv("OLLAMA_MODEL", "llama3.2"))  # noqa: E731
        labeled = _from_generator(generator, prompt, terms, posts)
        if labeled["label_source"] != "fallback":
            labeled["label_source"] = "ollama"
        if "arguments" not in labeled:
            labeled["arguments"] = heuristic_arguments(posts, terms)
        return labeled
    if chosen == "openai":
        generator = lambda text: _openai_generate(text, model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))  # noqa: E731
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


def _openai_generate(prompt: str, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
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
