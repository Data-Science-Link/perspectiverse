"""Label each face with a short title and one sentence.

Default order: Ollama if it answers, else an OpenAI-compatible API when
OPENAI_API_KEY is set, else a visible fallback. One retry, then the fallback.
This module labels faces, not individual posts.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from pipeline.http_json import read_json

FALLBACK_TITLE = "Untitled cluster"


def build_prompt(posts: list[dict]) -> str:
    lines = []
    for post in posts[:12]:
        likes = int(post.get("likes") or 0)
        text = str(post.get("text") or post.get("clean_text") or "")[:280]
        lines.append(f"- ({likes} likes) {text}")
    body = "\n".join(lines)
    return (
        "Label one perspective cluster from public social posts.\n"
        'Return JSON only, with no markdown: {"title": "2-3 words", "summary": "one sentence"}\n'
        "The title is 2 to 3 words. The summary is one sentence.\n"
        f"Posts:\n{body}\n"
    )


def parse_label(text: str) -> dict | None:
    """Pull the first JSON object that has both title and summary."""
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
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not title or not summary:
        return None
    return {"title": title[:48], "summary": summary[:280]}


def fallback_label(terms: list[str]) -> dict:
    shown = ", ".join(terms[:5]) if terms else "no stable terms"
    return {
        "title": FALLBACK_TITLE,
        "summary": f"Automatic label unavailable; top terms: {shown}.",
        "label_source": "fallback",
    }


def heuristic_label(terms: list[str]) -> dict:
    words = [term.capitalize() for term in terms[:3]]
    title = " ".join(words) if words else FALLBACK_TITLE
    shown = ", ".join(terms[:5]) if terms else "these posts"
    return {
        "title": title,
        "summary": f"Posts in this face concentrate on {shown}.",
        "label_source": "heuristic",
    }


def label_perspective(
    posts: list[dict],
    terms: list[str],
    *,
    backend: str = "auto",
    generate: Callable[[str], str] | None = None,
    model: str | None = None,
) -> dict:
    """Return title, summary, and label_source. `generate` is a test seam."""
    if generate is not None:
        return _from_generator(generate, posts, terms)

    chosen = backend
    if chosen == "heuristic":
        return heuristic_label(terms)
    if chosen == "auto":
        if ollama_reachable():
            chosen = "ollama"
        elif os.getenv("OPENAI_API_KEY"):
            chosen = "openai"
        else:
            return fallback_label(terms)

    if chosen == "ollama":
        generator = lambda prompt: _ollama_generate(prompt, model or os.getenv("OLLAMA_MODEL", "llama3.2"))  # noqa: E731
        labeled = _from_generator(generator, posts, terms)
        if labeled["label_source"] != "fallback":
            labeled["label_source"] = "ollama"
        return labeled
    if chosen == "openai":
        generator = lambda prompt: _openai_generate(prompt, model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))  # noqa: E731
        labeled = _from_generator(generator, posts, terms)
        if labeled["label_source"] != "fallback":
            labeled["label_source"] = "openai"
        return labeled
    raise ValueError(f"Unknown label_backend {backend}")


def _from_generator(generate: Callable[[str], str], posts: list[dict], terms: list[str]) -> dict:
    prompt = build_prompt(posts)
    for _attempt in range(2):
        try:
            raw = generate(prompt) or ""
        except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError):
            raw = ""
        parsed = parse_label(raw)
        if parsed:
            parsed["label_source"] = "model"
            return parsed
    return fallback_label(terms)


def ollama_reachable(timeout: float = 0.4) -> bool:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        read_json(f"{host}/api/tags", timeout=timeout)
    except (RuntimeError, json.JSONDecodeError):
        return False
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
