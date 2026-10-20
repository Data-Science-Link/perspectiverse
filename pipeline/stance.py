"""Merge same-stance faces, then look for a real second stance on a one-face planet.

The calls use whatever label model the pipeline is already using (DeepInfra
Llama when that is the configured backend). The heuristic backend makes none
of them. It still runs the local disagreement gate, which does not call a
model. A second face is kept only when the other pole is at least
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

After that, a second local check publishes two or more faces only when the
posts disagree. Same-subject faces with no disagreement fold into the larger
face and keep its title. Faces kept apart by that disagreement are
``stance_locked`` so a later title fold cannot merge them. A title whose
polarity contradicts its posts swaps a known polarity word onto the posts'
side. Appending Opposed or Supported, and replacing the summary, wait until
a majority of the posts (at least two) take that side. A denial title such
as "Not Genocidal" is left alone. A second face from the model is kept only
when this check agrees. The check does not call a model. Exact duplicate
titles are a separate finalize fold and are not handled here.
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


# Same cue lists as scripts/baseline_metrics.py. "against" is not a negator.
_CONDEMN_CUES = frozenset(
    """
    condemn condemned condemnation accuse accused accusation racist racism
    genocide genocidal kill kills killing killed murder murdered inhumane
    fascist fascism despise despised abuse abused cruel cruelty appalled
    barbaric repugnant cowardly oppose opposed opposition reject rejected
    hate hated hatred threat threats poorly illegal illegally propaganda
    harm harms harmful flawed terrorism terrorist disproportionate violence
    violent horrific horror sick wrong idiot idiots moron moronic pedophile
    pedophiles piss liar lies lying corrupt corruption ashamed garbage stupid
    evil criminal criminals apartheid
    """.split()
)
_ENDORSE_CUES = frozenset(
    """
    support supports supported supporters supporting defend defends defending
    deserve deserves deserved success successful worth protect protection
    protecting boost effective favor favour endorse endorsed
    """.split()
)
_NEGATION_CUES = frozenset(
    "not no never nor neither without cannot dont doesnt didnt cant wont".split()
)
_SUBJECT_GLUE = frozenset(
    """
    about argue been being claim from have many most other people post posts
    should some that their there these they this those which with would
    various individual reason indicate current also just really into over
    than then discuss comment remark preference share update
    """.split()
)
_TITLE_STOP = frozenset(
    """
    the and for has was are not its but you his her our who how why can may
    did had any all one two per via
    """.split()
)
_WORD_RE = re.compile(r"[a-z0-9']+")
_UP_WORDS = frozenset(
    "rising rise rises risen high higher increase increased increasing".split()
)
_DOWN_WORDS = frozenset(
    "decrease decreased decreasing lower lowered lowering falling fall down".split()
)
_ATTACK_WORDS = frozenset(
    "attack attacks attacking strike strikes sank sink sinking kill kills killed bomb bombed missile ship ships".split()
)
_ANTIWAR_WORDS = frozenset("unnecessary oppose opposed opposition wrong".split())
# Enjoyment versus a quality complaint is a different claim, even on one show.
_VALENCE_STEMS = frozenset(
    "enjoy love excit loved loves loving enjoyed enjoys excited exciting excitement".split()
)
# A protest thread and a language joke share a nationality word and still differ.
_TOPIC_FAMILIES = (
    frozenset({"protest", "riot"}),
    frozenset({"languag", "translation", "misunderstood"}),
)
_POLE_SHARE = 0.15
# Appending a side word, or replacing the summary, needs a majority. The 15%
# pole is enough to swap a polarity word the title already uses.
_STRONG_POLE_SHARE = 0.5


def _lex_tokens(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _near_stem(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) < 4 or len(right) < 4:
        return False
    return left.startswith(right) or right.startswith(left)


def _share_stems(left: set[str], right: set[str]) -> set[str]:
    shared: set[str] = set()
    for item in left:
        for other in right:
            if _near_stem(item, other):
                shared.add(item)
                shared.add(other)
    return shared


def _content_stems(text: str) -> set[str]:
    stems: set[str] = set()
    for token in content_tokens(text or ""):
        if token in _SUBJECT_GLUE:
            continue
        stem = subject_stem(token)
        if len(stem) < 4 or stem in _SUBJECT_GLUE:
            continue
        stems.add(stem)
    return stems


def _title_stems(title: str) -> set[str]:
    stems = _content_stems(title)
    for token in _lex_tokens(title):
        if token in _TITLE_STOP:
            continue
        stem = subject_stem(token)
        # "ice" would otherwise strip to "ic" and disappear. Keep the short token.
        if len(stem) < 3:
            stem = token
        if len(token) == 3 and len(stem) >= 3 and stem not in _SUBJECT_GLUE:
            stems.add(stem)
        elif 3 <= len(stem) < 4 and stem not in _SUBJECT_GLUE:
            stems.add(stem)
    return stems


def _cue_pole(text: str) -> int:
    """-1 condemn, +1 endorse, 0 when the cues do not pick a side."""
    tokens = _lex_tokens(text)
    condemn = 0
    endorse = 0
    for index, token in enumerate(tokens):
        negated = any(word in _NEGATION_CUES for word in tokens[max(0, index - 3) : index])
        if token in _CONDEMN_CUES:
            if negated:
                endorse += 1
            else:
                condemn += 1
        elif token in _ENDORSE_CUES:
            if negated:
                condemn += 1
            else:
                endorse += 1
    if condemn > endorse and condemn >= 1:
        return -1
    if endorse > condemn and endorse >= 1:
        return 1
    return 0


def _claim_blob(face: dict) -> str:
    parts = [str(face.get("title") or ""), str(face.get("summary") or "")]
    for item in face.get("arguments") or []:
        parts.append(str(item))
    return " ".join(parts)


def _posts_pole(posts: list[dict]) -> int:
    """The posts' side when at least two of them take it and they are not stray cues."""
    if not posts:
        return 0
    signs = [_cue_pole(str(post.get("clean_text") or post.get("text") or "")) for post in posts]
    negative = sum(1 for sign in signs if sign < 0)
    positive = sum(1 for sign in signs if sign > 0)
    count = len(posts)

    def holds(found: int, other: int) -> bool:
        if found < 2 or found <= other:
            return False
        if found / count >= _POLE_SHARE:
            return True
        return count <= 6 and other == 0

    if holds(negative, positive):
        return -1
    if holds(positive, negative):
        return 1
    return 0


def _posts_pole_strong(posts: list[dict]) -> int:
    """The posts' side when at least two of them are a majority, not a 15% trace."""
    if not posts:
        return 0
    signs = [_cue_pole(str(post.get("clean_text") or post.get("text") or "")) for post in posts]
    negative = sum(1 for sign in signs if sign < 0)
    positive = sum(1 for sign in signs if sign > 0)
    count = len(posts)

    def holds(found: int, other: int) -> bool:
        return found >= 2 and found > other and found / count >= _STRONG_POLE_SHARE

    if holds(negative, positive):
        return -1
    if holds(positive, negative):
        return 1
    return 0


def _title_is_denial(title: str) -> bool:
    """True when every polarity cue in the title is negated, as in 'Not Genocidal'."""
    tokens = _lex_tokens(title)
    cues = 0
    negated_cues = 0
    for index, token in enumerate(tokens):
        if token not in _CONDEMN_CUES and token not in _ENDORSE_CUES:
            continue
        cues += 1
        window = tokens[max(0, index - 3) : index]
        if any(word in _NEGATION_CUES or word in {"stop", "anti"} for word in window):
            negated_cues += 1
    return cues > 0 and negated_cues == cues


def _title_denies(title: str, other: str) -> bool:
    left = _lex_tokens(title)
    right = [word for word in _lex_tokens(other) if len(word) >= 3]
    negators = _NEGATION_CUES | {"stop", "anti"}
    for index, word in enumerate(left):
        if len(word) < 3 or word in negators:
            continue
        window = left[max(0, index - 3) : index]
        if not any(item in negators for item in window):
            continue
        if any(_near_stem(subject_stem(word), subject_stem(other_word)) for other_word in right):
            return True
    return False


def _posts_affirm(posts: list[dict], word: str) -> bool:
    """True when the posts state the word unnegated often enough to mean the claim."""
    if not posts or len(word) < 3:
        return False
    hits = 0
    for post in posts:
        tokens = _lex_tokens(str(post.get("clean_text") or post.get("text") or ""))
        for index, token in enumerate(tokens):
            if not _near_stem(subject_stem(token), subject_stem(word)):
                continue
            if any(item in _NEGATION_CUES for item in tokens[max(0, index - 3) : index]):
                continue
            hits += 1
            break
    if len(posts) == 1:
        return hits >= 1
    needed = max(2, (len(posts) * 40 + 99) // 100)
    return hits >= needed


def _denial_conflict(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    """One title negates a claim the other affirms, and the posts do not affirm it."""
    if _title_denies(str(left.get("title") or ""), str(right.get("title") or "")):
        denied = [word for word in _lex_tokens(str(right.get("title") or "")) if len(word) >= 4]
        if denied and not any(_posts_affirm(left_posts, word) for word in denied):
            return True
    if _title_denies(str(right.get("title") or ""), str(left.get("title") or "")):
        denied = [word for word in _lex_tokens(str(left.get("title") or "")) if len(word) >= 4]
        if denied and not any(_posts_affirm(right_posts, word) for word in denied):
            return True
    return False


def _plain_direction(text: str, vocab: frozenset[str]) -> bool:
    tokens = _lex_tokens(text)
    for index, token in enumerate(tokens):
        if token in vocab and not any(word in _NEGATION_CUES for word in tokens[max(0, index - 3) : index]):
            return True
    lowered = (text or "").lower()
    if "down" in vocab and ("coming way down" in lowered or "way down" in lowered):
        return True
    return False


def _negates_price_effect(text: str) -> bool:
    """'prices will not come down' / 'not about relief' denies a price effect."""
    effects = _DOWN_WORDS | {"relief"}
    for sentence in re.split(r"[.!?]", text or ""):
        tokens = _lex_tokens(sentence)
        for index, token in enumerate(tokens):
            if token not in effects:
                continue
            if any(word in _NEGATION_CUES for word in tokens[:index]):
                return True
    return False


def _direction_conflict(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    """Rising versus falling, including a negated effect such as 'will not come down'."""
    left_blob = f"{left.get('title') or ''} {left.get('summary') or ''}"
    right_blob = f"{right.get('title') or ''} {right.get('summary') or ''}"
    left_posts_blob = " ".join(str(post.get("text") or "") for post in left_posts)
    right_posts_blob = " ".join(str(post.get("text") or "") for post in right_posts)
    left_up = _plain_direction(left_blob, _UP_WORDS)
    right_up = _plain_direction(right_blob, _UP_WORDS)
    left_down = _plain_direction(left_blob, _DOWN_WORDS) or _negates_price_effect(left_blob) or _negates_price_effect(left_posts_blob)
    right_down = _plain_direction(right_blob, _DOWN_WORDS) or _negates_price_effect(right_blob) or _negates_price_effect(right_posts_blob)
    return (left_up and right_down and not left_down and not right_up) or (
        right_up and left_down and not right_down and not left_up
    )


def _is_attack_report(face: dict) -> bool:
    blob = f"{face.get('title') or ''} {face.get('summary') or ''}"
    return any(token in _ATTACK_WORDS for token in _lex_tokens(blob))


def _is_antiwar(face: dict) -> bool:
    blob = f"{face.get('title') or ''} {face.get('summary') or ''}".lower()
    if "anti war" in blob or "anti-war" in blob:
        return True
    return any(token in _ANTIWAR_WORDS for token in _lex_tokens(blob))


def _attack_versus_antiwar(left: dict, right: dict) -> bool:
    """Attack headlines stay apart from a face that calls the war unnecessary."""
    left_attack = _is_attack_report(left) and not _is_antiwar(left)
    right_attack = _is_attack_report(right) and not _is_antiwar(right)
    return (left_attack and _is_antiwar(right)) or (right_attack and _is_antiwar(left))


def local_faces_disagree(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    """True when the pair is a real opposition and both faces should stay."""
    if _denial_conflict(left, right, left_posts, right_posts):
        return True
    left_posts_pole = _posts_pole(left_posts)
    right_posts_pole = _posts_pole(right_posts)
    if left_posts_pole and right_posts_pole and left_posts_pole == -right_posts_pole:
        return True
    left_claim = _cue_pole(_claim_blob(left))
    right_claim = _cue_pole(_claim_blob(right))
    if left_claim and right_claim and left_claim == -right_claim:
        return True
    if _direction_conflict(left, right, left_posts, right_posts):
        return True
    if _attack_versus_antiwar(left, right):
        return True
    return False


def _stem_counts(posts: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for post in posts:
        seen: set[str] = set()
        for stem in _content_stems(str(post.get("clean_text") or post.get("text") or "")):
            seen.add(stem)
        for stem in seen:
            counts[stem] = counts.get(stem, 0) + 1
    return counts


def _greeting_count(posts: list[dict]) -> int:
    count = 0
    pattern = re.compile(r"\bgood (morning|evening|night|day)\b|\bhappy\b")
    for post in posts:
        if pattern.search(str(post.get("clean_text") or post.get("text") or "").lower()):
            count += 1
    return count


def _family_hits(face: dict, posts: list[dict], family: frozenset[str]) -> bool:
    summary = _content_stems(str(face.get("summary") or "")) | _content_stems(str(face.get("title") or ""))
    if any(any(_near_stem(stem, item) for item in family) for stem in summary):
        return True
    counts = _stem_counts(posts)
    for stem, found in counts.items():
        if found < 2:
            continue
        if any(_near_stem(stem, item) for item in family):
            return True
    return False


def _different_family(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    for family in _TOPIC_FAMILIES:
        left_hit = _family_hits(left, left_posts, family)
        right_hit = _family_hits(right, right_posts, family)
        if left_hit == right_hit:
            continue
        other_families = [item for item in _TOPIC_FAMILIES if item is not family]
        other_left = any(_family_hits(left, left_posts, item) for item in other_families)
        other_right = any(_family_hits(right, right_posts, item) for item in other_families)
        if (left_hit and other_right) or (right_hit and other_left):
            return True
    return False


def _evidenced(count: int, total: int) -> bool:
    if total <= 0 or count <= 0:
        return False
    if total <= 4:
        return count / total >= 0.5
    return count >= 2 and count / total >= 0.5


def _exclusive_blocks(
    left: dict,
    right: dict,
    left_posts: list[dict],
    right_posts: list[dict],
    shared: set[str],
) -> bool:
    """A rival subject on one face, unless both faces take the same claim pole."""
    if _cue_pole(_claim_blob(left)) and _cue_pole(_claim_blob(left)) == _cue_pole(_claim_blob(right)):
        return False
    left_counts = _stem_counts(left_posts)
    right_counts = _stem_counts(right_posts)
    left_claim = _title_stems(str(left.get("title") or "")) | _content_stems(str(left.get("summary") or ""))
    right_claim = _title_stems(str(right.get("title") or "")) | _content_stems(str(right.get("summary") or ""))

    def blocks(claim: set[str], own: dict[str, int], other: dict[str, int], own_posts: list[dict]) -> bool:
        total = max(len(own_posts), 1)
        shared_counts = [
            found for stem, found in own.items() if any(_near_stem(stem, item) for item in shared)
        ]
        for stem in claim:
            if any(_near_stem(stem, item) for item in shared):
                continue
            found = max((count for key, count in own.items() if _near_stem(stem, key)), default=0)
            other_found = any(_near_stem(stem, key) and count > 0 for key, count in other.items())
            valence = stem in _VALENCE_STEMS or any(_near_stem(stem, item) for item in _VALENCE_STEMS)
            if valence and found >= 2 and not other_found:
                return True
            if other_found or not _evidenced(found, total):
                continue
            # A name that outranks the shared subject is a different story (SpaceX vs the car).
            if shared_counts and found > max(shared_counts):
                return True
            if not shared and found >= 2:
                return True
        return False

    return blocks(left_claim, left_counts, right_counts, left_posts) or blocks(
        right_claim, right_counts, left_counts, right_posts
    )


def _both_titles_have_their_own_claim(
    left_title: set[str],
    right_title: set[str],
    left_posts: list[dict],
    right_posts: list[dict],
) -> bool:
    """Each title has a stem the other face's posts never say."""

    def owns(stems: set[str], own_posts: list[dict], other_posts: list[dict]) -> bool:
        own = _stem_counts(own_posts)
        other = _stem_counts(other_posts)
        total = max(len(own_posts), 1)
        for stem in stems:
            found = max((count for key, count in own.items() if _near_stem(stem, key)), default=0)
            if not _evidenced(found, total):
                continue
            if any(_near_stem(stem, key) and count > 0 for key, count in other.items()):
                continue
            return True
        return False

    return owns(left_title, left_posts, right_posts) and owns(right_title, right_posts, left_posts)


def local_faces_same_subject(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    """True when the faces are one thread rather than two subjects."""
    if _different_family(left, right, left_posts, right_posts):
        return False
    left_title = _title_stems(str(left.get("title") or ""))
    right_title = _title_stems(str(right.get("title") or ""))
    left_summary = _content_stems(str(left.get("summary") or ""))
    right_summary = _content_stems(str(right.get("summary") or ""))
    shared_titles = _share_stems(left_title, right_title)
    # Titles that name two claims, and each claim shows up in that face's posts
    # and not the other's, are different subjects even when a summary noun overlaps.
    if not shared_titles and _both_titles_have_their_own_claim(left_title, right_title, left_posts, right_posts):
        return False
    shared = shared_titles | _share_stems(left_summary, right_summary)
    left_greet = _greeting_count(left_posts)
    right_greet = _greeting_count(right_posts)
    greetings = bool(left_posts and right_posts) and (
        (left_greet / len(left_posts) >= 0.5 and right_greet >= 2)
        or (right_greet / len(right_posts) >= 0.5 and left_greet >= 2)
    )
    post_shared = False
    if left_posts and right_posts:
        left_counts = _stem_counts(left_posts)
        right_counts = _stem_counts(right_posts)
        claim = left_title | right_title | left_summary | right_summary
        for stem, found in left_counts.items():
            if found / len(left_posts) < 0.5 or right_counts.get(stem, 0) / len(right_posts) < 0.5:
                continue
            if any(_near_stem(stem, item) for item in claim):
                post_shared = True
                shared |= {stem}
                break
    if not shared and not greetings and not post_shared:
        return False
    if _exclusive_blocks(left, right, left_posts, right_posts, shared):
        return False
    return bool(shared or greetings or post_shared)


def local_faces_fold(left: dict, right: dict, left_posts: list[dict], right_posts: list[dict]) -> bool:
    """Fold when they share a subject and none of the disagreement signals fire."""
    if local_faces_disagree(left, right, left_posts, right_posts):
        return False
    return local_faces_same_subject(left, right, left_posts, right_posts)


def _swap_polarity_word(word: str, table: dict[str, str]) -> str | None:
    replacement = table.get(word.lower())
    if not replacement:
        return None
    if word[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement.lower()


def align_contradicting_title(face: dict, posts: list[dict]) -> bool:
    """Rewrite a title that takes the opposite side from its posts. Denial titles stay.

    A known polarity token is swapped when the posts take a side. Appending
    Opposed or Supported, and generating a summary, wait for a majority.
    """
    title = " ".join(str(face.get("title") or "").split())
    if not title or _title_is_denial(title):
        return False
    title_pole = _cue_pole(title)
    posts_pole = _posts_pole(posts)
    if not title_pole or not posts_pole or title_pole == posts_pole:
        return False
    strong = _posts_pole_strong(posts) == posts_pole
    table = {
        "support": "Opposed",
        "supports": "Opposed",
        "supported": "Opposed",
        "supporters": "Opponents",
        "supporting": "Opposing",
        "defend": "Condemn",
        "defends": "Condemns",
        "defending": "Condemning",
        "pro": "Anti",
    }
    if posts_pole > 0:
        table = {
            "oppose": "Support",
            "opposes": "Support",
            "opposed": "Supported",
            "condemn": "Defend",
            "condemns": "Defends",
            "condemned": "Defended",
            "anti": "Pro",
        }
    words = title.split()
    rewritten = []
    swapped = False
    for word in words:
        replacement = _swap_polarity_word(word, table)
        if replacement is None:
            rewritten.append(word)
            continue
        rewritten.append(replacement)
        swapped = True
    if not swapped:
        if not strong:
            return False
        rewritten.append("Opposed" if posts_pole < 0 else "Supported")
    face["title"] = " ".join(rewritten)
    summary = " ".join(str(face.get("summary") or "").split())
    if strong and summary and _cue_pole(summary) == title_pole:
        subject = " ".join(word for word in words if _swap_polarity_word(word, table) is None) or face["title"]
        side = "oppose" if posts_pole < 0 else "support"
        face["summary"] = f"These posts {side} {subject}."
    if face.get("_draft_face_label"):
        face["_draft_face_label"] = {
            **face["_draft_face_label"],
            "title": face["title"],
            "summary": face.get("summary") or "",
        }
    return True


def _cluster_faces(count: int, fold, disagree) -> list[list[int]]:
    """Join faces that share a subject. A disagreement anywhere in the pair blocks the join."""
    groups = [[index] for index in range(count)]
    changed = True
    while changed:
        changed = False
        left = 0
        while left < len(groups):
            right = left + 1
            while right < len(groups):
                pairs = [(a, b) for a in groups[left] for b in groups[right]]
                if any(disagree(a, b) for a, b in pairs):
                    right += 1
                    continue
                if not any(fold(a, b) for a, b in pairs):
                    right += 1
                    continue
                groups[left].extend(groups[right])
                groups.pop(right)
                changed = True
                break
            if changed:
                break
            left += 1
    return groups


def _groups_kept_by_disagreement(groups: list[list[int]], disagree) -> set[int]:
    """Group indexes that stay apart because a pair across them disagrees."""
    home: dict[int, int] = {}
    for group_index, indexes in enumerate(groups):
        for index in indexes:
            home[index] = group_index
    count = len(home)
    locked: set[int] = set()
    for left in range(count):
        for right in range(left + 1, count):
            if home[left] == home[right]:
                continue
            if disagree(left, right):
                locked.add(home[left])
                locked.add(home[right])
    return locked


def _lock_prepass_disagreements(drafted: list, members: list[dict]) -> None:
    """Lock faces a failed call hands back when the posts already disagree.

    Finalize still title-merges whatever this pass returns. The local gate
    did not run, so the lock has to be stamped on these faces directly.
    """
    if len(drafted) < 2:
        return
    post_sets = [_posts_for_draft(item[0], item[1], members) for item in drafted]
    for left in range(len(drafted)):
        for right in range(left + 1, len(drafted)):
            if not local_faces_disagree(
                drafted[left][0], drafted[right][0], post_sets[left], post_sets[right]
            ):
                continue
            drafted[left][0]["stance_locked"] = True
            drafted[right][0]["stance_locked"] = True


def _posts_for_draft(perspective: dict, rows: list, members: list[dict]) -> list[dict]:
    by_uri = {str(post.get("uri") or ""): post for post in members}
    posts = []
    for uri, _position, _distance in rows:
        post = by_uri.get(str(uri))
        if post is not None:
            posts.append(post)
    if posts:
        return posts
    return list(perspective.get("representative_posts") or [])


def apply_local_stance_gate(
    drafted: list,
    members: list[dict],
    *,
    subject: str = "",
    post_limit: int = 36,
) -> list:
    """Fold same-subject faces that do not disagree, then align contradicting titles.

    ``subject`` is the planet name, kept for callers. The check does not use it
    as a cue and does not call a model.
    """
    del subject
    if len(drafted) < 1:
        return drafted
    post_sets = [_posts_for_draft(item[0], item[1], members) for item in drafted]

    def fold(left: int, right: int) -> bool:
        return local_faces_fold(drafted[left][0], drafted[right][0], post_sets[left], post_sets[right])

    def disagree(left: int, right: int) -> bool:
        return local_faces_disagree(drafted[left][0], drafted[right][0], post_sets[left], post_sets[right])

    if len(drafted) == 1:
        tagged = [(drafted[0], False)]
    else:
        clusters = _cluster_faces(len(drafted), fold, disagree)
        locked_groups = _groups_kept_by_disagreement(clusters, disagree)
        tagged = []
        for group_index, indexes in enumerate(clusters):
            lock = group_index in locked_groups
            if len(indexes) == 1:
                tagged.append((drafted[indexes[0]], lock))
                continue
            folded = _fold(drafted, indexes, post_limit)
            if not lock:
                perspective, rows, size = folded
                perspective = dict(perspective)
                perspective.pop("stance_locked", None)
                folded = (perspective, rows, size)
            tagged.append((folded, lock))
        tagged.sort(key=lambda item: -int(item[0][2]))
    aligned = []
    for (perspective, rows, size), lock in tagged:
        face = dict(perspective)
        if lock:
            # Finalize merges alike titles and skips a locked face. A face kept
            # because the posts disagree has to carry that lock or the merge
            # puts the opposition back together.
            face["stance_locked"] = True
        align_contradicting_title(face, _posts_for_draft(face, rows, members))
        aligned.append((face, rows, size))
    return aligned


def gate_published_perspectives(faces: list[dict], *, post_limit: int = 36) -> list[dict]:
    """The same local gate on a published planet. Uses representative posts and post counts."""
    if len(faces) < 1:
        return [dict(face) for face in faces]
    copied = [dict(face) for face in faces]
    post_sets = [list(face.get("representative_posts") or []) for face in copied]

    def fold(left: int, right: int) -> bool:
        return local_faces_fold(copied[left], copied[right], post_sets[left], post_sets[right])

    def disagree(left: int, right: int) -> bool:
        return local_faces_disagree(copied[left], copied[right], post_sets[left], post_sets[right])

    grouped: list[dict] = []
    if len(copied) == 1:
        grouped = copied
    else:
        clusters = _cluster_faces(len(copied), fold, disagree)
        locked_groups = _groups_kept_by_disagreement(clusters, disagree)
        for group_index, indexes in enumerate(clusters):
            ranked = sorted(indexes, key=lambda index: (-int(copied[index].get("post_count") or 0), index))
            base = dict(copied[ranked[0]])
            posts = list(base.get("representative_posts") or [])
            seen = {str(post.get("text") or "") for post in posts}
            total = int(base.get("post_count") or 0)
            for index in ranked[1:]:
                other = copied[index]
                total += int(other.get("post_count") or 0)
                for post in other.get("representative_posts") or []:
                    text = str(post.get("text") or "")
                    if text in seen:
                        continue
                    posts.append(post)
                    seen.add(text)
            base["representative_posts"] = posts[: max(int(post_limit), 1)]
            base["post_count"] = total
            if group_index in locked_groups:
                base["stance_locked"] = True
            elif len(indexes) > 1:
                base.pop("stance_locked", None)
            grouped.append(base)
    for face in grouped:
        align_contradicting_title(face, list(face.get("representative_posts") or []))
    counts = [max(int(face.get("post_count") or 0), 0) for face in grouped]
    if sum(counts) > 0 and len(grouped) > 1:
        from pipeline.schema import to_percents

        for face, volume in zip(grouped, to_percents(counts)):
            face["volume_percent"] = volume
    elif len(grouped) == 1:
        grouped[0]["volume_percent"] = 100.0
    return grouped


def _gate_signature(drafted: list) -> list[tuple[str, int]]:
    return [(str(item[0].get("title") or ""), int(item[2])) for item in drafted]


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
    on the context. The heuristic backend does not call the model. It still
    runs the local gate.
    """
    context.pop("stance_check_failed", None)
    context.pop("stance_check_incoherent", None)
    context.pop("stance_failure_reason", None)
    if len(drafted) < 1:
        return drafted, []
    if context.get("chosen") == "heuristic":
        gated = apply_local_stance_gate(
            drafted, members, subject=subject, post_limit=int(context.get("limit") or 36)
        )
        return gated, []
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
        _lock_prepass_disagreements(drafted, members)
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
        gated = apply_local_stance_gate(drafted, members, subject=subject, post_limit=int(context.get("limit") or 36))
        if _gate_signature(gated) == _gate_signature(drafted):
            for original, updated in zip(drafted, gated):
                if updated[0].get("stance_locked"):
                    original[0]["stance_locked"] = True
            log.append(
                f"Second side not coherent on {subject or 'planet'}:{detail}. "
                f"Pre-pass faces kept ({before})."
            )
            return drafted, log
        log.append(
            f"Second side not coherent on {subject or 'planet'}:{detail}. "
            f"Local gate kept {len(gated)} face(s); the geometric split did not come back on its own."
        )
        return gated, log
    current = apply_local_stance_gate(
        current, members, subject=subject, post_limit=int(context.get("limit") or 36)
    )
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
