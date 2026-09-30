"""Small JSON HTTP helper with a host allow-list.

Bandit flags urlopen (B310). Hosts are limited to Bluesky's public AppView,
OpenAI, DeepInfra, and the configured Ollama host.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

_ALLOWED_HOSTS = frozenset(
    {
        "public.api.bsky.app",
        "api.bsky.app",
        "bsky.social",
        "api.openai.com",
        "api.deepinfra.com",
    }
)


def _allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        return False
    host = parsed.hostname or ""
    if host in _ALLOWED_HOSTS:
        return True
    ollama = urllib.parse.urlparse(os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
    return bool(host) and host == (ollama.hostname or "")


def read_json(url: str, *, timeout: float, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    """GET or POST JSON. Raises RuntimeError on transport or HTTP errors."""
    if not _allowed(url):
        raise RuntimeError(f"Refusing to call a host outside the pipeline allow-list: {url}")
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {urllib.parse.urlparse(url).hostname}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Request failed for {urllib.parse.urlparse(url).hostname}: {exc}") from exc
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError("Expected a JSON object")
    return payload
