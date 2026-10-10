#!/usr/bin/env python3
"""Paid before/after for the stance face pass. Nothing is published.

Refuses to start unless scripts/check_pipeline_overlap.py would exit 0.
Stops before a call that would push the metered spend over --max-usd.
The blind labeler is a different model family from grok-4.7 and from the
pipeline's DeepInfra Llama. Its prompt never receives an existing label.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.costs import get_meter
from pipeline.label import _openai_generate, resolve_openai_model
from pipeline.settings import load_dotenv
from pipeline.stance import (
    STANCES,
    _normalize_stance,
    build_merge_prompt,
    clears_second_stance,
    cohen_kappa,
    parse_merge_groups,
)

# DeepSeek, not Llama and not grok. The pipeline judge stays resolve_openai_model().
BLIND_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
BLIND_FALLBACK = "Qwen/Qwen3.5-9B"
INPUT_USD_PER_TOKEN = Decimal("0.10") / Decimal(1_000_000)
OUTPUT_USD_PER_TOKEN = Decimal("0.32") / Decimal(1_000_000)


def _spent() -> Decimal:
    total = Decimal("0")
    for attempt in get_meter().attempts():
        if attempt.cost_usd > 0:
            total += attempt.cost_usd
            continue
        total += INPUT_USD_PER_TOKEN * attempt.input_tokens
        total += OUTPUT_USD_PER_TOKEN * attempt.output_tokens
    return total


def _require_clear() -> None:
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/check_pipeline_overlap.py")])
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _call(prompt: str, model: str, cap: Decimal) -> str:
    if _spent() >= cap:
        raise RuntimeError(f"spend cap reached at ${_spent()}")
    return _openai_generate(prompt, model)


def _posts_by_uri(db_path: Path) -> dict[str, dict]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    found = {}
    for row in connection.execute("SELECT uri, author, text, clean_text, likes, section FROM posts"):
        found[row["uri"]] = {
            "uri": row["uri"],
            "author": row["author"] or "unknown",
            "text": row["text"] or "",
            "clean_text": row["clean_text"] or row["text"] or "",
            "likes": int(row["likes"] or 0),
            "section": row["section"] or "",
        }
    return found


def _face_rows(db_path: Path) -> dict[int, dict[int, list[tuple]]]:
    connection = sqlite3.connect(db_path)
    grouped: dict[int, dict[int, list[tuple]]] = {}
    for uri, topic_id, face_index, distance in connection.execute(
        "SELECT uri, topic_id, face_index, distance FROM perspectives"
    ):
        grouped.setdefault(int(topic_id), {}).setdefault(int(face_index), []).append(
            (uri, int(face_index), float(distance))
        )
    return grouped


def _blind_prompt(question: str, supports_means: str, opposes_means: str, texts: list[str]) -> str:
    lines = [
        "Label each post's stance on the question. You have not been shown anyone else's labels.",
        f"Question: {question}",
        f"supports means: {supports_means}",
        f"opposes means: {opposes_means}",
        "other-angle means the post is about the subject and is not a yes or no.",
        "off-topic means a different subject.",
        'Return JSON only: {"labels": [{"i": 1, "stance": "supports"}]}',
        "i starts at 1. Use only supports, opposes, other-angle, or off-topic.",
        "",
        "Posts:",
    ]
    for number, text in enumerate(texts, start=1):
        flat = " ".join(text.split())
        if len(flat) > 400:
            flat = flat[:399].rstrip() + "…"
        lines.append(f"{number}. {flat}")
    return "\n".join(lines)


def _label_batch(texts: list[str], prompt: str, model: str, cap: Decimal) -> list[str] | None:
    raw = _call(prompt, model, cap)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    numbered: dict[int, str] = {}
    for item in data.get("labels") or []:
        if not isinstance(item, dict):
            return None
        stance = _normalize_stance(item.get("stance"))
        if stance is None:
            return None
        try:
            numbered[int(item["i"])] = stance
        except (TypeError, ValueError):
            return None
    if set(numbered) != set(range(1, len(texts) + 1)):
        return None
    return [numbered[index] for index in range(1, len(texts) + 1)]


def blind_label_planets(reference: dict, posts: dict[str, dict], rows: dict, model: str, cap: Decimal, batch: int) -> dict:
    """Label every post on each reference planet. The prompt has no prior stance."""
    labeled = []
    failures = []
    for planet in reference["planets"]:
        topic_id = int(planet["planet_id"])
        ordered = []
        for face_index in sorted(rows.get(topic_id, {})):
            ordered.extend(sorted(rows[topic_id][face_index], key=lambda row: (row[2], row[0])))
        seen = set()
        unique = []
        for row in ordered:
            if row[0] in seen:
                continue
            seen.add(row[0])
            unique.append(row)
        texts_meta = []
        for uri, _position, distance in unique:
            post = posts.get(uri)
            if post is None:
                continue
            texts_meta.append((uri, distance, post["clean_text"] or post["text"]))
        for start in range(0, len(texts_meta), batch):
            chunk = texts_meta[start : start + batch]
            prompt = _blind_prompt(
                planet["stance_question"],
                planet["supports_means"],
                planet["opposes_means"],
                [item[2] for item in chunk],
            )
            try:
                labels = _label_batch([item[2] for item in chunk], prompt, model, cap)
            except Exception as exc:
                failures.append({"planet": planet["name"], "error": str(exc), "start": start})
                if "spend cap" in str(exc):
                    return {"model": model, "labels": labeled, "failures": failures, "stopped": "cap"}
                continue
            if not labels:
                failures.append({"planet": planet["name"], "error": "unreadable", "start": start})
                continue
            for (uri, distance, _text), stance in zip(chunk, labels):
                labeled.append(
                    {
                        "uri": uri,
                        "planet_id": topic_id,
                        "planet": planet["name"],
                        "distance": distance,
                        "stance": stance,
                    }
                )
    return {"model": model, "labels": labeled, "failures": failures, "stopped": None}


def _draft_from_published(planet: dict, face_rows: dict[int, list[tuple]], posts: dict[str, dict]) -> tuple[list, list[dict]]:
    drafted = []
    members = []
    seen = set()
    for position, face in enumerate(planet.get("perspectives") or []):
        rows = list(face_rows.get(position) or [])
        perspective = {
            "title": face.get("title") or "",
            "summary": face.get("summary") or "",
            "representative_posts": list(face.get("representative_posts") or []),
            "top_terms": list(face.get("top_terms") or []),
            "_face_member_uris": [uri for uri, _position, _distance in rows],
            "_draft_face_label": {
                "title": face.get("title") or "",
                "summary": face.get("summary") or "",
                "representative_posts": list(face.get("representative_posts") or []),
            },
        }
        drafted.append((perspective, rows, len(rows)))
        for uri, _position, _distance in rows:
            if uri in seen or uri not in posts:
                continue
            seen.add(uri)
            members.append(posts[uri])
    return drafted, members


def _face_snapshot(drafted: list) -> list[dict]:
    faces = []
    for perspective, rows, size in drafted:
        faces.append(
            {
                "title": perspective.get("title"),
                "post_count": int(size),
                "uris": [str(uri) for uri, _position, _distance in rows],
                "stance_locked": bool(perspective.get("stance_locked")),
                "mixed_remarks": str(perspective.get("title") or "").strip().lower() == "mixed remarks",
            }
        )
    return faces


def run_global(data: dict, posts: dict, grouped: dict, cap: Decimal) -> list[dict]:
    from pipeline.stance import apply_stance_pass

    model = resolve_openai_model(None)
    context = {
        "chosen": "openai",
        "limit": 36,
        "stance_second_face_share": 0.10,
        "story_calls": {},
        "stance_generate": lambda prompt: _call(prompt, model, cap),
    }
    results = []
    for planet in data["topics"]:
        topic_id = int(planet["id"])
        before_faces = [
            {"title": face.get("title"), "post_count": int(face.get("post_count") or 0)}
            for face in planet.get("perspectives") or []
        ]
        before_sum = sum(item["post_count"] for item in before_faces)
        drafted, members = _draft_from_published(planet, grouped.get(topic_id, {}), posts)
        before_uris = sorted(uri for _perspective, rows, _size in drafted for uri, _p, _d in rows)
        try:
            after, log = apply_stance_pass(drafted, members, context, subject=str(planet.get("name") or ""))
        except RuntimeError as exc:
            results.append(
                {
                    "scope": "global",
                    "id": topic_id,
                    "name": planet.get("name"),
                    "error": str(exc),
                    "before_post_count": int(planet.get("post_count") or 0),
                    "after_post_count": int(planet.get("post_count") or 0),
                }
            )
            if "spend cap" in str(exc):
                break
            continue
        after_uris = sorted(uri for _perspective, rows, _size in after for uri, _p, _d in rows)
        faces = _face_snapshot(after)
        results.append(
            {
                "scope": "global",
                "id": topic_id,
                "name": planet.get("name"),
                "before_post_count": int(planet.get("post_count") or 0),
                "before_face_sum": before_sum,
                "before_faces": before_faces,
                "after_post_count": sum(face["post_count"] for face in faces),
                "after_face_sum": sum(face["post_count"] for face in faces),
                "after_faces": [{key: face[key] for key in ("title", "post_count", "stance_locked", "mixed_remarks")} for face in faces],
                "uris_equal": before_uris == after_uris,
                "dropped_uris": sorted(set(before_uris) - set(after_uris)),
                "log": log,
                "stance_last": context.get("stance_last"),
                "face_uris": [{"title": face["title"], "uris": face["uris"]} for face in faces],
            }
        )
        context.pop("stance_last", None)
    results.append({"pipeline_model": model, "stance_calls": int(context["story_calls"].get("stance") or 0)})
    return results


def section_merge(data: dict, cap: Decimal) -> list[dict]:
    """Short same-stance call on published section faces. Counts are added, not dropped."""
    model = resolve_openai_model(None)
    rows = []
    for section, planets in (data.get("sections") or {}).items():
        for planet in planets:
            faces = list(planet.get("perspectives") or [])
            before_sum = sum(int(face.get("post_count") or 0) for face in faces)
            record = {
                "scope": section,
                "id": planet.get("id"),
                "name": planet.get("name"),
                "before_post_count": int(planet.get("post_count") or 0),
                "before_face_sum": before_sum,
                "before_faces": len(faces),
                "after_post_count": int(planet.get("post_count") or 0),
                "after_face_sum": before_sum,
                "after_faces": len(faces),
                "uris_equal": True,
                "dropped_uris": [],
                "note": "Section face membership is not in the saved corpus. Planet post_count is unchanged. One-face sample check was not run.",
            }
            if len(faces) < 2:
                rows.append(record)
                continue
            drafted = []
            members = []
            for index, face in enumerate(faces):
                snippets = list(face.get("representative_posts") or [])[:2]
                fake_rows = []
                for offset, snippet in enumerate(snippets):
                    uri = f"rep:{section}:{planet.get('id')}:{index}:{offset}"
                    fake_rows.append((uri, index, offset))
                    members.append(
                        {
                            "uri": uri,
                            "author": snippet.get("author") or "unknown",
                            "text": snippet.get("text") or "",
                            "clean_text": snippet.get("text") or "",
                            "likes": int(snippet.get("likes") or 0),
                        }
                    )
                if not fake_rows:
                    fake_rows = [(f"rep:{section}:{planet.get('id')}:{index}:0", index, 0)]
                drafted.append(
                    (
                        {"title": face.get("title") or "", "summary": face.get("summary") or ""},
                        fake_rows,
                        int(face.get("post_count") or 0),
                    )
                )
            try:
                raw = _call(build_merge_prompt(drafted, members), model, cap)
            except RuntimeError as exc:
                record["error"] = str(exc)
                rows.append(record)
                if "spend cap" in str(exc):
                    return rows
                continue
            groups = parse_merge_groups(raw, len(faces))
            if not groups:
                record["note"] = "Merge call unreadable. Faces and post counts unchanged."
                rows.append(record)
                continue
            after_faces = []
            for group in groups:
                count = sum(int(faces[index].get("post_count") or 0) for index in group)
                title = faces[max(group, key=lambda index: int(faces[index].get("post_count") or 0))].get("title")
                after_faces.append({"title": title, "post_count": count, "merged_from": group})
            after_sum = sum(item["post_count"] for item in after_faces)
            record["after_face_sum"] = after_sum
            record["after_faces"] = len(after_faces)
            record["after_face_detail"] = after_faces
            record["face_sum_equal"] = after_sum == before_sum
            record["note"] = "Merge adds the published face post_counts. The planet total is unchanged."
            rows.append(record)
    return rows


def coverage(planets: list[dict], scope_posts: int) -> dict:
    published = sum(int(planet.get("post_count") or 0) for planet in planets)
    face_sum = 0
    for planet in planets:
        face_sum += sum(int(face.get("post_count") or 0) for face in planet.get("perspectives") or [])
    return {
        "planets": len(planets),
        "published_posts": published,
        "face_post_sum": face_sum,
        "scope_posts": scope_posts,
        "coverage": (published / scope_posts) if scope_posts else None,
    }


def score_reference(global_results: list[dict], reference: dict, share: float) -> dict:
    by_id = {int(item["id"]): item for item in global_results if "face_uris" in item}
    planets = []
    missed = []
    duplicate_planets = []
    for planet in reference["planets"]:
        result = by_id.get(int(planet["planet_id"]))
        hand = {post["uri"]: post["stance"] for post in planet["posts"]}
        if result is None:
            planets.append({"name": planet["name"], "missing": True})
            continue
        face_rows = []
        for face in result["face_uris"]:
            labels = [hand[uri] for uri in face["uris"] if uri in hand]
            counts = Counter(labels)
            majority = counts.most_common(1)[0][0] if counts else None
            purity = (counts[majority] / len(labels)) if majority and labels else None
            face_rows.append(
                {
                    "title": face["title"],
                    "hand_posts": len(labels),
                    "counts": dict(counts),
                    "majority": majority,
                    "purity": purity,
                }
            )
        majors = [row["majority"] for row in face_rows if row["majority"] in {"supports", "opposes", "other-angle"}]
        dup = len(majors) >= 2 and len(set(majors)) < len(majors)
        if dup:
            duplicate_planets.append(planet["name"])
        sample_split, stance, found, ratio = clears_second_stance(planet["counts"], planet["sample_n"], share)
        still_one = len(result["face_uris"]) == 1
        miss = bool(planet.get("one_face_in_pipeline")) and still_one and sample_split
        if miss:
            missed.append(planet["name"])
        planets.append(
            {
                "name": planet["name"],
                "faces": face_rows,
                "duplicate_same_majority": dup,
                "still_one_face": still_one,
                "hand_second": stance,
                "hand_second_n": found,
                "hand_second_share": ratio,
                "missed_second_stance": miss,
            }
        )
    one_face = [planet["name"] for planet in reference["planets"] if planet.get("one_face_in_pipeline")]
    return {
        "threshold": share,
        "denominator": "stance sample (at most 40 posts), not the whole planet",
        "planets": planets,
        "duplicate_planets": duplicate_planets,
        "missed_second_stance": missed,
        "one_face_planets": one_face,
        "missed_of": f"{len(missed)} of {len(one_face)}",
    }


def threshold_table(label_rows: list[dict], reference: dict, whole: bool) -> list[dict]:
    by_planet: dict[str, list[str]] = {}
    sample_uris = {
        planet["name"]: {post["uri"] for post in planet["posts"]} for planet in reference["planets"]
    }
    for row in label_rows:
        if whole or row["uri"] in sample_uris.get(row["planet"], set()):
            by_planet.setdefault(row["planet"], []).append(row["stance"])
    table = []
    for planet in reference["planets"]:
        labels = by_planet.get(planet["name"], [])
        counts = {name: 0 for name in STANCES}
        for label in labels:
            if label in counts:
                counts[label] += 1
        entry = {"planet": planet["name"], "n": len(labels), "counts": counts, "thresholds": {}}
        for share in (0.05, 0.10, 0.15):
            kept, stance, found, ratio = clears_second_stance(counts, len(labels), share)
            entry["thresholds"][f"{share:.2f}"] = {
                "split": kept,
                "second": stance,
                "second_n": found,
                "share": ratio,
            }
        table.append(entry)
    return table


def agreement(reference: dict, blind_rows: list[dict]) -> dict:
    hand = {}
    for planet in reference["planets"]:
        for post in planet["posts"]:
            hand[post["uri"]] = post["stance"]
    blind = {row["uri"]: row["stance"] for row in blind_rows}
    shared = [uri for uri in hand if uri in blind]
    left = [hand[uri] for uri in shared]
    right = [blind[uri] for uri in shared]
    matched = sum(one == two for one, two in zip(left, right))
    disagreements = []
    for uri in shared:
        if hand[uri] != blind[uri]:
            planet_name = next(planet["name"] for planet in reference["planets"] if any(post["uri"] == uri for post in planet["posts"]))
            post = next(post for planet in reference["planets"] for post in planet["posts"] if post["uri"] == uri)
            disagreements.append(
                {
                    "uri": uri,
                    "planet": planet_name,
                    "snippet": post.get("snippet"),
                    "grok": hand[uri],
                    "blind": blind[uri],
                }
            )
    return {
        "n": len(shared),
        "matched": matched,
        "agreement": (matched / len(shared)) if shared else None,
        "cohen_kappa": cohen_kappa(left, right),
        "disagreements": disagreements,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("/tmp/stance/today/public/data.json"))
    parser.add_argument("--db", type=Path, default=Path("/tmp/stance/today/pipeline/data/live_corpus.db"))
    parser.add_argument("--reference", type=Path, default=Path("/tmp/stance_reference.json"))
    parser.add_argument("--out", type=Path, default=ROOT / "docs/evidence/face-stance")
    parser.add_argument("--max-usd", type=Decimal, default=Decimal("0.22"))
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--skip-blind", action="store_true")
    parser.add_argument("--skip-stance", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    _require_clear()
    started = time.monotonic()
    reference = json.loads(args.reference.read_text())
    data = json.loads(args.data.read_text())
    posts = _posts_by_uri(args.db)
    grouped = _face_rows(args.db)
    args.out.mkdir(parents=True, exist_ok=True)
    blind_model = BLIND_MODEL
    blind = {"model": None, "labels": [], "failures": [], "stopped": "skipped"}
    if not args.skip_blind:
        probe = _blind_prompt("Is this a test question?", "Yes.", "No.", ["One short sentence about the subject."])
        try:
            _call(probe, blind_model, args.max_usd)
        except Exception as exc:
            print(f"Blind model {blind_model} failed ({exc}). Trying {BLIND_FALLBACK}.")
            blind_model = BLIND_FALLBACK
        blind = blind_label_planets(reference, posts, grouped, blind_model, args.max_usd, args.batch)
    global_results = []
    sections = []
    if not args.skip_stance and _spent() < args.max_usd:
        global_results = run_global(data, posts, grouped, args.max_usd)
        if _spent() < args.max_usd:
            sections = section_merge(data, args.max_usd)
    section_counts = Counter(post["section"] for post in posts.values())
    before_coverage = {"global": coverage(data["topics"], int(data["total_posts"]))}
    for name, planets in (data.get("sections") or {}).items():
        before_coverage[name] = coverage(planets, int(section_counts.get(name) or 0))
    payload = {
        "pipeline_model": resolve_openai_model(None),
        "blind_model": blind.get("model") or blind_model,
        "reference_labeler": reference.get("model"),
        "spent_usd": format(float(_spent()), ".6f"),
        "seconds": round(time.monotonic() - started, 1),
        "calls": len(get_meter().attempts()),
        "blind": {"model": blind.get("model"), "n": len(blind.get("labels") or []), "failures": blind.get("failures"), "stopped": blind.get("stopped")},
        "agreement": agreement(reference, blind.get("labels") or []),
        "threshold_sample_blind": threshold_table(blind.get("labels") or [], reference, whole=False),
        "threshold_planet_blind": threshold_table(blind.get("labels") or [], reference, whole=True),
        "global": global_results,
        "sections": sections,
        "before_coverage": before_coverage,
        "score_against_grok_sample": score_reference(
            [item for item in global_results if "face_uris" in item], reference, 0.10
        ),
    }
    # Drop the bulky per-face URI lists from the score copy; keep them for rescoring.
    (args.out / "measure_raw.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (args.out / "blind_labels.json").write_text(
        json.dumps({"model": blind.get("model"), "labels": blind.get("labels"), "failures": blind.get("failures")}, indent=2),
        encoding="utf-8",
    )
    print(f"Spent ${payload['spent_usd']} in {payload['calls']} attempts, {payload['seconds']}s")
    print(f"Wrote {args.out / 'measure_raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
