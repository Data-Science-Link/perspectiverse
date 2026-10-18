#!/usr/bin/env python3
"""Before/after evidence for #228 on main's stored corpus or a data.json snapshot.

No paid calls. R2 restore is read-only when credentials are set.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.chitchat_guard import ingest_block_reason
from pipeline.section_sanity import partition_politics_planets, politics_planet_destination
from pipeline.store import connect, load_posts, should_drop_stored_post
from pipeline.weather_guard import weather_bot_reason


def section_planet_names(data: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for section, planets in (data.get("sections") or {}).items():
        names = [str(p.get("name") or "") for p in planets]
        out[str(section)] = names
    return out


def politics_relocate_on_snapshot(data: dict) -> dict[str, list[str]]:
    sections = data.get("sections") or {}
    politics = list(sections.get("Politics") or [])
    if not politics:
        return {}
    posts: list[dict] = []
    for planet in politics:
        for face in planet.get("perspectives") or []:
            for rep in face.get("representative_posts") or []:
                posts.append({"text": rep.get("text"), "author": rep.get("author")})
    kept, moved = partition_politics_planets(politics, posts)
    result = {"Politics": [p.get("name") for p in kept]}
    for dest, planets in moved.items():
        result.setdefault(dest, []).extend(p.get("name") for p in planets)
    return result


def corpus_weather_counts(db_path: Path) -> dict:
    connection = connect(db_path)
    posts = load_posts(connection)
    connection.close()
    hits: list[dict] = []
    for post in posts:
        if weather_bot_reason(post):
            hits.append(post)
    before_ingest = len(hits)
    after_ingest = sum(1 for post in hits if ingest_block_reason(post) == "weather_bot")
    stored_delete = sum(1 for post in posts if should_drop_stored_post(post) and weather_bot_reason(post))
    return {
        "weather_bot_posts_in_corpus": before_ingest,
        "blocked_at_ingest_weather_only": after_ingest,
        "stored_rows_deleted_for_weather_bot": stored_delete,
        "sample_texts": [str(p.get("text") or "")[:240] for p in random.sample(hits, min(20, len(hits)))],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, help="Published data.json for section planet lists")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("PERSPECTIVERSE_CORPUS_DB", "/tmp/live_corpus.db")))
    parser.add_argument("--restore-r2", action="store_true")
    parser.add_argument("--seed", type=int, default=228)
    args = parser.parse_args()
    random.seed(args.seed)
    report: dict = {}

    if args.restore_r2:
        from pipeline.r2 import restore_corpus

        status = restore_corpus(args.db)
        report["r2_restore"] = status

    if args.db.is_file():
        report["corpus"] = corpus_weather_counts(args.db)

    if args.data and args.data.is_file():
        data = json.loads(args.data.read_text(encoding="utf-8"))
        before = section_planet_names(data)
        after = dict(before)
        relocated = politics_relocate_on_snapshot(data)
        if relocated:
            after["Politics"] = relocated.get("Politics", after.get("Politics", []))
            for section, names in relocated.items():
                if section == "Politics":
                    continue
                after.setdefault(section, []).extend(names)
        report["section_planets_before"] = before
        report["section_planets_after_politics_sanity"] = after

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
