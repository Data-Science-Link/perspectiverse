"""Per-post spam and newspaper-section decisions via Jev.

Jev does not write planet names or steelmans. One call per post asks a spam
noul and a section choice together. A missing key, a rejected key, or a
failed call keeps the post and leaves the section blank so the keyword map
can still label the planet.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from pipeline.http_json import read_json, read_json_value
from pipeline.schema import CATEGORIES

SYSTEMONE_URL = "https://api.typesafe.ai/v1/systemone"
MODELS_URL = "https://api.typesafe.ai/v1/models"
DEFAULT_MODEL = "jev-latest"
SPAM_THRESHOLD = 0.8
CLAIM_THRESHOLD = 0.5
_WORKERS = 8

SECTION_CRITERIA = {
    "World": "International conflict, diplomacy, wars, and foreign governments",
    "Politics": "Domestic civic conflict, elections, courts, and policy",
    "Business": "Markets, companies, labor, prices, and the economy",
    "Technology": "Software, AI, platforms, science, and engineering",
    "Sports": "Games, athletes, leagues, and sporting events",
    "Culture": "Arts, entertainment, media, and celebrity",
    "Health": "Medicine, public health, hospitals, and illness",
    "Environment": "Climate, pollution, energy, and nature",
    "Education": "Schools, universities, teaching, and students",
    "Other": "None of these sections is the primary subject",
}

_disabled_reason: str | None = None


def reset_jev_state() -> None:
    """Test seam. Clears a rejected-key latch."""
    global _disabled_reason
    _disabled_reason = None


def _api_key() -> str:
    return (os.getenv("TYPESAFE_API_KEY") or "").strip()


def _model() -> str:
    return (os.getenv("JEV_MODEL") or "").strip() or DEFAULT_MODEL


def describe_jev() -> str:
    """One startup line. Probes /v1/models only when a key is set and this is not pytest."""
    global _disabled_reason
    if not _api_key():
        return "Jev: off (TYPESAFE_API_KEY unset); regex and keyword sections."
    if os.getenv("PYTEST_CURRENT_TEST"):
        return f"Jev: on (model {_model()}; pytest skips the live probe)."
    try:
        read_json_value(
            MODELS_URL,
            timeout=15,
            headers={"Authorization": f"Bearer {_api_key()}", "Accept": "application/json"},
        )
    except RuntimeError as exc:
        _disabled_reason = str(exc)
        return f"Jev: off ({exc}); regex and keyword sections."
    return f"Jev: on (model {_model()})."


def apply_jev(posts: list[dict]) -> list[dict]:
    """Drop high-confidence spam and attach a section. Unlabeled posts are the only calls."""
    if _disabled_reason or not _api_key():
        return list(posts)
    pending = [post for post in posts if not post.get("section")]
    if not pending:
        return list(posts)
    decisions = _classify_many(pending)
    kept: list[dict] = []
    for post in posts:
        if post.get("section"):
            kept.append(post)
            continue
        decision = decisions.get(str(post.get("uri") or ""))
        if decision is None:
            kept.append(post)
            continue
        updated = dict(post)
        updated["spam_score"] = decision["spam_score"]
        if decision["spam_score"] >= SPAM_THRESHOLD:
            continue
        section = decision["section"] if decision["section"] in CATEGORIES else "Other"
        updated["section"] = section
        updated["section_confidence"] = decision["section_confidence"]
        if decision.get("is_claim") is not None:
            updated["is_claim"] = bool(decision["is_claim"])
        kept.append(updated)
    return kept


def _classify_many(posts: list[dict]) -> dict[str, dict | None]:
    workers = max(1, min(_WORKERS, len(posts)))
    found: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for post, decision in zip(posts, pool.map(_classify_post, posts)):
            found[str(post.get("uri") or "")] = decision
    answered = next((item.get("model") for item in found.values() if item and item.get("model")), "")
    if answered:
        print(f"Jev answered as {answered}.")
    return found


def _classify_post(post: dict) -> dict | None:
    text = str(post.get("clean_text") or post.get("text") or "")[:4000]
    if not text:
        return None
    try:
        payload = _post_systemone(text)
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return None
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return None
    spam = answers.get("spam") or {}
    section = answers.get("section") or {}
    try:
        spam_score = float(spam.get("noul"))
    except (TypeError, ValueError):
        return None
    choice = str(section.get("choice") or "Other")
    confidence = section.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else float((section.get("probabilities") or {}).get(choice) or 0.0)
    except (TypeError, ValueError):
        confidence_value = 0.0
    claim = answers.get("claim") or {}
    try:
        claim_noul = float(claim.get("noul"))
        is_claim: bool | None = claim_noul >= CLAIM_THRESHOLD
    except (TypeError, ValueError):
        is_claim = None
    return {
        "spam_score": spam_score,
        "section": choice,
        "section_confidence": confidence_value,
        "is_claim": is_claim,
        "model": str(payload.get("model") or ""),
    }


# A second section is listed when Jev treats it as a real alternative.
# Both probabilities must clear this floor, and the gap must be no wider than
# CLOSE_SECTION_GAP. This is the planet-level form of "the top two are close".
CLOSE_SECTION_PROBABILITY = 0.35
CLOSE_SECTION_GAP = 0.15
# Shadow bar from the #87 / #90 decision: planet section vs the majority of
# today's per-post sections.
SECTION_AGREEMENT_BAR = 0.90


def _section_question() -> dict:
    return {
        "type": "choice",
        "instructions": "Which newspaper section is this post's primary subject?",
        "criteria": SECTION_CRITERIA,
    }


def _planet_section_question() -> dict:
    """Planet-level section question.

    The 102-planet shadow (issue #90) agreed 91.2% overall and 50% on Culture:
    commentary about entertainment, media, and celebrity was sent to Other.
    The per-post question is unchanged. This nudge applies only when Jev
    classifies a planet.
    """
    criteria = dict(SECTION_CRITERIA)
    criteria["Culture"] = (
        "Arts, entertainment, media, celebrity, creators, and commentary about them, "
        "including a specific creator, show, clip, or dress code"
    )
    criteria["Other"] = (
        "None of the named sections is the primary subject. "
        "Not a fallback for culture, entertainment, media, or celebrity commentary"
    )
    return {
        "type": "choice",
        "instructions": (
            "Which newspaper section is this planet's primary subject? "
            "Arts, entertainment, media, celebrity, and creator commentary belong in Culture, not Other."
        ),
        "criteria": criteria,
    }


def _post_questions() -> dict:
    return {
        "spam": {
            "type": "noul",
            "instructions": "Is this post promotional, a bot, engagement bait, or spam rather than a real remark?",
            "criteria": {
                "true": "Promo, bot, giveaway, follow-bait, or an advertisement",
                "false": "A person saying something, including a messy or informal remark",
            },
        },
        "section": _section_question(),
        "claim": {
            "type": "noul",
            "instructions": (
                "Is this a public claim: a position on an event, policy, institution, or shared issue?"
            ),
            "criteria": {
                "true": "A position about an event, policy, institution, or public issue",
                "false": "Personal status, a joke, fandom aside, small talk, or promo",
            },
        },
    }


def planet_section_state(planet: dict) -> str:
    """The summary and arguments Jev reads when it picks a planet's section."""
    lines = [f"Planet: {planet.get('name') or 'Untitled'}"]
    brief = str(planet.get("brief") or planet.get("summary") or "").strip()
    if brief:
        lines.append(brief)
    for face in planet.get("perspectives") or []:
        title = str(face.get("title") or "").strip()
        summary = str(face.get("summary") or "").strip()
        lines.append(f"Perspective: {title}")
        if summary and summary != title:
            lines.append(summary)
        for argument in (face.get("arguments") or [])[:4]:
            text = str(argument).strip()
            if text:
                lines.append(f"- {text}")
    return "\n".join(lines)[:4000]


def sections_from_choice(choice: str, probabilities: dict | None) -> list[str]:
    """Primary section, plus a second when the top two probabilities are close."""
    probs: dict[str, float] = {}
    if isinstance(probabilities, dict):
        for name, value in probabilities.items():
            if str(name) not in CATEGORIES:
                continue
            try:
                probs[str(name)] = float(value)
            except (TypeError, ValueError):
                continue
    if choice in CATEGORIES and not probs:
        probs[choice] = 1.0
    if not probs:
        return []
    ranked = sorted(probs.items(), key=lambda item: (-item[1], CATEGORIES.index(item[0])))
    chosen = [ranked[0][0]]
    if len(ranked) > 1:
        top = ranked[0][1]
        second = ranked[1][1]
        if second >= CLOSE_SECTION_PROBABILITY and (top - second) <= CLOSE_SECTION_GAP:
            chosen.append(ranked[1][0])
    return chosen


def classify_planet_section(state: str) -> dict | None:
    """One section choice for an already-labeled planet. None when Jev is off or the call fails."""
    if _disabled_reason or not _api_key():
        return None
    text = str(state or "").strip()[:4000]
    if not text:
        return None
    try:
        payload = _post_questions_body(text, {"section": _planet_section_question()})
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return None
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return None
    section = answers.get("section") or {}
    choice = str(section.get("choice") or "")
    raw_probs = section.get("probabilities") if isinstance(section.get("probabilities"), dict) else {}
    chosen = sections_from_choice(choice, raw_probs)
    if not chosen:
        return None
    return {
        "sections": chosen,
        "primary": chosen[0],
        "probabilities": {name: float(raw_probs[name]) for name in raw_probs if name in CATEGORIES and _is_float(raw_probs[name])},
        "model": str(payload.get("model") or ""),
    }


def _is_float(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


def _post_systemone(text: str) -> dict:
    return _post_questions_body(text, _post_questions())


def _post_questions_body(text: str, questions: dict) -> dict:
    body = json.dumps(
        {
            "state": text,
            "model": _model(),
            "questions": questions,
        }
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    delay = 0.4
    last: RuntimeError | None = None
    for attempt in range(4):
        try:
            payload = read_json(SYSTEMONE_URL, timeout=30, data=body, headers=headers)
        except RuntimeError as exc:
            last = exc
            message = str(exc)
            retryable = "HTTP 429" in message or "HTTP 529" in message
            will_retry = retryable and attempt < 3
            _remember_jev_cost(getattr(exc, "payload", None), "retry" if will_retry else "failure")
            if not retryable:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        _remember_jev_cost(payload, "success")
        return payload
    assert last is not None
    raise last


def _remember_jev_cost(payload: dict | None, status: str) -> None:
    """Best effort. A metering error must not change the Jev decision."""
    try:
        from pipeline.costs import record_jev_attempt

        record_jev_attempt(requested_model=_model(), payload=payload, status=status)
    except Exception as exc:
        sys.stderr.write(f"WARNING: Cost log skipped for a Jev call: {exc}\n")
