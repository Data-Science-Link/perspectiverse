"""Offline embedding comparison for issue #104.

Replays the grouping on PR #114 (density balls, author cap of 3, same-story
attach) on the saved 9,832-post corpus. Thresholds for each model are
calibrated on a held-out split that excludes the story reference. The
reference is scored once, after the thresholds are locked.

No production modules are modified. No hosted embedding calls.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

from pipeline.cluster_math import salient_terms  # noqa: E402
from pipeline.grouping import density_labels  # noqa: E402
from pipeline.language import partition_posts  # noqa: E402
from pipeline.perspectives import split_perspectives  # noqa: E402
from pipeline.schema import CATEGORIES  # noqa: E402
from pipeline.store import connect, load_posts  # noqa: E402
from pipeline.topics import _cap_author_posts  # noqa: E402
import pipeline.grouping as grouping  # noqa: E402
import story_attach  # noqa: E402

REFERENCE_COMMIT = "28c93de9cfb7f43ba46fb3ecf94bb588fdde869c"
EXPECTED_URI_SHA = "6189f0ee54e5091ea20aec162c46eafffde63925259af9a0ea0e6b321a75ba7a"
EXPECTED_KEPT = 9832
CORPUS_DB = Path("/tmp/issue104/pipeline/data/live_corpus.db")
CACHE = Path("/tmp/issue104/emb")
OUT_DIR = Path(__file__).resolve().parent / "out"

# Production MiniLM operating point. Used as the control and as the
# percentile source for every other model.
STOCK = {
    "member": 0.50,
    "merge": 0.72,
    "mean": 0.60,
    "attach": 0.42,
    "fold": 0.55,
}
# Stems that name the frozen reference stories. They are not tuning targets.
REFERENCE_STEMS = {
    "ukrain",
    "ukraine",
    "russia",
    "russian",
    "kyiv",
    "putin",
    "zelensk",
    "zelensky",
    "gaza",
    "israel",
    "israeli",
    "hamas",
    "palestin",
    "palestine",
    "zionism",
    "zionist",
    "iran",
    "iranian",
    "epstein",
    "ice",
}
TUNE_SEED = 104
TUNE_SIZE = 1200
FLOOR = 5
AUTHOR_CAP = 3

# Local ONNX models fastembed 0.9 can run on a CPU Actions runner.
# e5-base-v2 and all-mpnet-base-v2 are not in that build.
MODELS = {
    "minilm": {
        "fastembed": "sentence-transformers/all-MiniLM-L6-v2",
        "prefix": "",
        "stock": True,
        "size_gb": 0.09,
        "dim": 384,
    },
    "bge-small": {
        "fastembed": "BAAI/bge-small-en-v1.5",
        "prefix": "",
        "stock": False,
        "size_gb": 0.067,
        "dim": 384,
    },
    "bge-base": {
        "fastembed": "BAAI/bge-base-en-v1.5",
        "prefix": "",
        "stock": False,
        "size_gb": 0.21,
        "dim": 768,
    },
    "gte-base": {
        "fastembed": "thenlper/gte-base",
        "prefix": "",
        "stock": False,
        "size_gb": 0.44,
        "dim": 768,
    },
    "nomic": {
        "fastembed": "nomic-ai/nomic-embed-text-v1.5",
        # Model card: clustering uses this prefix. fastembed does not add it.
        "prefix": "clustering: ",
        "stock": False,
        "size_gb": 0.52,
        "dim": 768,
    },
}


def rss_mb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024.0
    return 0.0


def hwm_mb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) / 1024.0
    return 0.0


def load_corpus() -> list[dict]:
    posts = load_posts(connect(CORPUS_DB))
    claims = [post for post in posts if post.get("is_claim") is True]
    kept, language, links = partition_posts(claims)
    if len(kept) != EXPECTED_KEPT or language != 56 or links != 112:
        raise SystemExit(
            f"Corpus filter mismatch: kept={len(kept)} language={language} links={links}"
        )
    digest = hashlib.sha256("\n".join(sorted(post["uri"] for post in kept)).encode()).hexdigest()
    if digest != EXPECTED_URI_SHA:
        raise SystemExit(f"URI hash {digest} != {EXPECTED_URI_SHA}")
    return kept


def load_reference() -> dict:
    import subprocess

    raw = subprocess.check_output(
        ["git", "show", f"{REFERENCE_COMMIT}:docs/evidence/issue-104/story_reference.json"],
        cwd=ROOT,
    )
    return json.loads(raw)


def l2(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def embed_texts(name: str, texts: list[str]) -> tuple[np.ndarray, dict]:
    spec = MODELS[name]
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.npy"
    if path.exists():
        matrix = np.load(path)
        meta = json.loads((CACHE / f"{name}.json").read_text())
        meta["cache"] = True
        return matrix, meta
    from fastembed import TextEmbedding

    before = rss_mb()
    started = time.perf_counter()
    model = TextEmbedding(spec["fastembed"], threads=4)
    loaded = time.perf_counter()
    after_load = rss_mb()
    prefixed = [spec["prefix"] + text for text in texts]
    rows = []
    batch = 64
    for begin in range(0, len(prefixed), batch):
        chunk = prefixed[begin : begin + batch]
        rows.extend(np.asarray(vector, dtype=np.float32) for vector in model.embed(chunk))
        if begin and begin % 2048 == 0:
            print(f"  {name}: embedded {begin}/{len(prefixed)}", flush=True)
    matrix = np.vstack(rows)
    elapsed = time.perf_counter() - started
    meta = {
        "model": name,
        "fastembed": spec["fastembed"],
        "prefix": spec["prefix"],
        "dim": int(matrix.shape[1]),
        "rows": int(matrix.shape[0]),
        "embed_seconds": round(elapsed, 2),
        "load_seconds": round(loaded - started, 2),
        "rss_before_mb": round(before, 1),
        "rss_after_load_mb": round(after_load, 1),
        "rss_after_embed_mb": round(rss_mb(), 1),
        "hwm_mb": round(hwm_mb(), 1),
        "catalog_size_gb": spec["size_gb"],
        "cache": False,
    }
    np.save(path, matrix)
    (CACHE / f"{name}.json").write_text(json.dumps(meta))
    del model
    gc.collect()
    print(f"  {name}: embed {elapsed:.1f}s dim={matrix.shape[1]} rss={meta['rss_after_embed_mb']}MB", flush=True)
    return matrix, meta


def tune_indices(posts: list[dict], reference_uris: set[str]) -> np.ndarray:
    pool = [index for index, post in enumerate(posts) if post["uri"] not in reference_uris]
    rng = np.random.default_rng(TUNE_SEED)
    chosen = rng.choice(pool, size=min(TUNE_SIZE, len(pool)), replace=False)
    return np.sort(chosen.astype(int))


# Capitalized tokens that are still not a subject. Kept out of the tuning stories.
_TUNE_GENERIC = frozenset(
    {
        "green",
        "black",
        "white",
        "thank",
        "street",
        "english",
        "south",
        "earth",
        "north",
        "angel",
        "andrew",
        "david",
        "susan",
        "howev",
        "however",
        "america",
        "american",
    }
)


def pseudo_stories(posts: list[dict], indices: np.ndarray) -> list[dict]:
    """Proper-name groups inside the tuning split.

    A stem counts when the original token is capitalized most of the time, so
    the group is Congress or Medicare rather than "much" or "country".
    Reference-story stems are skipped. The groups are only a scale for
    cosine thresholds. They are not the recall bar.
    """
    import re

    token_re = re.compile(r"[A-Za-z][A-Za-z']{4,}")
    cap: dict[str, int] = {}
    low: dict[str, int] = {}
    per_post: list[set[str]] = []
    for index in indices:
        found: set[str] = set()
        for token in token_re.findall(posts[int(index)]["clean_text"]):
            if "'" in token:
                continue
            stem = story_attach.subject_stem(token.lower())
            if len(stem) < 5:
                continue
            if any(story_attach.stems_match(stem, blocked) for blocked in REFERENCE_STEMS):
                continue
            if stem in _TUNE_GENERIC:
                continue
            found.add(stem)
            if token[0].isupper():
                cap[stem] = cap.get(stem, 0) + 1
            else:
                low[stem] = low.get(stem, 0) + 1
        per_post.append(found)
    ranked = []
    for stem, capped in cap.items():
        total = capped + low.get(stem, 0)
        if not (6 <= total <= 18):
            continue
        if capped < 0.6 * total:
            continue
        ranked.append(stem)
    ranked.sort(key=lambda stem: (-(cap[stem] + low.get(stem, 0)), -len(stem), stem))
    taken = np.zeros(len(indices), dtype=bool)
    groups = []
    for stem in ranked:
        members = [position for position, found in enumerate(per_post) if stem in found and not taken[position]]
        if len(members) < 6:
            continue
        for position in members:
            taken[position] = True
        groups.append(
            {
                "stem": stem,
                "local": members,
                "global": [int(indices[position]) for position in members],
            }
        )
        if len(groups) >= 8:
            break
    return groups


def _centroid(unit: np.ndarray) -> np.ndarray:
    center = unit.mean(axis=0)
    norm = float(np.linalg.norm(center))
    if norm == 0.0:
        return center
    return center / norm


def geometry(unit: np.ndarray, groups: list[dict], seed: int) -> dict[str, np.ndarray]:
    """Cosines that describe this model's scale on the tuning split only."""
    rng = np.random.default_rng(seed)
    to_center = []
    halves = []
    centers = []
    for group in groups:
        members = np.asarray(group["local"], dtype=int)
        rows = unit[members]
        center = _centroid(rows)
        centers.append(center)
        to_center.append(rows @ center)
        if members.size < 6:
            continue
        for draw in range(4):
            order = rng.permutation(members.size)
            cut = members.size // 2
            left = _centroid(rows[order[:cut]])
            right = _centroid(rows[order[cut:]])
            halves.append(float(left @ right))
    cross = []
    for left in range(len(centers)):
        for right in range(left + 1, len(centers)):
            cross.append(float(centers[left] @ centers[right]))
    return {
        "to_center": np.asarray(np.concatenate(to_center) if to_center else [0.0], dtype=float),
        "halves": np.asarray(halves or [0.0], dtype=float),
        "cross": np.asarray(cross or [0.0], dtype=float),
    }


def _percentile_rank(samples: np.ndarray, value: float) -> float:
    return float(np.mean(samples <= value))


def _at_rank(samples: np.ndarray, rank: float) -> float:
    return float(np.quantile(samples, min(max(rank, 0.0), 1.0)))


def enforce_order(thresholds: dict[str, float]) -> dict[str, float]:
    """Keep attach <= member <= fold <= mean <= merge. Do not widen a real gap.

    A forced 0.02 gap pushed gte-base's mean gate above its own cells.
    """
    order = ["attach", "member", "fold", "mean", "merge"]
    values = [float(thresholds[name]) for name in order]
    for index in range(1, len(values)):
        if values[index] < values[index - 1]:
            values[index] = values[index - 1]
    values = [min(max(value, 0.05), 0.99) for value in values]
    return {name: round(value, 4) for name, value in zip(order, values)}


def calibrate(minilm_geo: dict[str, np.ndarray], geo: dict[str, np.ndarray]) -> dict:
    """Put each stock threshold at the same rank of same-story cosine.

    MiniLM's 0.50 is about the 25th percentile of tuning-story posts to their
    own centroid, and 0.60 is about the median. A new model keeps those ranks
    on its own posts. Ranks are not taken from half-centroid or cross-story
    cosine: those sit on top of each other once a model is anisotropic, and
    matching them pushes every gate above the story.
    """
    source = minilm_geo["to_center"]
    ranks = {name: _percentile_rank(source, value) for name, value in STOCK.items()}
    mapped = {name: _at_rank(geo["to_center"], rank) for name, rank in ranks.items()}
    mapped = enforce_order(mapped)
    return {
        "ranks": {key: round(value, 4) for key, value in ranks.items()},
        "thresholds": mapped,
        "to_center_p50": round(float(np.median(geo["to_center"])), 4),
        "halves_p50": round(float(np.median(geo["halves"])), 4),
        "cross_p50": round(float(np.median(geo["cross"])), 4),
        "cross_p75": round(float(np.quantile(geo["cross"], 0.75)), 4),
        "merge_floor_bound": False,
    }


def cluster_posts(
    matrix: np.ndarray,
    texts: list[str],
    authors: list[str],
    thresholds: dict[str, float],
    *,
    seed: int = 0,
) -> np.ndarray:
    saved = (
        grouping._BALL_MEMBER,
        grouping._BALL_MERGE,
        grouping._BALL_MEAN,
        story_attach.ATTACH_COSINE,
        story_attach.FOLD_COSINE,
    )
    grouping._BALL_MEMBER = float(thresholds["member"])
    grouping._BALL_MERGE = float(thresholds["merge"])
    grouping._BALL_MEAN = float(thresholds["mean"])
    story_attach.ATTACH_COSINE = float(thresholds["attach"])
    story_attach.FOLD_COSINE = float(thresholds["fold"])
    try:
        raw = np.asarray(density_labels(matrix, min_cluster_size=FLOOR, seed=seed), dtype=int)
        before = raw.tolist()
        capped = _cap_author_posts(before, authors, AUTHOR_CAP)
        skip = [index for index, (left, right) in enumerate(zip(before, capped)) if left >= 0 and right < 0]
        labels, stats = story_attach.attach_same_story(matrix, texts, capped, skip=skip)
    finally:
        (
            grouping._BALL_MEMBER,
            grouping._BALL_MERGE,
            grouping._BALL_MEAN,
            story_attach.ATTACH_COSINE,
            story_attach.FOLD_COSINE,
        ) = saved
    labels = np.asarray(labels, dtype=int)
    # Groups the author cap shrank under the floor are noise, as in cluster_texts.
    for label in sorted(set(int(item) for item in labels if int(item) >= 0)):
        members = np.flatnonzero(labels == label)
        if members.size < FLOOR:
            labels[members] = -1
    labels.flags.writeable = True
    return labels, stats


def groups_of(labels: np.ndarray) -> dict[int, np.ndarray]:
    found: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        if int(label) < 0:
            continue
        found.setdefault(int(label), []).append(index)
    return {label: np.asarray(members, dtype=int) for label, members in found.items()}


def ranked_ids(labels: np.ndarray, authors: list[str]) -> list[tuple[int, int, int]]:
    """Publish order: more distinct authors, then more posts."""
    rows = []
    for label, members in groups_of(labels).items():
        voices = len({authors[int(index)] for index in members})
        rows.append((int(label), voices, int(members.size)))
    rows.sort(key=lambda item: (-item[1], -item[2], item[0]))
    return rows


def tuning_diagnostic(
    labels: np.ndarray,
    groups: list[dict],
    local_to_global: np.ndarray,
) -> dict:
    """How the locked thresholds treat the tuning stories. Not used to rescore the reference."""
    global_to_local = {int(global_index): local for local, global_index in enumerate(local_to_global)}
    local_labels = np.full(len(local_to_global), -1, dtype=int)
    for global_index, label in enumerate(labels):
        local = global_to_local.get(global_index)
        if local is not None:
            local_labels[local] = int(label)
    recalls = []
    owners = []
    for group in groups:
        members = np.asarray(group["local"], dtype=int)
        owned = local_labels[members]
        owned = owned[owned >= 0]
        if owned.size == 0:
            recalls.append(0.0)
            owners.append(None)
            continue
        values, counts = np.unique(owned, return_counts=True)
        best = int(values[int(np.argmax(counts))])
        recalls.append(float(counts.max() / len(group["local"])))
        owners.append(best)
    collisions = 0
    for left in range(len(owners)):
        for right in range(left + 1, len(owners)):
            if owners[left] is not None and owners[left] == owners[right] and recalls[left] >= 0.4 and recalls[right] >= 0.4:
                collisions += 1
    return {
        "pseudo_stories": [
            {"stem": group["stem"], "posts": len(group["local"]), "recall": round(recall, 3)}
            for group, recall in zip(groups, recalls)
        ],
        "mean_recall": round(float(np.mean(recalls) if recalls else 0.0), 3),
        "collisions": collisions,
    }


def gate_diagnostic(unit: np.ndarray, groups: list[dict], thresholds: dict[str, float]) -> dict:
    """Would the peel, the mean gate, and the merge keep the tuning stories apart.

    This does not run k-means. A 1,200-post grid shatters a 10-post story
    before the cosine gates are ever the reason, so the gates are scored directly.
    """
    keep_rates = []
    means = []
    centers = []
    for group in groups:
        rows = unit[np.asarray(group["local"], dtype=int)]
        center = _centroid(rows)
        centers.append(center)
        scores = rows @ center
        kept = scores[scores >= float(thresholds["member"])]
        keep_rates.append(float(kept.size / scores.size))
        means.append(float(kept.mean()) if kept.size else 0.0)
    cross = 0
    for left in range(len(centers)):
        for right in range(left + 1, len(centers)):
            if float(centers[left] @ centers[right]) >= float(thresholds["merge"]):
                cross += 1
    passing = sum(1 for value in means if value >= float(thresholds["mean"]))
    return {
        "mean_keep": round(float(np.mean(keep_rates) if keep_rates else 0.0), 3),
        "stories_passing_mean": passing,
        "stories": len(groups),
        "cross_merges": cross,
        "per_story": [
            {"stem": group["stem"], "keep": round(rate, 3), "kept_mean": round(mean, 3)}
            for group, rate, mean in zip(groups, keep_rates, means)
        ],
    }


def repair_thresholds(
    unit: np.ndarray,
    groups: list[dict],
    thresholds: dict[str, float],
) -> tuple[dict[str, float], dict]:
    """Loosen a gate that drops the tuning stories; raise a merge that glues them.

    Reference posts are not in `groups`.
    """
    current = dict(thresholds)
    notes = []
    diagnostic = {}
    for step in range(4):
        diagnostic = gate_diagnostic(unit, groups, current)
        notes.append({"step": step, "thresholds": dict(current), **{k: diagnostic[k] for k in ("mean_keep", "stories_passing_mean", "cross_merges")}})
        changed = False
        if diagnostic["mean_keep"] < 0.55:
            current["member"] = round(current["member"] - 0.02, 4)
            changed = True
        if diagnostic["stories_passing_mean"] < max(1, diagnostic["stories"] // 2):
            current["mean"] = round(current["mean"] - 0.02, 4)
            changed = True
        if diagnostic["cross_merges"] > 0:
            current["merge"] = round(min(0.95, current["merge"] + 0.02), 4)
            changed = True
        if not changed:
            break
        current = enforce_order(current)
    return current, {"steps": notes, "final": diagnostic}


def best_planet(labels: np.ndarray, wanted: set[str], uris: list[str]) -> tuple[int, int]:
    hits: dict[int, int] = {}
    for index, uri in enumerate(uris):
        if uri not in wanted:
            continue
        label = int(labels[index])
        if label < 0:
            continue
        hits[label] = hits.get(label, 0) + 1
    if not hits:
        return -1, 0
    label = max(hits, key=lambda item: (hits[item], -item))
    return label, hits[label]


def story_rows(labels: np.ndarray, posts: list[dict], stories: list[dict]) -> dict:
    uris = [post["uri"] for post in posts]
    rows = {}
    for story in stories:
        wanted = set(story["reference_uris"])
        label, hits = best_planet(labels, wanted, uris)
        size = int(np.sum(labels == label)) if label >= 0 else 0
        rows[story["id"]] = {
            "reference": len(wanted),
            "on_best": hits,
            "recall": round(hits / len(wanted), 4) if wanted else 0.0,
            "planet": label,
            "planet_size": size,
            "meets_100": bool(story.get("meets_100_post_bar")),
        }
    gaza = rows.get("gaza_israel", {})
    zionism = next((story for story in stories if story["id"] == "zionism_motion"), None)
    if zionism and gaza.get("planet", -1) >= 0:
        wanted = set(zionism["reference_uris"])
        on_gaza = sum(1 for index, uri in enumerate(uris) if uri in wanted and int(labels[index]) == gaza["planet"])
        rows["zionism_on_gaza_planet"] = on_gaza
    return rows


def coverage(labels: np.ndarray, authors: list[str], posts: list[dict]) -> dict:
    ranked = ranked_ids(labels, authors)
    top = ranked[:10]
    noise = int(np.sum(labels < 0))
    by_size = sorted(groups_of(labels).items(), key=lambda item: (-item[1].size, item[0]))
    from collections import Counter

    majority = {"World": 0, "Politics": 0}
    for label, members in groups_of(labels).items():
        counts = Counter(posts[int(index)].get("section") or "" for index in members)
        if not counts:
            continue
        section, _count = counts.most_common(1)[0]
        if section in majority and int(members.size) > majority[section]:
            majority[section] = int(members.size)
    return {
        "noise": noise,
        "noise_pct": round(100.0 * noise / len(posts), 2),
        "majority_section_lead": majority,
        "planets": len(ranked),
        "largest": int(by_size[0][1].size) if by_size else 0,
        "top10_posts": int(sum(size for _label, _voices, size in top)),
        "top10_pct": round(100.0 * sum(size for _label, _voices, size in top) / len(posts), 2),
        "size_top10_posts": int(sum(int(members.size) for _label, members in by_size[:10])),
        "top10_ids": [label for label, _voices, _size in top],
        "largest_ids": [int(label) for label, _members in by_size[:10]],
    }


def section_metrics(
    matrix: np.ndarray,
    posts: list[dict],
    authors: list[str],
    thresholds: dict[str, float],
    section: str,
) -> dict:
    indices = [index for index, post in enumerate(posts) if post.get("section") == section]
    if len(indices) < FLOOR:
        return {"posts": len(indices), "lead": 0, "top10_posts": 0, "planets": 0, "labels": None}
    sub_posts = [posts[index] for index in indices]
    sub_authors = [authors[index] for index in indices]
    texts = [post["clean_text"] for post in sub_posts]
    labels, stats = cluster_posts(matrix[indices], texts, sub_authors, thresholds)
    ranked = ranked_ids(labels, sub_authors)
    top = ranked[:10]
    by_size = sorted((int(members.size) for members in groups_of(labels).values()), reverse=True)
    return {
        "posts": len(indices),
        "lead": int(by_size[0]) if by_size else 0,
        "top10_posts": int(sum(size for _label, _voices, size in top)),
        "top10_pct": round(100.0 * sum(size for _label, _voices, size in top) / len(indices), 2),
        "planets": len(ranked),
        "largest_ids": [label for label, _voices, _size in sorted(ranked, key=lambda item: -item[2])[:3]],
        "labels": labels,
        "indices": indices,
        "attach": stats,
    }


def sample_planet(posts, matrix, members: np.ndarray, limit: int = 15) -> list[dict]:
    unit = l2(matrix)
    center = _centroid(unit[members])
    scores = unit[members] @ center
    order = np.argsort(-scores)
    picks = []
    if order.size <= limit:
        chosen = order
    else:
        edge = max(1, limit // 3)
        middle_start = max(edge, (order.size // 2) - edge // 2)
        chosen = np.unique(
            np.concatenate(
                [
                    order[:edge],
                    order[middle_start : middle_start + edge],
                    order[-edge:],
                ]
            )
        )
    for position in chosen[:limit]:
        index = int(members[int(position)])
        text = " ".join(posts[index]["clean_text"].split())
        picks.append(
            {
                "uri": posts[index]["uri"],
                "section": posts[index].get("section") or "",
                "cosine": round(float(scores[int(position)]), 3),
                "text": text[:320],
            }
        )
    return picks


def describe(labels, posts, matrix, ids: list[int]) -> list[dict]:
    described = []
    for label in ids:
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        texts = [posts[int(index)]["clean_text"] for index in members]
        described.append(
            {
                "label": int(label),
                "size": int(members.size),
                "terms": salient_terms(texts, limit=6),
                "posts": sample_planet(posts, matrix, members),
            }
        )
    return described


def face_counts(labels, posts, matrix, ids: list[int]) -> dict:
    faces = 0
    planets = 0
    multi = 0
    identical_terms = 0
    for label in ids:
        members = np.flatnonzero(labels == label)
        if members.size < FLOOR:
            continue
        planets += 1
        texts = [posts[int(index)]["clean_text"] for index in members]
        split = split_perspectives(texts, seed=0, matrix=matrix[members])
        count = len(split.get("faces") or []) or 1
        faces += count
        if count >= 2:
            multi += 1
            term_sets = [tuple(face.get("terms") or []) for face in split["faces"]]
            if len(term_sets) >= 2 and len(set(term_sets)) < len(term_sets):
                identical_terms += 1
    return {
        "planets": planets,
        "faces": faces,
        "multi_face_planets": multi,
        "planets_with_identical_face_terms": identical_terms,
    }


def section_face_plan(section_result: dict, posts, matrix) -> list[int]:
    labels = section_result.get("labels")
    if labels is None:
        return []
    authors = [posts[index].get("author") or "unknown" for index in section_result["indices"]]
    return [label for label, _voices, _size in ranked_ids(labels, authors)[:10]]


def reference_spread(matrix: np.ndarray, posts: list[dict], stories: list[dict]) -> dict:
    """Median cosine of a reference story to its own centroid. Not a threshold input."""
    unit = l2(matrix)
    uri_index = {post["uri"]: index for index, post in enumerate(posts)}
    found = {}
    for story in stories:
        indices = [uri_index[uri] for uri in story["reference_uris"] if uri in uri_index]
        if len(indices) < 2:
            continue
        rows = unit[np.asarray(indices)]
        center = _centroid(rows)
        scores = rows @ center
        found[story["id"]] = {
            "posts": len(indices),
            "median_to_centroid": round(float(np.median(scores)), 3),
            "p20_to_centroid": round(float(np.quantile(scores, 0.2)), 3),
        }
    return found


def cell_distributions(unit: np.ndarray) -> dict[str, np.ndarray]:
    """Raw k-means cells, before the peel. Reference rows are already left out."""
    from pipeline.cluster_math import cluster_kmeans

    count = int(unit.shape[0])
    grid = min(count, max(FLOOR, count // FLOOR))
    labels, _centers = cluster_kmeans(np.asarray(unit, dtype=np.float32), grid, seed=0)
    labels = np.asarray(labels)
    means = []
    centers = []
    member_scores = []
    for label in np.unique(labels):
        members = np.flatnonzero(labels == label)
        if members.size == 0:
            continue
        center = unit[members].mean(axis=0)
        norm = float(np.linalg.norm(center))
        if norm == 0.0:
            continue
        center = center / norm
        scores = unit[members] @ center
        means.append(float(scores.mean()))
        member_scores.append(scores)
        centers.append(center)
    stacked = np.vstack(centers)
    similarity = stacked @ stacked.T
    np.fill_diagonal(similarity, -1.0)
    return {
        "member": np.concatenate(member_scores),
        "cell_mean": np.asarray(means, dtype=float),
        "nearest_center": similarity.max(axis=1),
    }


def calibrate_cells(baseline: dict[str, np.ndarray], dist: dict[str, np.ndarray]) -> dict:
    """Match the stock gates to the same rank in the raw-cell distributions.

    On MiniLM the 0.50 peel and the 0.60 mean gate sit at the floor of a raw
    cell, not in the middle of it. Matching the middle of a small tuning story
    sets every gate above the cells and deletes them.
    """
    ranks = {
        "member": _percentile_rank(baseline["member"], STOCK["member"]),
        "attach": _percentile_rank(baseline["member"], STOCK["attach"]),
        "fold": _percentile_rank(baseline["member"], STOCK["fold"]),
        "mean": _percentile_rank(baseline["cell_mean"], STOCK["mean"]),
        "merge": _percentile_rank(baseline["nearest_center"], STOCK["merge"]),
    }
    mapped = {
        "member": _at_rank(dist["member"], ranks["member"]),
        "attach": _at_rank(dist["member"], ranks["attach"]),
        "fold": _at_rank(dist["member"], ranks["fold"]),
        "mean": _at_rank(dist["cell_mean"], ranks["mean"]),
        "merge": _at_rank(dist["nearest_center"], ranks["merge"]),
    }
    mapped = enforce_order(mapped)
    return {
        "mode": (
            "same rank in the raw k-means cell distributions on posts that are "
            "not in the story reference. MiniLM's peel and mean gate are near "
            "the floor of those cells; the merge is near the closest cell pairs."
        ),
        "ranks": {key: round(value, 4) for key, value in ranks.items()},
        "thresholds": mapped,
        "cell_mean_p50": round(float(np.median(dist["cell_mean"])), 4),
        "member_p50": round(float(np.median(dist["member"])), 4),
        "nearest_center_p50": round(float(np.median(dist["nearest_center"])), 4),
    }


def run_model(name: str, posts, stories, reference_uris, indices, groups, minilm_geo, mini_cells) -> dict:
    texts = [post["clean_text"] for post in posts]
    authors = [str(post.get("author") or "unknown") for post in posts]
    print(f"=== {name} ===", flush=True)
    matrix, embed_meta = embed_texts(name, texts)
    unit = l2(matrix)
    tune_unit = unit[indices]
    geo = geometry(tune_unit, groups, seed=TUNE_SEED)
    if MODELS[name]["stock"]:
        thresholds = dict(STOCK)
        calibration = {
            "mode": "stock MiniLM control, not retuned",
            "thresholds": thresholds,
            "to_center_p50": round(float(np.median(geo["to_center"])), 4),
            "halves_p50": round(float(np.median(geo["halves"])), 4),
            "cross_p50": round(float(np.median(geo["cross"])), 4),
            "cross_p75": round(float(np.quantile(geo["cross"], 0.75)), 4),
        }
        repair = {
            "steps": [],
            "final": gate_diagnostic(tune_unit, groups, thresholds),
        }
    else:
        nonref = np.asarray(
            [index for index, post in enumerate(posts) if post["uri"] not in reference_uris],
            dtype=int,
        )
        calibration = calibrate_cells(mini_cells, cell_distributions(unit[nonref]))
        thresholds = dict(calibration["thresholds"])
        repair = {"steps": [], "final": gate_diagnostic(tune_unit, groups, thresholds)}
    print(f"  thresholds {thresholds}", flush=True)
    started = time.perf_counter()
    labels, attach_stats = cluster_posts(matrix, texts, authors, thresholds)
    cluster_seconds = time.perf_counter() - started
    print(f"  clustered in {cluster_seconds:.1f}s attach={attach_stats}", flush=True)
    global_cov = coverage(labels, authors, posts)
    stories_scored = story_rows(labels, posts, stories)
    spread = reference_spread(matrix, posts, stories)
    sections = {}
    section_labels = {}
    for section in ("World", "Politics"):
        started = time.perf_counter()
        result = section_metrics(matrix, posts, authors, thresholds, section)
        elapsed = time.perf_counter() - started
        print(f"  {section} lead={result['lead']} top10={result['top10_posts']}/{result['posts']} in {elapsed:.1f}s", flush=True)
        section_labels[section] = result
        sections[section] = {
            key: value
            for key, value in result.items()
            if key not in {"labels", "indices"}
        }
        sections[section]["seconds"] = round(elapsed, 2)
    # Face counts on the planets the labeler would actually see: top 10 global
    # and top 10 in every section. This is local; no title model is called.
    face = face_counts(labels, posts, matrix, global_cov["top10_ids"])
    for section in CATEGORIES:
        if section in section_labels:
            result = section_labels[section]
        else:
            result = section_metrics(matrix, posts, authors, thresholds, section)
        ids = section_face_plan(result, posts, matrix)
        # split_perspectives needs the section matrix, so score faces here.
        if result.get("labels") is not None:
            sub_matrix = matrix[result["indices"]]
            sub_posts = [posts[index] for index in result["indices"]]
            part = face_counts(result["labels"], sub_posts, sub_matrix, ids)
            face["planets"] += part["planets"]
            face["faces"] += part["faces"]
            face["multi_face_planets"] += part["multi_face_planets"]
            face["planets_with_identical_face_terms"] += part["planets_with_identical_face_terms"]
    samples = {
        "global": describe(labels, posts, matrix, global_cov["largest_ids"]),
        "world": describe(
            section_labels["World"]["labels"],
            [posts[index] for index in section_labels["World"]["indices"]],
            matrix[section_labels["World"]["indices"]],
            section_labels["World"]["largest_ids"],
        )
        if section_labels["World"].get("labels") is not None
        else [],
        "politics": describe(
            section_labels["Politics"]["labels"],
            [posts[index] for index in section_labels["Politics"]["indices"]],
            matrix[section_labels["Politics"]["indices"]],
            section_labels["Politics"]["largest_ids"],
        )
        if section_labels["Politics"].get("labels") is not None
        else [],
    }
    return {
        "model": name,
        "fastembed": MODELS[name]["fastembed"],
        "embed": embed_meta,
        "calibration": calibration,
        "tuning_diagnostic": repair.get("final"),
        "repair": repair.get("steps"),
        "cluster_seconds": round(cluster_seconds, 2),
        "attach": attach_stats,
        "global": {key: value for key, value in global_cov.items() if key not in {"top10_ids", "largest_ids"}},
        "stories": stories_scored,
        "reference_spread": spread,
        "sections": sections,
        "faces": face,
        "samples": samples,
    }


def minilm_geometry(posts, indices, groups) -> dict[str, np.ndarray]:
    texts = [post["clean_text"] for post in posts]
    matrix, _meta = embed_texts("minilm", texts)
    return geometry(l2(matrix)[indices], groups, seed=TUNE_SEED)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["minilm", "bge-small", "bge-base", "gte-base", "nomic"])
    args = parser.parse_args()
    posts = load_corpus()
    reference = load_reference()
    stories = reference["stories"]
    reference_uris = {uri for story in stories for uri in story["reference_uris"]}
    indices = tune_indices(posts, reference_uris)
    groups = pseudo_stories(posts, indices)
    print(
        f"corpus {len(posts)} tune {len(indices)} pseudo {[group['stem'] for group in groups]}",
        flush=True,
    )
    if len(groups) < 4:
        raise SystemExit("tuning split did not yield enough pseudo-stories")
    geo = minilm_geometry(posts, indices, groups)
    nonref = np.asarray(
        [index for index, post in enumerate(posts) if post["uri"] not in reference_uris],
        dtype=int,
    )
    print(f"cell distributions on {len(nonref)} non-reference posts", flush=True)
    mini_cells = cell_distributions(l2(np.load(CACHE / "minilm.npy"))[nonref])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in args.models:
        result = run_model(name, posts, stories, reference_uris, indices, groups, geo, mini_cells)
        # Samples are large. Keep them beside the metrics.
        samples = result.pop("samples")
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(result, indent=2))
        (OUT_DIR / f"{name}.samples.json").write_text(json.dumps(samples, indent=2))
        print(f"wrote {path}", flush=True)
        brief = {
            story: result["stories"][story]["recall"]
            for story in ("ukraine_russia", "gaza_israel", "iran_war", "ice", "epstein")
        }
        print(
            f"RESULT {name} recall={brief} noise={result['global']['noise_pct']} "
            f"top10={result['global']['top10_pct']} world={result['sections']['World']['lead']} "
            f"politics_lead={result['sections']['Politics']['lead']} "
            f"politics_cov={result['sections']['Politics']['top10_pct']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
