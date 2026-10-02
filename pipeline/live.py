"""Live path: rotate the retained corpus, cluster, label, write data.json."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from pipeline.assemble import assemble_payload, face_id, topic_name, write_payload
from pipeline.cleaning import clean_posts, drop_near_duplicates
from pipeline.corpus import (
    TARGET_POSTS,
    cap_sample,
    posts_on_utc_date,
    retain_window,
    utc_dates_present,
    window_utc_dates,
)
from pipeline.data_sources.extract_bluesky import extract_posts
from pipeline.jev import apply_jev, describe_jev
from pipeline.label import label_perspective, label_topic, unique_label
from pipeline.perspectives import select_representatives, split_perspectives
from pipeline.schema import SYSTEM_SIZE, category_for_members, to_percents
from pipeline.settings import load_settings
from pipeline.store import (
    LIVE_CORPUS_DB,
    connect,
    fetched_day_set,
    load_posts,
    record_fetched_days,
    replace_posts,
    write_clusters,
)
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
    relabel: bool = False,
) -> Path:
    settings = load_settings(config)
    target = int(settings.get("sample_size") or TARGET_POSTS)
    database = Path(db_path) if db_path else LIVE_CORPUS_DB
    print(describe_jev())
    connection = connect(database)
    try:
        existing = load_posts(connection)
        cleaned, source = _collect_posts(
            existing,
            settings,
            fixture,
            queries,
            target,
            connection,
            relabel=relabel,
        )
        if source == "bluesky" and not relabel:
            cleaned = apply_jev(cleaned)
        if not cleaned:
            raise RuntimeError("No quality posts in the retained corpus or the extract.")

        replace_posts(connection, cleaned)
        planet_posts = posts_for_planets(cleaned)
        texts = [post["clean_text"] for post in planet_posts]
        catalog_size = int(settings.get("catalog_size") or SYSTEM_SIZE)
        clustered = cluster_texts(
            texts,
            min_cluster_size=int(settings["min_cluster_size"]),
            cluster_backend=str(settings["cluster_backend"]),
            embedding_model=str(settings["embedding_model"]),
            seed=int(settings["seed"]),
            catalog_size=catalog_size,
        )
        topics, membership, face_rows = _build_topics(planet_posts, clustered, settings)
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
    connection,
    *,
    relabel: bool = False,
    now: datetime | None = None,
) -> tuple[list[dict], str]:
    if fixture:
        return clean_posts(load_fixture(fixture)), "fixture"
    if relabel:
        if not existing:
            raise RuntimeError("Cannot relabel: the retained corpus is empty.")
        print(f"Relabeling {len(existing)} retained posts without fetching Bluesky.")
        return list(existing), "bluesky"

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    today = moment.date().isoformat()
    search_queries = [item for item in (queries or []) if item]
    ledger = fetched_day_set(connection)
    if not search_queries and not ledger and existing:
        covered = utc_dates_present(existing)
        if covered:
            record_fetched_days(connection, covered, fetched_at=moment.isoformat(), kept=len(existing))
            ledger = fetched_day_set(connection)
            print(f"Backfilled fetched_days for {len(covered)} dates already in the retained corpus.")
    if not search_queries and today in ledger and posts_on_utc_date(existing, today):
        print(f"UTC day {today} already fetched; keeping {len(existing)} retained posts.")
        return list(existing), "bluesky"

    window_hours = int(settings["window_hours"])
    refresh_hours = int(settings.get("refresh_hours") or 24)
    neutral = [item for item in (settings.get("neutral_queries") or []) if item]
    # An empty ledger with no posts is the first fill. Posts without a ledger
    # are backfilled above so a seeded file is not replaced by a 7-day scrape.
    refill = not search_queries and not ledger and not existing
    rng = random.Random(int(settings["seed"]))
    if search_queries:
        fetch_queries = search_queries
        hours = window_hours if len(existing) < max(int(target * 0.5), 80) else refresh_hours
        pool = max(target, 80)
    elif refill:
        fetch_queries = neutral
        hours = window_hours
        pool = max(target * 2, 80)
        print("No neutral fetch on record. Replacing the retained window with a 7-day sample.")
    else:
        fetch_queries = neutral
        hours = refresh_hours
        pool = max(int(target * 0.4), 80)

    try:
        incoming = extract_posts(
            sample_size=pool,
            window_hours=hours,
            queries=fetch_queries,
            rng=rng,
            now=moment,
        )
    except RuntimeError as exc:
        print(f"Bluesky extract failed ({exc}). Rebuilding from the retained corpus.")
        incoming = []

    fresh = drop_near_duplicates(clean_posts(incoming))
    if not fresh:
        if not existing:
            raise RuntimeError("Bluesky returned no quality posts and no corpus is retained")
        print(f"No new quality posts; keeping {len(existing)} retained posts.")
        return list(existing), "bluesky"

    if refill:
        cleaned = cap_sample(fresh, target, rng)
        dates = window_utc_dates(moment)
    else:
        cleaned = retain_window(
            existing,
            fresh,
            now=moment,
            window_hours=window_hours,
            target=target,
            rng=rng,
        )
        dates = [today]
    cleaned = drop_near_duplicates(cleaned)
    if not search_queries and cleaned:
        record_fetched_days(connection, dates, fetched_at=moment.isoformat(), kept=len(cleaned))
    return cleaned, "bluesky"


def _build_topics(posts: list[dict], clustered: dict, settings: dict) -> tuple[list[dict], list[tuple], list[tuple]]:
    volumes = to_percents([topic["size"] for topic in clustered["topics"]])
    limit = int(settings["representative_posts"])
    backend = str(settings["label_backend"])
    seed = int(settings["seed"])
    model = str(settings.get("openai_model") or "") or None
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
        planet = label_topic(members, terms, backend=backend, model=model)
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
            label = label_perspective(representatives, face["terms"] or terms, backend=backend, model=model)
            arguments = label.get("arguments") or []
            focus = " ".join([str(label.get("title") or ""), str(label.get("summary") or ""), *arguments])
            representatives = _align_representatives(representatives, focus)
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
                "category": category_for_members(name, terms, member_texts, members),
                "total_volume_percent": volume,
                "perspectives": perspectives,
            }
        )
    _dedupe_labels(built)
    return built, membership, face_rows


def posts_for_planets(posts: list[dict]) -> list[dict]:
    """Leave personal asides in the window and out of planet membership.

    ``is_claim is None`` means Jev has not been asked, so those posts stay in.
    A claim set smaller than a few planets is not enough to map, so the whole
    window is used instead of publishing an empty solar system.
    """
    claims = [post for post in posts if post.get("is_claim") is not False]
    if len(claims) >= 24 and len(claims) < len(posts):
        print(
            f"Clustering {len(claims)} public claims; "
            f"{len(posts) - len(claims)} non-claims stay in the window."
        )
        return claims
    return list(posts)


def _align_representatives(posts: list[dict], focus: str) -> list[dict]:
    """Show the post the title is about first. Likes break a tie."""
    from pipeline.label import content_tokens

    focus_tokens = content_tokens(focus)

    def sort_key(post: dict) -> tuple:
        overlap = len(content_tokens(str(post.get("text") or "")) & focus_tokens)
        return (-overlap, -int(post.get("likes") or 0))

    return sorted(posts, key=sort_key)


def _dedupe_labels(topics: list[dict]) -> None:
    seen: set[str] = set()
    for topic in topics:
        topic["name"] = unique_label(str(topic.get("name") or ""), seen)
        for face in topic.get("perspectives") or []:
            face["title"] = unique_label(str(face.get("title") or ""), seen)
