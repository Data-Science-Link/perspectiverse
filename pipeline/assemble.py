"""Turn clustered faces into the data.json document the React app loads."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.briefs import apply_level_summaries, assemble_email
from pipeline.schema import NOISE_POLICY, WINDOW_HOURS, validate_payload

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "public" / "data.json"
FACE_LETTERS = "ABCDEF"


def topic_name(terms: list[str]) -> str:
    words = [term.capitalize() for term in terms[:3]]
    return " ".join(words) if words else "Untitled topic"


def assemble_payload(
    topics: list[dict[str, Any]],
    *,
    mode: str,
    source: str,
    total_posts: int,
    last_updated: str | None = None,
    sections: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    for topic in topics:
        if not topic.get("brief") or not topic.get("detail"):
            apply_level_summaries(topic)
    if sections:
        for section_topics in sections.values():
            for topic in section_topics:
                if not topic.get("brief") or not topic.get("detail"):
                    apply_level_summaries(topic)
    payload: dict[str, Any] = {
        "last_updated": last_updated or datetime.now(timezone.utc).date().isoformat(),
        "total_posts": int(total_posts),
        "window_hours": WINDOW_HOURS,
        "source": source,
        "mode": mode,
        "noise_policy": NOISE_POLICY,
        "topics": topics,
        "digest": assemble_email(topics),
    }
    if sections:
        payload["sections"] = sections
    validate_payload(payload)
    return payload


def face_id(topic_id: int, index: int) -> str:
    return f"{topic_id}{FACE_LETTERS[index]}"


def write_payload(payload: dict[str, Any], path: Path | None = None) -> Path:
    destination = Path(path) if path else DEFAULT_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination
