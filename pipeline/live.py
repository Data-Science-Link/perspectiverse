"""Live path: rotate the retained corpus, cluster, label, write data.json."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.assemble import assemble_payload, face_id, topic_name, write_payload
from pipeline.briefs import apply_level_summaries
from pipeline.cleaning import clean_posts, drop_near_duplicates
from pipeline.corpus import (
    TARGET_POSTS,
    claim_count,
    counted_posts,
    parse_created,
    posts_on_utc_date,
    refresh_floor,
    retain_window,
    retire_oldest,
    utc_dates_present,
    window_utc_dates,
)
from pipeline.data_sources.extract_bluesky import extract_posts
from pipeline.jev import apply_jev, describe_jev
from pipeline.settings import EXAMPLE_POST_CAP
from pipeline.label import (
    content_tokens,
    label_perspective,
    label_topic,
    name_from_perspectives,
    shares_claim_word,
    specific_shared_words,
    subject_stem,
    titles_alike,
    topic_name_is_weak,
    _generator_for,
    _is_camp_title,
    _resolve_backend,
    _title_needs_repair,
    unique_label,
)
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
        cleaned, source, refreshed = _collect_posts(
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
            if refreshed:
                before = len(counted_posts(cleaned))
                cleaned = retire_oldest(
                    cleaned,
                    now=datetime.now(timezone.utc),
                    window_hours=int(settings["window_hours"]),
                    target=target,
                )
                kept = len(counted_posts(cleaned))
                if kept < target:
                    print(f"Claim shortfall: {kept} of {target} filtered claims. Search did not fill the window.")
                elif before > kept:
                    print(f"Retired the oldest posts down to {kept} of {target}.")
        if not cleaned:
            raise RuntimeError("No quality posts in the retained corpus or the extract.")

        replace_posts(connection, cleaned)
        planet_posts = posts_for_planets(
            cleaned,
            require_claims=source == "bluesky" and not relabel,
        )
        # Full set, from scratch. Yesterday's membership is deleted in write_clusters.
        print(f"Reclustering {len(planet_posts)} posts from scratch.")
        texts = [post["clean_text"] for post in planet_posts]
        catalog_size = int(settings.get("catalog_size") or SYSTEM_SIZE)
        floor = max(int(settings["min_cluster_size"]), len(planet_posts) // 200)
        # Ask for a few spare groups so a mixed planet can be dropped without
        # leaving the solar system short of specific conversations.
        pool = catalog_size
        if str(settings["cluster_backend"]) == "embedding":
            pool = min(20, catalog_size + 10)
        clustered = cluster_texts(
            texts,
            min_cluster_size=floor,
            cluster_backend=str(settings["cluster_backend"]),
            embedding_model=str(settings["embedding_model"]),
            seed=int(settings["seed"]),
            catalog_size=pool,
            authors=[str(post.get("author") or "unknown") for post in planet_posts],
        )
        topics, membership, face_rows = _build_topics(
            planet_posts, clustered, settings, keep=catalog_size
        )
        write_clusters(connection, membership, face_rows)
    finally:
        connection.close()

    payload = assemble_payload(
        topics,
        mode="live",
        source=source,
        total_posts=len(planet_posts),
    )
    destination = write_payload(payload, output)
    print(
        f"Live snapshot: {len(planet_posts)} public claims "
        f"from {len(cleaned)} posts in the window, "
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
) -> tuple[list[dict], str, bool]:
    """Return posts, source, and whether this morning fetched new posts.

    The third flag is false when the day was already fetched, the fetch failed,
    or this is a relabel. Retirement runs only after a real fetch.
    """
    if fixture:
        return clean_posts(load_fixture(fixture)), "fixture", False
    if relabel:
        if not existing:
            raise RuntimeError("Cannot relabel: the retained corpus is empty.")
        print(f"Relabeling {len(existing)} retained posts without fetching Bluesky.")
        return list(existing), "bluesky", False

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
        return list(existing), "bluesky", False

    window_hours = int(settings["window_hours"])
    refresh_hours = int(settings.get("refresh_hours") or 24)
    neutral = [item for item in (settings.get("neutral_queries") or []) if item]
    # An empty ledger with no posts is the first fill. Posts without a ledger
    # are backfilled above so a seeded file is not replaced by a 7-day scrape.
    refill = not search_queries and not ledger and not existing
    rng = random.Random(int(settings["seed"]))
    cutoff = moment - timedelta(hours=window_hours)
    in_window = [
        post for post in existing
        if parse_created(post.get("created_at") or "") >= cutoff
    ]
    labeled = any(post.get("is_claim") is not None for post in in_window)
    held = claim_count(in_window) if labeled else len(in_window)
    gap = 0 if refill else max(0, target - held)
    quota = target if refill else max(refresh_floor(target), gap)
    if search_queries:
        fetch_queries = search_queries
        hours = window_hours if len(existing) < max(int(target * 0.5), 80) else refresh_hours
    elif refill:
        fetch_queries = neutral
        hours = window_hours
        print("No neutral fetch on record. Replacing the retained window with a 7-day sample.")
    else:
        fetch_queries = neutral
        hours = refresh_hours

    pulled: list[dict] = []
    seen = {post.get("uri") for post in existing if post.get("uri")}
    rounds = 0
    while len(pulled) < quota and rounds < 6:
        rounds += 1
        try:
            incoming = extract_posts(
                sample_size=max(quota - len(pulled), 1),
                window_hours=hours,
                queries=fetch_queries,
                rng=rng,
                now=moment,
                skip_uris=seen,
            )
        except RuntimeError as exc:
            print(f"Bluesky extract failed ({exc}). Rebuilding from the retained corpus.")
            incoming = []
        fresh = []
        for post in drop_near_duplicates(clean_posts(incoming)):
            uri = post.get("uri")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            fresh.append(post)
        if not fresh:
            break
        pulled.extend(fresh)
        print(f"Morning fetch {rounds}: {len(pulled)} new posts toward {quota}.")

    if not pulled:
        if not existing:
            raise RuntimeError("Bluesky returned no quality posts and no corpus is retained")
        print(f"No new quality posts; keeping {len(existing)} retained posts.")
        return list(existing), "bluesky", False

    if refill:
        cleaned = list(pulled)
        dates = window_utc_dates(moment)
    else:
        cleaned = retain_window(
            existing,
            pulled,
            now=moment,
            window_hours=window_hours,
            target=target,
            rng=rng,
            cap=False,
        )
        dates = [today]
    cleaned = drop_near_duplicates(cleaned)
    if not search_queries and cleaned:
        record_fetched_days(connection, dates, fetched_at=moment.isoformat(), kept=len(cleaned))
    return cleaned, "bluesky", True


def _build_topics(
    posts: list[dict],
    clustered: dict,
    settings: dict,
    keep: int | None = None,
) -> tuple[list[dict], list[tuple], list[tuple]]:
    volumes = to_percents([topic["size"] for topic in clustered["topics"]])
    limit = int(settings["representative_posts"])
    backend = str(settings["label_backend"])
    seed = int(settings["seed"])
    model = str(settings.get("openai_model") or "") or None
    chosen = _resolve_backend(backend)
    summary_model = None
    if chosen != "heuristic":
        try:
            summary_model = _generator_for(chosen, model)
        except Exception as exc:
            print(f"Level summaries will use the grounded writer ({exc}).")
    built: list[dict] = []
    membership: list[tuple[str, int]] = []
    face_rows: list[tuple[str, int, int, float]] = []

    for topic, volume in zip(clustered["topics"], volumes):
        members = [posts[index] for index in topic["member_indices"]]
        member_texts = [post["clean_text"] for post in members]
        matrix = clustered.get("matrix")
        member_matrix = None
        if matrix is not None:
            member_matrix = matrix[topic["member_indices"]]
        split = split_perspectives(member_texts, seed=seed, matrix=member_matrix)
        face_volumes = to_percents([face["size"] for face in split["faces"]])
        topic_id = topic["id"] + 1
        terms = list(topic["terms"])
        planet = label_topic(members, terms, backend=backend, model=model)
        name = str(planet.get("name") or topic_name(terms))
        drafted: list[tuple[dict, list[tuple[str, int, int, float]], int]] = []
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
            title = str(label.get("title") or "")
            on_claim = [
                post
                for post in face_posts
                if shares_claim_word(str(post.get("text") or post.get("clean_text") or ""), title)
            ]
            if len(on_claim) >= 3:
                representatives = select_representatives(on_claim, [0.0] * len(on_claim), limit=limit)
            focus = " ".join([str(label.get("title") or ""), str(label.get("summary") or ""), *arguments])
            representatives = _align_representatives(representatives, focus)
            summary = _without_ungrounded_tail(str(label.get("summary") or ""), representatives)
            label["summary"] = summary
            if content_tokens(title) and (
                not _claim_words_overlap(title, summary) or not _title_covers_posts(title, representatives)
            ):
                label = {
                    "title": "Mixed remarks",
                    "summary": "These posts do not share a claim.",
                    "label_source": "heuristic",
                }
                arguments = []
            elif len(representatives) < 2 or not _posts_share_a_subject(representatives):
                label = {
                    "title": "Mixed remarks",
                    "summary": "These posts do not share a claim.",
                    "label_source": "heuristic",
                }
                arguments = []
                representatives = _align_representatives(representatives, label["title"])
            perspective = {
                "id": face_id(topic_id, position),
                "title": label["title"],
                "summary": label["summary"],
                "volume_percent": face_volume,
                "representative_posts": representatives,
            }
            if len(arguments) >= 2:
                perspective["arguments"] = arguments[:6]
            rows = [
                (members[index]["uri"], topic_id, position, float(split["distances"][index]))
                for index in face["member_indices"]
            ]
            drafted.append((perspective, rows, int(face["size"])))
        drafted = [
            item for item in drafted if not _face_has_no_shared_claim(item[0])
        ]
        if not drafted:
            print(f"Dropping {name}: the posts do not share a claim.")
            continue
        perspectives = [item[0] for item in drafted]
        if len(perspectives) >= 2 and not specific_shared_words(perspectives):
            print(f"Dropping {name}: its faces are different stories.")
            continue
        if (
            planet.get("label_source") == "heuristic"
            or topic_name_is_weak(name, members, terms)
            or _name_misses_faces(name, perspectives)
        ):
            renamed = name_from_perspectives(members, perspectives, terms, backend=backend, model=model)
            fallback = str(perspectives[0].get("title") or "") if perspectives else ""
            if renamed and not _name_misses_faces(renamed, perspectives):
                name = renamed
            elif fallback and not _title_needs_repair(fallback) and not _is_camp_title(fallback):
                name = fallback
        face_volumes = to_percents([item[2] for item in drafted])
        perspectives = []
        for position, ((perspective, rows, _size), volume) in enumerate(zip(drafted, face_volumes)):
            perspective["volume_percent"] = volume
            perspective["post_count"] = int(_size)
            perspective["id"] = face_id(topic_id, position)
            perspectives.append(perspective)
            for uri, _topic_id, _position, distance in rows:
                face_rows.append((uri, topic_id, position, distance))
        print(
            f"Planet {name}: "
            + " | ".join(f"{item['volume_percent']}% {item['title']}" for item in perspectives)
        )
        for post in members:
            membership.append((post["uri"], topic_id))
        planet = {
            "id": topic_id,
            "name": name,
            "category": category_for_members(name, terms, member_texts, members),
            "total_volume_percent": volume,
            "post_count": sum(int(item[2]) for item in drafted),
            "perspectives": perspectives,
        }
        apply_level_summaries(planet, generate=summary_model)
        built.append(planet)
        _dedupe_labels(built, limit)
    built = _drop_unshared_planets(built)
    if keep is not None:
        built = built[: max(int(keep), 1)]
    if built:
        # Volumes were shares of the pre-drop set. Rebalance after a mixed planet leaves.
        sizes = [max(topic.get("total_volume_percent") or 0, 0.1) for topic in built]
        for topic, volume in zip(built, to_percents(sizes)):
            topic["total_volume_percent"] = volume
    return _renumber_planets(built, membership, face_rows)


def posts_for_planets(posts: list[dict], *, require_claims: bool = False) -> list[dict]:
    """Leave personal asides in the window and out of planet membership.

    A live fetch with no claim labels fails. Fixtures and a relabel of an
    unlabeled file still cluster the posts they were given.
    """
    labeled = any(post.get("is_claim") is not None for post in posts)
    if require_claims and not labeled:
        raise RuntimeError("Jev did not label claims. Refusing to cluster unlabeled posts.")
    if not labeled:
        return list(posts)
    claims = [post for post in posts if post.get("is_claim") is True]
    unlabeled = sum(1 for post in posts if post.get("is_claim") is None)
    if require_claims and unlabeled and not claims:
        raise RuntimeError("Jev left the posts unlabeled. Refusing to cluster them.")
    if require_claims and not claims:
        raise RuntimeError("No public claims passed the filters.")
    if not claims:
        return list(posts)
    if unlabeled:
        print(f"Jev left {unlabeled} posts unlabeled. They stay out of the planets.")
    print(
        f"Clustering {len(claims)} public claims; "
        f"{len(posts) - len(claims)} non-claims stay in the window."
    )
    return claims


def _name_misses_faces(name: str, faces: list[dict]) -> bool:
    """True when a long name word never appears on any published face."""
    tokens = [token for token in content_tokens(name) if len(token) >= 5]
    if not tokens or not faces:
        return False
    parts: list[str] = []
    for face in faces:
        parts.append(str(face.get("title") or ""))
        parts.append(str(face.get("summary") or ""))
        parts.extend(
            str(post.get("text") or "") for post in (face.get("representative_posts") or [])[:6]
        )
    text = " ".join(parts)
    return any(not shares_claim_word(token, text) for token in tokens)


def _claim_words_overlap(left: str, right: str) -> bool:
    """True when a title and a summary are about the same words."""
    left_stems = {subject_stem(token) for token in content_tokens(left)}
    right_stems = {subject_stem(token) for token in content_tokens(right)}
    return bool(left_stems & right_stems)


def _without_ungrounded_tail(summary: str, posts: list[dict]) -> str:
    """Drop an 'and ...' ending that the shown posts never say."""
    text = str(summary or "").strip()
    if " and " not in text:
        return text
    head, tail = text.split(" and ", 1)
    if len(head.split()) < 3 or len(tail.split()) > 3:
        return text
    post_stems: set[str] = set()
    for post in posts:
        body = str(post.get("text") or post.get("clean_text") or "")
        post_stems.update(subject_stem(token) for token in content_tokens(body))
    tail_stems = {subject_stem(token) for token in content_tokens(tail)}
    if tail_stems and any(stem not in post_stems for stem in tail_stems):
        return head.rstrip(" ,;")
    return text


def _title_covers_posts(title: str, posts: list[dict]) -> bool:
    """True when the claim is what most of the shown posts are about."""
    title_stems = {subject_stem(token) for token in content_tokens(title)}
    title_stems = {stem for stem in title_stems if len(stem) >= 3}
    shown = posts[:6]
    if len(shown) < 2 or not title_stems:
        return True
    hits = 0
    for post in shown:
        text = str(post.get("text") or post.get("clean_text") or "")
        stems = {subject_stem(token) for token in content_tokens(text)}
        if title_stems & stems:
            hits += 1
    return hits >= 2 and hits * 2 >= len(shown)


def _word_bags_overlap(left: set[str], right: set[str]) -> bool:
    stemmed_left = {subject_stem(token) for token in left}
    stemmed_right = {subject_stem(token) for token in right}
    return bool(stemmed_left & stemmed_right)


def _posts_share_a_subject(posts: list[dict]) -> bool:
    """False when the shown posts are a grab bag rather than one claim."""
    glue = {
        "actually",
        "think",
        "thinking",
        "anything",
        "through",
        "against",
        "certain",
        "support",
        "people",
        "would",
        "could",
        "should",
        "there",
        "their",
        "other",
        "about",
        "being",
        "really",
        "something",
    }
    bags = []
    for post in posts[:5]:
        text = str(post.get("text") or post.get("clean_text") or "")
        bags.append({token for token in content_tokens(text) if token not in glue})
    if len(bags) == 2:
        return _word_bags_overlap(bags[0], bags[1])
    if len(bags) < 2:
        return True
    pairs = hits = 0
    for index, left in enumerate(bags):
        for right in bags[index + 1 :]:
            pairs += 1
            if _word_bags_overlap(left, right):
                hits += 1
    if pairs == 0:
        return True
    return hits > 0


def _align_representatives(posts: list[dict], focus: str) -> list[dict]:
    """Show posts that use the claim's words. Likes break a tie."""
    from pipeline.label import content_tokens

    focus_tokens = content_tokens(focus)

    def sort_key(post: dict) -> tuple:
        overlap = len(content_tokens(str(post.get("text") or "")) & focus_tokens)
        return (-overlap, -int(post.get("likes") or 0))

    ranked = sorted(posts, key=sort_key)
    matched = [post for post in ranked if shares_claim_word(str(post.get("text") or ""), focus)]
    if matched:
        return matched
    return ranked


def _face_has_no_shared_claim(face: dict) -> bool:
    title = str(face.get("title") or "").strip().lower()
    summary = str(face.get("summary") or "").lower()
    if title in {"mixed remarks", "untitled cluster"}:
        return True
    return any(
        phrase in summary
        for phrase in ("various opinions", "various issues", "no shared claim", "do not share a claim")
    )


def _renumber_planets(
    topics: list[dict],
    membership: list[tuple],
    face_rows: list[tuple],
) -> tuple[list[dict], list[tuple], list[tuple]]:
    """Publish ids 1..N after a mixed planet is dropped, and drop its membership."""
    remap = {int(topic["id"]): new_id for new_id, topic in enumerate(topics, start=1)}
    for topic in topics:
        new_id = remap[int(topic["id"])]
        topic["id"] = new_id
        topic["perspectives"] = [
            {**face, "id": face_id(new_id, position)}
            for position, face in enumerate(topic.get("perspectives") or [])
        ]
    kept_membership = [(uri, remap[int(topic_id)]) for uri, topic_id in membership if int(topic_id) in remap]
    kept_faces = [
        (uri, remap[int(topic_id)], face_index, distance)
        for uri, topic_id, face_index, distance in face_rows
        if int(topic_id) in remap
    ]
    return topics, kept_membership, kept_faces


def _drop_unshared_planets(topics: list[dict]) -> list[dict]:
    """A planet whose label admits the posts do not share a claim is not published."""
    kept = []
    for topic in topics:
        faces = [face for face in (topic.get("perspectives") or []) if not _face_has_no_shared_claim(face)]
        if not faces:
            print(f"Dropping {topic.get('name')}: the posts do not share a claim.")
            continue
        topic["perspectives"] = faces
        counts = [int(face.get("post_count") or 0) for face in faces]
        if any(counts):
            topic["post_count"] = sum(counts)
        kept.append(topic)
    return kept


def _dedupe_labels(topics: list[dict], post_limit: int = EXAMPLE_POST_CAP) -> None:
    seen: set[str] = set()
    for topic in topics:
        topic["name"] = unique_label(str(topic.get("name") or ""), seen)
        _merge_alike_faces(topic, post_limit)


def _merge_alike_faces(topic: dict, post_limit: int = EXAMPLE_POST_CAP) -> None:
    """Fold a second face into the larger one when the titles are the same stance.

    Numbering a duplicate ("Pro Ukraine 2") was presenting one view as two.
    """
    ranked = sorted(
        topic.get("perspectives") or [],
        key=lambda face: (-float(face.get("volume_percent") or 0), str(face.get("id") or "")),
    )
    kept: list[dict] = []
    for face in ranked:
        match = next((item for item in kept if titles_alike(item.get("title"), face.get("title"))), None)
        if match is None:
            kept.append(face)
            continue
        match["volume_percent"] = float(match.get("volume_percent") or 0) + float(face.get("volume_percent") or 0)
        match["post_count"] = int(match.get("post_count") or 0) + int(face.get("post_count") or 0)
        seen_text = {str(post.get("text") or "") for post in match.get("representative_posts") or []}
        posts = list(match.get("representative_posts") or [])
        for post in face.get("representative_posts") or []:
            if str(post.get("text") or "") in seen_text:
                continue
            posts.append(post)
            seen_text.add(str(post.get("text") or ""))
        posts.sort(key=lambda post: -int(post.get("likes") or 0))
        match["representative_posts"] = posts[: max(int(post_limit), 1)]
    topic_id = int(topic["id"])
    topic["perspectives"] = [
        {**face, "id": face_id(topic_id, position)}
        for position, face in enumerate(kept)
    ]
