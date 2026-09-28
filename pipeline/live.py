"""Live path: extract or load a fixture, cluster, label, write data.json."""

from __future__ import annotations

import json
import random
from pathlib import Path

from pipeline.assemble import assemble_payload, face_id, topic_name, write_payload
from pipeline.cleaning import clean_posts
from pipeline.data_sources.extract_bluesky import extract_posts
from pipeline.label import label_perspective
from pipeline.perspectives import select_representatives, split_perspectives
from pipeline.schema import infer_category, to_percents
from pipeline.settings import load_settings
from pipeline.store import connect, replace_posts, write_clusters
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
    search_queries = [item for item in (queries or []) if item] or list(settings["queries"])
    if fixture:
        raw_posts = load_fixture(fixture)
        source = "fixture"
    else:
        raw_posts = extract_posts(
            sample_size=int(settings["sample_size"]),
            window_hours=int(settings["window_hours"]),
            queries=search_queries,
            rng=random.Random(int(settings["seed"])),
        )
        source = "bluesky"
        if not raw_posts:
            raise RuntimeError("Bluesky returned no posts inside the 7-day window")

    cleaned = clean_posts(raw_posts)
    if not cleaned:
        raise RuntimeError("Every post was dropped by cleaning. Check the extract.")

    connection = connect(db_path)
    try:
        replace_posts(connection, cleaned)
        texts = [post["clean_text"] for post in cleaned]
        clustered = cluster_texts(
            texts,
            min_cluster_size=int(settings["min_cluster_size"]),
            cluster_backend=str(settings["cluster_backend"]),
            embedding_model=str(settings["embedding_model"]),
            seed=int(settings["seed"]),
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
        f"Live snapshot: {len(cleaned)} cleaned posts, "
        f"{clustered['noise_count']} excluded as noise, wrote {destination}"
    )
    return destination


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
        name = topic_name(terms)
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
            perspectives.append(
                {
                    "id": face_id(topic_id, position),
                    "title": label["title"],
                    "summary": label["summary"],
                    "volume_percent": face_volume,
                    "representative_posts": representatives,
                }
            )
            for index in face["member_indices"]:
                post = members[index]
                face_rows.append((post["uri"], topic_id, position, float(split["distances"][index])))
        for post in members:
            membership.append((post["uri"], topic_id))
        built.append(
            {
                "id": topic_id,
                "name": name,
                "category": infer_category(name, terms),
                "total_volume_percent": volume,
                "perspectives": perspectives,
            }
        )
    return built, membership, face_rows
