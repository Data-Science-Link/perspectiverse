"""Short and long summaries at planet and perspective level, plus the weekly email.

The model is asked when a generator is passed. Otherwise the copy is built from
the claim, the steelman, and the posts already on the planet. Nothing here
invents a side that is not in that material.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def sentences(text: str) -> list[str]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    parts = _SENTENCE_END.split(cleaned)
    found: list[str] = []
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if piece[-1] not in ".!?":
            piece += "."
        found.append(piece)
    return found


def at_most_four(text: str) -> str:
    return " ".join(sentences(text)[:4])


def _dedupe(items: list[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _clean(item).rstrip(".").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _clause(text: str) -> str:
    return _clean(text).rstrip(".").strip()


def _lower_article(text: str) -> str:
    for word in ("The ", "A ", "An "):
        if text.startswith(word):
            return word.lower() + text[len(word) :]
    return text


def _lower_leading(text: str) -> str:
    text = _lower_article(text)
    word = text.split(" ", 1)[0].rstrip(".,;:")
    if word.endswith("ing") and word[:1].isupper() and not word.isupper():
        return text[0].lower() + text[1:]
    return text


def brief_from(*parts: str) -> str:
    """At most four sentences. Later fragments are paired so a list does not eat the cap."""
    found: list[str] = []
    for part in parts:
        found.extend(sentences(part))
    found = _dedupe(found)
    if not found:
        return ""
    packed = [found[0]]
    rest = found[1:]
    index = 0
    while index < len(rest) and len(packed) < 4:
        current = _clause(rest[index])
        nxt = _clause(rest[index + 1]) if index + 1 < len(rest) else ""
        if nxt and len(current) + len(nxt) < 180:
            packed.append(f"{current}; {nxt}.")
            index += 2
        else:
            packed.append(f"{current}.")
            index += 1
    return " ".join(packed[:4])


def _quote(post: dict, limit: int = 280) -> str:
    text = _clean(post.get("text") or post.get("clean_text") or "")
    if not text:
        return ""
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut >= int(limit * 0.45):
        return window[: cut + 1].strip()
    shortened = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{shortened}…"


def _best_post(posts: list[dict]) -> tuple[dict, str] | None:
    ranked = sorted(posts, key=lambda post: -int(post.get("likes") or 0))
    for post in ranked:
        quote = _quote(post)
        if quote:
            return post, quote
    return None


def _defense(title: str, clauses: list[str]) -> str:
    kept = [_clause(item) for item in clauses if _clause(item)][:6]
    if not kept:
        return ""
    opening = _lower_leading(kept[0])
    lines = [f"{title} argues that {opening}."]
    for extra in kept[1:]:
        lines.append(f"{extra}.")
    return " ".join(lines)


def detail_from(
    *,
    brief: str,
    arguments: list[str],
    posts: list[dict],
    rivals: list[str],
    title: str = "",
) -> str:
    """Longer copy: the position in full, then a post, then the other view."""
    paragraphs: list[str] = []
    claim = sentences(brief)[:1]
    argument_sentences = [sentence for argument in arguments for sentence in sentences(argument)]
    ordered = _dedupe([*claim, *argument_sentences]) if argument_sentences else sentences(brief)
    clauses = [_clause(sentence) for sentence in ordered if _clause(sentence)]
    if title and clauses:
        paragraphs.append(_defense(title, clauses[:4]))
    elif clauses:
        paragraphs.append(" ".join(f"{item}." for item in clauses[:4]))
    chosen = _best_post(posts)
    if chosen:
        post, quote = chosen
        author = _clean(post.get("author") or "")
        speaker = f"@{author}: " if author else ""
        paragraphs.append(f"{speaker}“{quote}”")
    if rivals:
        shown = ", ".join(rivals[:4])
        paragraphs.append(f"The other view in this conversation is {shown}.")
    if not paragraphs:
        paragraphs.append(brief)
    return "\n\n".join(paragraphs)


def _ask_model(generate: Callable[[str], str], prompt: str) -> dict | None:
    try:
        raw = generate(prompt)
    except Exception:
        return None
    start = str(raw or "").find("{")
    end = str(raw or "").rfind("}")
    if start < 0 or end <= start:
        return None
    import json

    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    brief = at_most_four(str(data.get("brief") or ""))
    detail = _clean(str(data.get("detail") or ""))
    if not brief or len(sentences(brief)) > 4 or len(detail) < 40:
        return None
    return {"brief": brief, "detail": detail.replace("\\n", "\n")}


def _perspective_prompt(face: dict, rivals: list[str]) -> str:
    posts = face.get("representative_posts") or []
    lines = []
    for post in posts[:6]:
        lines.append(f"- {_quote(post)}")
    arguments = face.get("arguments") or []
    return (
        "Write the reading-screen copy for one perspective.\n"
        "Return JSON only: {\"brief\": \"...\", \"detail\": \"...\"}\n"
        "brief is at most 4 sentences. It states the claim in the posts' own terms.\n"
        "detail is 2 or 3 paragraphs separated by a blank line: the claim, then a defense "
        "that paraphrases the posts, then the disagreement if another view is listed.\n"
        "Do not add a fact, number, or name that is not below. Do not explain percentages.\n"
        f"Title: {face.get('title')}\n"
        f"Claim: {face.get('summary')}\n"
        f"Arguments: {'; '.join(arguments)}\n"
        f"Other views: {', '.join(rivals) or 'none'}\n"
        f"Posts:\n{chr(10).join(lines)}\n"
    )


def apply_level_summaries(topic: dict, generate: Callable[[str], str] | None = None) -> dict:
    """Fill brief and detail on the planet and on every perspective."""
    perspectives = list(topic.get("perspectives") or [])
    for face in perspectives:
        rivals = [
            str(other.get("title"))
            for other in perspectives
            if other is not face and other.get("title") and other.get("title") != face.get("title")
        ]
        arguments = [str(item) for item in (face.get("arguments") or []) if str(item).strip()]
        posts = list(face.get("representative_posts") or [])
        lead = str(face.get("summary") or face.get("title") or "")
        brief = brief_from(lead, *arguments)
        detail = detail_from(
            brief=brief,
            arguments=arguments,
            posts=posts,
            rivals=rivals,
            title=str(face.get("title") or ""),
        )
        if generate is not None:
            written = _ask_model(generate, _perspective_prompt(face, rivals))
            if written:
                brief = written["brief"]
                detail = written["detail"]
        face["brief"] = brief or at_most_four(lead)
        face["detail"] = detail or face["brief"]

    face_lines = [
        f"{face.get('title')}: {face.get('summary') or face.get('brief')}"
        for face in perspectives
        if face.get("title")
    ]
    if len(perspectives) == 1:
        planet_brief = perspectives[0].get("brief") or brief_from(str(topic.get("name") or ""))
        topic["summary"] = sentences(planet_brief)[0] if sentences(planet_brief) else str(topic.get("name") or "")
        topic["brief"] = planet_brief
        topic["detail"] = perspectives[0].get("detail") or planet_brief
        return topic
    else:
        planet_brief = brief_from(
            *[
                str(face.get("summary") or face.get("title") or "")
                for face in perspectives
            ]
        )
    planet_posts: list[dict] = []
    defenses: list[str] = []
    for face in perspectives:
        planet_posts.extend(face.get("representative_posts") or [])
        title = str(face.get("title") or "This view")
        clauses = []
        for argument in face.get("arguments") or []:
            clauses.extend(_clause(sentence) for sentence in sentences(str(argument)))
        if not clauses and face.get("summary"):
            clauses.extend(_clause(sentence) for sentence in sentences(str(face.get("summary"))))
        defense = _defense(title, [item for item in clauses if item])
        if defense:
            defenses.append(defense)
    paragraphs = []
    if defenses:
        paragraphs.append(" ".join(defenses))
    chosen = _best_post(planet_posts)
    if chosen:
        post, quote = chosen
        author = _clean(post.get("author") or "")
        speaker = f"@{author}: " if author else ""
        paragraphs.append(f"{speaker}“{quote}”")
    if len(perspectives) >= 2:
        split = []
        for face in perspectives:
            claim = _lower_article(_clause(str(face.get("summary") or face.get("title") or "")))
            share = face.get("volume_percent")
            if share is None:
                split.append(f"{face.get('title')} says {claim}.")
            else:
                split.append(f"{face.get('title')} ({_percent(share)}) says {claim}.")
        paragraphs.append(" ".join(split))
    planet_detail = "\n\n".join(paragraphs) or planet_brief
    if generate is not None and perspectives:
        prompt = (
            "Write the reading-screen copy for one planet.\n"
            "Return JSON only: {\"brief\": \"...\", \"detail\": \"...\"}\n"
            "brief is at most 4 sentences naming the subject and each view.\n"
            "detail is 2 or 3 paragraphs: the subject, the defense of each view, and where they disagree.\n"
            "Use only the claims below.\n"
            f"Planet: {topic.get('name')}\n"
            f"Views:\n" + "\n".join(f"- {line}" for line in face_lines)
        )
        written = _ask_model(generate, prompt)
        if written:
            planet_brief = written["brief"]
            planet_detail = written["detail"]
    topic["summary"] = sentences(planet_brief)[0] if sentences(planet_brief) else str(topic.get("name") or "")
    topic["brief"] = planet_brief
    topic["detail"] = planet_detail or planet_brief
    return topic


def _percent(value: object) -> str:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if number == int(number):
        return f"{int(number)}%"
    return f"{number:.1f}%"


def assemble_email(topics: list[dict]) -> dict:
    """One email: the published planets, their arguments, and their disagreements."""
    ranked = sorted(topics, key=lambda topic: -float(topic.get("total_volume_percent") or 0))
    planets = []
    for topic in ranked:
        if not topic.get("brief"):
            apply_level_summaries(topic)
        faces = list(topic.get("perspectives") or [])
        arguments: list[str] = []
        if len(faces) <= 1:
            face = faces[0] if faces else {}
            for argument in face.get("arguments") or []:
                text = _clean(argument)
                if text:
                    arguments.append(text)
            if not arguments and face.get("summary"):
                arguments.append(_clean(face.get("summary")))
            claim = _clause(str(face.get("summary") or topic.get("name") or "this planet"))
            arguments = [item for item in arguments if _clause(item).lower() != claim.lower()]
            disagreement = (
                f"{claim}."
                if not arguments
                else f"The posts share one claim: {claim}."
            )
        else:
            for face in faces:
                title = str(face.get("title") or "View")
                wrote = False
                for argument in face.get("arguments") or []:
                    text = _clean(argument)
                    if text:
                        arguments.append(f"{title}: {text}")
                        wrote = True
                if not wrote and face.get("summary"):
                    arguments.append(f"{title}: {_clean(face.get('summary'))}")
            bits = []
            for face in faces:
                claim = _lower_article(_clause(str(face.get("summary") or face.get("title") or "")))
                share = _percent(face.get("volume_percent"))
                label = f"{face.get('title')} ({share})" if share else str(face.get("title"))
                bits.append(f"{label} says {claim}.")
            disagreement = " ".join(bits)
        planets.append(
            {
                "name": topic.get("name"),
                "category": topic.get("category"),
                "percent": topic.get("total_volume_percent"),
                "arguments": arguments[:6],
                "disagreement": disagreement,
            }
        )
    lead = ", ".join(str(planet["name"]) for planet in planets[:3] if planet.get("name"))
    subject = f"This week: {lead}" if lead else "This week"
    return {"subject": subject, "planets": planets}
