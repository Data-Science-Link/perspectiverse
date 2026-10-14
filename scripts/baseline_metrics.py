#!/usr/bin/env python3
"""Print edition baseline metrics from a published ``public/data.json``.

Metric definitions: ``.factory/BASELINE_METRICS.md``

No model or LLM calls. Hidden volume prefers end-of-run unique log lines.
The same-side check is a fixed keyword lexicon over published fields.

Usage::

    python scripts/baseline_metrics.py public/data.json
    python scripts/baseline_metrics.py --log pipeline.log public/data.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Whole-word tokens from face titles and post text (see BASELINE_METRICS.md).
STOPWORDS = frozenset(
    "the a an of and or to in on for is are be by with vs not no".split()
)
WORD_RE = re.compile(r"[a-z0-9']+")

NOISE_RE = re.compile(r"Live snapshot:.*?(\d+) excluded as noise")
LEFTOVER_LABELED_RE = re.compile(r"INFO ([^:\n]+): catch-all leftover (\d+) posts")
STAYED_OFF_RE = re.compile(r"INFO .*?: (\d+) of \d+ posts stayed off")
THIN_RE = re.compile(r"held \d+ thin fragments \((\d+) posts\)")
THIN_UNIQUE_RE = re.compile(r"\((\d+) in thin fragments held below \d+ posts\)")
LEFTOVERS_UNIQUE_RE = re.compile(r"Leftovers: (\d+)")
GLOBAL_TIMING_RE = re.compile(r"Timing: \d+ global planet\(s\) labeled")

# Fixed polarity lexicon for the same-side check. Not a model.
CONDEMN_CUES = frozenset(
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
# "back" is omitted: "go back" is not an endorsement.
ENDORSE_CUES = frozenset(
    """
    support supports supported supporters supporting defend defends defending
    deserve deserves deserved success successful worth protect protection
    protecting boost effective favor favour endorse endorsed
    """.split()
)
# "against" is not a negator here. "actions against Palestinians are racist"
# would otherwise flip "racist".
NEGATION_CUES = frozenset(
    "not no never nor neither without cannot dont doesnt didnt cant wont".split()
)

SAMPLE_SEED = 0
UNFLAGGED_SAMPLE = 10


def tokenize(text: str) -> set[str]:
    """Lowercase whole-word tokens with length >= 3, minus STOPWORDS."""
    return {
        w
        for w in WORD_RE.findall(text.lower())
        if len(w) >= 3 and w not in STOPWORDS
    }


def _tokens(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def iter_planets(data: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """``(scope, planet)`` for global topics, then each section."""
    for planet in data.get("topics") or []:
        yield "global", planet
    for scope, planets in (data.get("sections") or {}).items():
        for planet in planets:
            yield str(scope), planet


def total_posts(data: dict[str, Any]) -> int:
    return int(data["total_posts"])


def posts_unsupported_title(data: dict[str, Any]) -> tuple[int, int]:
    """Informational lexical overlap. Not a done bar.

    Return (post_count, face_count) for faces whose representative posts
    rarely share a title word. See BASELINE_METRICS.md.
    """
    bad_posts = 0
    bad_faces = 0
    for _scope, planet in iter_planets(data):
        for face in planet.get("perspectives") or []:
            reps = face.get("representative_posts") or []
            if not reps:
                continue
            title_words = tokenize(face.get("title") or "")
            if not title_words:
                continue
            hits = sum(
                1
                for rep in reps
                if title_words & tokenize(rep.get("text") or "")
            )
            if hits / len(reps) < 0.4:
                bad_posts += int(face.get("post_count") or 0)
                bad_faces += 1
    return bad_posts, bad_faces


def _last_int(pattern: re.Pattern[str], text: str) -> int | None:
    found = pattern.findall(text)
    if not found:
        return None
    return int(found[-1])


def _section_pass_text(log_text: str) -> tuple[str, bool]:
    """Text after the global-pass timing line, when that marker exists."""
    match = GLOBAL_TIMING_RE.search(log_text)
    if not match:
        return log_text, False
    return log_text[match.end() :], True


def parse_hidden_from_log(log_text: str) -> dict[str, Any]:
    """Split hidden volume into noise vs grouping controls.

    End-of-run unique lines win over summed per-pass lines. The global
    ("All topics") pass and the section passes otherwise log the same posts
    twice. See BASELINE_METRICS.md.
    """
    noise = _last_int(NOISE_RE, log_text)
    if noise is None:
        raise ValueError("log missing 'Live snapshot: ... N excluded as noise' line")

    thin_unique = _last_int(THIN_UNIQUE_RE, log_text)
    if thin_unique is None:
        thin_fragments = sum(int(n) for n in THIN_RE.findall(log_text))
        thin_source = "summed held-fragment lines"
    else:
        thin_fragments = thin_unique
        thin_source = "end-of-run unique thin-fragment count"

    leftovers_unique = _last_int(LEFTOVERS_UNIQUE_RE, log_text)
    if leftovers_unique is None:
        labeled = LEFTOVER_LABELED_RE.findall(log_text)
        sections = {label.strip() for label, _count in labeled}
        drop_global = "All topics" in sections and len(sections) > 1
        catch_all = 0
        for label, count in labeled:
            if drop_global and label.strip() == "All topics":
                continue
            catch_all += int(count)
        catch_source = (
            "section catch-all lines only (All topics pass omitted)"
            if drop_global
            else "summed catch-all leftover lines"
        )
    else:
        # Leftovers already includes the thin-fragment URIs. Subtract them
        # so the printed parts stay additive. The remainder also includes
        # sub-floor drops folded into that unique bucket.
        catch_all = max(0, leftovers_unique - thin_fragments)
        catch_source = (
            f"end-of-run Leftovers {leftovers_unique} minus thin_fragments "
            f"{thin_fragments} (includes sub-floor drops)"
        )

    section_text, section_only = _section_pass_text(log_text)
    stayed_off = sum(int(n) for n in STAYED_OFF_RE.findall(section_text))
    stayed_source = (
        "section pass only, after the global timing line"
        if section_only
        else "summed stayed-off lines (no global timing marker)"
    )

    grouping_controls = catch_all + stayed_off + thin_fragments
    return {
        "noise": noise,
        "catch_all_leftover": catch_all,
        "stayed_off_face": stayed_off,
        "thin_fragments": thin_fragments,
        "grouping_controls": grouping_controls,
        "hidden_total": noise + grouping_controls,
        "thin_source": thin_source,
        "catch_all_source": catch_source,
        "stayed_off_source": stayed_source,
    }


def _cue_polarity(text: str) -> tuple[int, list[str]]:
    """Return (-1 condemn, +1 endorse, 0 unclear) and the cue tokens that fired."""
    tokens = _tokens(text)
    condemn = 0
    endorse = 0
    cues: list[str] = []
    for index, token in enumerate(tokens):
        negated = any(word in NEGATION_CUES for word in tokens[max(0, index - 3) : index])
        if token in CONDEMN_CUES:
            if negated:
                endorse += 1
                cues.append(f"+{token}(negated)")
            else:
                condemn += 1
                cues.append(f"-{token}")
        elif token in ENDORSE_CUES:
            if negated:
                condemn += 1
                cues.append(f"-{token}(negated)")
            else:
                endorse += 1
                cues.append(f"+{token}")
    if condemn > endorse and condemn >= 1:
        return -1, cues
    if endorse > condemn and endorse >= 1:
        return 1, cues
    return 0, cues


def _claim_text(face: dict[str, Any]) -> str:
    parts = [str(face.get("title") or ""), str(face.get("summary") or "")]
    parts.extend(str(item) for item in (face.get("arguments") or []))
    return "\n".join(parts)


def _unique_cues(cues: list[str], limit: int = 8) -> str:
    seen: list[str] = []
    for cue in cues:
        if cue not in seen:
            seen.append(cue)
        if len(seen) >= limit:
            break
    return ", ".join(seen) if seen else "(no cue)"


def flagged_planets(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Planets whose published faces share one side, or whose title contradicts posts.

    Deterministic lexicon only. No model call. Planets the lexicon cannot
    score are left unflagged rather than guessed.
    """
    flagged: list[dict[str, Any]] = []
    for scope, planet in iter_planets(data):
        faces = list(planet.get("perspectives") or [])
        face_rows: list[dict[str, Any]] = []
        for face in faces:
            pole, cues = _cue_polarity(_claim_text(face))
            face_rows.append(
                {
                    "id": face.get("id"),
                    "title": face.get("title") or "",
                    "summary": face.get("summary") or "",
                    "pole": pole,
                    "cues": cues,
                }
            )
        reasons: list[str] = []
        evidence: list[str] = []
        nonzero = [row["pole"] for row in face_rows if row["pole"]]
        if (
            len(faces) >= 2
            and len(nonzero) == len(faces)
            and len(set(nonzero)) == 1
        ):
            reasons.append("same_side")
            side = "condemn" if nonzero[0] < 0 else "endorse"
            evidence.append(
                f"same_side: all {len(faces)} faces score {side} on title, summary, and arguments"
            )
            for row in face_rows:
                evidence.append(
                    f"  {row['id']} {row['title']!r}: {_unique_cues(row['cues'])}"
                )

        for face, row in zip(faces, face_rows):
            title_pole, title_cues = _cue_polarity(str(face.get("title") or ""))
            if not title_pole:
                continue
            posts = list(face.get("representative_posts") or [])
            post_poles = [
                _cue_polarity(str(rep.get("text") or ""))[0] for rep in posts
            ]
            scored = [pole for pole in post_poles if pole]
            if len(scored) < 2:
                continue
            oppose = sum(1 for pole in scored if pole == -title_pole)
            agree = sum(1 for pole in scored if pole == title_pole)
            if oppose >= 2 and oppose > agree:
                reasons.append("title_contradicts_posts")
                title_side = "endorse" if title_pole > 0 else "condemn"
                evidence.append(
                    f"title_contradicts_posts: {row['id']} {row['title']!r} "
                    f"title scores {title_side} ({_unique_cues(title_cues)}); "
                    f"representative posts with a cue: oppose {oppose}, agree {agree}, "
                    f"of {len(posts)} posts"
                )
        if not reasons:
            continue
        context: list[str] = []
        if planet.get("stance_check"):
            context.append(f"stance_check={planet['stance_check']}")
        if planet.get("opposing_note"):
            context.append(f"opposing_note={planet['opposing_note']}")
        flagged.append(
            {
                "scope": scope,
                "name": planet.get("name") or "",
                "id": planet.get("id"),
                "post_count": planet.get("post_count"),
                "reasons": reasons,
                "evidence": evidence,
                "context": context,
            }
        )
    return flagged


def unflagged_two_face_sample(
    data: dict[str, Any],
    *,
    count: int = UNFLAGGED_SAMPLE,
    seed: int = SAMPLE_SEED,
) -> list[dict[str, Any]]:
    """Fixed-seed sample of unflagged planets that publish two or more faces."""
    flagged_keys = {
        (row["scope"], row["name"], str(row["id"])) for row in flagged_planets(data)
    }
    candidates: list[dict[str, Any]] = []
    for scope, planet in iter_planets(data):
        faces = list(planet.get("perspectives") or [])
        if len(faces) < 2:
            continue
        key = (scope, planet.get("name") or "", str(planet.get("id")))
        if key in flagged_keys:
            continue
        candidates.append(
            {
                "scope": scope,
                "name": planet.get("name") or "",
                "id": planet.get("id"),
                "post_count": planet.get("post_count"),
                "faces": [
                    {
                        "id": face.get("id"),
                        "title": face.get("title") or "",
                        "summary": face.get("summary") or "",
                    }
                    for face in faces
                ],
            }
        )
    candidates.sort(key=lambda row: (row["scope"], row["name"], str(row["id"])))
    if count <= 0 or not candidates:
        return []
    if len(candidates) <= count:
        return candidates
    return random.Random(seed).sample(candidates, count)


def format_report(
    data: dict[str, Any],
    *,
    log_text: str | None = None,
    label: str = "",
    unflagged_sample: int = UNFLAGGED_SAMPLE,
    sample_seed: int = SAMPLE_SEED,
) -> str:
    lines: list[str] = []
    if label:
        lines.append(label)
    lines.append(f"last_updated: {data.get('last_updated', '?')}")
    lines.append(f"total_posts: {total_posts(data)}")
    unsupported_posts, unsupported_faces = posts_unsupported_title(data)
    lines.append(
        "informational_unsupported_title_posts: "
        f"{unsupported_posts} ({unsupported_faces} faces)"
    )
    lines.append(
        "  note: lexical title overlap only; not a done bar for same-side or missing opposition"
    )
    if log_text is not None:
        hidden = parse_hidden_from_log(log_text)
        lines.append("hidden_from_log:")
        lines.append(f"  noise: {hidden['noise']}")
        lines.append(f"  catch_all_leftover: {hidden['catch_all_leftover']}")
        lines.append(f"  stayed_off_face: {hidden['stayed_off_face']}")
        lines.append(f"  thin_fragments: {hidden['thin_fragments']}")
        lines.append(f"  grouping_controls_total: {hidden['grouping_controls']}")
        lines.append(f"  hidden_total: {hidden['hidden_total']}")
        lines.append(f"  dedupe.thin: {hidden['thin_source']}")
        lines.append(f"  dedupe.catch_all: {hidden['catch_all_source']}")
        lines.append(f"  dedupe.stayed_off: {hidden['stayed_off_source']}")

    flagged = flagged_planets(data)
    lines.append(f"flagged_planets: {len(flagged)}")
    if not flagged:
        lines.append("  (none)")
    for row in flagged:
        reason = ",".join(row["reasons"])
        lines.append(
            f"- [{row['scope']}] {row['name']} id={row['id']} "
            f"posts={row['post_count']}: {reason}"
        )
        for item in row["evidence"]:
            lines.append(f"    {item}")
        if row["context"]:
            lines.append(f"    context: {'; '.join(row['context'])}")

    sample = unflagged_two_face_sample(
        data, count=unflagged_sample, seed=sample_seed
    )
    lines.append(
        f"unflagged_two_face_sample: seed={sample_seed} count={len(sample)}"
    )
    if not sample:
        lines.append("  (none)")
    for row in sample:
        lines.append(
            f"- [{row['scope']}] {row['name']} id={row['id']} posts={row['post_count']}"
        )
        for face in row["faces"]:
            lines.append(f"    {face['id']} {face['title']!r}: {face['summary']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data_json",
        type=Path,
        help="Path to published public/data.json from a data-snapshot commit",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Optional Daily Discourse Pipeline job log for hidden-post breakdown",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Optional heading printed above the report (e.g. commit id)",
    )
    parser.add_argument(
        "--unflagged-sample",
        type=int,
        default=UNFLAGGED_SAMPLE,
        help="How many unflagged multi-face planets to print (fixed seed)",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=SAMPLE_SEED,
        help="Seed for the unflagged multi-face sample",
    )
    args = parser.parse_args(argv)

    data = json.loads(args.data_json.read_text(encoding="utf-8"))
    log_text = args.log.read_text(encoding="utf-8") if args.log else None
    print(
        format_report(
            data,
            log_text=log_text,
            label=args.label,
            unflagged_sample=args.unflagged_sample,
            sample_seed=args.sample_seed,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
