"""Merge same-stance faces, then look for a real second stance on a one-face planet.

The calls use whatever label model the pipeline is already using (DeepInfra
Llama when that is the configured backend). The heuristic backend makes none
of them. A second face is kept only when the other pole is at least
``stance_second_face_share`` of the stance sample, at least two posts, and
one coherent claim. Every planet is sampled at most 40 posts. The whole
planet is used when it is smaller than that cap. The whole-planet count is not what this
pass compares. The first call uses the pipeline seed. A retry uses that seed
plus one. Seed 0 draws an even spread. Any other seed draws a different
sample of the same size. A pole that clears the share but is not one claim
keeps the faces from before this pass and is marked second side not coherent.
A call that times out, returns an HTTP error, or cannot be parsed is tried
once more. If that also fails, the planet keeps those same pre-pass faces.
It is marked stance check failed and does not get the one-view note.

A split that clears that share is still kept as one face unless the model's
``second.stance`` is the pole of the posts that would move and a claim word
from ``second.title`` or ``second.summary`` shows up with the same polarity
in about 40% of those posts. Subject words and short title-topic terms such
as ICE are not claim words. A summary word is not a claim word when it is a
topic noun of the planet or the majority face: it is one of the planet's top
terms, it is in that face's title or summary, or it shows up in about 40% of
that face's posts. A word in the minority title is the claim, so it still
counts. That check is local and does not call the model.
"""

from __future__ import annotations

import inspect
import json
import math
import random
import re
import sys
import threading
from collections.abc import Callable

from pipeline.cluster_math import salient_terms
from pipeline.label import _SHORT_SUBJECTS, content_tokens, shares_claim_word, subject_stem
from pipeline.perspectives import MIN_FACE_POSTS
from pipeline.schema import TOP_TERMS_LIMIT
from pipeline.settings import (
    MAX_PROMPT_POSTS,
    STANCE_SAMPLE_LARGE_PLANET,
    STANCE_SAMPLE_LIMIT,
    STANCE_SAMPLE_LIMIT_LARGE,
    STANCE_SECOND_FACE_SHARE,
)

POLES = ("supports", "opposes")
STANCES = ("supports", "opposes", "other-angle", "off-topic")
_MIXED = "mixed remarks"
_stance_failure_lock = threading.Lock()
_stance_failures = 0
_stance_incoherent = 0


def reset_stance_check_failures() -> None:
    """This run's failed and incoherent stance checks. A live run resets before drafting."""
    global _stance_failures, _stance_incoherent
    with _stance_failure_lock:
        _stance_failures = 0
        _stance_incoherent = 0


def note_stance_check_failure() -> None:
    """One planet whose stance call timed out, errored, or could not be parsed."""
    global _stance_failures
    with _stance_failure_lock:
        _stance_failures += 1


def stance_check_failures() -> int:
    with _stance_failure_lock:
        return _stance_failures


def report_stance_check_failures() -> int:
    """Error line for this run. Quiet when every stance check finished."""
    count = stance_check_failures()
    if count:
        print(f"Stance check failed: {count} planet(s)", file=sys.stderr)
    return count


def note_stance_check_incoherent() -> None:
    """One planet whose second pole cleared the share and was not one claim."""
    global _stance_incoherent
    with _stance_failure_lock:
        _stance_incoherent += 1


def stance_check_incoherent() -> int:
    with _stance_failure_lock:
        return _stance_incoherent


def report_stance_check_incoherent() -> int:
    """Error line for this run. Quiet when no second side was rejected."""
    count = stance_check_incoherent()
    if count:
        print(f"Second side not coherent: {count} planet(s)", file=sys.stderr)
    return count


def _mark_call_failed(context: dict) -> None:
    """Count this planet once. A later call in the same pass does not add again."""
    if context.get("stance_check_failed"):
        return
    context["stance_check_failed"] = True
    note_stance_check_failure()


def _mark_incoherent(context: dict) -> None:
    """Count this planet once. A failed call is a different counter."""
    if context.get("stance_check_incoherent") or context.get("stance_check_failed"):
        return
    context["stance_check_incoherent"] = True
    note_stance_check_incoherent()


def stance_share(context: dict | None) -> float:
    """The one configured cut. Invalid values fall back to the default."""
    raw = None if context is None else context.get("stance_second_face_share")
    if raw is None:
        return STANCE_SECOND_FACE_SHARE
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return STANCE_SECOND_FACE_SHARE
    if value <= 0.0 or value > 1.0:
        return STANCE_SECOND_FACE_SHARE
    return value


def spread_indexes(count: int, limit: int) -> list[int]:
    """Evenly spaced indexes across ``0 .. count-1``, including both ends."""
    if count <= 0 or limit <= 0:
        return []
    if count <= limit:
        return list(range(count))
    if limit == 1:
        return [0]
    chosen: list[int] = []
    seen: set[int] = set()
    for step in range(limit):
        index = round(step * (count - 1) / (limit - 1))
        if index in seen:
            continue
        seen.add(index)
        chosen.append(index)
    if len(chosen) < limit:
        for index in range(count):
            if index in seen:
                continue
            seen.add(index)
            chosen.append(index)
            if len(chosen) >= limit:
                break
        chosen = sorted(chosen)[:limit]
    return chosen


def ordered_rows(rows: list[tuple]) -> list[tuple]:
    """Distance, then URI. The same order as the hand sample."""
    return sorted(rows, key=lambda row: (float(row[2]), str(row[0])))


def sample_limit(planet_posts: int) -> int:
    """At most 40 posts, including a planet of 100 or of 100,000.

    A smaller planet is labeled in full. The share is divided by this sample,
    not by every post on the planet. The old 100-post cap on large planets
    timed out under concurrency (run 39038944044).
    """
    if int(planet_posts) >= STANCE_SAMPLE_LARGE_PLANET:
        cap = STANCE_SAMPLE_LIMIT_LARGE
    else:
        cap = STANCE_SAMPLE_LIMIT
    return min(int(cap), MAX_PROMPT_POSTS)


def sample_rows(rows: list[tuple], limit: int | None = None, seed: int = 0) -> list[tuple]:
    """Distance order. Seed 0 is the even spread, including both ends.

    Any other seed draws a different sample of the same size from that order,
    and the same seed repeats it. A planet smaller than the cap is returned
    whole, so the seed does not change its membership.
    """
    ordered = ordered_rows(rows)
    cap = sample_limit(len(ordered)) if limit is None else int(limit)
    count = len(ordered)
    if count <= cap or int(seed) == 0:
        indexes = spread_indexes(count, cap)
    else:
        indexes = sorted(random.Random(int(seed)).sample(range(count), cap))
    return [ordered[index] for index in indexes]


def second_pole(counts: dict[str, int]) -> tuple[str, int]:
    """Largest supports/opposes pole that is not the plurality.

    When the plurality is other-angle or off-topic, the largest pole itself
    is the second stance. other-angle is never that pole.
    """
    tallies = {name: int(counts.get(name) or 0) for name in STANCES}
    plurality = max(STANCES, key=lambda name: (tallies[name], name == "supports", name))
    if plurality in POLES:
        other = "opposes" if plurality == "supports" else "supports"
        return other, tallies[other]
    best = max(POLES, key=lambda name: (tallies[name], name == "supports"))
    return best, tallies[best]


def clears_second_stance(counts: dict[str, int], sample_n: int, share: float) -> tuple[bool, str, int, float]:
    """True when the second pole is large enough and is at least two posts."""
    stance, found = second_pole(counts)
    ratio = (found / sample_n) if sample_n else 0.0
    kept = found >= MIN_FACE_POSTS and sample_n > 0 and ratio + 1e-12 >= share
    return kept, stance, found, ratio


def cohen_kappa(left: list[str], right: list[str], labels: tuple[str, ...] = STANCES) -> float | None:
    """Cohen's kappa for two labelers. None when there is nothing to score."""
    if len(left) != len(right) or not left:
        return None
    index = {label: pos for pos, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for one, two in zip(left, right):
        if one not in index or two not in index:
            return None
        matrix[index[one]][index[two]] += 1
    total = len(left)
    observed = sum(matrix[pos][pos] for pos in range(len(labels))) / total
    expected = 0.0
    for pos in range(len(labels)):
        row = sum(matrix[pos]) / total
        column = sum(matrix[row_index][pos] for row_index in range(len(labels))) / total
        expected += row * column
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def _json_object(text: str) -> dict | None:
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
    return data if isinstance(data, dict) else None


def _snippet(post: dict, limit: int = 180) -> str:
    text = " ".join(str(post.get("clean_text") or post.get("text") or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_merge_prompt(drafted: list, members: list[dict]) -> str:
    by_uri = {str(post.get("uri") or ""): post for post in members}
    lines = [
        "Group these faces by stance, not by wording.",
        "A stance is which side of one yes/no question the face argues.",
        "Same side with different titles is one group. Opposite sides are different groups.",
        "Facts, places, and wordings can differ and still be the same side.",
        "Example: Trump Helps Russia, Trump Putin Ties, Russia Invasion, and Russian Diesel Deal are one group when each condemns the deal or Russia.",
        "Example: Iran War and Iran Conflict are one group.",
        "Keep a face separate only when it answers the question the other way.",
        "Return JSON only: {\"groups\": [[0, 1], [2]]}",
        "Every face index appears in exactly one group.",
        "",
        "Faces:",
    ]
    for index, (perspective, rows, _size) in enumerate(drafted):
        snippets = []
        for uri, _position, _distance in ordered_rows(rows)[:2]:
            post = by_uri.get(str(uri))
            if post is None:
                continue
            snippet = _snippet(post)
            if snippet:
                snippets.append(snippet)
        shown = " | ".join(f"\"{item}\"" for item in snippets) or "(no post text)"
        lines.append(
            f"{index}. Title: {perspective.get('title') or ''}\n"
            f"   Summary: {perspective.get('summary') or ''}\n"
            f"   Posts: {shown}"
        )
    return "\n".join(lines)


def parse_merge_groups(text: str, count: int) -> list[list[int]] | None:
    data = _json_object(text)
    if not data or count <= 0:
        return None
    raw = data.get("groups")
    if not isinstance(raw, list):
        return None
    groups: list[list[int]] = []
    seen: set[int] = set()
    for group in raw:
        if not isinstance(group, list) or not group:
            return None
        indexes: list[int] = []
        for item in group:
            try:
                index = int(item)
            except (TypeError, ValueError):
                return None
            if index < 0 or index >= count or index in seen:
                return None
            seen.add(index)
            indexes.append(index)
        groups.append(indexes)
    if seen != set(range(count)):
        return None
    return groups


def build_stance_prompt(rows: list[tuple], members: list[dict], subject: str) -> str:
    chosen = list(rows)
    if len(chosen) > MAX_PROMPT_POSTS:
        # Even spread, including both ends. A prefix would hide the rest of a
        # 100K-post planet. The pipeline samples before this; the slice is the
        # backstop when a caller passes the whole membership.
        chosen = sample_rows(chosen, limit=MAX_PROMPT_POSTS)
    by_uri = {str(post.get("uri") or ""): post for post in members}
    lines = [
        "These posts are one planet that would otherwise show a single face.",
        f"Subject hint: {subject or 'the posts below'}.",
        "Decide the yes/no question they are mostly about.",
        "Label every post as supports, opposes, other-angle, or off-topic.",
        "supports means yes to that question. opposes means no.",
        "other-angle is about the subject and is not a yes or no.",
        "off-topic is a different subject.",
        "opposes is a clear no. A headline, a joke, or a different complaint is other-angle.",
        "A minority is coherent when those posts take the same side, even if the wording differs and there are only a few.",
        "Rejecting the majority claim is one claim. If you can name it in the title, coherent is true.",
        "Set coherent to false only when those posts do not agree with each other.",
        "Return JSON only, no markdown:",
        '{"question": "...", "labels": [{"i": 1, "stance": "supports"}], '
        '"second": {"stance": "opposes", "coherent": false, "title": "2-4 words", "summary": "one sentence"}}',
        "i starts at 1. Include every i from 1 through the last post. Do not skip a number.",
        "second.stance is supports or opposes, never other-angle.",
        "The title names that minority claim. Do not use Mixed remarks.",
        "",
        "Posts:",
    ]
    for number, (uri, _position, _distance) in enumerate(chosen, start=1):
        post = by_uri.get(str(uri)) or {}
        lines.append(f"{number}. {_snippet(post, limit=320)}")
    return "\n".join(lines)


def _normalize_stance(value: object) -> str | None:
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    if text in {"support", "yes", "pro"}:
        return "supports"
    if text in {"oppose", "opposes", "no", "against"}:
        return "opposes"
    if text in {"other", "other-angle", "otherangle", "mixed", "aside"}:
        return "other-angle"
    if text in {"off-topic", "offtopic", "unrelated"}:
        return "off-topic"
    if text in STANCES:
        return text
    return None


def parse_stance_response(text: str, count: int) -> dict | None:
    data = _json_object(text)
    if not data or count <= 0:
        return None
    raw_labels = data.get("labels")
    if not isinstance(raw_labels, list):
        return None
    numbered: dict[int, str] = {}
    for item in raw_labels:
        if not isinstance(item, dict):
            return None
        try:
            index = int(item.get("i"))
        except (TypeError, ValueError):
            return None
        stance = _normalize_stance(item.get("stance"))
        if stance is None:
            return None
        numbered[index] = stance
    indexes = set(numbered)
    if indexes == set(range(1, count + 1)):
        labels = [numbered[index] for index in range(1, count + 1)]
    elif indexes == set(range(count)):
        labels = [numbered[index] for index in range(count)]
    else:
        return None
    second = data.get("second") if isinstance(data.get("second"), dict) else {}
    stance = _normalize_stance(second.get("stance"))
    coherent_raw = second.get("coherent")
    if isinstance(coherent_raw, str):
        coherent = coherent_raw.strip().lower() in {"1", "true", "yes", "y"}
    else:
        coherent = bool(coherent_raw)
    title = " ".join(str(second.get("title") or "").split())[:48]
    summary = " ".join(str(second.get("summary") or "").split())[:280]
    return {
        "question": " ".join(str(data.get("question") or "").split())[:240],
        "labels": labels,
        "second_stance": stance if stance in POLES else None,
        "coherent": coherent,
        "title": title,
        "summary": summary,
    }


def _pipeline_seed(context: dict) -> int:
    """The run seed. Missing or invalid is 0, which is the even-spread sample."""
    try:
        return int(context.get("seed"))
    except (TypeError, ValueError):
        return 0


def _bump(context: dict) -> None:
    calls = context.setdefault("story_calls", {})
    calls["stance"] = int(calls.get("stance") or 0) + 1


def _accepts_seed(generate: Callable) -> bool:
    try:
        signature = inspect.signature(generate)
    except (TypeError, ValueError):
        return False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD or parameter.name == "seed":
            return True
    return False


def _invoke(generate: Callable, prompt: str, seed: int | None) -> tuple[str | None, BaseException | None]:
    """One generator call. A raised transport error is the failure, not a crash."""
    try:
        if seed is not None and _accepts_seed(generate):
            raw = generate(prompt, seed=seed)
        else:
            raw = generate(prompt)
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        return None, exc
    return raw or "", None


def explain_stance_failure(
    raw: str | None,
    error: BaseException | None,
    *,
    kind: str,
    count: int,
) -> str:
    """Why a stance reply cannot be used. The text is the reason, not a stance."""
    if error is not None:
        detail = " ".join(str(error).split())[:160]
        if isinstance(error, TimeoutError) or "timeout" in detail.lower():
            return f"timeout: {type(error).__name__}: {detail}"
        return f"HTTP error: {type(error).__name__}: {detail}"
    text = "" if raw is None else str(raw).strip()
    if not text:
        return "empty"
    lowered = text.lower()
    if lowered.startswith(("i can't", "i cannot", "sorry,", "as an ai")):
        return "refusal"
    data = _json_object(text)
    if data is None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return "unparseable: no JSON object"
        return "invalid JSON"
    if kind == "merge":
        return "schema mismatch: merge groups rejected"
    labels = data.get("labels")
    if not isinstance(labels, list):
        return "schema mismatch: labels is not a list"
    numbered: set[int] = set()
    bad_stance = False
    for item in labels:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if _normalize_stance(item.get("stance")) is None:
            bad_stance = True
        numbered.add(index)
    expected = set(range(1, count + 1))
    if numbered != expected and numbered != set(range(count)):
        covered = numbered & expected if numbered & expected else numbered
        return f"schema mismatch: labels cover {len(covered)} of {count}"
    if bad_stance:
        return "schema mismatch: a label stance is not supports, opposes, other-angle, or off-topic"
    return "schema mismatch: stance object rejected"


def _call_parsed(
    generate: Callable,
    prompt: str,
    context: dict,
    *,
    kind: str,
    count: int,
    parse: Callable[[str], object],
):
    """One call at the pipeline seed, then one retry at that seed plus one."""
    pipeline_seed = _pipeline_seed(context)
    _bump(context)
    raw, error = _invoke(generate, prompt, pipeline_seed)
    parsed = None if raw is None else parse(raw)
    if parsed is not None:
        return parsed
    first = explain_stance_failure(raw, error, kind=kind, count=count)
    _bump(context)
    retry = prompt + "\n\nThe previous reply was not usable. Return one JSON object only, no markdown."
    if kind == "sample":
        retry += f" labels must include every i from 1 to {count}."
    raw_retry, error_retry = _invoke(generate, retry, pipeline_seed + 1)
    parsed_retry = None if raw_retry is None else parse(raw_retry)
    if parsed_retry is not None:
        return parsed_retry
    second = explain_stance_failure(raw_retry, error_retry, kind=kind, count=count)
    context["stance_failure_reason"] = f"the call failed ({first}; retry: {second})"
    _mark_call_failed(context)
    return None


def _uri_key(drafted: list) -> tuple[str, ...]:
    return tuple(sorted(str(row[0]) for _perspective, rows, _size in drafted for row in rows))


def _fold(drafted: list, indexes: list[int], post_limit: int) -> tuple:
    ranked = sorted(indexes, key=lambda index: (-int(drafted[index][2]), index))
    base_perspective, base_rows, _base_size = drafted[ranked[0]]
    perspective = dict(base_perspective)
    rows = list(base_rows)
    seen_uri = {str(uri) for uri, _position, _distance in rows}
    shown = list(perspective.get("representative_posts") or [])
    seen_text = {str(post.get("text") or "") for post in shown}
    uris = [str(item) for item in (perspective.get("_face_member_uris") or [])]
    seen_member = set(uris)
    for index in ranked[1:]:
        other, other_rows, _other_size = drafted[index]
        for uri, position, distance in other_rows:
            if str(uri) in seen_uri:
                continue
            seen_uri.add(str(uri))
            rows.append((uri, position, distance))
        for post in other.get("representative_posts") or []:
            text = str(post.get("text") or "")
            if text in seen_text:
                continue
            shown.append(post)
            seen_text.add(text)
        for uri in other.get("_face_member_uris") or []:
            if str(uri) in seen_member:
                continue
            seen_member.add(str(uri))
            uris.append(str(uri))
    perspective["representative_posts"] = shown[: max(int(post_limit), 1)]
    if uris or rows:
        perspective["_face_member_uris"] = [str(uri) for uri, _position, _distance in rows]
    if perspective.get("_draft_face_label"):
        perspective["_draft_face_label"] = {
            **perspective["_draft_face_label"],
            "representative_posts": list(perspective["representative_posts"]),
        }
    return perspective, rows, len(rows)


def merge_same_stance(
    drafted: list,
    members: list[dict],
    generate: Callable[[str], str],
    context: dict,
) -> tuple[list, bool]:
    """Fold faces the model puts on the same side. False when the call fails."""
    if len(drafted) < 2:
        return drafted, False
    groups = _call_parsed(
        generate,
        build_merge_prompt(drafted, members),
        context,
        kind="merge",
        count=len(drafted),
        parse=lambda raw: parse_merge_groups(raw, len(drafted)),
    )
    if groups is None:
        return drafted, False
    post_limit = int(context.get("limit") or 36)
    merged = [_fold(drafted, group, post_limit) if len(group) > 1 else drafted[group[0]] for group in groups]
    merged.sort(key=lambda item: -int(item[2]))
    return merged, True


def _representatives(posts: list[dict], limit: int) -> list[dict]:
    ranked = sorted(posts, key=lambda post: (-int(post.get("likes") or 0), str(post.get("uri") or "")))
    chosen = []
    for post in ranked[: max(int(limit), 1)]:
        chosen.append(
            {
                "author": post.get("author") or "unknown",
                "text": post.get("clean_text") or post.get("text") or "",
                "likes": int(post.get("likes") or 0),
            }
        )
    return chosen


def _split_face(
    source: tuple,
    move_uris: set[str],
    members: list[dict],
    *,
    title: str,
    summary: str,
    post_limit: int,
) -> tuple[tuple, tuple] | None:
    perspective, rows, _size = source
    stay = [row for row in rows if str(row[0]) not in move_uris]
    move = [row for row in rows if str(row[0]) in move_uris]
    if len(move) < MIN_FACE_POSTS or not stay:
        return None
    by_uri = {str(post.get("uri") or ""): post for post in members}
    moved_posts = [by_uri[str(uri)] for uri, _position, _distance in move if str(uri) in by_uri]
    if len(moved_posts) < MIN_FACE_POSTS:
        return None
    stay_posts = [by_uri[str(uri)] for uri, _position, _distance in stay if str(uri) in by_uri]
    moved_texts = {str(post.get("text") or "") for post in _representatives(moved_posts, 10_000)}
    stay_perspective = dict(perspective)
    stay_shown = [
        post
        for post in (perspective.get("representative_posts") or [])
        if str(post.get("text") or "") not in moved_texts
    ]
    if not stay_shown and stay_posts:
        stay_shown = _representatives(stay_posts, post_limit)
    stay_perspective["representative_posts"] = stay_shown[: max(int(post_limit), 1)] or list(
        perspective.get("representative_posts") or []
    )[:1]
    stay_uris = [str(uri) for uri, _position, _distance in stay]
    stay_perspective["_face_member_uris"] = stay_uris
    if stay_perspective.get("_draft_face_label"):
        stay_perspective["_draft_face_label"] = {
            **stay_perspective["_draft_face_label"],
            "representative_posts": list(stay_perspective["representative_posts"]),
        }
    texts = [str(post.get("clean_text") or post.get("text") or "") for post in moved_posts]
    terms = salient_terms(texts, limit=TOP_TERMS_LIMIT)
    new_reps = _representatives(moved_posts, post_limit)
    new_face = {
        "title": title,
        "summary": summary or title,
        "representative_posts": new_reps,
        "stance_locked": True,
        "_face_member_uris": [str(uri) for uri, _position, _distance in move],
    }
    if terms:
        new_face["top_terms"] = terms
    new_face["_draft_face_label"] = {
        "title": title,
        "summary": new_face["summary"],
        "representative_posts": list(new_reps),
    }
    return (stay_perspective, stay, len(stay)), (new_face, move, len(move))


# Same bar as pipeline.live._coverage_needed: at least two posts, and about 40%.
_CLAIM_COVERAGE = 0.40
_SURFACE = re.compile(r"[a-z0-9]+")
_NEGATION = frozenset(
    {
        "not",
        "no",
        "never",
        "nor",
        "neither",
        "without",
        "against",
        "cannot",
        "nobody",
        "nothing",
        "nowhere",
        "isnt",
        "arent",
        "wasnt",
        "werent",
        "dont",
        "doesnt",
        "didnt",
        "cant",
        "wont",
        "shouldnt",
        "wouldnt",
        "couldnt",
        "havent",
        "hasnt",
        "hadnt",
        "aint",
    }
)
# Three-letter title words can be the claim ("war"). Function words cannot.
_SHORT_TITLE_SKIP = _NEGATION | frozenset(
    {
        "all",
        "and",
        "any",
        "are",
        "but",
        "can",
        "did",
        "for",
        "get",
        "got",
        "had",
        "has",
        "her",
        "his",
        "how",
        "its",
        "may",
        "new",
        "off",
        "old",
        "one",
        "our",
        "out",
        "own",
        "per",
        "the",
        "too",
        "two",
        "was",
        "who",
        "why",
        "you",
    }
)


def _coverage_needed(count: int) -> int:
    """At least two posts, and about 40% of the moved posts."""
    return max(2, math.ceil(_CLAIM_COVERAGE * count - 1e-9))


def _surface_tokens(text: str) -> list[str]:
    lowered = str(text or "").lower().replace("'", "").replace("’", "").replace("`", "")
    return _SURFACE.findall(lowered)


def _negated(tokens: list[str], index: int) -> bool:
    """True when a negation word sits within the three words before ``index``."""
    for token in tokens[max(0, index - 3) : index]:
        if token in _NEGATION:
            return True
    return False


def _topic_stems(subject: str, title: str) -> set[str]:
    """Subject words and short title-topic terms. ICE is a topic, not a claim."""
    stems: set[str] = set()
    for token in _surface_tokens(subject):
        if len(token) >= 2:
            stems.add(subject_stem(token))
    for token in _surface_tokens(f"{subject} {title}"):
        if token in _SHORT_SUBJECTS:
            stems.add(subject_stem(token))
            stems.add(token)
    return stems


def _mention_tokens(text: str, *, from_title: bool) -> list[tuple[int, str]]:
    """Content words, plus a three-letter title word that is not a function word."""
    tokens = _surface_tokens(text)
    allowed = content_tokens(text)
    chosen: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        if token in allowed:
            chosen.append((index, token))
            continue
        if (
            from_title
            and len(token) == 3
            and token not in _SHORT_TITLE_SKIP
            and token not in _SHORT_SUBJECTS
        ):
            chosen.append((index, token))
    return chosen


def _shared_topic_stems(
    *,
    majority_posts: list[dict] | None = None,
    majority_title: str = "",
    majority_summary: str = "",
    planet_terms: list[str] | None = None,
) -> set[str]:
    """Topic stems common to the planet or the majority face.

    A stem counts when it is one of the planet's top terms, when it is in the
    majority face's title or summary, or when it shows up in about 40% of that
    face's posts (at least two). One post is not frequent.
    """
    stems: set[str] = set()
    for term in planet_terms or []:
        for token in _surface_tokens(term):
            if len(token) >= 3:
                stems.add(subject_stem(token))
    for text in (majority_title, majority_summary):
        for token in content_tokens(text):
            stems.add(subject_stem(token))
    posts = list(majority_posts or [])
    if len(posts) >= 2:
        counts: dict[str, int] = {}
        for post in posts:
            seen: set[str] = set()
            for token in content_tokens(_post_text(post)):
                seen.add(subject_stem(token))
            for stem in seen:
                counts[stem] = counts.get(stem, 0) + 1
        need = _coverage_needed(len(posts))
        for stem, count in counts.items():
            if count >= need:
                stems.add(stem)
    return stems


def _claim_mentions(
    title: str,
    summary: str,
    subject: str,
    shared: set[str] | None = None,
) -> list[tuple[str, int]]:
    """Claim words from the title and summary, each with polarity +1 or -1.

    A subject stem and a short title-topic term are left out. A summary word
    whose stem is a shared topic noun is left out. A word in the minority
    title is the claim, so it stays. Polarity is -1 when the word is negated.
    """
    topic = _topic_stems(subject, title)
    shared_stems = shared or set()
    mentions: list[tuple[str, int]] = []
    for text, from_title in ((title, True), (summary, False)):
        tokens = _surface_tokens(text)
        for index, token in _mention_tokens(text, from_title=from_title):
            if token in _SHORT_SUBJECTS or subject_stem(token) in topic or token in topic:
                continue
            stem = subject_stem(token)
            if not from_title and stem in shared_stems:
                continue
            mentions.append((token, -1 if _negated(tokens, index) else 1))
    return mentions


def _post_text(post: dict) -> str:
    return str(post.get("clean_text") or post.get("text") or "")


def _mentions_claim(text: str, mentions: list[tuple[str, int]]) -> bool:
    tokens = _surface_tokens(text)
    for index, token in enumerate(tokens):
        polarity = -1 if _negated(tokens, index) else 1
        for claim, claim_polarity in mentions:
            if polarity != claim_polarity:
                continue
            if subject_stem(token) == subject_stem(claim) or shares_claim_word(token, claim):
                return True
    return False


def claim_words_cover(
    title: str,
    summary: str,
    posts: list[dict],
    subject: str = "",
    *,
    majority_posts: list[dict] | None = None,
    majority_title: str = "",
    majority_summary: str = "",
    planet_terms: list[str] | None = None,
) -> bool:
    """True when claim words hit about 40% of ``posts`` at the same polarity.

    A summary word that is a topic noun of the majority face or the planet
    does not count. A word in ``title`` does.
    """
    shared = _shared_topic_stems(
        majority_posts=majority_posts,
        majority_title=majority_title,
        majority_summary=majority_summary,
        planet_terms=planet_terms,
    )
    mentions = _claim_mentions(title, summary, subject, shared)
    if not mentions or len(posts) < 2:
        return False
    hits = sum(1 for post in posts if _mentions_claim(_post_text(post), mentions))
    return hits >= _coverage_needed(len(posts))


def second_claim_grounded(
    *,
    stance: str,
    second_stance: str | None,
    title: str,
    summary: str,
    posts: list[dict],
    subject: str = "",
    majority_posts: list[dict] | None = None,
    majority_title: str = "",
    majority_summary: str = "",
    planet_terms: list[str] | None = None,
) -> bool:
    """Both gates for a stance split. No model call.

    ``second.stance`` has to be the pole of ``posts``, and a claim word from
    the title or summary has to show up with the same polarity in about 40%
    of those posts. Subject terms, short title-topic terms, and topic nouns
    shared with the majority face or the planet's top terms do not count.
    """
    if second_stance not in POLES or second_stance != stance:
        return False
    return claim_words_cover(
        title,
        summary,
        posts,
        subject,
        majority_posts=majority_posts,
        majority_title=majority_title,
        majority_summary=majority_summary,
        planet_terms=planet_terms,
    )


def split_second_stance(
    drafted: list,
    members: list[dict],
    generate: Callable[[str], str],
    context: dict,
    *,
    subject: str,
    terms: list[str] | None = None,
) -> tuple[list, bool]:
    """One sample call. Split only when the share is met and the claim is in the posts."""
    if len(drafted) != 1:
        return drafted, False
    sample_seed = _pipeline_seed(context)
    rows = sample_rows(drafted[0][1], seed=sample_seed)
    if len(rows) < MIN_FACE_POSTS:
        return drafted, False
    parsed = _call_parsed(
        generate,
        build_stance_prompt(rows, members, subject),
        context,
        kind="sample",
        count=len(rows),
        parse=lambda raw: parse_stance_response(raw, len(rows)),
    )
    if parsed is None:
        return drafted, False
    counts: dict[str, int] = {name: 0 for name in STANCES}
    for label in parsed["labels"]:
        counts[label] += 1
    share = stance_share(context)
    keep, stance, found, ratio = clears_second_stance(counts, len(rows), share)
    title = parsed["title"]
    model_coherent = bool(parsed["coherent"])
    coherent = model_coherent and bool(title) and title.lower() != _MIXED
    context["stance_last"] = {
        "sample_n": len(rows),
        "planet_posts": len(drafted[0][1]),
        "sample_cap": sample_limit(len(drafted[0][1])),
        "sample_seed": sample_seed,
        "counts": counts,
        "labels": list(parsed["labels"]),
        "uris": [str(row[0]) for row in rows],
        "second": stance,
        "second_n": found,
        "share": ratio,
        "threshold": share,
        "coherent": coherent,
        "model_coherent": model_coherent,
        "title": title,
        "blocked": False,
        "split": False,
    }
    if keep and not coherent:
        context["stance_last"]["blocked"] = True
        _mark_incoherent(context)
        return drafted, True
    if not keep:
        return drafted, True
    move_uris = {
        str(row[0])
        for row, label in zip(rows, parsed["labels"])
        if label == stance
    }
    by_uri = {str(post.get("uri") or ""): post for post in members}
    moved_posts = [by_uri[uri] for uri in move_uris if uri in by_uri]
    stay_posts = [
        by_uri[str(uri)]
        for uri, _position, _distance in drafted[0][1]
        if str(uri) not in move_uris and str(uri) in by_uri
    ]
    face = drafted[0][0]
    grounded = second_claim_grounded(
        stance=stance,
        second_stance=parsed["second_stance"],
        title=title,
        summary=parsed["summary"],
        posts=moved_posts,
        subject=subject,
        majority_posts=stay_posts,
        majority_title=str(face.get("title") or ""),
        majority_summary=str(face.get("summary") or ""),
        planet_terms=list(terms) if terms is not None else _surface_tokens(subject),
    )
    context["stance_last"]["stance_aligned"] = parsed["second_stance"] == stance
    context["stance_last"]["claim_grounded"] = grounded
    if len(moved_posts) >= MIN_FACE_POSTS and not grounded:
        context["stance_last"]["blocked"] = True
        _mark_incoherent(context)
        return drafted, True
    post_limit = int(context.get("limit") or 36)
    split = _split_face(
        drafted[0],
        move_uris,
        members,
        title=title,
        summary=parsed["summary"] or title,
        post_limit=post_limit,
    )
    if split is None:
        return drafted, True
    context["stance_last"]["split"] = True
    return [split[0], split[1]], True


def apply_stance_pass(
    drafted: list,
    members: list[dict],
    context: dict,
    *,
    subject: str = "",
    terms: list[str] | None = None,
) -> tuple[list, list[str]]:
    """Same-stance merge, then a sample check only when one face would remain.

    A failed call (timeout, HTTP error, unparseable output), after one retry,
    restores the faces from before this pass and sets ``stance_check_failed``
    on the context. The heuristic backend returns immediately and does not
    call the model.
    """
    context.pop("stance_check_failed", None)
    context.pop("stance_check_incoherent", None)
    context.pop("stance_failure_reason", None)
    if context.get("chosen") == "heuristic" or len(drafted) < 1:
        return drafted, []
    generate = context.get("stance_generate") or context.get("summary_model")
    if generate is None:
        return drafted, ["Stance check skipped: no label model."]
    context.pop("stance_last", None)
    log: list[str] = []
    before = len(drafted)
    original_uris = _uri_key(drafted)
    current = drafted
    if len(current) >= 2 and not context.get("stance_check_failed"):
        merged, called = merge_same_stance(current, members, generate, context)
        if called and _uri_key(merged) == original_uris and not context.get("stance_check_failed"):
            current = merged
        elif called and _uri_key(merged) != original_uris:
            log.append(f"Stance merge kept {subject or 'planet'}: the groups would have dropped posts.")
    if len(current) == 1 and not context.get("stance_check_failed"):
        checked, called = split_second_stance(
            current, members, generate, context, subject=subject, terms=terms
        )
        if called and _uri_key(checked) == original_uris and not context.get("stance_check_failed"):
            current = checked
        elif not called and not context.get("stance_check_failed"):
            log.append(
                f"Stance check kept one face on {subject or 'planet'}: "
                f"fewer than {MIN_FACE_POSTS} posts to check."
            )
        elif called and _uri_key(checked) != original_uris:
            log.append(f"Stance check kept one face on {subject or 'planet'}: the split would have dropped posts.")
    if context.get("stance_check_failed"):
        reason = context.get("stance_failure_reason") or "the call failed"
        log.append(
            f"Stance check failed on {subject or 'planet'}: {reason}. "
            f"Pre-pass faces kept ({before})."
        )
        return drafted, log
    if context.get("stance_check_incoherent"):
        last = context.get("stance_last") or {}
        detail = ""
        if last:
            detail = (
                f" sample {last.get('second_n')}/{last.get('sample_n')}"
                f"={float(last.get('share') or 0):.1%} vs {float(last.get('threshold') or 0):.0%}"
                f", title {last.get('title')!r}"
            )
        log.append(
            f"Second side not coherent on {subject or 'planet'}:{detail}. "
            f"Pre-pass faces kept ({before})."
        )
        return drafted, log
    if _uri_key(current) != original_uris:
        return drafted, [f"Stance pass skipped on {subject or 'planet'}: post count changed."]
    last = context.get("stance_last") or {}
    detail = ""
    if last:
        detail = (
            f" sample {last.get('second_n')}/{last.get('sample_n')}"
            f"={float(last.get('share') or 0):.1%} vs {float(last.get('threshold') or 0):.0%}"
        )
    log.append(f"Stance on {subject or 'planet'}: {before} face(s) -> {len(current)}{detail}.")
    return current, log
