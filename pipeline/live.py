"""Live path: rotate the retained corpus, cluster, label, write data.json."""

from __future__ import annotations

import json
import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.assemble import FACE_LETTERS, assemble_payload, face_id, topic_name, write_payload
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
from pipeline.cluster_math import salient_terms, vectorize
from pipeline.grouping import distinctness_score
from pipeline.schema import TOP_TERMS_LIMIT
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
from pipeline.schema import (
    CATEGORIES,
    MAX_FACES,
    MIN_FACES,
    SYSTEM_SIZE,
    category_for_members,
    to_percents,
)
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

# Planets drafted at once when a network label backend is on (I/O bound).
DEFAULT_LABEL_WORKERS = 8
# Section planets share one pool. Each slot is one planet, and that planet
# makes its LLM calls one at a time, so this is also how many label calls are
# in flight across every section. The default ``label_workers`` of 8 becomes
# this wider pool; any other setting is used as the cap.
DEFAULT_SECTION_LABEL_IN_FLIGHT = 12
# Section solar systems get this many minutes after the global system is built.
# 0 is a real budget and skips sections. None means this default.
DEFAULT_SECTION_BUDGET_MINUTES = 20


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
            # Keep only public claims; non-claims are discarded and not stored.
            cleaned = [p for p in cleaned if p.get("is_claim") is True]
            if refreshed:
                # Top up: keep fetching until claim count reaches target so the
                # rolling window stays at the threshold, not below it.
                if len(cleaned) < target:
                    cleaned = _topup_claims(cleaned, target=target, settings=settings)
                before = len(cleaned)
                cleaned = retire_oldest(
                    cleaned,
                    now=datetime.now(timezone.utc),
                    window_hours=int(settings["window_hours"]),
                    target=target,
                )
                kept = len(cleaned)
                if kept < target:
                    print(f"Claim shortfall: {kept} of {target}. Bluesky could not fill the window.")
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
        started = time.monotonic()
        clustered = cluster_texts(
            texts,
            min_cluster_size=floor,
            cluster_backend=str(settings["cluster_backend"]),
            embedding_model=str(settings["embedding_model"]),
            seed=int(settings["seed"]),
            catalog_size=pool,
            authors=[str(post.get("author") or "unknown") for post in planet_posts],
        )
        print(
            f"Timing: embedded and clustered {len(planet_posts)} claims into "
            f"{len(clustered['topics'])} candidate planets in {time.monotonic() - started:.1f}s."
        )
        context = _label_context(settings)
        print(f"Labels: {context['chosen']} backend, {context['workers']} planet(s) at a time.")
        started = time.monotonic()
        topics, membership, face_rows = _build_topics(
            planet_posts, clustered, settings, keep=catalog_size, context=context
        )
        print(f"Timing: {len(topics)} global planet(s) labeled in {time.monotonic() - started:.1f}s.")
        # Section clustering reuses the precomputed embedding matrix so posts
        # are not re-embedded ten times. Only sections that produce at least one
        # planet appear in the output; a section that fails is skipped.
        global_matrix = clustered.get("matrix")
        sections: dict[str, list[dict]] = {}
        if global_matrix is not None:
            # 0 is a real budget (skip sections). Missing means the default.
            budget = _section_budget_minutes(settings.get("section_budget_minutes"))
            started = time.monotonic()
            sections = _cluster_sections(
                planet_posts,
                global_matrix,
                settings,
                catalog_size,
                floor,
                context=context,
                deadline=started + budget * 60.0,
            )
            print(
                f"Timing: {len(sections)} section solar system(s), "
                f"{sum(len(items) for items in sections.values())} planet(s) in {time.monotonic() - started:.1f}s."
            )
        write_clusters(connection, membership, face_rows)
    finally:
        connection.close()

    payload = assemble_payload(
        topics,
        mode="live",
        source=source,
        total_posts=len(planet_posts),
        sections=sections or None,
    )
    destination = write_payload(payload, output)
    print(
        f"Live snapshot: {len(planet_posts)} public claims "
        f"from {len(cleaned)} posts in the window, "
        f"{clustered['noise_count']} excluded as noise, wrote {destination}"
    )
    return destination


def _topup_claims(
    claims: list[dict],
    *,
    target: int,
    settings: dict,
    max_rounds: int = 6,
) -> list[dict]:
    """Fetch additional posts and Jev-classify them until claim count reaches target.

    Each round over-fetches by 4× the remaining gap to account for the Bluesky
    claim rate (~30 %). Stops early if Bluesky returns nothing new or max_rounds
    is exhausted — the caller still gets whatever claims were collected.
    """
    result = list(claims)
    seen = {post.get("uri") for post in result if post.get("uri")}
    neutral = [item for item in (settings.get("neutral_queries") or []) if item]
    refresh_hours = int(settings.get("refresh_hours") or 24)
    # Use a shifted seed so each round samples a different slice of Bluesky.
    rng = random.Random(int(settings["seed"]) + len(result))
    now = datetime.now(timezone.utc)

    for round_num in range(1, max_rounds + 1):
        gap = target - len(result)
        if gap <= 0:
            break
        # 4× overfetch compensates for the ~25–35 % claim rate on Bluesky.
        fetch_size = min(gap * 4, 5000)
        try:
            incoming = extract_posts(
                sample_size=fetch_size,
                window_hours=refresh_hours,
                queries=neutral,
                rng=rng,
                now=now,
                skip_uris=seen,
            )
        except RuntimeError as exc:
            print(f"Top-up fetch {round_num} failed ({exc}); stopping.")
            break
        fresh = []
        for post in drop_near_duplicates(clean_posts(incoming)):
            uri = post.get("uri")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            fresh.append(post)
        if not fresh:
            print(f"Top-up {round_num}: no new posts from Bluesky; stopping.")
            break
        new_claims = [p for p in apply_jev(fresh) if p.get("is_claim") is True]
        result.extend(new_claims)
        print(
            f"Top-up {round_num}: {len(new_claims)} claims from {len(fresh)} posts "
            f"(total {len(result)}/{target})."
        )

    return result


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


def _label_context(settings: dict, *, summaries: bool = True) -> dict:
    """Backend, model, and the summary writer shared by every planet in a run."""
    backend = str(settings["label_backend"])
    model = str(settings.get("openai_model") or "") or None
    chosen = _resolve_backend(backend)
    summary_model = None
    if chosen != "heuristic" and summaries:
        try:
            summary_model = _generator_for(chosen, model)
        except Exception as exc:
            print(f"Level summaries will use the grounded writer ({exc}).")
    workers = 1
    if chosen != "heuristic":
        # Labeling is network-bound. Planets are drafted independently, so a
        # few run at once; results are still taken in rank order. 0 means
        # "one at a time", not the default.
        raw_workers = settings.get("label_workers")
        if raw_workers is None:
            raw_workers = DEFAULT_LABEL_WORKERS
        workers = max(1, int(raw_workers))
    return {
        "backend": backend,
        "model": model,
        "chosen": chosen,
        "summary_model": summary_model,
        "limit": int(settings["representative_posts"]),
        "seed": int(settings["seed"]),
        "workers": workers,
    }


# A planet whose labels collapse below MIN_FACES may try this many other
# passing face counts (best fit first) before it is dropped.
_FACE_RETRIES = 1


def _label_faces(
    members: list[dict],
    split: dict,
    terms: list[str],
    context: dict,
    *,
    lock_floor: bool = False,
) -> tuple[list[tuple[dict, list[tuple[str, int, float]], int]], int]:
    """Label each face of one split. Returns surviving drafts and how many were labeled.

    A face that admits no shared claim is dropped; faces whose titles are the
    same stance are merged. If that would leave fewer than two faces, the
    pre-collapse faces are kept and alike titles get a distinguishing term
    (issue #76). ``lock_floor`` skips that collapse entirely.
    """
    backend = context["backend"]
    model = context["model"]
    limit = context["limit"]
    face_volumes = to_percents([face["size"] for face in split["faces"]])
    drafted: list[tuple[dict, list[tuple[str, int, float]], int]] = []
    ordered_faces = sorted(
        zip(split["faces"], face_volumes),
        key=lambda item: (-item[1], item[0]["index"]),
    )
    for position, (face, face_volume) in enumerate(ordered_faces):
        face_posts = [members[index] for index in face["member_indices"]]
        face_distances = [split["distances"][index] for index in face["member_indices"]]
        face_cosines = [split["cosines"][index] for index in face["member_indices"]]
        representatives = select_representatives(
            face_posts, face_distances, limit=limit, matches=face_cosines
        )
        label = label_perspective(representatives, face["terms"] or terms, backend=backend, model=model)
        arguments = label.get("arguments") or []
        title = str(label.get("title") or "")
        on_claim = [
            (post, score)
            for post, score in zip(face_posts, face_cosines)
            if shares_claim_word(str(post.get("text") or post.get("clean_text") or ""), title)
        ]
        if len(on_claim) >= 3:
            representatives = select_representatives(
                [post for post, _score in on_claim],
                [0.0] * len(on_claim),
                limit=limit,
                matches=[score for _post, score in on_claim],
            )
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
        member_texts = [
            str(post.get("clean_text") or post.get("text") or "") for post in face_posts
        ]
        perspective = {
            "id": face_id(1, position),
            "title": label["title"],
            "summary": label["summary"],
            "volume_percent": face_volume,
            "representative_posts": representatives,
            "top_terms": salient_terms(member_texts, limit=TOP_TERMS_LIMIT),
        }
        if len(arguments) >= 2:
            perspective["arguments"] = arguments[:6]
        rows = [
            (members[index]["uri"], position, float(split["distances"][index]))
            for index in face["member_indices"]
        ]
        drafted.append((perspective, rows, int(face["size"])))
    labeled = len(drafted)
    if lock_floor:
        return drafted[:MAX_FACES], labeled
    snapshot = list(drafted)
    drafted = [item for item in drafted if not _face_has_no_shared_claim(item[0])]
    drafted = _merge_alike_drafts(drafted, limit)
    if len(drafted) < MIN_FACES <= len(snapshot):
        drafted = _keep_collapsed_faces(snapshot[:MAX_FACES])
    return drafted, labeled


def _keep_collapsed_faces(
    drafted: list[tuple[dict, list[tuple[str, int, float]], int]],
) -> list[tuple[dict, list[tuple[str, int, float]], int]]:
    """Keep a collapsed planet's faces and make alike titles readable."""
    for index, (perspective, _rows, _size) in enumerate(drafted):
        title = str(perspective.get("title") or "")
        clash = any(
            other != index and titles_alike(title, drafted[other][0].get("title"))
            for other in range(len(drafted))
        )
        if not clash:
            continue
        used = {
            str(drafted[other][0].get("title") or "").lower()
            for other in range(len(drafted))
            if other != index
        }
        extra = next(
            (
                term
                for term in perspective.get("top_terms") or []
                if term.lower() not in title.lower() and term.lower() not in " ".join(used)
            ),
            "",
        )
        if extra:
            perspective["title"] = f"{title} ({extra})"
    return drafted


def _draft_planet(posts: list[dict], clustered: dict, topic: dict, context: dict) -> tuple[dict | None, list[str]]:
    """Split, label, and check one candidate planet. Returns (draft or None, log lines).

    Only this planet's posts are touched, so drafts can run in parallel.
    The face count is the best fit in 2..6 (``split_perspectives``). If no
    count passes, the split is already a forced 2-way cut. If the labels
    collapse that split below MIN_FACES, the next passing count is tried
    once; after that the pre-collapse faces are kept, or a fresh 2-way cut
    is labeled and locked. The planet is not dropped for having one face
    (#76, supersedes the drop in #53). The planet name and level summaries
    are written only for a planet that survives.
    """
    log: list[str] = []
    backend = context["backend"]
    model = context["model"]
    members = [posts[index] for index in topic["member_indices"]]
    member_texts = [post["clean_text"] for post in members]
    matrix = clustered.get("matrix")
    member_matrix = None
    if matrix is not None:
        member_matrix = matrix[topic["member_indices"]]
    terms = list(topic["terms"])
    split = split_perspectives(member_texts, seed=context["seed"], matrix=member_matrix)
    if len(split["faces"]) < MIN_FACES:
        log.append(f"Dropping {topic_name(terms)}: {split.get('reason') or 'no two faces'}.")
        return None, log
    attempts = [split, *(split.get("alternatives") or [])[:_FACE_RETRIES]]
    drafted: list = []
    tried: list[str] = []
    chosen_split = split
    for attempt in attempts:
        drafted, labeled = _label_faces(members, attempt, terms, context)
        tried.append(f"k={attempt.get('k', len(attempt['faces']))}: {len(drafted)} of {labeled}")
        chosen_split = attempt
        if len(drafted) >= MIN_FACES:
            break
    if len(drafted) < MIN_FACES and len(members) >= 2:
        forced_matrix = member_matrix
        if forced_matrix is None:
            try:
                forced_matrix = vectorize(member_texts)
            except ValueError:
                forced_matrix = None
        if forced_matrix is not None:
            from pipeline.grouping import force_two_labels
            from pipeline.perspectives import _faces_from, _mean_centers

            forced_labels, method = force_two_labels(member_texts, forced_matrix, seed=context["seed"])
            chosen_split = _faces_from(
                member_texts,
                forced_matrix,
                forced_labels,
                _mean_centers(forced_matrix, forced_labels, 2),
                2,
            )
            chosen_split["forced"] = True
            chosen_split["method"] = method
            drafted, labeled = _label_faces(members, chosen_split, terms, context, lock_floor=True)
            tried.append(f"forced {method}: {len(drafted)} of {labeled}")
    if len(drafted) < MIN_FACES:
        log.append(
            f"Dropping {topic_name(terms)}: too few faces kept a distinct shared claim "
            f"({'; '.join(tried)}; need {MIN_FACES})."
        )
        return None, log
    drafted = drafted[:MAX_FACES]
    perspectives = [item[0] for item in drafted]
    if not specific_shared_words(perspectives):
        log.append(f"Dropping {topic_name(terms)}: its faces are different stories.")
        return None, log
    planet = label_topic(members, terms, backend=backend, model=model)
    name = str(planet.get("name") or topic_name(terms))
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
    face_rows: list[tuple[str, int, float]] = []
    for position, ((perspective, rows, size), volume) in enumerate(zip(drafted, face_volumes)):
        perspective["volume_percent"] = volume
        perspective["post_count"] = int(size)
        perspective["id"] = face_id(1, position)
        perspectives.append(perspective)
        for uri, _old_position, distance in rows:
            face_rows.append((uri, position, distance))
    planet_out = {
        "id": 1,
        "name": name,
        "category": category_for_members(name, terms, member_texts, members),
        "total_volume_percent": 0.0,
        "post_count": sum(int(item[2]) for item in drafted),
        "perspectives": perspectives,
    }
    apply_level_summaries(planet_out, generate=context["summary_model"])
    distinctness = _face_distinctness(member_matrix, members, member_texts, drafted)
    planet_out["face_distinctness"] = distinctness
    k_scores = ", ".join(
        f"k={row['k']}:{row['silhouette'] if row['valid'] else 'x'}" for row in split.get("k_scores") or []
    )
    retried = f" (retried k={chosen_split.get('k')})" if chosen_split is not split else ""
    forced = " forced" if chosen_split.get("forced") or split.get("forced") else ""
    log.append(
        f"Planet {name}: "
        + " | ".join(f"{item['volume_percent']}% {item['title']}" for item in perspectives)
        + (f"  [silhouette {k_scores}]{retried}{forced} distinctness={distinctness}" if k_scores else f"{retried}{forced} distinctness={distinctness}")
    )
    return {
        "planet": planet_out,
        "membership": [post["uri"] for post in members],
        "face_rows": face_rows,
    }, log


def _merge_alike_drafts(
    drafted: list[tuple[dict, list[tuple[str, int, float]], int]],
    post_limit: int = EXAMPLE_POST_CAP,
) -> list[tuple[dict, list[tuple[str, int, float]], int]]:
    """Fold a face into a larger one when the titles are the same stance.

    Same rule as ``_merge_alike_faces``, but the membership rows move with
    the merged face so the database matches what is published.
    """
    ranked = sorted(drafted, key=lambda item: (-int(item[2]), str(item[0].get("id") or "")))
    kept: list[list] = []
    for perspective, rows, size in ranked:
        match = next((item for item in kept if titles_alike(item[0].get("title"), perspective.get("title"))), None)
        if match is None:
            kept.append([perspective, list(rows), int(size)])
            continue
        target = match[0]
        seen_text = {str(post.get("text") or "") for post in target.get("representative_posts") or []}
        shown = list(target.get("representative_posts") or [])
        for post in perspective.get("representative_posts") or []:
            if str(post.get("text") or "") in seen_text:
                continue
            shown.append(post)
            seen_text.add(str(post.get("text") or ""))
        shown.sort(
            key=lambda post: (
                -(float(post["match"]) if post.get("match") is not None else 0.0),
                -int(post.get("likes") or 0),
            )
        )
        target["representative_posts"] = shown[: max(int(post_limit), 1)]
        match[1].extend(rows)
        match[2] += int(size)
    kept.sort(key=lambda item: -int(item[2]))  # largest face first, as published
    return [(item[0], item[1], item[2]) for item in kept]


def _section_budget_minutes(raw: object) -> float:
    """Minutes of wall time the section solar systems may spend.

    ``None`` is the default. ``0`` is a real budget: the deadline is already
    due, so every section is skipped and the global snapshot still publishes.
    """
    if raw is None:
        return float(DEFAULT_SECTION_BUDGET_MINUTES)
    return float(raw)


def _section_pool_size(context: dict) -> int:
    """In-flight section label calls, shared by every section.

    Each slot drafts one planet, and that planet makes its LLM calls one at
    a time, so the slot count is the number of label calls in flight. The
    heuristic backend and ``label_workers=0`` stay one at a time. The default
    of 8 (one section's worth) is widened to 12 so ten sections fit the
    ceiling. Any other configured value is the cap, including a lower one
    set to ease HTTP 429s and a higher one.
    """
    workers = max(1, int(context.get("workers") or 1))
    if workers <= 1:
        return 1
    if workers == DEFAULT_LABEL_WORKERS:
        return DEFAULT_SECTION_LABEL_IN_FLIGHT
    return workers


def _safe_draft(posts: list[dict], clustered: dict, topic: dict, context: dict):
    """Draft one candidate. A raised error is a log line, not a failed snapshot."""
    try:
        return _draft_planet(posts, clustered, topic, context)
    except Exception as exc:  # noqa: BLE001 - one bad planet must not block the snapshot
        return None, [f"Dropping candidate {topic.get('id')}: drafting failed ({type(exc).__name__}: {exc})."]


def _stage_planet(built: list[dict], seen_names: set[str], result: dict) -> dict:
    """Give a surviving draft its published id and a unique name."""
    planet = result["planet"]
    topic_id = len(built) + 1
    planet["id"] = topic_id
    planet["name"] = unique_label(str(planet.get("name") or ""), seen_names)
    planet["perspectives"] = [
        {**face, "id": face_id(topic_id, position)} for position, face in enumerate(planet["perspectives"])
    ]
    built.append(planet)
    return planet


def _build_topics(
    posts: list[dict],
    clustered: dict,
    settings: dict,
    keep: int | None = None,
    context: dict | None = None,
) -> tuple[list[dict], list[tuple], list[tuple]]:
    """Draft candidates in rank order until ``keep`` planets survive.

    Candidates arrive ranked by distinct authors, so stopping at ``keep``
    publishes the same planets as labeling every candidate and truncating,
    without paying for labels nobody sees (#53). One candidate that raises is
    logged and skipped instead of failing the snapshot.
    """
    context = context or _label_context(settings)
    candidates = list(clustered["topics"])
    target = len(candidates) if keep is None else max(int(keep), 1)
    workers = int(context.get("workers") or 1)
    built: list[dict] = []
    membership: list[tuple[str, int]] = []
    face_rows: list[tuple[str, int, int, float]] = []
    seen_names: set[str] = set()

    def draft(topic: dict):
        return _safe_draft(posts, clustered, topic, context)

    cursor = 0
    executor = None
    try:
        while cursor < len(candidates) and len(built) < target:
            need = target - len(built)
            # Exactly the planets still needed. The pool runs `workers` of
            # them at a time and results are applied in rank order. The next
            # candidate is labeled only when an earlier one was dropped, so a
            # full catalog does not pay for spare label calls.
            wave = candidates[cursor : cursor + need]
            cursor += len(wave)
            if workers > 1 and len(wave) > 1:
                if executor is None:
                    executor = ThreadPoolExecutor(max_workers=workers)
                results = list(executor.map(draft, wave))
            else:
                results = [draft(topic) for topic in wave]
            for result, log in results:
                if len(built) >= target:
                    break
                for line in log:
                    print(line)
                if result is None:
                    continue
                planet = _stage_planet(built, seen_names, result)
                topic_id = int(planet["id"])
                membership.extend((uri, topic_id) for uri in result["membership"])
                face_rows.extend((uri, topic_id, position, distance) for uri, position, distance in result["face_rows"])
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    built = _drop_unshared_planets(built)
    face_rows = _align_face_rows(built, face_rows)
    built = _publishable_planets(built)
    publish_volumes(built)
    return _renumber_planets(built, membership, face_rows)


def _publishable_planets(topics: list[dict]) -> list[dict]:
    """Last guard before validation: a planet outside 2..6 faces is dropped and logged.

    Drafting already enforces this. If a later step ever breaks it, one planet
    is lost instead of the whole snapshot. ``validate_payload`` stays strict.
    """
    kept = []
    for topic in topics:
        faces = topic.get("perspectives") or []
        if MIN_FACES <= len(faces) <= MAX_FACES:
            kept.append(topic)
            continue
        print(
            f"WARNING dropping {topic.get('name')}: {len(faces)} faces is outside "
            f"{MIN_FACES}-{MAX_FACES} after labeling."
        )
    return kept


class _SectionLabelJob:
    """One section's candidates, labeled only until ``keep`` planets survive.

    The shared pool asks ``can_submit`` / ``take`` and later ``accept`` in
    whatever order drafts finish. Results are applied in candidate order, and
    the next candidate is labeled only when an earlier one was dropped, so a
    full catalog does not pay for spare label calls (#53).
    """

    def __init__(self, name: str, posts: list[dict], clustered: dict, keep: int, context: dict, post_count: int):
        self.name = name
        self.posts = posts
        self.clustered = clustered
        self.keep = max(int(keep), 1)
        self.context = context
        self.post_count = int(post_count)
        self.candidates = list(clustered["topics"])
        self.cursor = 0
        self.built: list[dict] = []
        self.seen: set[str] = set()
        self.pending: dict[int, tuple] = {}
        self.order: list[int] = []
        self.applied = 0
        self.inflight = 0
        self.wave_left = 0
        self.wave_open = False
        self.budget_hit = False
        self.skipped_budget = False
        self.done = False

    def can_submit(self) -> bool:
        if self.done or self.budget_hit or self.skipped_budget:
            return False
        if not self.wave_open:
            if len(self.built) >= self.keep or self.cursor >= len(self.candidates):
                self.done = True
                return False
            need = self.keep - len(self.built)
            available = len(self.candidates) - self.cursor
            self.wave_left = min(need, available)
            self.wave_open = self.wave_left > 0
            if not self.wave_open:
                self.done = True
                return False
        return self.wave_left > 0

    def take(self) -> tuple[int, dict]:
        index = self.cursor
        topic = self.candidates[index]
        self.cursor += 1
        self.wave_left -= 1
        self.inflight += 1
        self.order.append(index)
        return index, topic

    def accept(self, index: int, result, log: list[str]) -> None:
        self.pending[index] = (result, log)
        self.inflight -= 1
        self._drain()
        self._close_wave_if_idle()

    def mark_budget(self) -> None:
        """Stop submitting. Planets already in flight still finish."""
        self.budget_hit = True
        self._close_wave_if_idle()

    def _drain(self) -> None:
        while self.applied < len(self.order):
            index = self.order[self.applied]
            if index not in self.pending:
                return
            result, log = self.pending.pop(index)
            for line in log:
                print(line)
            if result is not None and len(self.built) < self.keep:
                _stage_planet(self.built, self.seen, result)
            self.applied += 1

    def _close_wave_if_idle(self) -> None:
        if self.inflight > 0:
            return
        if self.wave_left > 0 and not self.budget_hit:
            return
        self.wave_open = False
        self.wave_left = 0
        if self.budget_hit or len(self.built) >= self.keep or self.cursor >= len(self.candidates):
            self.done = True


def _submit_section_drafts(jobs: list[_SectionLabelJob], inflight: dict, executor, workers: int, deadline) -> None:
    """Fill free slots from the largest section that still needs a planet."""
    for job in jobs:
        if job.done:
            continue
        if job.cursor == 0 and job.inflight == 0 and deadline is not None and time.monotonic() >= deadline:
            print(f"Section {job.name}: skipped, the section time budget is spent.")
            job.skipped_budget = True
            job.done = True
            continue
        while job.can_submit() and len(inflight) < workers:
            if deadline is not None and time.monotonic() >= deadline:
                job.mark_budget()
                break
            index, topic = job.take()
            future = executor.submit(_safe_draft, job.posts, job.clustered, topic, job.context)
            inflight[future] = (job, index)


def _label_section_jobs(jobs: list[_SectionLabelJob], workers: int, deadline) -> None:
    """Label every section through one pool. Biggest sections take free slots first."""
    if not jobs:
        return
    workers = max(1, int(workers))
    print(f"Section labels: {workers} call(s) in flight, shared by {len(jobs)} section(s).")
    executor = ThreadPoolExecutor(max_workers=workers)
    inflight: dict = {}
    # A catalog is a handful of planets. This only fires if the state machine loops.
    guard = 0
    try:
        while True:
            guard += 1
            if guard > 100_000:
                raise RuntimeError("section label scheduler did not finish")
            _submit_section_drafts(jobs, inflight, executor, workers, deadline)
            if not inflight:
                break
            done, _pending = wait(set(inflight), return_when=FIRST_COMPLETED)
            for future in done:
                job, index = inflight.pop(future)
                result, log = future.result()
                job.accept(index, result, log)
    finally:
        executor.shutdown(wait=True)


def _finish_section_planets(built: list[dict]) -> list[dict]:
    """Same last guards as the global catalog: drop collapses, renumber, volumes."""
    built = _drop_unshared_planets(built)
    built = _publishable_planets(built)
    publish_volumes(built)
    topics, _membership, _faces = _renumber_planets(built, [], [])
    return topics


def _cluster_sections(
    planet_posts: list[dict],
    global_matrix,
    settings: dict,
    catalog_size: int,
    floor: int,
    context: dict | None = None,
    deadline: float | None = None,
) -> dict[str, list[dict]]:
    """Cluster each Jev section, then label them through one shared pool.

    Posts are not re-embedded; the sub-rows of *global_matrix* (already
    L2-normalised) are sliced out and passed back into cluster_texts via the
    *embed* hook, which short-circuits the fastembed call. Sections are
    ordered by post volume so the biggest ones take pool slots first. Past
    ``deadline`` (time.monotonic) no new planet is labeled; a section that
    never started is skipped, and one that raises is logged and skipped, so
    the global snapshot still publishes.
    """
    import numpy as np

    section_indices: dict[str, list[int]] = {}
    for idx, post in enumerate(planet_posts):
        section = str(post.get("section") or "")
        if section in CATEGORIES:
            section_indices.setdefault(section, []).append(idx)

    order = sorted(section_indices, key=lambda name: (-len(section_indices[name]), name))
    if deadline is not None and time.monotonic() >= deadline:
        for section in order:
            print(f"Section {section}: skipped, the section time budget is spent.")
        return {}

    result: dict[str, list[dict]] = {}
    seed = int(settings["seed"])
    base_min = int(settings["min_cluster_size"])
    context = context or _label_context(settings)
    matrix = np.asarray(global_matrix)
    jobs: list[_SectionLabelJob] = []

    for section in order:
        indices = section_indices[section]
        # Scale the floor to the section size; smaller sections get a lower bar
        # than the global floor so they can still form tight groups.
        section_floor = max(base_min, len(indices) // 200)
        if len(indices) < section_floor:
            print(f"Section {section}: {len(indices)} posts, skipping (need {section_floor}).")
            continue

        section_posts = [planet_posts[i] for i in indices]
        section_texts = [p["clean_text"] for p in section_posts]
        sub_matrix = matrix[indices]

        try:
            pool = min(20, catalog_size + 10)
            section_clustered = cluster_texts(
                section_texts,
                min_cluster_size=section_floor,
                cluster_backend=str(settings["cluster_backend"]),
                embedding_model=str(settings["embedding_model"]),
                seed=seed,
                catalog_size=pool,
                embed=lambda _texts, m=sub_matrix: m,
                authors=[str(p.get("author") or "unknown") for p in section_posts],
            )
        except Exception as exc:  # noqa: BLE001 - one section must not block the snapshot
            print(f"Section {section}: skipped ({type(exc).__name__}: {exc}).")
            continue
        if not section_clustered.get("topics"):
            print(f"Section {section}: no planet with two distinct faces from {len(indices)} posts.")
            continue
        jobs.append(
            _SectionLabelJob(
                section,
                section_posts,
                section_clustered,
                catalog_size,
                context,
                len(indices),
            )
        )

    _label_section_jobs(jobs, _section_pool_size(context), deadline)
    for job in jobs:
        if job.skipped_budget:
            continue
        topics = _finish_section_planets(job.built)
        if topics:
            result[job.name] = topics
            print(f"Section {job.name}: {len(topics)} planet(s) from {job.post_count} posts.")
        elif job.budget_hit:
            print(f"Section {job.name}: stopped, the section time budget is spent.")
        else:
            print(f"Section {job.name}: no planet with two distinct faces from {job.post_count} posts.")

    return {name: result[name] for name in CATEGORIES if name in result}


def publish_volumes(topics: list[dict]) -> None:
    """Planet size is the posts still on the planet.

    A mixed face can leave a cluster, and the old share of that larger cluster
    must not keep a four-post planet the same size as one with dozens.
    """
    if not topics:
        return
    sizes = [max(int(topic.get("post_count") or 0), 1) for topic in topics]
    for topic, volume in zip(topics, to_percents(sizes)):
        topic["total_volume_percent"] = volume


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
        f"{len(posts) - len(claims)} non-claims excluded."
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
    """Show posts that use the claim's words. Closest embedding, then likes."""
    from pipeline.label import content_tokens

    focus_tokens = content_tokens(focus)

    def sort_key(post: dict) -> tuple:
        overlap = len(content_tokens(str(post.get("text") or "")) & focus_tokens)
        match = post.get("match")
        match_key = -float(match) if match is not None else 0.0
        return (match_key, -overlap, -int(post.get("likes") or 0))

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


def _face_distinctness(matrix, members: list[dict], texts: list[str], drafted: list) -> float:
    """Centroid separation of the published faces. 0 matches, 1 is orthogonal."""
    import numpy as np

    values = matrix
    if values is None:
        try:
            values = vectorize(texts)
        except ValueError:
            return 0.0
    values = np.asarray(values, dtype=float)
    if values.shape[0] != len(members):
        return 0.0
    uri_index = {str(post.get("uri") or ""): index for index, post in enumerate(members)}
    labels = np.full(len(members), -1, dtype=int)
    for face_index, (_perspective, rows, _size) in enumerate(drafted):
        for uri, _position, _distance in rows:
            index = uri_index.get(str(uri))
            if index is not None:
                labels[index] = face_index
    kept = labels >= 0
    if int(kept.sum()) < 2 or len({int(item) for item in labels[kept]}) < 2:
        return 0.0
    return round(distinctness_score(values[kept], labels[kept]), 3)


def _drop_unshared_planets(topics: list[dict]) -> list[dict]:
    """Remove a face with no shared claim, without deleting the planet for it.

    If removing those faces would leave fewer than two, the planet is kept
    as it was (#76). A planet that arrived already outside 2–6 faces is still
    dropped here; drafting is what stops that from happening. If two or more
    faces remain, their volumes are recomputed so they still sum to 100.
    """
    kept = []
    for topic in topics:
        original = list(topic.get("perspectives") or [])
        faces = [face for face in original if not _face_has_no_shared_claim(face)]
        if not MIN_FACES <= len(faces) <= MAX_FACES:
            if MIN_FACES <= len(original) <= MAX_FACES:
                print(
                    f"Keeping {topic.get('name')}: filtering unshared claims would leave "
                    f"{len(faces)} faces."
                )
                kept.append(topic)
                continue
            print(
                f"Dropping {topic.get('name')}: {len(faces)} faces left after "
                f"removing unshared claims (need {MIN_FACES}-{MAX_FACES})."
            )
            continue
        if len(faces) != len(original):
            counts = [int(face.get("post_count") or 0) for face in faces]
            if sum(counts) <= 0:
                print(f"Dropping {topic.get('name')}: remaining faces have no posts.")
                continue
            topic["post_count"] = sum(counts)
            for face, volume in zip(faces, to_percents(counts)):
                face["volume_percent"] = volume
        topic["perspectives"] = faces
        kept.append(topic)
    return kept


def _align_face_rows(topics: list[dict], face_rows: list[tuple]) -> list[tuple]:
    """Compact face indexes after a face is removed so they match the snapshot.

    Ids are ``{topic_id}{letter}`` (A–F) for the index assigned at label time.
    Rows for a removed face are dropped. The faces that remain become 0..n-1.
    """
    kept_index: dict[int, dict[int, int]] = {}
    for topic in topics:
        topic_id = int(topic["id"])
        mapping: dict[int, int] = {}
        for new_index, face in enumerate(topic.get("perspectives") or []):
            text = str(face.get("id") or "")
            prefix = str(topic_id)
            letter = text[len(prefix) :] if text.startswith(prefix) else ""
            old_index = FACE_LETTERS.find(letter) if len(letter) == 1 else -1
            if old_index < 0:
                old_index = new_index
            mapping[old_index] = new_index
            face["id"] = face_id(topic_id, new_index)
        kept_index[topic_id] = mapping
    aligned = []
    for uri, topic_id, face_index, distance in face_rows:
        topic_id = int(topic_id)
        mapping = kept_index.get(topic_id)
        if mapping is None:
            continue
        new_index = mapping.get(int(face_index))
        if new_index is None:
            continue
        aligned.append((uri, topic_id, new_index, distance))
    return aligned
