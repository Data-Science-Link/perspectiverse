"""Spam, public-claim, and newspaper-section decisions via Jev.

Jev does not write planet names or steelmans. The default is one call per
post: a spam noul, a section choice, and a claim noul. That section
question stays until #90 picks a section once per planet. Answers are
cached on the retained corpus for 14 days, including non-claims and spam,
so a URI is not scored twice inside that window. A free pre-filter drops
posts Jev is very unlikely to keep. Batching many posts into one request
is implemented and left off (``jev_batch`` defaults false). The shadow
test failed batched claims, so the live path stays one post per request.
That request asks spam and claim only. It does not send the section
question or ``SECTION_CRITERIA``.

A missing key, a rejected key, or a failed call keeps the post and leaves
the section blank so the keyword map can still label the planet.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from pipeline.http_json import read_json, read_json_value
from pipeline.jev_prefilter import (
    DuplicateIndex,
    post_text,
    prefilter_reason,
    text_fingerprint,
)
from pipeline.schema import CATEGORIES

SYSTEMONE_URL = "https://api.typesafe.ai/v1/systemone"
MODELS_URL = "https://api.typesafe.ai/v1/models"
DEFAULT_MODEL = "jev-latest"
SPAM_THRESHOLD = 0.8
CLAIM_THRESHOLD = 0.5
_WORKERS = 8
# Phase 3. Off: the shadow test failed batched claims. About 25 posts share one spam+claim request.
BATCH_SIZE = 25
CLAIM_TRUE = "A position about an event, policy, institution, or public issue"
CLAIM_FALSE = "Personal status, a joke, fandom aside, small talk, or promo"
SPAM_TRUE = "Promo, bot, giveaway, follow-bait, or an advertisement"
SPAM_FALSE = "A person saying something, including a messy or informal remark"

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


def known_scored_uris(connection, posts: list[dict] | None = None, now: datetime | None = None) -> set[str]:
    """URIs already scored, so a fetch does not pull them back for a second call.

    A cache error returns an empty set. The run still scores; it just cannot
    skip the URIs it failed to read.
    """
    try:
        _prepare_cache(connection, posts or [], now)
        from pipeline.store import jev_verdict_uris

        return jev_verdict_uris(connection)
    except Exception as exc:
        sys.stderr.write(f"WARNING: Jev verdict cache was not read: {exc}\n")
        return set()


def apply_jev(
    posts: list[dict],
    *,
    connection=None,
    now: datetime | None = None,
    batch: bool = False,
) -> list[dict]:
    """Drop high-confidence spam and attach a section. Unlabeled posts are the only calls.

    ``connection`` is the retained corpus. Verdicts, including non-claims and
    spam, are written there. ``batch`` is the phase-3 request shape and
    defaults off.
    """
    if _disabled_reason or not _api_key():
        return list(posts)
    cached, index = _open_cache(connection, posts, now)
    decisions = _decisions_for(posts, cached, index, batch=batch)
    if connection is not None:
        _store_verdicts(connection, posts, decisions, now)
    return _apply_decisions(posts, decisions)


def _open_cache(connection, posts: list[dict], now: datetime | None) -> tuple[dict[str, dict], DuplicateIndex]:
    index = DuplicateIndex()
    if connection is None:
        return {}, index
    try:
        _prepare_cache(connection, posts, now)
        from pipeline.store import load_jev_fingerprints, load_jev_verdicts

        uris = [str(post.get("uri") or "") for post in posts]
        cached = {uri: _decision_from_row(row) for uri, row in load_jev_verdicts(connection, uris).items()}
        for fingerprint in load_jev_fingerprints(connection):
            index.add_fingerprint(fingerprint)
        return cached, index
    except Exception as exc:
        sys.stderr.write(f"WARNING: Jev verdict cache was not read: {exc}\n")
        return {}, DuplicateIndex()


def _prepare_cache(connection, posts: list[dict], now: datetime | None) -> None:
    from pipeline.store import expire_jev_verdicts, remember_retained_verdicts

    today = _today(now)
    expire_jev_verdicts(connection, today)
    retained = []
    for post in posts:
        uri = str(post.get("uri") or "")
        section = str(post.get("section") or "")
        if not uri or not section or post.get("is_claim") is False:
            continue
        # Retained claims were already kept. The score is not a Jev noul.
        spam = post.get("spam_score")
        retained.append(
            (
                uri,
                None if spam is None else float(spam),
                1.0,
                section,
                "retained",
                today,
                text_fingerprint(post_text(post)),
            )
        )
    if retained:
        remember_retained_verdicts(connection, retained)


def _today(now: datetime | None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).date().isoformat()


def _decision_from_row(row: tuple) -> dict:
    _uri, spam_score, claim_score, section, model, _scored_on, _fingerprint = row
    claim_noul = None if claim_score is None else float(claim_score)
    is_claim = None if claim_noul is None else claim_noul >= CLAIM_THRESHOLD
    spam = None if spam_score is None else float(spam_score)
    return {
        "spam_score": spam,
        "claim_score": claim_noul,
        "section": str(section or ""),
        "section_confidence": None,
        "is_claim": is_claim,
        "model": str(model or ""),
        "cached": True,
    }


def _decisions_for(
    posts: list[dict],
    cached: dict[str, dict],
    index: DuplicateIndex,
    *,
    batch: bool,
) -> dict[str, dict | None]:
    """Decisions keyed by URI. Posts that still need Jev are classified here."""
    decisions: dict[str, dict | None] = {}
    pending: list[dict] = []
    skips: Counter[str] = Counter()
    hits = 0
    for post in posts:
        if post.get("section"):
            index.add_text(post_text(post))
            continue
        uri = str(post.get("uri") or "")
        if uri and uri in cached:
            decisions[uri] = cached[uri]
            hits += 1
            index.add_text(post_text(post))
            continue
        reason = prefilter_reason(post, index)
        if reason:
            skips[reason] += 1
            decisions[uri] = {"prefilter": reason}
            continue
        index.add_text(post_text(post))
        pending.append(post)
    _note_filters(hits, skips)
    if hits or skips:
        print(
            f"Jev cache hits: {hits}. Pre-filter skips: {sum(skips.values())} "
            f"(short {skips['short']}, language {skips['language']}, "
            f"link {skips['link']}, duplicate {skips['duplicate']})."
        )
    if pending:
        decisions.update(_classify_many(pending, batch=batch))
    return decisions


def _note_filters(hits: int, skips: Counter[str]) -> None:
    try:
        from pipeline.costs import note_jev_cache_hits, note_jev_prefilter

        if hits:
            note_jev_cache_hits(hits)
        for reason, count in skips.items():
            note_jev_prefilter(reason, count)
    except Exception as exc:
        sys.stderr.write(f"WARNING: Cost log skipped for a Jev filter count: {exc}\n")


def _store_verdicts(connection, posts: list[dict], decisions: dict[str, dict | None], now: datetime | None) -> None:
    """Persist answers Jev actually returned. Failures and pre-filter skips are not stored."""
    try:
        from pipeline.store import save_jev_verdicts

        today = _today(now)
        by_uri = {str(post.get("uri") or ""): post for post in posts}
        rows = []
        for uri, decision in decisions.items():
            if not uri or not isinstance(decision, dict):
                continue
            if decision.get("prefilter") or decision.get("cached"):
                continue
            section = decision.get("section") or None
            # A per-post claim with no section is a failed section answer, so it
            # is left uncached and can be retried. The batch path does not ask
            # for a section; null is the stored value until #90.
            if decision.get("is_claim") is True and not section and not decision.get("section_deferred"):
                continue
            if decision.get("claim_score") is None and decision.get("spam_score") is None:
                continue
            rows.append(
                (
                    uri,
                    decision.get("spam_score"),
                    decision.get("claim_score"),
                    section,
                    str(decision.get("model") or "") or _model(),
                    today,
                    text_fingerprint(post_text(by_uri.get(uri, {}))),
                )
            )
        if rows:
            save_jev_verdicts(connection, rows)
    except Exception as exc:
        sys.stderr.write(f"WARNING: Jev verdict cache was not written: {exc}\n")


def _apply_decisions(posts: list[dict], decisions: dict[str, dict | None]) -> list[dict]:
    kept: list[dict] = []
    for post in posts:
        if post.get("section"):
            kept.append(post)
            continue
        uri = str(post.get("uri") or "")
        decision = decisions.get(uri)
        if not isinstance(decision, dict) or decision.get("prefilter"):
            if decision is None:
                kept.append(post)
            continue
        updated = dict(post)
        if decision.get("spam_score") is not None:
            updated["spam_score"] = decision["spam_score"]
            if float(decision["spam_score"]) >= SPAM_THRESHOLD:
                continue
        section = str(decision.get("section") or "")
        if section:
            updated["section"] = section if section in CATEGORIES else "Other"
        if decision.get("section_confidence") is not None:
            updated["section_confidence"] = decision["section_confidence"]
        if decision.get("is_claim") is not None:
            updated["is_claim"] = bool(decision["is_claim"])
        kept.append(updated)
    return kept


def _classify_many(posts: list[dict], *, batch: bool = False) -> dict[str, dict | None]:
    if batch:
        found = _classify_batched(posts)
    else:
        workers = max(1, min(_WORKERS, len(posts)))
        found = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for post, decision in zip(posts, pool.map(_classify_post, posts)):
                found[str(post.get("uri") or "")] = decision
    answered = next((item.get("model") for item in found.values() if item and item.get("model")), "")
    if answered:
        print(f"Jev answered as {answered}.")
    return found


def per_post_body(text: str) -> dict:
    """Today's one-post request. Three questions, definitions repeated each call."""
    return {
        "state": text,
        "model": _model(),
        "questions": {
            "spam": {
                "type": "noul",
                "instructions": "Is this post promotional, a bot, engagement bait, or spam rather than a real remark?",
                "criteria": {
                    "true": SPAM_TRUE,
                    "false": SPAM_FALSE,
                },
            },
            "section": {
                "type": "choice",
                "instructions": "Which newspaper section is this post's primary subject?",
                "criteria": SECTION_CRITERIA,
            },
            "claim": {
                "type": "noul",
                "instructions": (
                    "Is this a public claim: a position on an event, policy, institution, or shared issue?"
                ),
                "criteria": {
                    "true": CLAIM_TRUE,
                    "false": CLAIM_FALSE,
                },
            },
        },
    }


def spam_claim_batch_body(texts: list[str]) -> dict:
    """Phase 3. Spam and claim for every post. No section question and no section definitions.

    The criteria text is in ``state`` once. Each post is two short questions
    that point at ``posts[i]``. The live pipeline does not use this unless
    ``jev_batch`` is on, and that setting defaults off.
    """
    questions = {}
    for index in range(len(texts)):
        questions[f"p{index}"] = {
            "type": "noul",
            "instructions": f"Is `posts[{index}]` spam, as defined by `spam_true`, rather than `spam_false`?",
            "criteria": {
                "true": "Matches `spam_true`",
                "false": "Matches `spam_false`",
            },
        }
        questions[f"c{index}"] = {
            "type": "noul",
            "instructions": (
                f"Is `posts[{index}]` a public claim, as defined by `claim_true`, rather than `claim_false`?"
            ),
            "criteria": {
                "true": "Matches `claim_true`",
                "false": "Matches `claim_false`",
            },
        }
    return {
        "state": {
            "spam_true": SPAM_TRUE,
            "spam_false": SPAM_FALSE,
            "claim_true": CLAIM_TRUE,
            "claim_false": CLAIM_FALSE,
            "posts": list(texts),
        },
        "model": _model(),
        "questions": questions,
    }


def planet_section_body(summary: str, arguments: str) -> dict:
    """One section question for a planet's summary and arguments.

    The live pipeline does not call this. #90 will, after #85. The shadow
    test is the only caller, and only when ``--planets`` is passed.
    """
    pointers = {name: f"See `sections.{name}`" for name in SECTION_CRITERIA}
    return {
        "state": {
            "summary": summary,
            "arguments": arguments,
            "sections": SECTION_CRITERIA,
        },
        "model": _model(),
        "questions": {
            "section": {
                "type": "choice",
                "instructions": (
                    "Which newspaper section in `sections` is the primary subject of this planet, "
                    "given `summary` and `arguments`?"
                ),
                "criteria": pointers,
            }
        },
    }


def parse_per_post(payload: dict) -> dict | None:
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
        confidence_value = (
            float(confidence)
            if confidence is not None
            else float((section.get("probabilities") or {}).get(choice) or 0.0)
        )
    except (TypeError, ValueError):
        confidence_value = 0.0
    claim = answers.get("claim") or {}
    try:
        claim_noul: float | None = float(claim.get("noul"))
        is_claim: bool | None = claim_noul >= CLAIM_THRESHOLD
    except (TypeError, ValueError):
        claim_noul = None
        is_claim = None
    return {
        "spam_score": spam_score,
        "claim_score": claim_noul,
        "section": choice,
        "section_confidence": confidence_value,
        "is_claim": is_claim,
        "model": str(payload.get("model") or ""),
    }


def parse_spam_claim_batch(payload: dict, count: int) -> tuple[str, list[tuple[float, float] | None]]:
    """Spam and claim nouls for each post. ``None`` is a missing half of the pair."""
    answers = payload.get("answers") if isinstance(payload, dict) else None
    model = str(payload.get("model") or "") if isinstance(payload, dict) else ""
    scores: list[tuple[float, float] | None] = []
    if not isinstance(answers, dict):
        return model, [None] * count
    for index in range(count):
        spam = answers.get(f"p{index}") or {}
        claim = answers.get(f"c{index}") or {}
        try:
            scores.append((float(spam.get("noul")), float(claim.get("noul"))))
        except (TypeError, ValueError):
            scores.append(None)
    return model, scores


def parse_planet_section(payload: dict) -> tuple[str, str, float] | None:
    """``(model, section, confidence)`` from one planet-level section call."""
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return None
    section = answers.get("section") or {}
    choice = str(section.get("choice") or "")
    if not choice:
        return None
    confidence = section.get("confidence")
    try:
        confidence_value = (
            float(confidence)
            if confidence is not None
            else float((section.get("probabilities") or {}).get(choice) or 0.0)
        )
    except (TypeError, ValueError):
        confidence_value = 0.0
    return str(payload.get("model") or ""), choice, confidence_value


def _classify_post(post: dict) -> dict | None:
    text = post_text(post)[:4000]
    if not text:
        return None
    try:
        payload = _post_systemone(per_post_body(text))
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return None
    return parse_per_post(payload)


def _classify_batched(posts: list[dict]) -> dict[str, dict | None]:
    """Phase 3. One spam question and one claim question per post. No section."""
    found: dict[str, dict | None] = {}
    chunks = [posts[start : start + BATCH_SIZE] for start in range(0, len(posts), BATCH_SIZE)]
    workers = max(1, min(_WORKERS, len(chunks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk, decisions in zip(chunks, pool.map(_classify_batch_chunk, chunks)):
            for post, decision in zip(chunk, decisions):
                found[str(post.get("uri") or "")] = decision
    return found


def _classify_batch_chunk(posts: list[dict]) -> list[dict | None]:
    texts = [post_text(post)[:4000] for post in posts]
    if any(not text for text in texts):
        return [None] * len(posts)
    try:
        payload = _post_systemone(spam_claim_batch_body(texts))
    except (RuntimeError, json.JSONDecodeError, KeyError, TypeError):
        return [None] * len(posts)
    model, scores = parse_spam_claim_batch(payload, len(posts))
    decisions: list[dict | None] = []
    for pair in scores:
        if pair is None:
            decisions.append(None)
            continue
        spam_score, claim_score = pair
        decisions.append(
            {
                "spam_score": spam_score,
                "claim_score": claim_score,
                "section": None,
                "section_confidence": None,
                "is_claim": claim_score >= CLAIM_THRESHOLD,
                "model": model or str(payload.get("model") or ""),
                "section_deferred": True,
            }
        )
    return decisions


def _post_systemone(body: dict) -> dict:
    encoded = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    delay = 0.4
    last: RuntimeError | None = None
    for attempt in range(4):
        try:
            payload = read_json(SYSTEMONE_URL, timeout=30, data=encoded, headers=headers)
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
