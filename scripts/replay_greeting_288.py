#!/usr/bin/env python3
"""Offline replay of the greeting matcher on a published edition (#288).

No network, no Jev, no section labeling. Reads ``data.json`` snapshots and,
optionally, a SQLite corpus. Prints greeting planets per section and the
posts this matcher would block at ingest.

The published file stores representative posts, not every member. A greeting
planet is one of the pleasantry family (Good Sunday, Good Morning, Great Time,
Happy Sunday, Good Day, Glad Returns, and the same day's wish planets). It
counts as gone when at least 55 percent of its representatives are chit-chat,
which is the existing planet-guard floor. Posts that are not in the file
cannot be re-counted.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.chitchat_guard import pleasantry_reason

# Names from the Oct 19 duplicate pairs and the Oct 20 Good Sunday planet.
_GREETING_PLANET_NAMES = frozenset(
    {
        "good sunday",
        "good morning",
        "good day",
        "good night",
        "good evening",
        "great day",
        "great time",
        "happy sunday",
        "glad returns",
        "wonderful day",
        "hope for the day",
    }
)


def representative_texts(topic: dict) -> list[str]:
    texts: list[str] = []
    for face in topic.get("perspectives") or []:
        for post in face.get("representative_posts") or []:
            text = str(post.get("text") or post.get("clean_text") or "").strip()
            if text:
                texts.append(text)
    return texts


def iter_planets(data: dict):
    for topic in data.get("topics") or []:
        yield "global", topic
    sections = data.get("sections") or {}
    if isinstance(sections, dict):
        items = sections.items()
    else:
        items = []
    for section, body in items:
        topics = body if isinstance(body, list) else (body or {}).get("topics") or []
        for topic in topics:
            yield str(section), topic


def is_greeting_planet(name: str) -> bool:
    return (name or "").strip().lower() in _GREETING_PLANET_NAMES


def classify_edition(data: dict) -> dict:
    """Per-section greeting planets, and real planets whose reps are chit-chat."""
    by_section: dict[str, list[dict]] = {}
    shrunk: list[dict] = []
    for section, topic in iter_planets(data):
        name = str(topic.get("name") or "")
        texts = representative_texts(topic)
        kinds = [pleasantry_reason({"text": text}) or "" for text in texts]
        blocked = sum(1 for kind in kinds if kind)
        row = {
            "section": section,
            "name": name,
            "post_count": int(topic.get("post_count") or 0),
            "reps": len(texts),
            "blocked_reps": blocked,
            "greeting_reps": sum(1 for kind in kinds if kind == "greeting"),
        }
        if is_greeting_planet(name):
            by_section.setdefault(section, []).append(row)
        elif blocked:
            shrunk.append(row)
    return {"greeting": by_section, "real_planets_with_blocked_reps": shrunk}


def format_edition(label: str, data: dict) -> str:
    report = classify_edition(data)
    lines = [
        f"## {label} ({data.get('last_updated')})",
        "Greeting planets are the pleasantry family. After = still published "
        "when fewer than 55% of representatives are chit-chat.",
        f"{'section':<14} {'before':>6} {'after':>6}  planets",
    ]
    sections = ["global", *sorted(k for k in report["greeting"] if k != "global")]
    seen = set()
    for section in sections:
        rows = report["greeting"].get(section) or []
        if not rows and section != "global":
            continue
        seen.add(section)
        after = [row for row in rows if not (row["reps"] and row["blocked_reps"] / row["reps"] >= 0.55)]
        names = ", ".join(
            f"{row['name']} {row['blocked_reps']}/{row['reps']} reps"
            for row in rows
        ) or "(none)"
        lines.append(f"{section:<14} {len(rows):>6} {len(after):>6}  {names}")
    for section, rows in sorted(report["greeting"].items()):
        if section in seen:
            continue
        after = [row for row in rows if not (row["reps"] and row["blocked_reps"] / row["reps"] >= 0.55)]
        names = ", ".join(f"{row['name']} {row['blocked_reps']}/{row['reps']}" for row in rows)
        lines.append(f"{section:<14} {len(rows):>6} {len(after):>6}  {names}")
    shrunk = report["real_planets_with_blocked_reps"]
    if not shrunk:
        lines.append("Real planets with a blocked representative: none.")
    else:
        lines.append("Real planets with a blocked representative (sample shrink):")
        for row in shrunk:
            lines.append(
                f"  {row['section']}: {row['name']} posts={row['post_count']} "
                f"blocked_reps={row['blocked_reps']}/{row['reps']}"
            )
    return "\n".join(lines)


def corpus_blocks(path: Path, *, seed: int, sample: int) -> str:
    connection = sqlite3.connect(path)
    blocked: list[tuple[str, str]] = []
    total = 0
    for uri, text in connection.execute("select uri, text from posts"):
        total += 1
        reason = pleasantry_reason({"text": text}) or ""
        if reason:
            blocked.append((reason, text))
    lines = [
        f"Corpus posts: {total}. Classified chit-chat by this matcher: {len(blocked)}.",
        "This count is every stored post the matcher blocks, not a before/after diff.",
    ]
    rng = random.Random(seed)
    picked = blocked[:]
    rng.shuffle(picked)
    lines.append(f"Sample {min(sample, len(picked))} of {len(blocked)} (seed {seed}):")
    for index, (reason, text) in enumerate(picked[:sample], start=1):
        flat = " ".join(text.split())
        lines.append(f"[{index}] {reason}: {flat}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the greeting matcher on snapshots")
    parser.add_argument("snapshots", nargs="+", type=Path, help="Published data.json files")
    parser.add_argument("--corpus", type=Path, help="Optional live_corpus.db")
    parser.add_argument("--seed", type=int, default=288)
    parser.add_argument("--sample", type=int, default=30)
    args = parser.parse_args(argv)
    for path in args.snapshots:
        data = json.loads(path.read_text())
        print(format_edition(path.name, data))
        print()
    if args.corpus:
        print(corpus_blocks(args.corpus, seed=args.seed, sample=args.sample))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
