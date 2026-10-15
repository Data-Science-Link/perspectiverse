"""Merge same-stance faces, then look for a real second stance on a one-face planet.

The calls use whatever label model the pipeline is already using (DeepInfra
Llama when that is the configured backend). The heuristic backend makes none
of them. A second face is kept only when the other pole is at least
``stance_second_face_share`` of the stance sample, at least two posts, and
one coherent claim. A planet under 100 posts is sampled at most 40 posts.
A planet of 100 or more is sampled at most 100. The whole planet is used
when it is smaller than that cap. The whole-planet count is not what this
pass compares. The first call uses the pipeline seed. A retry uses that seed
plus one. Seed 0 draws an even spread. Any other seed draws a different
sample of the same size. A pole that clears the share but is not one claim
keeps the faces from before this pass and is marked second side not coherent.
A call that times out, returns an HTTP error, or cannot be parsed is tried
once more. If that also fails, the planet keeps those same pre-pass faces.
It is marked stance check failed and does not get the one-view note.

A split that clears that share is still kept as one face unless the model's
``second.stance`` is the pole of the posts that would move and the posts
support that claim. Support is the 40% claim-word check, and, when the posts
do not repeat the title word, a local fallback: the title denies a stem the
majority title affirms and the posts do not affirm it, or a negated effect
in the summary is backed by a paraphrase in enough of the posts. Subject
words and short title-topic terms such as ICE are not claim words. A summary
word is not a claim word when it is a topic noun of the planet or the
majority face. A word in the minority title is the claim, so it still counts
for the 40% check. The fallback does not call the model and does not lower
the share bar.

Two faces that make the same claim are folded even when the model leaves
them in separate groups. A face whose title denies the other title stays
apart, so a real opposing side is not folded away. A title whose pole
contradicts its posts is rewritten locally. Yemen's attack reports and its
anti-war posts do not share that claim, so they are not folded.
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
from scripts.baseline_metrics import CONDEMN_CUES, ENDORSE_CUES, NEGATION_CUES, _cue_polarity
from pipeline.perspectives import MIN_FACE_POSTS
from pipeline.schema import TOP_TERMS_LIMIT
from pipeline.settings import (
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
    """40 posts when the planet has fewer than 100. 100 once it reaches 100.

    A smaller planet is labeled in full. The share is divided by this sample,
    not by every post on the planet.
    """
    if int(planet_posts) >= STANCE_SAMPLE_LARGE_PLANET:
        return STANCE_SAMPLE_LIMIT_LARGE
    return STANCE_SAMPLE_LIMIT


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
    for number, (uri, _position, _distance) in enumerate(rows, start=1):
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
    *,
    subject: str = "",
) -> tuple[list, bool]:
    """Fold faces the model puts on the same side. False when the call fails.

    A face whose title denies the other title is kept apart. Faces the model
    left in separate groups are still folded when they make the same claim.
    """
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
    parted: list[list[int]] = []
    for group in groups:
        parted.extend(_partition_deniers(drafted, group, subject))
    parted = _collapse_same_claim(drafted, parted, members, subject)
    post_limit = int(context.get("limit") or 36)
    merged = [_fold(drafted, group, post_limit) if len(group) > 1 else drafted[group[0]] for group in parted]
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


# Words that show up in every drafted summary or post and are not a claim.
_CLAIM_GLUE = frozenset(
    {
        "about",
        "argue",
        "been",
        "claim",
        "from",
        "have",
        "many",
        "most",
        "other",
        "people",
        "posts",
        "should",
        "some",
        "that",
        "their",
        "there",
        "these",
        "they",
        "this",
        "those",
        "which",
        "with",
        "would",
    }
)
# "stop" and "anti" deny the next claim. They are not general negators.
_TITLE_NEGATORS = _NEGATION | frozenset({"stop", "anti"})
# Negated summary words that are not a claim. "argue" and "various" are glue.
_EFFECT_GLUE = _CLAIM_GLUE | frozenset(
    {
        "citing",
        "could",
        "perspectives",
        "reasons",
        "various",
    }
)
_MINIMIZERS = frozenset(
    {
        "barely",
        "difference",
        "enough",
        "hardly",
        "less",
        "little",
        "marginal",
        "material",
        "minimal",
        "negligible",
        "slight",
        "slightly",
    }
)
_DENIAL_EFFECTS = ("lower", "relief", "reduce", "reduction", "help", "difference")
_EFFECT_DENIAL = re.compile(
    r"\b(?:won'?t|will not|not going to|no material|cannot|can'?t)\b"
    r".{0,60}\b(?:difference|lower\w*|relief|reduc\w*|help)\b"
    r"|\b(?:not|never|no)\s+lower\w*"
    r"|\bnegat\w*\b.{0,50}\b(?:reduc\w*|relief|cost|price\w*|difference)\b"
    r"|\bless than\b.{0,24}(?:\d|percent|price|cost|gallon)",
    re.IGNORECASE,
)


def _adjective_stem(word: str) -> str:
    """Fold genocidal onto genocide. Other stems stay as they are."""
    stem = subject_stem(word)
    if stem.endswith("al") and len(stem) - 2 >= 5:
        stem = stem[:-2].rstrip("e")
    return stem


def _claim_match(token: str, claim: str) -> bool:
    if subject_stem(token) == subject_stem(claim) or shares_claim_word(token, claim):
        return True
    return _adjective_stem(token) == _adjective_stem(claim)


def _member_posts(item: tuple, members: list[dict]) -> list[dict]:
    by_uri = {str(post.get("uri") or ""): post for post in members}
    _perspective, rows, _size = item
    return [by_uri[str(uri)] for uri, _position, _distance in rows if str(uri) in by_uri]


def _title_denies_title(title: str, other_title: str) -> bool:
    """True when ``title`` negates a word that ``other_title`` affirms."""
    title_tokens = _surface_tokens(title)
    other_tokens = [token for token in _surface_tokens(other_title) if len(token) >= 3]
    if not other_tokens:
        return False
    for index, token in enumerate(title_tokens):
        if len(token) < 3 or token in _TITLE_NEGATORS:
            continue
        window = title_tokens[max(0, index - 3) : index]
        if not any(word in _TITLE_NEGATORS for word in window):
            continue
        if any(_claim_match(token, other) for other in other_tokens):
            return True
    return False


def _claim_stems(title: str, summary: str, subject: str) -> set[str]:
    """Distinctive claim stems. The planet subject and glue words are left out."""
    topic = _topic_stems(subject, "")
    stems: set[str] = set()
    for token in _surface_tokens(f"{title} {summary}"):
        if len(token) < 4 or token in _CLAIM_GLUE or token in _TITLE_NEGATORS:
            continue
        stem = _adjective_stem(token)
        if stem in topic or token in topic or subject_stem(token) in topic:
            continue
        stems.add(stem)
    return stems


def _cue_stems(text: str) -> set[str]:
    stems: set[str] = set()
    for token in _surface_tokens(text):
        if token in CONDEMN_CUES or token in ENDORSE_CUES:
            stems.add(_adjective_stem(token))
    return stems


def _posts_affirm(posts: list[dict], stems: set[str]) -> bool:
    if not stems or len(posts) < 2:
        return False
    claims = list(stems)
    hits = sum(1 for post in posts if _affirms_any(_post_text(post), claims))
    return hits >= _coverage_needed(len(posts))


def _effect_mentions(title: str, summary: str, subject: str) -> list[str]:
    """Negated claim words. Glue and the planet subject are left out."""
    topic = _topic_stems(subject, "")
    effects: list[str] = []
    for claim, polarity in _claim_mentions(title, summary, subject, set()):
        if polarity >= 0 or claim in _EFFECT_GLUE or claim in _NEGATION or len(claim) < 4:
            continue
        if subject_stem(claim) in topic or claim in topic:
            continue
        effects.append(claim)
    return effects


def _post_effect_flags(text: str, effects: list[str]) -> tuple[bool, bool]:
    """Whether one post supports or contradicts a negated effect."""
    supports = False
    contradicts = False
    denial_family = any(_claim_match(effect, word) for effect in effects for word in _DENIAL_EFFECTS)
    if denial_family and _EFFECT_DENIAL.search(text):
        supports = True
    tokens = _surface_tokens(text)
    for index, token in enumerate(tokens):
        if not any(_claim_match(token, effect) for effect in effects):
            continue
        window = set(tokens[max(0, index - 8) : index + 9])
        if _negated(tokens, index) or window & _MINIMIZERS:
            supports = True
        else:
            contradicts = True
    return supports, contradicts


def _affirms_any(text: str, claims: list[str]) -> bool:
    tokens = _surface_tokens(text)
    for index, token in enumerate(tokens):
        if _negated(tokens, index):
            continue
        if any(_claim_match(token, claim) for claim in claims):
            return True
    return False


def _negated_title_words(title: str) -> list[str]:
    """Negated words in the title itself. The planet subject is not stripped.

    'Not Genocidal' still denies 'Genocide' when genocide is the planet subject.
    """
    tokens = _surface_tokens(title)
    words: list[str] = []
    for index, token in enumerate(tokens):
        if len(token) < 4 or token in _EFFECT_GLUE or token in _NEGATION:
            continue
        if _negated(tokens, index):
            words.append(token)
    return words


def _denies_majority_title(
    title: str,
    summary: str,
    posts: list[dict],
    subject: str,
    majority_title: str,
) -> bool:
    """True when the title negates the majority title and the posts do not affirm it.

    'Israel Not Genocidal' denies 'Israel Genocide' even when the posts never
    say genocidal. They argue the other side. A title that does not negate the
    majority title does not qualify, so 'ICE Has Role' stays out. A summary-only
    line such as 'not a threat' does not qualify either.
    """
    del summary, subject
    if len(posts) < 2 or not majority_title:
        return False
    negated = _negated_title_words(title)
    if not negated:
        return False
    tokens = _surface_tokens(majority_title)
    affirmed = [
        token
        for index, token in enumerate(tokens)
        if len(token) >= 4 and not _negated(tokens, index)
    ]
    matched = [token for token in affirmed if any(_claim_match(token, claim) for claim in negated)]
    if not matched:
        return False
    affirmers = sum(1 for post in posts if _affirms_any(_post_text(post), matched))
    return affirmers < _coverage_needed(len(posts))


def posts_support_claim(
    title: str,
    summary: str,
    posts: list[dict],
    subject: str = "",
    *,
    majority_title: str = "",
) -> bool:
    """True when the posts back the claim without repeating a title word at 40%.

    Local. No model call. The 10% share bar is not involved.
    """
    if len(posts) < 2:
        return False
    if _denies_majority_title(title, summary, posts, subject, majority_title):
        return True
    effects = _effect_mentions(title, summary, subject)
    if not effects:
        return False
    support = 0
    contra = 0
    for post in posts:
        supports, contradicts = _post_effect_flags(_post_text(post), effects)
        if supports:
            support += 1
        elif contradicts:
            contra += 1
    need = _coverage_needed(len(posts))
    threshold = max(2, math.ceil(need / 2))
    return support >= threshold and support > contra and contra < need


def _faces_same_claim(
    left_title: str,
    left_summary: str,
    left_posts: list[dict],
    right_title: str,
    right_summary: str,
    right_posts: list[dict],
    subject: str,
) -> bool:
    """True when the two faces make one claim.

    A title that denies the other title is a real opposing side. Yemen's
    attack reports and its anti-war posts do not cross-affirm each other's
    cues, so the lexicon's same-pole flag does not fold them.
    """
    if _title_denies_title(left_title, right_title) or _title_denies_title(right_title, left_title):
        return False
    # A local denial or negated-effect paraphrase is a real opposing side.
    # 'No Relief' must not fold into 'High Fuel Prices' because both summaries
    # mention diesel.
    if posts_support_claim(
        left_title, left_summary, left_posts, subject, majority_title=right_title
    ) or posts_support_claim(
        right_title, right_summary, right_posts, subject, majority_title=left_title
    ):
        return False
    left_text = f"{left_title} {left_summary}"
    right_text = f"{right_title} {right_summary}"
    left_cues = _cue_stems(left_text)
    right_cues = _cue_stems(right_text)
    left_stems = _claim_stems(left_title, left_summary, subject)
    right_stems = _claim_stems(right_title, right_summary, subject)
    shared = left_stems & right_stems
    if shared and _posts_affirm(left_posts, shared) and _posts_affirm(right_posts, shared):
        return True
    # Same cue on both claim texts, and each side's posts say the other's cue.
    # Yemen stays apart: "killed" and "oppose" are different cues, and the
    # posts do not say the other face's cue.
    left_pole, _ignored = _cue_polarity(left_text)
    right_pole, _ignored = _cue_polarity(right_text)
    if left_pole and left_pole == right_pole and left_cues and right_cues:
        if _posts_affirm(left_posts, right_cues) and _posts_affirm(right_posts, left_cues):
            return True
    # No cue, or the same cues, and both summaries are about one claim the posts
    # repeat. "release" still counts when it is also the planet subject. A single
    # topic word both summaries mention, such as "diesel", is not that claim.
    if left_cues == right_cues:
        shared_summary = _summary_claim_overlap(left_summary, right_summary)
        if shared_summary and _posts_affirm(left_posts, shared_summary) and _posts_affirm(right_posts, shared_summary):
            return True
    return False


def _summary_claim_overlap(left_summary: str, right_summary: str) -> set[str]:
    """Stems both summaries are about, not a topic word one of them mentions.

    The overlap has to be at least half of each summary. Epstein's two
    summaries are mostly "files" and "release". A dyed-diesel summary that
    only shares "diesel" with "prices are high" does not qualify.
    """
    left = _summary_stems(left_summary)
    right = _summary_stems(right_summary)
    shared = left & right
    if not shared:
        return set()
    if len(shared) * 2 < len(left) or len(shared) * 2 < len(right):
        return set()
    return shared


def _summary_stems(summary: str) -> set[str]:
    """Claim stems in a summary, including a word that is also the planet subject."""
    stems: set[str] = set()
    for token in _surface_tokens(summary):
        if len(token) < 4 or token in _CLAIM_GLUE or token in _TITLE_NEGATORS:
            continue
        stems.add(_adjective_stem(token))
    return stems


def _face_posts(item: tuple, members: list[dict]) -> list[dict]:
    return _member_posts(item, members)


def _draft_is_one_claim(drafted: list, members: list[dict], subject: str) -> bool:
    """True when every drafted face makes the largest face's claim."""
    if len(drafted) < 2:
        return False
    ranked = sorted(range(len(drafted)), key=lambda index: (-int(drafted[index][2]), index))
    base = drafted[ranked[0]]
    base_posts = _face_posts(base, members)
    base_title = str(base[0].get("title") or "")
    base_summary = str(base[0].get("summary") or "")
    for index in ranked[1:]:
        other = drafted[index]
        if not _faces_same_claim(
            base_title,
            base_summary,
            base_posts,
            str(other[0].get("title") or ""),
            str(other[0].get("summary") or ""),
            _face_posts(other, members),
            subject,
        ):
            return False
    return True


def _partition_deniers(drafted: list, indexes: list[int], subject: str) -> list[list[int]]:
    """Keep a face out of a fold when its title denies the other title."""
    del subject
    if len(indexes) < 2:
        return [list(indexes)]
    ranked = sorted(indexes, key=lambda index: (-int(drafted[index][2]), index))
    base = ranked[0]
    base_title = str(drafted[base][0].get("title") or "")
    stay = [base]
    apart: list[list[int]] = []
    for index in ranked[1:]:
        title = str(drafted[index][0].get("title") or "")
        if _title_denies_title(title, base_title) or _title_denies_title(base_title, title):
            apart.append([index])
        else:
            stay.append(index)
    return [stay, *apart]


def _collapse_same_claim(
    drafted: list,
    groups: list[list[int]],
    members: list[dict],
    subject: str,
) -> list[list[int]]:
    """Fold groups the model left apart when they make one claim."""
    pending = [list(group) for group in groups if group]
    changed = True
    while changed and len(pending) > 1:
        changed = False
        for left in range(len(pending)):
            for right in range(left + 1, len(pending)):
                left_index = max(pending[left], key=lambda index: (int(drafted[index][2]), -index))
                right_index = max(pending[right], key=lambda index: (int(drafted[index][2]), -index))
                left_face = drafted[left_index]
                right_face = drafted[right_index]
                if _faces_same_claim(
                    str(left_face[0].get("title") or ""),
                    str(left_face[0].get("summary") or ""),
                    _face_posts(left_face, members),
                    str(right_face[0].get("title") or ""),
                    str(right_face[0].get("summary") or ""),
                    _face_posts(right_face, members),
                    subject,
                ):
                    pending[left] = pending[left] + pending[right]
                    del pending[right]
                    changed = True
                    break
            if changed:
                break
    return pending


def _title_pole_is_a_denial(title: str) -> bool:
    """True when every cue in the title is negated.

    'Israel Not Genocidal' already states the opposing claim. Rewriting it to
    'Israel Opposed' would drop that claim. 'MAGA Support' has an unnegated
    endorse cue, so it can still be rewritten when the posts condemn it.
    """
    tokens = _surface_tokens(title)
    negated = 0
    plain = 0
    for index, token in enumerate(tokens):
        if token not in CONDEMN_CUES and token not in ENDORSE_CUES:
            continue
        window = tokens[max(0, index - 3) : index]
        if any(word in NEGATION_CUES for word in window):
            negated += 1
        else:
            plain += 1
    return negated > 0 and plain == 0


def align_contradicting_title(perspective: dict, posts: list[dict]) -> bool:
    """Rewrite a title whose pole is the opposite of its posts. No model call.

    'MAGA Support' over posts that condemn MAGA becomes 'MAGA Opposed'.
    A title with no cue, or posts that agree with it, is left as it is.
    """
    title = str(perspective.get("title") or "")
    title_pole, _title_cues = _cue_polarity(title)
    if not title_pole or _title_pole_is_a_denial(title):
        return False
    scored = []
    for post in posts:
        pole, _cues = _cue_polarity(_post_text(post))
        if pole:
            scored.append(pole)
    if len(scored) < 2:
        return False
    oppose = sum(1 for pole in scored if pole == -title_pole)
    agree = sum(1 for pole in scored if pole == title_pole)
    if oppose < 2 or oppose <= agree:
        return False
    kept: list[str] = []
    for word in re.findall(r"[A-Za-z0-9']+", title):
        low = word.lower()
        if low in CONDEMN_CUES or low in ENDORSE_CUES or low in NEGATION_CUES:
            continue
        if low in {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for"}:
            continue
        kept.append(word)
    subject_words = " ".join(kept).strip() or "This topic"
    if title_pole > 0:
        new_title = f"{subject_words} Opposed"
        new_summary = f"These posts oppose {subject_words}."
    else:
        new_title = f"{subject_words} Defended"
        new_summary = f"These posts defend {subject_words}."
    perspective["title"] = new_title
    perspective["summary"] = new_summary
    perspective.pop("arguments", None)
    draft = perspective.get("_draft_face_label")
    if isinstance(draft, dict):
        draft["title"] = new_title
        draft["summary"] = new_summary
        draft.pop("arguments", None)
    return True


def _align_faces(drafted: list, members: list[dict]) -> None:
    for item in drafted:
        align_contradicting_title(item[0], _face_posts(item, members))


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

    ``second.stance`` has to be the pole of ``posts``. The posts then have to
    support the claim: either a claim word at the same polarity in about 40%
    of them, or ``posts_support_claim`` when they do not repeat the title word.
    A second face that makes the majority face's claim does not pass.
    Subject terms, short title-topic terms, and topic nouns shared with the
    majority face or the planet's top terms do not count as claim words.
    """
    if second_stance not in POLES or second_stance != stance:
        return False
    if _faces_same_claim(
        title,
        summary,
        posts,
        majority_title,
        majority_summary,
        list(majority_posts or []),
        subject,
    ):
        return False
    if claim_words_cover(
        title,
        summary,
        posts,
        subject,
        majority_posts=majority_posts,
        majority_title=majority_title,
        majority_summary=majority_summary,
        planet_terms=planet_terms,
    ):
        return True
    return posts_support_claim(
        title,
        summary,
        posts,
        subject,
        majority_title=majority_title,
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
        _align_faces(drafted, members)
        return drafted, []
    generate = context.get("stance_generate") or context.get("summary_model")
    if generate is None:
        _align_faces(drafted, members)
        return drafted, ["Stance check skipped: no label model."]
    context.pop("stance_last", None)
    log: list[str] = []
    before = len(drafted)
    original_uris = _uri_key(drafted)
    current = drafted
    if len(current) >= 2 and not context.get("stance_check_failed"):
        merged, called = merge_same_stance(
            current, members, generate, context, subject=subject
        )
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
        _align_faces(drafted, members)
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
        if _draft_is_one_claim(drafted, members, subject) and _uri_key(current) == original_uris:
            log.append(
                f"Second side not coherent on {subject or 'planet'}:{detail}. "
                f"Same-side faces kept together ({len(current)}). "
                f"Pre-pass duplicates not restored ({before})."
            )
            _align_faces(current, members)
            return current, log
        log.append(
            f"Second side not coherent on {subject or 'planet'}:{detail}. "
            f"Pre-pass faces kept ({before})."
        )
        _align_faces(drafted, members)
        return drafted, log
    if _uri_key(current) != original_uris:
        _align_faces(drafted, members)
        return drafted, [f"Stance pass skipped on {subject or 'planet'}: post count changed."]
    last = context.get("stance_last") or {}
    detail = ""
    if last:
        detail = (
            f" sample {last.get('second_n')}/{last.get('sample_n')}"
            f"={float(last.get('share') or 0):.1%} vs {float(last.get('threshold') or 0):.0%}"
        )
    log.append(f"Stance on {subject or 'planet'}: {before} face(s) -> {len(current)}{detail}.")
    _align_faces(current, members)
    return current, log
