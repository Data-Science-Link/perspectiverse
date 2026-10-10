"""Merge same-stance faces, then look for a real second stance on a one-face planet.

The calls use whatever label model the pipeline is already using (DeepInfra
Llama when that is the configured backend). The heuristic backend makes none
of them. A second face is kept only when the other pole is at least
``stance_second_face_share`` of the stance sample, at least two posts, and
one coherent claim. The sample is at most 40 posts, or the whole planet when
it is smaller. The whole-planet count is not what this pass compares.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from pipeline.cluster_math import salient_terms
from pipeline.perspectives import MIN_FACE_POSTS
from pipeline.schema import TOP_TERMS_LIMIT
from pipeline.settings import STANCE_SAMPLE_LIMIT, STANCE_SECOND_FACE_SHARE

POLES = ("supports", "opposes")
STANCES = ("supports", "opposes", "other-angle", "off-topic")
_MIXED = "mixed remarks"


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


def sample_rows(rows: list[tuple], limit: int = STANCE_SAMPLE_LIMIT) -> list[tuple]:
    ordered = ordered_rows(rows)
    return [ordered[index] for index in spread_indexes(len(ordered), limit)]


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
        "Different events or stories are not the same stance.",
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
        "A minority is coherent when those posts share one claim, even if there are only a few.",
        "It is not coherent when they are unrelated asides.",
        "Return JSON only, no markdown:",
        '{"question": "...", "labels": [{"i": 1, "stance": "supports"}], '
        '"second": {"stance": "opposes", "coherent": false, "title": "2-4 words", "summary": "one sentence"}}',
        "i starts at 1. second.stance is supports or opposes, never other-angle.",
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


def _bump(context: dict) -> None:
    calls = context.setdefault("story_calls", {})
    calls["stance"] = int(calls.get("stance") or 0) + 1


def _call(generate: Callable[[str], str], prompt: str, context: dict) -> str | None:
    _bump(context)
    try:
        return generate(prompt) or ""
    except (OSError, RuntimeError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, TypeError):
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
    raw = _call(generate, build_merge_prompt(drafted, members), context)
    if raw is None:
        return drafted, False
    groups = parse_merge_groups(raw, len(drafted))
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


def split_second_stance(
    drafted: list,
    members: list[dict],
    generate: Callable[[str], str],
    context: dict,
    *,
    subject: str,
) -> tuple[list, bool]:
    """One sample call. Split only when the configured share is met."""
    if len(drafted) != 1:
        return drafted, False
    rows = sample_rows(drafted[0][1], STANCE_SAMPLE_LIMIT)
    if len(rows) < MIN_FACE_POSTS:
        return drafted, False
    raw = _call(generate, build_stance_prompt(rows, members, subject), context)
    if raw is None:
        return drafted, False
    parsed = parse_stance_response(raw, len(rows))
    if parsed is None:
        return drafted, False
    counts: dict[str, int] = {name: 0 for name in STANCES}
    for label in parsed["labels"]:
        counts[label] += 1
    share = stance_share(context)
    keep, stance, found, ratio = clears_second_stance(counts, len(rows), share)
    title = parsed["title"]
    coherent = bool(parsed["coherent"]) and bool(title) and title.lower() != _MIXED
    context["stance_last"] = {
        "sample_n": len(rows),
        "counts": counts,
        "second": stance,
        "second_n": found,
        "share": ratio,
        "threshold": share,
        "coherent": coherent,
        "split": False,
    }
    if not keep or not coherent:
        return drafted, True
    move_uris = {
        str(row[0])
        for row, label in zip(rows, parsed["labels"])
        if label == stance
    }
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
) -> tuple[list, list[str]]:
    """Same-stance merge, then a sample check only when one face would remain.

    A failed call leaves the faces as they were. The heuristic backend returns
    immediately and does not call the model.
    """
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
    if len(current) >= 2:
        merged, called = merge_same_stance(current, members, generate, context)
        if not called:
            log.append(f"Stance merge kept {subject or 'planet'}: the call failed.")
        elif _uri_key(merged) != original_uris:
            log.append(f"Stance merge kept {subject or 'planet'}: the groups would have dropped posts.")
        else:
            current = merged
    if len(current) == 1:
        checked, called = split_second_stance(current, members, generate, context, subject=subject)
        if not called:
            log.append(f"Stance check kept one face on {subject or 'planet'}: the call failed.")
        elif _uri_key(checked) != original_uris:
            log.append(f"Stance check kept one face on {subject or 'planet'}: the split would have dropped posts.")
        else:
            current = checked
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
