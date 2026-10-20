#!/usr/bin/env python3
"""Build the Oct 19 blind pair sheet for issue #275.

Reads a published edition file and writes docs/evidence/275/oct19-pairs.csv.
The is_duplicate column is left empty on purpose. This script does not call
Jev, a label model, or the grouping code, and it does not dispatch a workflow.

Guards that are not applied here: the 30-post floor (#266), the junk-planet
filter (#264), the stance gate (#268), and the exact-title fold (#235).
The sheet is the published edition, which is the method output from the
Oct 19 run (data-snapshot 44a537b), before those four guards.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Planet pairs are (scope, planet name, planet name). Scope "global" is the
# front catalog. Every other scope is one section solar system.
# The list mixes pairs a reader might call the same story with pairs a reader
# would keep apart. Nothing in the output file says which is which.
PLANET_PAIRS: list[tuple[str, str, str]] = [
    ("Technology", "AI Generated Articles", "AI bots"),
    ("Technology", "AI Generated Articles", "AI Adoption"),
    ("Technology", "AI Generated Articles", "AI Creative Effort"),
    ("Technology", "AI Generated Articles", "Crazy"),
    ("Technology", "AI Generated Articles", "AI Art"),
    ("Technology", "AI bots", "AI Adoption"),
    ("Technology", "AI bots", "AI Creative Effort"),
    ("Technology", "AI bots", "Crazy"),
    ("Technology", "AI bots", "AI Art"),
    ("Technology", "AI Adoption", "AI Creative Effort"),
    ("Technology", "AI Adoption", "Crazy"),
    ("Technology", "AI Adoption", "AI Art"),
    ("Technology", "AI Creative Effort", "Crazy"),
    ("Technology", "AI Creative Effort", "AI Art"),
    ("Technology", "Crazy", "AI Art"),
    ("Technology", "AI Control", "AI Generated Articles"),
    ("Technology", "AI Control", "AI Art"),
    ("Sports", "PS6 Pricing", "PS5 Compatibility"),
    ("Sports", "PS6 Pricing", "Sony PS5"),
    ("Sports", "PS6 Pricing", "Playstation Games Sony"),
    ("Sports", "PS5 Compatibility", "Sony PS5"),
    ("Sports", "PS5 Compatibility", "Playstation Games Sony"),
    ("Sports", "Sony PS5", "Playstation Games Sony"),
    ("Culture", "Tax Movie Titles", "Tax Purposes"),
    ("Health", "ADHD Struggles", "ADHD Struggles 2"),
    ("Education", "School Surgeries", "School Medical Care"),
    ("Other", "Good Day", "Good Morning"),
    ("Other", "Good Morning", "Great Day"),
    ("Other", "Great Day", "Hope For The Day"),
    ("Other", "Hope For The Day", "wonderful day"),
    ("Other", "wonderful day", "Great Time"),
    ("Other", "Great Time", "Glad Returns"),
    ("Other", "Glad Returns", "Happy Sunday"),
    ("Other", "Good Day", "Happy Sunday"),
    ("Business", "Trump Gas Prices", "Brent Oil Prices"),
    ("Business", "Millionaire Definition", "Ultra Rich"),
    ("World", "US Ukraine War", "Russia Sanctions"),
    ("World", "US Ukraine War", "Trump Krasnov Link"),
    ("World", "Russia Sanctions", "US Unreliable"),
    ("Sports", "College Football Playoff", "BYU vs Notre Dame"),
    ("Environment", "Fires", "Coffee Building Fire"),
    ("Environment", "Cold Weather", "Angeles Cities Heat"),
    ("Environment", "Cold Weather", "Autumn Foliage"),
    ("Environment", "Cold Weather", "Pretty Flowers"),
    ("Education", "Bar Exam", "Bits Limited Neighborhood"),
    ("Health", "Mental Health Struggles", "ADHD Struggles"),
    ("global", "Trump Ukraine Sanctions", "Halloween"),
    ("global", "Book Enthusiasm", "Musk Interference"),
    ("global", "Early Voting", "Movie Enjoyment"),
    ("World", "Israel Condemned", "WWII Veteran Age"),
    ("Politics", "Canada Unity", "Epstein Files Release"),
    ("Politics", "Oregon School Shooting", "Trans Rights Debate"),
    ("Business", "The Article", "Billionaire Power"),
    ("Sports", "Goal scored", "Retro Gaming Revival"),
    ("Culture", "Pokemon Fan Art", "French Protests"),
    ("Health", "Covid Vaccine", "Gym Workouts"),
    ("Environment", "Bird Behavior", "Climate Crisis"),
    ("Education", "Grade School Fashion", "College Republicans"),
    ("Other", "Pet Benefits", "JD Vance"),
    ("Other", "Short Term Jobs", "Law Degree"),
]

# Extra face pairs beyond every within-planet pair. Each item is
# (scope, planet, face title, scope, planet, face title).
EXTRA_FACE_PAIRS: list[tuple[str, str, str, str, str, str]] = [
    ("global", "Trump Ukraine Sanctions", "Trump Helps Russia", "World", "US Ukraine War", "Trump Helps Russia"),
    ("global", "Musk Interference", "Musk Corruption", "Politics", "Musk Accountability", "Musk Corruption"),
    ("global", "Trans Rights Debate", "Trans Rights", "Politics", "Trans Rights Debate", "Trans Rights"),
    ("global", "Good Morning", "Good Wishes", "Other", "Good Day", "Good Wishes"),
    ("global", "Good Morning", "Good Wishes", "Other", "Good Morning", "Good Morning"),
    ("Other", "Good Day", "Good Wishes", "Other", "Hope For The Day", "Good Wishes"),
    ("Other", "wonderful day", "Good Wishes", "Other", "Good Morning", "Good Morning"),
    ("World", "Israel Condemned", "Israel Condemned", "World", "WWII Veteran Age", "WWII Veteran Age"),
    ("World", "US Iran War", "Iran War", "World", "Russia Sanctions", "Sanction Policy"),
    ("Politics", "Canada Unity", "Canada Defended", "Politics", "Epstein Files Release", "Epstein Files"),
    ("Politics", "Oregon School Shooting", "School Shootings", "Politics", "Trump Corruption", "Trump Corruption"),
    ("Business", "Billionaire Power", "Billionaires Abuse Power", "Business", "Trump Gas Prices", "Gas Prices"),
    ("Business", "The Article", "Article Shared", "Business", "Trump Regime", "Campaign Finance"),
    ("Technology", "Twitter Exodus", "Twitter Sucks", "Technology", "Zuckerberg Condemned", "Zuckerberg Condemned"),
    ("Technology", "AI Control", "AI Control", "Technology", "Account Security", "Account Suspensions"),
    ("Sports", "Goal scored", "Goal scored", "Sports", "College Football Playoff", "College Football"),
    ("Sports", "Retro Gaming Revival", "Gaming experiences", "Sports", "Sony PS5", "Sony Thought Years"),
    ("Culture", "Pokemon Fan Art", "Pokemon Fans", "Culture", "Tax Purposes", "Tax Evasion"),
    ("Culture", "Tommy Exposed", "Tommy Exposed", "Culture", "Funny", "Funny"),
    ("Health", "Universal Healthcare", "Universal Healthcare", "Health", "Feel Better", "Feel Better"),
    ("Health", "Covid Vaccine", "Covid Vaccines", "Health", "Pope Leo Recovery", "Pope Recovery"),
    ("Environment", "Bird Behavior", "Bird remarks", "Environment", "Climate Crisis", "Climate Change"),
    ("Environment", "Deer References", "Deer References", "Environment", "Fires", "Fire Response"),
    ("Education", "Bar Exam", "Bar Exam", "Education", "Voucher Program", "Voucher Programs"),
    ("Education", "Cafeteria Duty", "Too", "Education", "Bully Bullies Bullying", "Bully Bullies Bullying"),
    ("Other", "Short Term Jobs", "Short Term Jobs", "Other", "Rise of Fascism", "Fascism Rising"),
    ("Other", "JD Vance", "Ethnic Crime", "Other", "Law Degree", "Law Degree"),
    ("global", "Book Enthusiasm", "Book Enthusiasm", "global", "Movie Enjoyment", "Movie praise"),
    ("global", "Early Voting", "Vote Early", "global", "Halloween", "Halloween Spirit"),
    ("global", "No Kings Protests", "No Kings", "global", "Video Game", "Game Enjoyment"),
    ("Sports", "Brewers Dodgers", "Brewers Success", "Sports", "Goal scored", "Goal scored"),
    ("Culture", "Twitch Streamers", "Stream Plans", "Culture", "The Show", "Show Quality"),
    ("Health", "Asthma Attacks", "Asthma Fatal", "Health", "ADHD Struggles", "ADHD Struggles"),
]

COLUMNS = [
    "pair_id",
    "level",
    "section",
    "planet_a",
    "planet_b",
    "title_a",
    "title_b",
    "post_count_a",
    "post_count_b",
    "sample_texts_a",
    "sample_texts_b",
    "is_duplicate",
]


def _clip(text: str, limit: int = 240) -> str:
    flat = " ".join(str(text or "").split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


def _samples(posts: list[dict], n: int = 3) -> str:
    chunks = []
    for post in posts[:n]:
        text = _clip(str(post.get("text") or ""))
        if text:
            chunks.append(text)
    return " || ".join(chunks)


def _catalogs(edition: dict) -> dict[str, list[dict]]:
    catalogs = {"global": list(edition.get("topics") or [])}
    sections = edition.get("sections") or {}
    for name, planets in sections.items():
        catalogs[str(name)] = list(planets or [])
    return catalogs


def _index(catalogs: dict[str, list[dict]]) -> dict[tuple[str, str], dict]:
    found: dict[tuple[str, str], dict] = {}
    for scope, planets in catalogs.items():
        for planet in planets:
            found[(scope, str(planet.get("name") or ""))] = planet
    return found


def _face(planet: dict, title: str) -> dict:
    for face in planet.get("perspectives") or []:
        if str(face.get("title") or "") == title:
            return face
    have = [str(face.get("title") or "") for face in planet.get("perspectives") or []]
    raise KeyError(f"{planet.get('name')!r} has no face {title!r}; has {have}")


def _planet_row(pair_id: str, scope: str, left: dict, right: dict) -> dict:
    left_posts: list[dict] = []
    right_posts: list[dict] = []
    for face in left.get("perspectives") or []:
        left_posts.extend(face.get("representative_posts") or [])
    for face in right.get("perspectives") or []:
        right_posts.extend(face.get("representative_posts") or [])
    return {
        "pair_id": pair_id,
        "level": "planet",
        "section": scope,
        "planet_a": left.get("name") or "",
        "planet_b": right.get("name") or "",
        "title_a": left.get("name") or "",
        "title_b": right.get("name") or "",
        "post_count_a": int(left.get("post_count") or 0),
        "post_count_b": int(right.get("post_count") or 0),
        "sample_texts_a": _samples(left_posts),
        "sample_texts_b": _samples(right_posts),
        "is_duplicate": "",
    }


def _face_row(
    pair_id: str,
    scope_a: str,
    planet_a: dict,
    face_a: dict,
    scope_b: str,
    planet_b: dict,
    face_b: dict,
) -> dict:
    section = scope_a if scope_a == scope_b else f"{scope_a}|{scope_b}"
    return {
        "pair_id": pair_id,
        "level": "face",
        "section": section,
        "planet_a": planet_a.get("name") or "",
        "planet_b": planet_b.get("name") or "",
        "title_a": face_a.get("title") or "",
        "title_b": face_b.get("title") or "",
        "post_count_a": int(face_a.get("post_count") or 0),
        "post_count_b": int(face_b.get("post_count") or 0),
        "sample_texts_a": _samples(list(face_a.get("representative_posts") or [])),
        "sample_texts_b": _samples(list(face_b.get("representative_posts") or [])),
        "is_duplicate": "",
    }


def build_rows(edition: dict) -> list[dict]:
    index = _index(_catalogs(edition))
    rows: list[dict] = []
    for scope, left_name, right_name in PLANET_PAIRS:
        left = index.get((scope, left_name))
        right = index.get((scope, right_name))
        if left is None or right is None:
            raise KeyError(f"missing planet pair {scope}: {left_name!r} / {right_name!r}")
        rows.append((scope, left_name, right_name, left, right))
    planet_rows = rows
    face_rows = []
    for scope, planets in _catalogs(edition).items():
        for planet in planets:
            faces = list(planet.get("perspectives") or [])
            for i in range(len(faces)):
                for j in range(i + 1, len(faces)):
                    face_rows.append((scope, planet, faces[i], scope, planet, faces[j]))
    for scope_a, planet_a, title_a, scope_b, planet_b, title_b in EXTRA_FACE_PAIRS:
        left_planet = index[(scope_a, planet_a)]
        right_planet = index[(scope_b, planet_b)]
        face_rows.append(
            (
                scope_a,
                left_planet,
                _face(left_planet, title_a),
                scope_b,
                right_planet,
                _face(right_planet, title_b),
            )
        )
    # Shuffle so a block of similar titles is not a hint. The empty label
    # column is the yardstick; order must not sort by a similarity score.
    rng = random.Random(275)
    rng.shuffle(planet_rows)
    rng.shuffle(face_rows)
    written: list[dict] = []
    for number, (_scope, _left, _right, left, right) in enumerate(planet_rows, start=1):
        written.append(_planet_row(f"p{number:03d}", _scope, left, right))
    for number, (scope_a, planet_a, face_a, scope_b, planet_b, face_b) in enumerate(face_rows, start=1):
        written.append(
            _face_row(f"f{number:03d}", scope_a, planet_a, face_a, scope_b, planet_b, face_b)
        )
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the Oct 19 blind pair sheet")
    parser.add_argument("--edition", type=Path, required=True, help="Oct 19 public/data.json")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "evidence" / "275" / "oct19-pairs.csv",
    )
    args = parser.parse_args(argv)
    edition = json.loads(args.edition.read_text(encoding="utf-8"))
    if str(edition.get("last_updated")) != "2026-10-19":
        print(f"Refusing edition last_updated={edition.get('last_updated')!r}", file=sys.stderr)
        return 2
    rows = build_rows(edition)
    planets = [row for row in rows if row["level"] == "planet"]
    faces = [row for row in rows if row["level"] == "face"]
    if len(planets) < 55 or len(faces) < 55:
        print(f"Too few pairs: planets={len(planets)} faces={len(faces)}", file=sys.stderr)
        return 2
    if any(row["is_duplicate"] for row in rows):
        print("is_duplicate must stay empty", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(planets)} planet pairs and {len(faces)} face pairs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
