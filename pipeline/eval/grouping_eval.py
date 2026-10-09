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
        floor = max(2, 8)
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
                catalog_size=10_000,
                embed=lambda _texts, rows=sub: rows,
                authors=[str(posts[index].get("author") or "") for index in indices],
            )
        except Exception as exc:  # noqa: BLE001 - one section should not hide the others
            print(f"{section}: clustering failed ({type(exc).__name__}: {exc})")
            continue
        print(
            f"{section}: {len(clustered['topics'])} candidate planets from {len(indices)} posts "
            f"({clustered['noise_count']} noise)"
        )
        shown = clustered["topics"][: min(20, int(catalog_size) + 10)]
        for topic in shown:
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


def _add_calls(total: dict, extra: dict) -> None:
    for key in ("faces", "names", "briefs", "finalize_faces"):
        total[key] = int(total.get(key) or 0) + int(extra.get(key) or 0)


def _zero_calls() -> dict:
    return {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}


def _stamp_section(planets: list[dict], section: str) -> list[dict]:
    stamped = []
    for planet in planets:
        row = dict(planet)
        if section and not row.get("section"):
            row["section"] = section
        stamped.append(row)
    return stamped


def catalog_walk(records: list[dict], keep: int, *, split_stories: bool) -> dict:
    """Publish up to ``keep`` planets in candidate order.

    ``split_stories`` false is the old rule: a glued candidate is dropped and
    the next candidate takes the slot. True keeps each story, still stopping
    at the catalog ceiling. Pieces under the planet-post floor are already
    absent from ``planet_objs``; ``floor_excluded`` counts them.
    """
    kept = []
    dropped = 0
    split_candidates = 0
    skipped_stories = 0
    floor_excluded = 0
    drafted = 0
    calls = _zero_calls()
    # Face labels and names spent on the stories themselves, not on the
    # glued candidate that was labeled only to notice the split.
    gross_split = _zero_calls()
    for record in records:
        if len(kept) >= keep:
            break
        drafted += 1
        spent = record.get("label_calls") or _zero_calls()
        detection = int(record.get("detection_faces") or 0)
        floor_excluded += int(record.get("floor_excluded") or 0)
        section = str(record.get("section") or "")
        if record.get("kind") == "split":
            split_candidates += 1
            skipped_stories += int(record.get("skipped") or 0)
            if not split_stories:
                calls["faces"] += detection
                dropped += 1
                continue
            _add_calls(calls, spent)
            gross_split["faces"] += max(0, int(spent.get("faces") or 0) - detection)
            gross_split["names"] += int(spent.get("names") or 0)
            gross_split["briefs"] += int(spent.get("briefs") or 0)
            room = keep - len(kept)
            chosen = _stamp_section(list(record.get("planet_objs") or [])[:room], section)
            if not chosen:
                dropped += 1
                continue
            kept.extend(chosen)
            continue
        _add_calls(calls, spent)
        if record.get("kind") != "keep" or not record.get("planet_objs"):
            dropped += 1
            continue
        kept.extend(_stamp_section([record["planet_objs"][0]], section))
    return {
        "candidates_drafted": drafted,
        "kept": len(kept),
        "dropped": dropped,
        "split_candidates": split_candidates if split_stories else 0,
        "skipped_stories": skipped_stories if split_stories else 0,
        "floor_excluded": floor_excluded if split_stories else 0,
        "label_calls": calls,
        "gross_split_calls": gross_split,
        "planets": kept,
    }


def _planet_brief(planet: dict) -> dict:
    faces = []
    for face in planet.get("perspectives") or []:
        posts = []
        for post in (face.get("representative_posts") or [])[:2]:
            text = " ".join(str(post.get("text") or "").split())
            if text:
                posts.append(text[:220])
        faces.append(
            {
                "title": face.get("title"),
                "volume_percent": face.get("volume_percent"),
                "posts": posts,
            }
        )
    return {
        "name": planet.get("name"),
        "post_count": planet.get("post_count"),
        "face_distinctness": planet.get("face_distinctness"),
        "faces": faces,
    }


def _draft_record(section: str, posts: list[dict], matrix, topic: dict, base_context: dict) -> dict:
    from pipeline.live import _draft_planet, _bundles_from

    clustered = {"topics": [topic], "matrix": matrix, "assignments": [], "noise_count": 0}
    stats: list[dict] = []
    context = dict(base_context)
    context["section"] = section
    context["draft_stats"] = stats
    context.pop("story_calls", None)
    try:
        result, log = _draft_planet(posts, clustered, topic, context)
    except Exception as exc:  # noqa: BLE001 - one candidate must not hide the table
        return {
            "section": section,
            "terms": " ".join(topic.get("terms") or []),
            "posts": len(topic.get("member_indices") or []),
            "kind": "drop",
            "detection_faces": 0,
            "skipped": 0,
            "label_calls": _zero_calls(),
            "planet_objs": [],
            "log": [f"{type(exc).__name__}: {exc}"],
        }
    info = stats[0] if stats else {}
    planets = [_planet_brief(bundle["planet"]) for bundle in _bundles_from(result)]
    return {
        "section": section,
        "terms": " ".join(str(term) for term in (topic.get("terms") or [])),
        "posts": len(topic.get("member_indices") or []),
        "kind": info.get("kind") or ("drop" if not planets else "keep"),
        "detection_faces": int((result or {}).get("detection_faces") or info.get("detection_faces") or 0),
        "skipped": int((result or {}).get("skipped") or info.get("skipped") or 0),
        "floor_excluded": int((result or {}).get("floor_excluded") or info.get("floor_excluded") or 0),
        "excluded": list((result or {}).get("excluded") or info.get("excluded") or []),
        "label_calls": dict(info.get("label_calls") or (result or {}).get("label_calls") or _zero_calls()),
        "planet_objs": planets,
        "log": list(log),
    }


def _section_candidates(posts: list[dict], matrix: np.ndarray, *, seed: int, catalog_size: int) -> list[dict]:
    """Same section clustering as the harness, keeping the posts for drafting."""
    from pipeline.schema import CATEGORIES
    from pipeline.topics import cluster_texts

    grouped: list[dict] = []
    by_section: dict[str, list[int]] = {}
    for index, post in enumerate(posts):
        section = str(post.get("section") or "")
        if section in CATEGORIES:
            by_section.setdefault(section, []).append(index)
    order = sorted(by_section, key=lambda name: (-len(by_section[name]), name))
    pools = [("All topics", list(range(len(posts))))] + [(name, by_section[name]) for name in order]
    for section, indices in pools:
        floor = max(2, 8)
        if len(indices) < floor:
            print(f"{section}: {len(indices)} posts, below floor {floor}")
            continue
        sub = matrix[indices]
        section_posts = [posts[index] for index in indices]
        texts = [post["clean_text"] for post in section_posts]
        try:
            clustered = cluster_texts(
                texts,
                min_cluster_size=floor,
                cluster_backend="embedding",
                seed=seed,
                catalog_size=10_000,
                embed=lambda _texts, rows=sub: rows,
                authors=[str(post.get("author") or "") for post in section_posts],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{section}: clustering failed ({type(exc).__name__}: {exc})")
            continue
        print(
            f"{section}: {len(clustered['topics'])} candidate planets from {len(indices)} posts "
            f"({clustered['noise_count']} noise)"
        )
        grouped.append(
            {
                "section": section,
                "posts": section_posts,
                "matrix": sub,
                "topics": list(clustered["topics"][: min(20, int(catalog_size) + 10)]),
                "candidate_count": len(clustered["topics"]),
                "noise_count": int(clustered["noise_count"]),
                "post_count": len(indices),
            }
        )
    return grouped


def _post_mass(planets: list[dict], section: str | None = None) -> int:
    chosen = planets
    if section is not None:
        chosen = [planet for planet in planets if planet.get("section") == section]
    return sum(int(planet.get("post_count") or 0) for planet in chosen)


def _smallest_planet(planets: list[dict]) -> dict | None:
    if not planets:
        return None
    planet = min(planets, key=lambda item: (int(item.get("post_count") or 0), str(item.get("name") or "")))
    return {
        "name": planet.get("name"),
        "section": planet.get("section"),
        "posts": int(planet.get("post_count") or 0),
    }


def evaluate_story_splits(
    posts: list[dict],
    matrix: np.ndarray,
    *,
    seed: int,
    catalog_size: int,
    min_planet_posts: int | None = None,
) -> dict:
    """Before/after the different-stories drop, on the same candidate planets.

    Labels are the local heuristic, so this spends no model calls. The split
    itself uses ``specific_shared_words``, the same signal as the daily job.
    Call counts are the face labels plus planet names the network backend
    would spend (a repair call or a brief rewrite is not included).
    """
    from pipeline.live import _label_context

    from pipeline.grouping import MIN_PLANET_POSTS

    floor = MIN_PLANET_POSTS if min_planet_posts is None else int(min_planet_posts)
    context = _label_context(
        {
            "label_backend": "heuristic",
            "representative_posts": 12,
            "seed": seed,
            "label_workers": 0,
            "min_planet_posts": floor,
        }
    )
    sections = _section_candidates(posts, matrix, seed=seed, catalog_size=catalog_size)
    drafted: dict[str, list[dict]] = {}
    for block in sections:
        rows = []
        topics = block["topics"]
        for number, topic in enumerate(topics, start=1):
            if number == 1 or number % 10 == 0 or number == len(topics):
                print(f"Drafting {block['section']} {number}/{len(topics)}")
            rows.append(_draft_record(block["section"], block["posts"], block["matrix"], topic, context))
        drafted[block["section"]] = rows

    def combine(mode: str) -> dict:
        kept = dropped = split_candidates = skipped = floor_excluded = drafted_n = 0
        calls = _zero_calls()
        gross_split = _zero_calls()
        published: list[dict] = []
        per_section = []
        for section, rows in drafted.items():
            walked = catalog_walk(rows, catalog_size, split_stories=mode == "after")
            kept += walked["kept"]
            dropped += walked["dropped"]
            split_candidates += walked["split_candidates"]
            skipped += walked["skipped_stories"]
            floor_excluded += walked["floor_excluded"]
            drafted_n += walked["candidates_drafted"]
            published.extend(walked["planets"])
            _add_calls(calls, walked["label_calls"])
            _add_calls(gross_split, walked["gross_split_calls"])
            per_section.append(
                {
                    "section": section,
                    "candidates": len(rows),
                    "drafted": walked["candidates_drafted"],
                    "kept": walked["kept"],
                    "dropped": walked["dropped"],
                    "split_candidates": walked["split_candidates"],
                    "skipped_stories": walked["skipped_stories"],
                    "floor_excluded": walked["floor_excluded"],
                    "post_mass": _post_mass(walked["planets"]),
                    "smallest_posts": (_smallest_planet(walked["planets"]) or {}).get("posts"),
                    "label_calls": walked["label_calls"],
                }
            )
        smallest = _smallest_planet(published)
        return {
            "candidates_in_pool": sum(len(rows) for rows in drafted.values()),
            "candidates_drafted": drafted_n,
            "kept": kept,
            "dropped": dropped,
            "split_candidates": split_candidates,
            "skipped_stories": skipped,
            "floor_excluded": floor_excluded,
            "post_mass": _post_mass(published),
            "post_mass_politics": _post_mass(published, "Politics"),
            "post_mass_health": _post_mass(published, "Health"),
            "smallest_planet": smallest,
            "label_calls": calls,
            "gross_split_calls": gross_split,
            "sections": per_section,
        }

    before = combine("before")
    after = combine("after")
    extra = {
        key: int(after["label_calls"][key]) - int(before["label_calls"][key])
        for key in ("faces", "names", "briefs")
    }
    extra["total"] = extra["faces"] + extra["names"] + extra["briefs"]

    examples = []
    for rows in drafted.values():
        for record in rows:
            if record["kind"] != "split" or len(record["planet_objs"]) < 2:
                continue
            examples.append(record)
    examples.sort(key=lambda record: (-record["posts"], record["section"], record["terms"]))
    shown = []
    for record in examples[:3]:
        shown.append(
            {
                "section": record["section"],
                "candidate_terms": record["terms"],
                "posts": record["posts"],
                "skipped": record["skipped"],
                "detection_face_labels": record["detection_faces"],
                "planets": record["planet_objs"],
            }
        )
    uncapped = {"candidates": 0, "before_kept": 0, "before_dropped": 0, "after_planets": 0, "after_dropped": 0, "split": 0}
    for rows in drafted.values():
        for record in rows:
            uncapped["candidates"] += 1
            if record["kind"] == "split":
                uncapped["before_dropped"] += 1
                uncapped["split"] += 1
                published = len(record["planet_objs"])
                uncapped["after_planets"] += published
                if published == 0:
                    uncapped["after_dropped"] += 1
            elif record["kind"] == "keep":
                uncapped["before_kept"] += 1
                uncapped["after_planets"] += 1
            else:
                uncapped["before_dropped"] += 1
                uncapped["after_dropped"] += 1
    excluded_examples = []
    surviving = []
    for rows in drafted.values():
        for record in rows:
            for piece in record.get("excluded") or []:
                excluded_examples.append(
                    {
                        "section": piece.get("section") or record["section"],
                        "label": piece.get("label"),
                        "posts": piece.get("posts"),
                        "parent_terms": record["terms"],
                        "parent_posts": record["posts"],
                        "samples": piece.get("samples") or [],
                    }
                )
            planets = [
                planet
                for planet in record.get("planet_objs") or []
                if int(planet.get("post_count") or 0) >= floor
            ]
            if record.get("kind") == "split" and len(planets) >= 2:
                surviving.append(
                    {
                        "section": record["section"],
                        "candidate_terms": record["terms"],
                        "posts": record["posts"],
                        "planets": planets,
                    }
                )
    excluded_examples.sort(key=lambda item: (-int(item.get("posts") or 0), item.get("section") or "", item.get("label") or ""))
    surviving.sort(key=lambda item: (-int(item.get("posts") or 0), item.get("section") or "", item.get("candidate_terms") or ""))
    pool_floor_excluded = sum(int(record.get("floor_excluded") or 0) for rows in drafted.values() for record in rows)
    return {
        "label_backend": "heuristic",
        "catalog_size": catalog_size,
        "min_planet_posts": floor,
        "pool_floor_excluded": pool_floor_excluded,
        "excluded_examples": excluded_examples[:12],
        "surviving_splits": surviving[:12],
        "before": before,
        "after": after,
        "extra_label_calls": extra,
        "gross_split_label_calls": after["gross_split_calls"],
        "uncapped_pool": uncapped,
        "examples": shown,
        "split_count": uncapped["split"],
    }


def production_census(
    posts: list[dict],
    matrix: np.ndarray,
    *,
    seed: int,
    catalog_size: int,
    min_cluster_size: int = 8,
) -> dict:
    """Candidate counts and a heuristic label of the published top planets.

    Clustering uses the production density path. Labeling stops at
    ``catalog_size`` per solar system and does not call a paid model.
    """
    from pipeline.live import _build_topics, _label_context
    from pipeline.schema import CATEGORIES
    from pipeline.topics import CANDIDATE_POOL, cluster_texts

    def block(name: str, indices: list[int]) -> dict:
        sub = matrix[indices]
        texts = [posts[index]["clean_text"] for index in indices]
        started = time.perf_counter()
        clustered = cluster_texts(
            texts,
            min_cluster_size=min_cluster_size,
            cluster_backend="embedding",
            seed=seed,
            catalog_size=CANDIDATE_POOL,
            embed=lambda _texts, rows=sub: rows,
            authors=[str(posts[index].get("author") or "") for index in indices],
        )
        elapsed = time.perf_counter() - started
        count = len(indices)
        noise = int(clustered["noise_count"])
        print(
            f"{name}: {len(clustered['topics'])} candidates, "
            f"{count - noise}/{count} posts in a group ({elapsed:.1f}s)"
        )
        return {
            "section": name,
            "posts": count,
            "candidates": len(clustered["topics"]),
            "noise": noise,
            "in_group": count - noise,
            "share": round((count - noise) / count, 4) if count else 0.0,
            "seconds": round(elapsed, 2),
            "top_sizes": [int(topic["size"]) for topic in clustered["topics"][:catalog_size]],
            "_clustered": clustered,
            "_posts": [posts[index] for index in indices],
        }

    rows = [block("All topics", list(range(len(posts))))]
    by_section: dict[str, list[int]] = {}
    for index, post in enumerate(posts):
        section = str(post.get("section") or "")
        if section in CATEGORIES:
            by_section.setdefault(section, []).append(index)
    for name in sorted(by_section, key=lambda item: (-len(by_section[item]), item)):
        if len(by_section[name]) < min_cluster_size:
            continue
        rows.append(block(name, by_section[name]))

    context = _label_context(
        {
            "label_backend": "heuristic",
            "representative_posts": 12,
            "seed": seed,
            "label_workers": 0,
            "openai_model": "",
        }
    )
    published = []
    for row in rows:
        built, _membership, _faces = _build_topics(
            row.pop("_posts"),
            row.pop("_clustered"),
            {},
            keep=catalog_size,
            context=context,
        )
        faces = [face for topic in built for face in topic["perspectives"]]
        mixed = [face for face in faces if "mixed remarks" in str(face.get("title") or "").lower()]
        published.append(
            {
                "section": row["section"],
                "published": len(built),
                "one_view": sum(1 for topic in built if len(topic["perspectives"]) == 1),
                "multi_view": sum(1 for topic in built if len(topic["perspectives"]) >= 2),
                "faces": len(faces),
                "mixed_faces": len(mixed),
                "all_mixed_planets": sum(
                    1
                    for topic in built
                    if topic["perspectives"]
                    and all("mixed remarks" in str(face.get("title") or "").lower() for face in topic["perspectives"])
                ),
                "mixed_names": sum(1 for topic in built if "mixed remarks" in str(topic.get("name") or "").lower()),
            }
        )
        print(
            f"  published {published[-1]['published']}: "
            f"{published[-1]['one_view']} one-view, {published[-1]['multi_view']} multi-view, "
            f"{published[-1]['mixed_faces']} mixed-remarks faces"
        )
    return {"min_cluster_size": min_cluster_size, "catalog_size": catalog_size, "groups": rows, "published": published}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare face-grouping approaches on a corpus snapshot")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--catalog-size", type=int, default=10)
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=5,
        help="Smallest dense ball that counts as a group (the live default is 5)",
    )
    parser.add_argument(
        "--census-only",
        action="store_true",
        help="Cluster with the production density path and heuristic-label the published top planets",
    )
    parser.add_argument("--llm", action="store_true", help="Spend a few model calls on hard planets")
    parser.add_argument("--llm-max", type=int, default=8)
    parser.add_argument(
        "--stories",
        action="store_true",
        help="Also compare dropping glued different-stories planets with splitting them",
    )
    parser.add_argument(
        "--planet-floor",
        type=int,
        default=None,
        help="Minimum posts for a published planet (default: MIN_PLANET_POSTS). 0 disables the floor.",
    )
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
    if args.census_only:
        census = production_census(
            posts,
            matrix,
            seed=args.seed,
            catalog_size=args.catalog_size,
            min_cluster_size=args.min_cluster_size,
        )
        payload = {"posts": len(posts), "census": census}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(args.out)
        return
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
    story_report = None
    if args.stories:
        print("Comparing the different-stories drop with a split")
        story_clock = time.perf_counter()
        story_report = evaluate_story_splits(
            posts,
            matrix,
            seed=args.seed,
            catalog_size=args.catalog_size,
            min_planet_posts=args.planet_floor,
        )
        print(f"Story comparison finished in {time.perf_counter() - story_clock:.1f}s")
        before = story_report["before"]
        after = story_report["after"]
        extra = story_report["extra_label_calls"]
        print(
            f"Planet floor {story_report['min_planet_posts']}. "
            f"Catalog walk before (main: drop glued stories): drafted {before['candidates_drafted']} "
            f"kept {before['kept']} dropped {before['dropped']} "
            f"calls faces {before['label_calls']['faces']} names {before['label_calls']['names']} "
            f"briefs {before['label_calls']['briefs']}"
        )
        print(
            f"Catalog walk after: drafted {after['candidates_drafted']} "
            f"kept {after['kept']} dropped {after['dropped']} "
            f"split {after['split_candidates']} "
            f"floor_excluded {after['floor_excluded']} "
            f"pool_floor_excluded {story_report['pool_floor_excluded']} "
            f"smallest {after['smallest_planet']} "
            f"post_mass {after['post_mass']} politics {after['post_mass_politics']} "
            f"health {after['post_mass_health']}"
        )
        for section in after["sections"]:
            print(
                f"  {section['section']}: kept {section['kept']} "
                f"floor_excluded {section['floor_excluded']} "
                f"post_mass {section['post_mass']} smallest {section['smallest_posts']}"
            )
        print(
            f"Catalog walk after calls: faces {after['label_calls']['faces']} "
            f"names {after['label_calls']['names']} briefs {after['label_calls']['briefs']}"
        )
        gross = story_report["gross_split_label_calls"]
        print(
            f"Extra label calls per run: {extra['total']} "
            f"(faces {extra['faces']}, names {extra['names']}, briefs {extra['briefs']})"
        )
        print(
            "Gross calls on the split planets themselves: "
            f"faces {gross['faces']} names {gross['names']} briefs {gross['briefs']}"
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
        "story_splits": story_report,
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
