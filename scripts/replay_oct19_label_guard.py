#!/usr/bin/env python3
"""Apply label guard offline to the Oct 19 edition for UI replay (PR #265)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.assemble import assemble_payload
from pipeline.label_guard import guard_published_labels

DEFAULT_SRC = Path("/home/ubuntu/.cursor/projects/workspace/uploads/data_2026-10-19_79cf.json")
OUT = ROOT / "public" / "data.json"


def _hydrate_posts(topic: dict, counter: list[int]) -> list[dict]:
    posts: list[dict] = []
    uris: list[str] = []
    for face in topic.get("perspectives") or []:
        for rep in face.get("representative_posts") or []:
            text = str(rep.get("text") or rep.get("clean_text") or "").strip()
            if not text:
                continue
            uri = f"at://replay/oct19/{counter[0]}"
            counter[0] += 1
            post = {
                "uri": uri,
                "text": text,
                "clean_text": text,
                "likes": int(rep.get("likes") or 0),
            }
            posts.append(post)
            uris.append(uri)
    topic["_member_uris"] = uris
    for face in topic.get("perspectives") or []:
        face["_face_member_uris"] = uris
    return posts


def main(src: Path = DEFAULT_SRC) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    counter = [0]
    all_posts: list[dict] = []
    sections: dict[str, list[dict]] = {}
    for section, planets in (payload.get("sections") or {}).items():
        topics = copy.deepcopy(planets)
        for topic in topics:
            all_posts.extend(_hydrate_posts(topic, counter))
        for line in guard_published_labels(topics, all_posts):
            print(line)
        sections[section] = topics
    out = assemble_payload(
        payload.get("topics") or [],
        mode=str(payload.get("mode") or "live"),
        source=str(payload.get("source") or "bluesky"),
        total_posts=int(payload.get("total_posts") or 0),
        last_updated=payload.get("last_updated"),
        sections=sections,
    )
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC)
