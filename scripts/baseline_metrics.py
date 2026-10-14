#!/usr/bin/env python3
"""Print edition baseline metrics from a published ``public/data.json``.

Metric definitions: ``.factory/BASELINE_METRICS.md``

Usage::

    python scripts/baseline_metrics.py public/data.json
    python scripts/baseline_metrics.py --log pipeline.log public/data.json
"""

from __future__ import annotations

import argparse
import json
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
LEFTOVER_RE = re.compile(r"catch-all leftover (\d+) posts")
STAYED_OFF_RE = re.compile(r"INFO .*?: (\d+) of \d+ posts stayed off")
THIN_RE = re.compile(r"held \d+ thin fragments \((\d+) posts\)")


def tokenize(text: str) -> set[str]:
    """Lowercase whole-word tokens with length >= 3, minus STOPWORDS."""
    return {
        w
        for w in WORD_RE.findall(text.lower())
        if len(w) >= 3 and w not in STOPWORDS
    }


def iter_planets(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Every planet row in the edition (global topics plus section planets)."""
    yield from data.get("topics") or []
    for planets in (data.get("sections") or {}).values():
        yield from planets


def total_posts(data: dict[str, Any]) -> int:
    return int(data["total_posts"])


def posts_unsupported_title(data: dict[str, Any]) -> tuple[int, int]:
    """Return (post_count, face_count) failing the title-support rule."""
    bad_posts = 0
    bad_faces = 0
    for planet in iter_planets(data):
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


def parse_hidden_from_log(log_text: str) -> dict[str, int]:
    """Split hidden volume into noise vs grouping-control log lines."""
    noise_m = NOISE_RE.search(log_text)
    if not noise_m:
        raise ValueError("log missing 'Live snapshot: ... N excluded as noise' line")
    noise = int(noise_m.group(1))
    catch_all_leftover = sum(int(n) for n in LEFTOVER_RE.findall(log_text))
    stayed_off_face = sum(int(n) for n in STAYED_OFF_RE.findall(log_text))
    thin_fragments = sum(int(n) for n in THIN_RE.findall(log_text))
    grouping_controls = catch_all_leftover + stayed_off_face + thin_fragments
    return {
        "noise": noise,
        "catch_all_leftover": catch_all_leftover,
        "stayed_off_face": stayed_off_face,
        "thin_fragments": thin_fragments,
        "grouping_controls": grouping_controls,
        "hidden_total": noise + grouping_controls,
    }


def format_report(
    data: dict[str, Any],
    *,
    log_text: str | None = None,
    label: str = "",
) -> str:
    lines: list[str] = []
    if label:
        lines.append(label)
    lines.append(f"last_updated: {data.get('last_updated', '?')}")
    lines.append(f"total_posts: {total_posts(data)}")
    unsupported_posts, unsupported_faces = posts_unsupported_title(data)
    lines.append(
        f"unsupported_title_posts: {unsupported_posts} ({unsupported_faces} faces)"
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
    args = parser.parse_args(argv)

    data = json.loads(args.data_json.read_text(encoding="utf-8"))
    log_text = args.log.read_text(encoding="utf-8") if args.log else None
    print(format_report(data, log_text=log_text, label=args.label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
