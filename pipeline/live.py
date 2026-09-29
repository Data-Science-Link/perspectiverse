"""Live path: rotate the retained corpus, cluster, label, write data.json."""

from __future__ import annotations

import json
import random
from pathlib import Path

from pipeline.assemble import assemble_payload, face_id, topic_name, write_payload
from pipeline.cleaning import clean_posts, drop_near_duplicates
from pipeline.corpus import TARGET_POSTS, rotate_corpus, scale_quotas, select_quality
from pipeline.data_sources.extract_bluesky import extract_grouped_posts, extract_posts
from pipeline.label import label_perspective, label_topic
from pipeline.perspectives import select_representatives, split_perspectives
from pipeline.schema import SYSTEM_SIZE, infer_category, to_percents
from pipeline.settings import load_settings
from pipeline.store import LIVE_CORPUS_DB, connect, load_posts, replace_posts, write_clusters
from pipeline.topics import cluster_texts


def load_fixture(path: Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Fixture must be a JSON list of posts")
    return payload


def run_live(
    *,
    fixture: Path | None = None,
    output: Path | None = None,
    config: Path | None = None,
    db_path: Path | None = None,
    queries: list[str] | None = None,
) -> Path:
    settings = load_settings(config)
    target = int(settings.get("sample_size") or TARGET_POSTS)
    database = Path(db_path) if db_path else LIVE_CORPUS_DB
    connection = connect(database)
    try:
        existing = load_posts(connection)
        cleaned, source = _collect_posts(existing, settings, fixture, queries, target)
        if not cleaned:
            raise RuntimeError("No quality posts in the retained corpus or the extract.")

        replace_posts(connection, cleaned)
        texts = [post["clean_text"] for post in cleaned]
        catalog_size = int(settings.get("catalog_size") or SYSTEM_SIZE)
        try:
            clustered = cluster_texts(
                texts,
                min_cluster_size=int(settings["min_cluster_size"]),
                cluster_backend=str(settings["cluster_backend"]),
                embedding_model=str(settings["embedding_model"]),
                seed=int(settings["seed"]),
                catalog_size=catalog_size,
            )
        except RuntimeError:
            clustered = cluster_texts(
                texts,
                min_cluster_size=3,
                cluster_backend="lexical",
                embedding_model=str(settings["embedding_model"]),
                seed=int(settings["seed"]),
                catalog_size=catalog_size,
            )
        topics, membership, face_rows = _build_topics(cleaned, clustered, settings)
        write_clusters(connection, membership, face_rows)
    finally:
        connection.close()

    payload = assemble_payload(
        topics,
        mode="live",
        source=source,
        total_posts=len(cleaned),
    )
    destination = write_payload(payload, output)
    print(
        f"Live snapshot: {len(cleaned)} quality posts, "
        f"{clustered['noise_count']} excluded as noise, wrote {destination}"
    )
    return destination


def _collect_posts(
    existing: list[dict],
    settings: dict,
    fixture: Path | None,
    queries: list[str] | None,
    target: int,
) -> tuple[list[dict], str]:
    if fixture:
        return clean_posts(load_fixture(fixture)), "fixture"

    first_fill = len(existing) < max(int(target * 0.5), 80)
    window_hours = int(settings["window_hours"] if first_fill else settings.get("refresh_hours") or 24)
    fetch_size = target if first_fill else max(40, int(round(target * float(settings.get("refresh_fraction") or (1 / 7)))))
    search_queries = [item for item in (queries or []) if item]
    incoming: list[dict] = []
    try:
        if search_queries:
            incoming = extract_posts(
                sample_size=max(fetch_size, 80),
                window_hours=window_hours,
                queries=search_queries,
                rng=random.Random(int(settings["seed"])),
            )
        else:
            groups = dict(settings.get("query_groups") or {})
            quotas = scale_quotas(max(fetch_size, 80), dict(settings.get("group_quotas") or {}))
            incoming = extract_grouped_posts(
                quotas=quotas,
                query_groups=groups,
                window_hours=window_hours,
                rng=random.Random(int(settings["seed"])),
            )
    except RuntimeError as exc:
        print(f"Bluesky extract failed ({exc}). Rebuilding from the retained corpus.")
        incoming = []

    fresh = drop_near_duplicates(clean_posts(incoming))
    if len(existing) < target:
        combined = drop_near_duplicates(existing + fresh)
        cleaned = select_quality(combined, target)
    else:
        cleaned = rotate_corpus(
            existing,
            fresh,
            target=target,
            drop_fraction=float(settings.get("refresh_fraction") or (1 / 7)),
        )
    source = "bluesky" if (fresh or existing) else "bluesky"
    if not cleaned and not existing:
        raise RuntimeError("Bluesky returned no quality posts and no corpus is retained")
    return drop_near_duplicates(cleaned or existing), source


def _build_topics(posts: list[dict], clustered: dict, settings: dict) -> tuple[list[dict], list[tuple], list[tuple]]:
    volumes = to_percents([topic["size"] for topic in clustered["topics"]])
    limit = int(settings["representative_posts"])
    backend = str(settings["label_backend"])
    seed = int(settings["seed"])
    built: list[dict] = []
    membership: list[tuple[str, int]] = []
    face_rows: list[tuple[str, int, int, float]] = []

    for topic, volume in zip(clustered["topics"], volumes):
        members = [posts[index] for index in topic["member_indices"]]
        member_texts = [post["clean_text"] for post in members]
        split = split_perspectives(member_texts, seed=seed)
        face_volumes = to_percents([face["size"] for face in split["faces"]])
        topic_id = topic["id"] + 1
        terms = list(topic["terms"])
        planet = label_topic(members, terms, backend=backend)
        name = str(planet.get("name") or topic_name(terms))
        perspectives = []
        ordered_faces = sorted(
            zip(split["faces"], face_volumes),
            key=lambda item: (-item[1], item[0]["index"]),
        )
        for position, (face, face_volume) in enumerate(ordered_faces):
            face_posts = [members[index] for index in face["member_indices"]]
            face_distances = [split["distances"][index] for index in face["member_indices"]]
            representatives = select_representatives(face_posts, face_distances, limit=limit)
            label = label_perspective(representatives, face["terms"] or terms, backend=backend)
            arguments = label.get("arguments") or []
            perspective = {
                "id": face_id(topic_id, position),
                "title": label["title"],
                "summary": label["summary"],
                "volume_percent": face_volume,
                "representative_posts": representatives,
            }
            if len(arguments) >= 2:
                perspective["arguments"] = arguments[:6]
            perspectives.append(perspective)
            for index in face["member_indices"]:
                post = members[index]
                face_rows.append((post["uri"], topic_id, position, float(split["distances"][index])))
        for post in members:
            membership.append((post["uri"], topic_id))
        built.append(
            {
                "id": topic_id,
                "name": name,
                "category": infer_category(name, terms, member_texts),
                "total_volume_percent": volume,
                "perspectives": perspectives,
            }
        )
    return built, membership, face_rows
