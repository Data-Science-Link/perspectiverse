"""Compare perspective-grouping approaches on a retained corpus snapshot.

The database is read only. Nothing here is written back into the repo.
Example::

    python -m pipeline.eval.grouping_eval --db /tmp/live_corpus.db --out /tmp/grouping_eval.json

Sentence embeddings are cached next to the output. ``--llm`` asks the
configured OpenAI-compatible model for 2–4 positions on a few hard planets
and assigns every post by embedding similarity. That is the only path that
spends a model call.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from pipeline.grouping import APPROACHES, assign_to_descriptions, ensure_two_sides, run_approach
from pipeline.store import connect, load_posts


def _l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def embed_texts(texts: list[str], cache: Path | None) -> np.ndarray:
    if cache is not None and cache.exists():
        cached = np.load(cache)
        if cached.shape[0] == len(texts):
            return cached
    from pipeline.embed import embed_minilm

    rows = []
    batch = 256
    started = time.monotonic()
    for begin in range(0, len(texts), batch):
        rows.append(embed_minilm(texts[begin : begin + batch]))
        print(f"Embedded {min(begin + batch, len(texts))}/{len(texts)} in {time.monotonic() - started:.0f}s")
    matrix = _l2(np.vstack(rows))
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, matrix)
    return matrix


def _examples(texts: list[str], matrix: np.ndarray, labels: list[int], face: int, limit: int = 2) -> list[str]:
    array = np.asarray(labels)
    members = np.flatnonzero(array == face)
    if members.size == 0:
        return []
    center = matrix[members].mean(axis=0)
    norm = float(np.linalg.norm(center))
    if norm:
        center = center / norm
    order = np.argsort(-(matrix[members] @ center))
    chosen = []
    for index in order[:limit]:
        chosen.append(texts[int(members[int(index)])][:280])
    return chosen


def _qualitative(texts: list[str], matrix: np.ndarray, packed: dict) -> list[dict]:
    faces = []
    if packed["dropped"]:
        return faces
    labels = packed["labels"]
    for face, (size, terms) in enumerate(zip(packed["sizes"], packed["terms"])):
        faces.append(
            {
                "face": face,
                "size": size,
                "label": ", ".join(terms) or "(no terms)",
                "posts": _examples(texts, matrix, labels, face),
            }
        )
    return faces


def _parse_positions(raw: str) -> list[str]:
    text = raw.strip()
    if "```" in text:
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    positions = payload.get("positions") if isinstance(payload, dict) else None
    if not isinstance(positions, list):
        return []
    cleaned = []
    for item in positions:
        line = str(item).strip()
        if line and line not in cleaned:
            cleaned.append(line)
    return cleaned[:6]


def llm_opposing_positions(texts: list[str], matrix: np.ndarray, generate, embed) -> dict:
    """One model call proposes positions. Posts are assigned locally."""
    from pipeline.grouping import _floor_for, _pack

    count = len(texts)
    sample = min(24, count)
    indexes = list(dict.fromkeys(np.linspace(0, count - 1, sample).round().astype(int).tolist()))
    numbered = "\n".join(f"{number}. {texts[index][:240]}" for number, index in enumerate(indexes, start=1))
    prompt = (
        "These short social posts are already about one topic. "
        "Propose 2 to 4 distinct positions people are taking. "
        "Positions must disagree or stress different claims, not paraphrase one view. "
        'Return JSON only: {"positions": ["one sentence", "another sentence"]}\n\n'
        f"Posts:\n{numbered}"
    )
    raw = generate(prompt)
    positions = _parse_positions(raw)
    if len(positions) < 2:
        packed = _pack(
            "llm_opposing",
            texts,
            matrix,
            None,
            dropped=True,
            forced=False,
            llm_calls=1,
            note="model did not return two positions",
        )
        return packed
    description_matrix = _l2(embed(positions))
    labels = assign_to_descriptions(matrix, description_matrix)
    scores = description_matrix @ description_matrix.T
    del scores
    # Side score: cosine to the second description minus cosine to the first.
    posts = _l2(matrix)
    side = posts @ description_matrix[1] - posts @ description_matrix[0]
    # More than two descriptions: keep the argmax, then only rebalance empties.
    labels = ensure_two_sides(labels, side, _floor_for(count, 2)) if len(positions) == 2 else labels
    if len(set(int(item) for item in labels)) < 2:
        labels = ensure_two_sides(np.zeros(count, dtype=int), side, _floor_for(count, 2))
    packed = _pack("llm_opposing", texts, matrix, labels, dropped=False, forced=False, llm_calls=1)
    packed["position_labels"] = positions
    packed["terms"] = [[position] for position in positions[: packed["k"]]]
    return packed


def _mean(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None and not row.get("dropped")]
    if not values:
        return None
    return round(float(sum(values) / len(values)), 3)


def evaluate_planets(planets: list[dict], approaches: list[str], *, seed: int = 0) -> dict:
    """``planets`` items have section, name, texts, matrix."""
    started = {}
    per_approach: dict[str, list[dict]] = {name: [] for name in approaches}
    for planet_number, planet in enumerate(planets, start=1):
        if planet_number == 1 or planet_number % 10 == 0:
            print(f"Grouping planet {planet_number}/{len(planets)}: {planet['section']} / {planet['name']}")
        for name in approaches:
            clock = time.perf_counter()
            packed = run_approach(name, planet["texts"], planet["matrix"], seed=seed)
            elapsed = time.perf_counter() - clock
            packed["section"] = planet["section"]
            packed["planet"] = planet["name"]
            packed["posts"] = len(planet["texts"])
            packed["seconds"] = round(elapsed, 4)
            per_approach[name].append(packed)
            started[name] = started.get(name, 0.0) + elapsed
    summary = []
    baseline_dropped = {
        (row["section"], row["planet"])
        for row in per_approach.get("baseline", [])
        if row["dropped"]
    }
    for name in approaches:
        rows = per_approach[name]
        kept = [row for row in rows if not row["dropped"]]
        on_baseline_drops = [
            row
            for row in rows
            if (row["section"], row["planet"]) in baseline_dropped and not row["dropped"]
        ]
        summary.append(
            {
                "approach": name,
                "planets": len(rows),
                "kept": len(kept),
                "dropped": len(rows) - len(kept),
                "mean_faces": _mean(kept, "k"),
                "mean_distinctness": _mean(kept, "distinctness"),
                "mean_distinctness_where_baseline_dropped": _mean(on_baseline_drops, "distinctness"),
                "mean_silhouette": _mean(kept, "silhouette"),
                "mean_term_overlap": _mean(kept, "term_overlap"),
                "mean_ctfidf_overlap": _mean(kept, "ctfidf_overlap"),
                "mean_balance": _mean(kept, "balance"),
                "llm_calls": int(sum(row["llm_calls"] for row in rows)),
                "seconds": round(started.get(name, 0.0), 2),
            }
        )
    return {"summary": summary, "rows": per_approach, "baseline_dropped": baseline_dropped}


def _candidate_planets(posts: list[dict], matrix: np.ndarray, *, seed: int, catalog_size: int) -> list[dict]:
    from pipeline.schema import CATEGORIES
    from pipeline.topics import cluster_texts

    by_section: dict[str, list[int]] = {}
    for index, post in enumerate(posts):
        section = str(post.get("section") or "")
        if section in CATEGORIES:
            by_section.setdefault(section, []).append(index)
    planets = []
    for section, indices in sorted(by_section.items(), key=lambda item: (-len(item[1]), item[0])):
        floor = max(8, len(indices) // 200)
        if len(indices) < floor:
            print(f"{section}: {len(indices)} posts, below floor {floor}")
            continue
        sub = matrix[indices]
        texts = [posts[index]["clean_text"] for index in indices]
        try:
            clustered = cluster_texts(
                texts,
                min_cluster_size=floor,
                cluster_backend="embedding",
                seed=seed,
                catalog_size=min(20, catalog_size + 10),
                embed=lambda _texts, rows=sub: rows,
                authors=[str(posts[index].get("author") or "") for index in indices],
            )
        except Exception as exc:  # noqa: BLE001 - one section should not hide the others
            print(f"{section}: clustering failed ({type(exc).__name__}: {exc})")
            continue
        print(f"{section}: {len(clustered['topics'])} candidate planets from {len(indices)} posts")
        for topic in clustered["topics"]:
            member_index = topic["member_indices"]
            planets.append(
                {
                    "section": section,
                    "name": " ".join(topic["terms"]) or f"{section}-{topic['id']}",
                    "texts": [texts[index] for index in member_index],
                    "matrix": sub[member_index],
                    "hard_case": section == "Health",
                }
            )
    return planets


def _sample_planets(planets: list[dict], rows: dict, limit: int = 5) -> list[dict]:
    """Health planets first (drops, then the rest), then other baseline drops."""
    baseline = {row["planet"] + "|" + row["section"]: row for row in rows.get("baseline", [])}

    def dropped(planet: dict) -> bool:
        return bool(baseline.get(planet["name"] + "|" + planet["section"], {}).get("dropped"))

    health = [planet for planet in planets if planet["section"] == "Health"]
    health.sort(key=lambda planet: (0 if dropped(planet) else 1, -len(planet["texts"]), planet["name"]))
    chosen = health[:3]
    others = [planet for planet in planets if planet not in chosen and dropped(planet)]
    others.sort(key=lambda planet: (-len(planet["texts"]), planet["section"], planet["name"]))
    for planet in others:
        if len(chosen) >= limit:
            break
        chosen.append(planet)
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare face-grouping approaches on a corpus snapshot")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--catalog-size", type=int, default=10)
    parser.add_argument("--llm", action="store_true", help="Spend a few model calls on hard planets")
    parser.add_argument("--llm-max", type=int, default=8)
    args = parser.parse_args()
    connection = connect(args.db)
    try:
        posts = load_posts(connection)
    finally:
        connection.close()
    posts = [post for post in posts if post.get("is_claim") is True and post.get("clean_text")]
    print(f"Loaded {len(posts)} claims from {args.db}")
    cache = args.cache or args.out.with_suffix(".embeddings.npy")
    matrix = embed_texts([post["clean_text"] for post in posts], cache)
    planets = _candidate_planets(posts, matrix, seed=args.seed, catalog_size=args.catalog_size)
    approaches = list(APPROACHES)
    clock = time.perf_counter()
    report = evaluate_planets(planets, approaches, seed=args.seed)
    print(f"Grouped {len(planets)} planets in {time.perf_counter() - clock:.1f}s")
    samples = _sample_planets(planets, report["rows"])
    qualitative = []
    for planet in samples:
        block = {"section": planet["section"], "planet": planet["name"], "posts": len(planet["texts"]), "approaches": {}}
        for name in ("baseline", "ward", "ctfidf", "keep_floor"):
            packed = next(
                row
                for row in report["rows"][name]
                if row["planet"] == planet["name"] and row["section"] == planet["section"]
            )
            block["approaches"][name] = {
                "dropped": packed["dropped"],
                "k": packed["k"],
                "distinctness": packed["distinctness"],
                "term_overlap": packed["term_overlap"],
                "balance": packed["balance"],
                "sizes": packed["sizes"],
                "note": packed["note"],
                "faces": _qualitative(planet["texts"], planet["matrix"], packed),
            }
        qualitative.append(block)

    llm_rows = []
    if args.llm and samples:
        from pipeline.embed import embed_minilm
        from pipeline.label import _openai_generate, resolve_openai_model

        model = resolve_openai_model(None)
        generate = lambda prompt, chosen=model: _openai_generate(prompt, chosen)  # noqa: E731
        spent = 0
        targets = [planet for planet in planets if planet["section"] == "Health"] or samples
        for planet in targets:
            if spent >= args.llm_max:
                break
            try:
                packed = llm_opposing_positions(planet["texts"], planet["matrix"], generate, embed_minilm)
            except Exception as exc:  # noqa: BLE001 - record the failure, keep the local table
                packed = {
                    "approach": "llm_opposing",
                    "dropped": True,
                    "llm_calls": 1,
                    "note": type(exc).__name__,
                    "k": 0,
                    "distinctness": 0.0,
                    "terms": [],
                    "sizes": [],
                    "labels": [],
                }
            spent += int(packed.get("llm_calls") or 0)
            llm_rows.append(
                {
                    "section": planet["section"],
                    "planet": planet["name"],
                    "dropped": packed["dropped"],
                    "k": packed.get("k"),
                    "distinctness": packed.get("distinctness"),
                    "llm_calls": packed.get("llm_calls"),
                    "note": packed.get("note"),
                    "positions": packed.get("position_labels") or packed.get("terms"),
                    "faces": _qualitative(planet["texts"], planet["matrix"], packed) if not packed["dropped"] else [],
                }
            )
        print(f"LLM opposing-position calls: {spent}")

    hard = []
    for row in report["rows"].get("baseline", []):
        if row["section"] != "Health":
            continue
        kept = next(
            item
            for item in report["rows"]["keep_floor"]
            if item["planet"] == row["planet"] and item["section"] == row["section"]
        )
        hard.append(
            {
                "section": row["section"],
                "planet": row["planet"],
                "posts": row["posts"],
                "baseline_dropped": row["dropped"],
                "baseline_note": row["note"],
                "keep_k": kept["k"],
                "keep_distinctness": kept["distinctness"],
                "keep_sizes": kept["sizes"],
                "keep_terms": kept["terms"],
                "keep_note": kept["note"],
            }
        )
    payload = {
        "posts": len(posts),
        "candidate_planets": len(planets),
        "health_planets": sum(1 for planet in planets if planet["section"] == "Health"),
        "health_baseline_dropped": sum(1 for row in hard if row["baseline_dropped"]),
        "summary": report["summary"],
        "hard_cases": hard,
        "qualitative": qualitative,
        "llm_opposing": llm_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    for row in report["summary"]:
        print(
            f"{row['approach']}: kept {row['kept']}/{row['planets']} "
            f"faces {row['mean_faces']} distinctness {row['mean_distinctness']} "
            f"on-drops {row['mean_distinctness_where_baseline_dropped']} "
            f"term_overlap {row['mean_term_overlap']} balance {row['mean_balance']} "
            f"llm {row['llm_calls']} {row['seconds']}s"
        )


if __name__ == "__main__":
    main()
