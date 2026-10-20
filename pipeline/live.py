"""Live path: rotate the retained corpus, cluster, label, write data.json."""

from __future__ import annotations

import json
import math
import os
import random
import sys
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.assemble import FACE_LETTERS, assemble_payload, face_id, topic_name, write_payload
from pipeline.briefs import apply_level_summaries
from pipeline.cleaning import clean_posts, clean_text, drop_near_duplicates
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
from pipeline.costs import format_usd
from pipeline.data_sources.extract_bluesky import MAX_SEARCH_PAGES, extract_posts, format_search_time
from pipeline.chitchat_guard import (
    edition_posts_for_clustering,
    get_chitchat_log,
    planet_chitchat_reason,
    reset_chitchat_log,
    write_chitchat_log,
)
from pipeline.edition_fill import run_edition_fill_loop
from pipeline.free_ingest import free_ingest_enabled, log_fetch_bucket_summary, stamp_candidate_sections
from pipeline.jev import apply_jev, classify_planet_section, describe_jev, known_scored_uris
from pipeline.spend_cap import (
    FILL_BUDGET_TOTAL_USD,
    SpendCapExceeded,
    day_paid_usd,
    guard_before_paid_call,
    is_fill_run,
)
from pipeline.cluster_math import salient_terms, vectorize
from pipeline.grouping import MIN_PLANET_POSTS, distinctness_score
from pipeline.schema import TOP_TERMS_LIMIT
from pipeline.settings import EXAMPLE_POST_CAP
from pipeline.label import (
    catchall_reasons,
    content_tokens,
    chitchat_flag,
    label_perspective,
    label_topic,
    name_from_perspectives,
    set_label_deadline,
    shares_claim_word,
    majority_story_groups,
    specific_shared_words,
    repeated_stems_below_floor,
    split_catchall_posts,
    story_groups,
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
from pipeline.stance import (
    apply_stance_pass,
    report_stance_check_failures,
    report_stance_check_incoherent,
    reset_stance_check_failures,
)
from pipeline.prompt_sample import cosines_to_matrix_centroid, planet_member_cosines, select_prompt_posts
from pipeline.schema import (
    CATEGORIES,
    MAX_FACES,
    MIN_FACES,
    STANCE_CHECK_FAILED,
    STANCE_CHECK_UNSHARED,
    STANCE_CHECK_INCOHERENT,
    SYSTEM_SIZE,
    apply_opposing_note,
    category_for_members,
    to_percents,
)
from pipeline.section_sanity import partition_politics_planets
from pipeline.settings import load_settings
from pipeline.store import (
    LIVE_CORPUS_DB,
    connect,
    drop_non_quality_posts,
    fetched_day_set,
    is_quality_post,
    load_posts,
    record_fetched_days,
    replace_posts,
    write_clusters,
    write_quality_posts,
)
from pipeline.story_attach import merge_alike_published_faces, return_same_story_posts
from pipeline.topics import CANDIDATE_POOL, cluster_texts

# Planets drafted at once when a network label backend is on (I/O bound).
DEFAULT_LABEL_WORKERS = 8
# Section planets share one pool. Each slot is one planet, and that planet
# makes its LLM calls one at a time, so this is also how many label calls are
# in flight across every section. The default ``label_workers`` of 8 becomes
# this wider pool; any other setting is used as the cap.
DEFAULT_SECTION_LABEL_IN_FLIGHT = 12
# Section solar systems get this many minutes after the global system is built.
# 0 is a real budget and skips sections. None means this default.
DEFAULT_SECTION_BUDGET_MINUTES = 30
# Wide face relabel keeps this much of the section window. Drafts stop
# submitting before it, so a full draft wave cannot leave relabel at 0 calls.
# A shorter remaining window reserves only half, so drafts still start.
SECTION_RELABEL_RESERVE_MINUTES = 6
SECTION_RELABEL_RESERVE_SECONDS = SECTION_RELABEL_RESERVE_MINUTES * 60
# GitHub Actions kills the pipeline job at this many minutes (pipeline.yml).
PIPELINE_JOB_LIMIT_MINUTES = 360
# Stop the fill search this long before the job limit so clustering, labeling,
# and the corpus upload can finish. Checked before each date window.
FILL_JOB_MARGIN_MINUTES = 45
# Safety stop if every day still returns posts. Budget and the job clock stop sooner.
FILL_MAX_LOOKBACK_DAYS = 120
# Days in a row whose search returned zero posts. A window that only repeats
# URIs already in the corpus does not count, and the walk keeps going.
FILL_EMPTY_WINDOWS_STOP = 14
ENV_JOB_STARTED_AT = "PERSPECTIVERSE_JOB_STARTED_AT"


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
    started_at = datetime.now(timezone.utc)
    # This process may already have recorded calls (a second live run, or
    # tests). The artifact should be this run only.
    try:
        from pipeline.costs import bind_cost_checkpoint, reset_meter

        reset_meter()
        bind_cost_checkpoint(started_at)
    except Exception as exc:
        print(f"WARNING: Cost meter reset skipped: {exc}", file=sys.stderr)
    reset_stance_check_failures()
    reset_coherence_stats()
    settings = load_settings(config)
    target = int(settings.get("sample_size") or TARGET_POSTS)
    database = Path(db_path) if db_path else LIVE_CORPUS_DB
    print(describe_jev())
    connection = connect(database)
    drop_non_quality_posts(connection)
    from pipeline.spend_cap import SpendCapExceeded, enforce_before_paid_work

    cleaned: list[dict] | None = None
    corpus_posts: list[dict] | None = None
    source = "bluesky"
    free_ingest = free_ingest_enabled(settings)
    stage_seconds: dict[str, float] = {}
    jev_planet_calls = 0
    edition_fill_done = False
    edition_pipeline: dict | None = None
    planet_posts: list[dict] | None = None
    try:
        enforce_before_paid_work()
        existing = load_posts(connection)
        carried_uris = {str(post.get("uri") or "") for post in existing if post.get("uri")}
        if free_ingest and fixture is None and not relabel:
            print(
                "Free ingest is on: spam and chit-chat guards instead of per-post Jev, "
                "edition-quality posts are stored, Jev runs once per planet."
            )
            ingest_started = time.monotonic()
            fill = run_edition_fill_loop(
                existing,
                settings,
                queries,
                target=target,
            )
            cleaned = fill.cleaned
            planet_posts = fill.planet_posts
            edition_pipeline = fill.pipeline_dict()
            stage_seconds["ingest"] = round(time.monotonic() - ingest_started, 3)
            source, refreshed = "bluesky", True
            edition_fill_done = True
        else:
            cleaned, source, refreshed = _collect_posts(
                existing,
                settings,
                fixture,
                queries,
                target,
                connection,
                relabel=relabel,
            )
        # Legacy per-post Jev. The schedule and a normal dispatch set
        # PERSPECTIVERSE_FREE_INGEST=1, so they never reach this call. It
        # scores the full cleaned list (stored rows plus the morning fetch)
        # before any top-up. A free-ingest corpus has no per-post verdicts;
        # sending about 100K of those rows here is the ~$2.78 path that hits
        # the $1 stop and publishes nothing.
        if source == "bluesky" and not relabel and not free_ingest:
            corpus_posts = list(cleaned)
            scored = apply_jev(
                corpus_posts,
                connection=connection,
                batch=_jev_batch(settings),
                update_input=True,
            )
            _merge_jev_output(corpus_posts, scored)
            # Only quality claims are stored or clustered. Rejected URIs stay in the Jev cache.
            cleaned = [p for p in corpus_posts if is_quality_post(p)]
            corpus_posts = list(cleaned)
            fill_span_hours = 0
            if is_fill_run():
                # Fill only. Scheduled and push runs keep the single latest search.
                cleaned, corpus_posts, fill_span_hours = _fill_claims_by_day(
                    cleaned,
                    target=target,
                    settings=settings,
                    connection=connection,
                    corpus_posts=corpus_posts,
                    queries=queries,
                )
            elif refreshed and len(cleaned) < target:
                # Top up: keep fetching until claim count reaches target so the
                # rolling window stays at the threshold, not below it.
                cleaned, corpus_posts = _topup_claims(
                    cleaned,
                    target=target,
                    settings=settings,
                    connection=connection,
                    corpus_posts=corpus_posts,
                )
            if refreshed or fill_span_hours:
                before = len(cleaned)
                hours = int(settings["window_hours"])
                if fill_span_hours:
                    hours = max(hours, fill_span_hours)
                cleaned = retire_oldest(
                    cleaned,
                    now=datetime.now(timezone.utc),
                    window_hours=hours,
                    target=target,
                )
                kept = len(cleaned)
                if kept < target:
                    print(f"Claim shortfall: {kept} of {target}. Bluesky could not fill the window.")
                elif before > kept:
                    print(f"Retired the oldest posts down to {kept} of {target}.")
        if not cleaned:
            raise RuntimeError("No quality posts in the retained corpus or the extract.")

        if source == "bluesky" and not relabel and not free_ingest:
            write_quality_posts(connection, cleaned)
        else:
            replace_posts(connection, cleaned)
        if not edition_fill_done:
            planet_posts = posts_for_planets(
                cleaned,
                require_claims=source == "bluesky" and not relabel and not free_ingest,
            )
            # Full set, from scratch. Yesterday's membership is deleted in write_clusters.
            # Link-only and non-English posts are removed here on both switch
            # settings. That filter is partition_posts, which main already ran.
            # DROP_LINK_AND_LANGUAGE_AT_INGEST=0 only lets them count in the
            # stored corpus; it does not put them in this clustering set.
            before_filter = len(planet_posts)
            carried_cluster_skips: dict[str, int] = {}
            planet_posts, skipped_language, skipped_links, skipped_chitchat = edition_posts_for_clustering(
                planet_posts,
                carried_uris=carried_uris,
                carried_skips=carried_cluster_skips,
            )
            if carried_cluster_skips:
                print(
                    "Carried-over clustering filters: "
                    f"chitchat={carried_cluster_skips.get('chitchat', 0)}, "
                    f"link_only={carried_cluster_skips.get('link_only', 0)}, "
                    f"language={carried_cluster_skips.get('language', 0)}."
                )
            if skipped_language or skipped_links:
                print(
                    f"Skipped {skipped_language} non-English and {skipped_links} link-only "
                    f"before clustering ({before_filter} were eligible)."
                )
            if skipped_chitchat:
                print(
                    f"Skipped {skipped_chitchat} chit-chat post(s) before clustering "
                    f"({before_filter - skipped_language - skipped_links} remained)."
                )
            edition_pipeline = {
                "target_quality_posts": target,
                "ingest_stored": len(cleaned),
                "before_language_filter": before_filter,
                "skipped_non_english": skipped_language,
                "skipped_link_only": skipped_links,
                "skipped_chitchat_cluster_pass": skipped_chitchat,
                "carried_cluster_skips": carried_cluster_skips,
                "edition_posts_for_clustering": len(planet_posts),
            }
        else:
            skipped_language = int(edition_pipeline.get("skipped_non_english") or 0)
            skipped_links = int(edition_pipeline.get("skipped_link_only") or 0)
            skipped_chitchat = int(edition_pipeline.get("skipped_chitchat_cluster_pass") or 0)
            before_filter = int(edition_pipeline.get("before_language_filter") or 0)
            if skipped_language or skipped_links:
                print(
                    f"Skipped {skipped_language} non-English and {skipped_links} link-only "
                    f"before clustering ({before_filter} were eligible)."
                )
            if skipped_chitchat:
                print(
                    f"Skipped {skipped_chitchat} chit-chat post(s) before clustering "
                    f"({before_filter - skipped_language - skipped_links} remained)."
                )
        if not planet_posts:
            raise RuntimeError("No English claims left to cluster.")
        print(
            f"Reclustering {len(planet_posts)} edition-quality posts from scratch "
            f"({len(cleaned)} stored in corpus)."
        )
        texts = [
            clean_text(str(post.get("text") or post.get("clean_text") or ""))
            for post in planet_posts
        ]
        catalog_size = int(settings.get("catalog_size") or SYSTEM_SIZE)
        # Fixed floor. The corpus size does not raise it, and the group count
        # is not n // floor. Density clustering decides how many groups exist.
        floor = max(2, int(settings["min_cluster_size"]))
        # Rank every natural group. Labeling stops at catalog_size, so the
        # extra candidates are not extra model calls.
        pool = CANDIDATE_POOL
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
        cluster_seconds = time.monotonic() - started
        print(
            f"Timing: embedded and clustered {len(planet_posts)} claims into "
            f"{len(clustered['topics'])} candidate planets in {cluster_seconds:.1f}s."
        )
        if free_ingest:
            stage_seconds["cluster"] = round(cluster_seconds, 3)
            jev_planet_calls = stamp_candidate_sections(
                planet_posts, clustered, classify_planet_section
            )
        context = _label_context(settings)
        print(f"Labels: {context['chosen']} backend, {context['workers']} planet(s) at a time.")
        started = time.monotonic()
        topics, membership, face_rows = _build_topics(
            planet_posts, clustered, settings, keep=catalog_size, context=context
        )
        label_seconds = time.monotonic() - started
        print(f"Timing: {len(topics)} global planet(s) labeled in {label_seconds:.1f}s.")
        if free_ingest:
            stage_seconds["label"] = round(label_seconds, 3)
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
            section_seconds = time.monotonic() - started
            print(
                f"Timing: {len(sections)} section solar system(s), "
                f"{sum(len(items) for items in sections.values())} planet(s) in {section_seconds:.1f}s."
            )
            if free_ingest:
                stage_seconds["sections"] = round(section_seconds, 3)
        elif free_ingest:
            stage_seconds["sections"] = 0.0
        write_clusters(connection, membership, face_rows)
    except SpendCapExceeded as exc:
        from pipeline.corpus_persist import persist_paid_corpus

        persist_paid_corpus(
            connection,
            corpus_posts if corpus_posts is not None else cleaned,
            db_path=database,
        )
        _abort_for_spend_cap(started_at, exc)
        raise
    finally:
        try:
            from pipeline.costs import flush_cost_checkpoint

            flush_cost_checkpoint()
        except Exception as exc:
            print(f"WARNING: Cost checkpoint on exit skipped: {exc}", file=sys.stderr)
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
        f"Live snapshot: {len(planet_posts)} edition-quality posts "
        f"from {len(cleaned)} stored in the window, "
        f"{clustered['noise_count']} excluded as clustering noise, wrote {destination}"
    )
    if free_ingest:
        log_fetch_bucket_summary()
    _log_fill_run_summary(payload)
    _write_cost_run(payload, started_at, edition_pipeline=edition_pipeline)
    if free_ingest:
        from pipeline.free_ingest_preview import write_stage_timings

        write_stage_timings(
            database.parent / "free_ingest_stages.json",
            wall_seconds=stage_seconds,
            jev_planet_label_calls=jev_planet_calls,
            edition_pipeline=edition_pipeline,
            chitchat_ingest=get_chitchat_log().to_dict(),
        )
        write_chitchat_log(database.parent / "chitchat_removed.json")
    return destination


def _log_fill_run_summary(payload: dict | None = None) -> None:
    """Planet and labeling totals for a fill dispatch (success or cap halt)."""
    from pipeline.spend_cap import is_fill_run

    if not is_fill_run():
        return
    from pipeline.costs import LLM_SERVICES, count_published_planets, get_meter

    planets = count_published_planets(payload) if payload else 0
    labeling_calls = sum(1 for attempt in get_meter().attempts() if attempt.service in LLM_SERVICES)
    print(f"Fill run: {planets} published planet(s), {labeling_calls} labeling call(s).")


def _abort_for_spend_cap(started_at: datetime, exc: SpendCapExceeded) -> None:
    """Write the cost run and stop marker. Do not write ``data.json``.

    The retained corpus should already be saved by ``persist_paid_corpus``.
    """
    print(
        "Daily spend cap halted the pipeline before publish. "
        "Yesterday's edition stays.",
        file=sys.stderr,
    )
    _log_fill_run_summary()
    try:
        from pipeline.costs import get_meter, write_cost_run
        from pipeline.spend_cap import cost_run_path, write_stop_marker

        write_cost_run(
            posts_processed=0,
            planets_published=0,
            started_at=started_at,
            path=cost_run_path(),
            attempts=get_meter().attempts(),
        )
        write_stop_marker(exc)
    except Exception as log_exc:
        print(f"WARNING: Spend cap stop log skipped: {log_exc}", file=sys.stderr)


def _write_cost_run(
    payload: dict,
    started_at: datetime,
    *,
    edition_pipeline: dict | None = None,
) -> None:
    """Best effort. A cost-log error must not fail a snapshot that already wrote."""
    pending_kept = unshared_pending_planet_count()
    failed_checks = report_stance_check_failures()
    incoherent_checks = report_stance_check_incoherent()
    report_unshared_pending_planets()
    report_coherence_stats()
    try:
        from pipeline.costs import (
            count_published_planets,
            deepinfra_error_summary,
            get_meter,
            update_cost_checkpoint_counts,
            write_cost_run,
        )
        from pipeline.publish_guard import report_label_health, write_label_run

        summary = deepinfra_error_summary(get_meter().attempts())
        update_cost_checkpoint_counts(
            posts_processed=int(payload.get("total_posts") or 0),
            planets_published=count_published_planets(payload),
        )
        fill_reason = None
        fill_target = None
        if isinstance(edition_pipeline, dict):
            fill_reason = edition_pipeline.get("edition_fill_stop_reason")
            fill_target = edition_pipeline.get("target_quality_posts")
        write_cost_run(
            posts_processed=int(payload.get("total_posts") or 0),
            planets_published=count_published_planets(payload),
            started_at=started_at,
            deepinfra_errors=summary,
            stance_check_failed=failed_checks,
            stance_check_incoherent=incoherent_checks,
            kept_pending_unshared=pending_kept,
            edition_fill_stop_reason=str(fill_reason) if fill_reason else None,
            edition_quality_target=int(fill_target) if fill_target is not None else None,
        )
        face = section_face_relabel()
        try:
            write_label_run(
                deepinfra_errors=summary,
                face_relabel=face,
                section_planets=_count_section_planets(payload),
            )
        except Exception as exc:
            print(f"WARNING: Label run log skipped: {exc}", file=sys.stderr)
        report_label_health(summary)
        if int(face.get("sections_queued") or 0):
            from pipeline.publish_guard import append_github_step_summary

            relabel_line = (
                "Section face relabel: "
                f"{face['calls_completed']} of {face['calls_queued']} call(s) finished; "
                f"{face['sections_incomplete']} of {face['sections_queued']} section(s) unfinished."
            )
            print(relabel_line)
            append_github_step_summary(relabel_line + "\n")
    except Exception as exc:
        print(f"WARNING: Cost log skipped: {exc}", file=sys.stderr)


def _count_section_planets(payload: dict) -> int:
    sections = payload.get("sections") or {}
    if not isinstance(sections, dict):
        return 0
    total = 0
    for planets in sections.values():
        if isinstance(planets, list):
            total += len(planets)
    return total


def _jev_batch(settings: dict) -> bool:
    """Phase 3 stays off unless the pipeline setting says otherwise."""
    return bool(settings.get("jev_batch"))


def _merge_jev_output(corpus_posts: list[dict], scored: list[dict]) -> None:
    """Copy Jev fields from ``scored`` onto the retained window by URI."""
    by_uri = {str(post.get("uri") or ""): post for post in scored if post.get("uri")}
    for index, post in enumerate(corpus_posts):
        uri = str(post.get("uri") or "")
        update = by_uri.get(uri)
        if update is not None:
            corpus_posts[index] = {**post, **update}


def _note_cache_reuses(count: int) -> None:
    """Count URIs the fetch skipped because a prior run already scored them."""
    if count <= 0:
        return
    try:
        from pipeline.costs import note_jev_cache_hits, note_jev_cache_lookups

        note_jev_cache_hits(count)
        note_jev_cache_lookups(count)
    except Exception as exc:
        print(f"WARNING: Jev cache reuse was not counted: {exc}", file=sys.stderr)


def _extract_skipping_cached(cache_only: set[str], **kwargs) -> list[dict]:
    """Fetch posts, counting cached URIs that search handed back."""
    reused: set[str] = set()
    incoming = extract_posts(cache_uris=cache_only, cache_reused=reused, **kwargs)
    _note_cache_reuses(len(reused))
    if reused:
        cache_only.difference_update(reused)
    return incoming


def _topup_claims(
    claims: list[dict],
    *,
    target: int,
    settings: dict,
    max_rounds: int = 6,
    connection=None,
    corpus_posts: list[dict] | None = None,
) -> tuple[list[dict], list[dict] | None]:
    """Fetch additional posts and Jev-classify them until claim count reaches target.

    Each round over-fetches by 4× the remaining gap to account for the Bluesky
    claim rate (~30 %). Stops early if Bluesky returns nothing new or max_rounds
    is exhausted — the caller still gets whatever claims were collected.
    """
    result = list(claims)
    seen = {post.get("uri") for post in result if post.get("uri")}
    now = datetime.now(timezone.utc)
    cache_only: set[str] = set()
    if connection is not None:
        verdicts = known_scored_uris(connection, result, now=now)
        cache_only = verdicts - seen
        seen.update(verdicts)
    neutral = [item for item in (settings.get("neutral_queries") or []) if item]
    refresh_hours = int(settings.get("refresh_hours") or 24)
    # Use a shifted seed so each round samples a different slice of Bluesky.
    rng = random.Random(int(settings["seed"]) + len(result))

    for round_num in range(1, max_rounds + 1):
        gap = target - len(result)
        if gap <= 0:
            break
        # 4× overfetch compensates for the ~25–35 % claim rate on Bluesky.
        fetch_size = min(gap * 4, 5000)
        try:
            incoming = _extract_skipping_cached(
                cache_only,
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
        scored = list(fresh)
        apply_jev(
            scored,
            connection=connection,
            batch=_jev_batch(settings),
            update_input=True,
        )
        if corpus_posts is not None:
            corpus_posts.extend([post for post in scored if is_quality_post(post)])
        new_claims = [p for p in scored if is_quality_post(p)]
        result.extend(new_claims)
        print(
            f"Top-up {round_num}: {len(new_claims)} claims from {len(fresh)} posts "
            f"(total {len(result)}/{target})."
        )

    return result, corpus_posts


def _job_started_at(now: datetime) -> datetime:
    """When the Actions job began, or ``now`` when the clock was not recorded."""
    raw = (os.getenv(ENV_JOB_STARTED_AT) or "").strip()
    if not raw:
        return now
    started = parse_created(raw)
    if started.year < 2000:
        return now
    return started


def fill_past_safe_margin(now: datetime) -> bool:
    """True when the 360-minute job has no more than the fill margin left."""
    started = _job_started_at(now)
    deadline = started + timedelta(minutes=PIPELINE_JOB_LIMIT_MINUTES - FILL_JOB_MARGIN_MINUTES)
    return now >= deadline


def _fill_queries(settings: dict, queries: list[str] | None) -> list[str]:
    chosen = [item for item in (queries or []) if item]
    if chosen:
        return chosen
    return [item for item in (settings.get("neutral_queries") or []) if item]


def _fill_claims_by_day(
    claims: list[dict],
    *,
    target: int,
    settings: dict,
    connection,
    corpus_posts: list[dict] | None,
    queries: list[str] | None = None,
    now: datetime | None = None,
    clock=None,
) -> tuple[list[dict], list[dict] | None, int]:
    """Fill only: repeat each query on older UTC days until a stop condition.

    Bluesky search caps a query at about 40 pages, so one latest search is
    about 11K posts. Each UTC day (``since`` / ``until``) gets its own pages.
    Stops when quality posts (Jev claims that are not spam) reach ``target``.
    That number is ``TARGET_POSTS``, the one corpus constant, when the caller
    passes the default. Also stops before a paid call once fill spend is at
    ``FILL_BUDGET_TOTAL_USD``, when the job clock is inside the safe margin,
    after ``FILL_MAX_LOOKBACK_DAYS``, or after ``FILL_EMPTY_WINDOWS_STOP``
    searches in a row that returned zero posts. Spam and non-claims are not
    kept. A window whose posts are all already in the corpus does not count
    as empty. The current UTC day is not searched again when the corpus
    already has a post from that day (the latest search just ran). Does not
    change ``catalog_size`` (10 planets per solar system).

    Returns quality claims, the corpus list (quality posts, plus an in-flight
    window when the spend cap halts mid-batch), and the hour span to keep
    when retiring. The span is 0 when this walk added no posts.
    ``SpendCapExceeded`` propagates so the caller keeps posts already paid for.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    tick = clock or (lambda: datetime.now(timezone.utc))
    result = list(claims)
    if corpus_posts is None:
        corpus_posts = list(result)
    seen = {post.get("uri") for post in corpus_posts if post.get("uri")}
    cache_only: set[str] = set()
    if connection is not None:
        verdicts = known_scored_uris(connection, result, now=moment)
        cache_only = verdicts - seen
        seen.update(verdicts)
    fetch_queries = _fill_queries(settings, queries)
    rng = random.Random(int(settings.get("seed") or 0) + len(result))
    oldest_since: datetime | None = None
    newest_until: datetime | None = None
    windows = 0
    empty_streak = 0
    stop_reason = "lookback limit"
    day = moment.date()

    def _log_window(since: datetime, until: datetime, posts: int, *, note: str = "") -> None:
        extra = f" {note}" if note else ""
        print(
            f"Fill window {format_search_time(since)} .. {format_search_time(until)}: "
            f"{posts} posts{extra}, {len(result)} quality posts so far, "
            f"spend ${format_usd(day_paid_usd())} of ${format_usd(FILL_BUDGET_TOTAL_USD)}."
        )

    def _log_range() -> None:
        spent = f"spend ${format_usd(day_paid_usd())} of ${format_usd(FILL_BUDGET_TOTAL_USD)}"
        if oldest_since is not None and newest_until is not None:
            print(
                f"Fill date range {format_search_time(oldest_since)} .. {format_search_time(newest_until)}: "
                f"{windows} window(s), {len(result)} quality posts so far, "
                f"{spent} (stop: {stop_reason})."
            )
        else:
            print(
                f"Fill date range: none. {len(result)} quality posts so far, "
                f"{spent} (stop: {stop_reason})."
            )

    try:
        if len(result) >= target:
            stop_reason = "quality posts"
        elif not fetch_queries:
            stop_reason = "no search queries"
            print("Fill walk skipped: no search queries.")
        else:
            # The latest search already covered today when those posts are on
            # the corpus. Skip that window instead of paying for it again.
            start_offset = 1 if posts_on_utc_date(corpus_posts, day.isoformat()) else 0
            if start_offset:
                print(
                    f"Fill skipped {day.isoformat()}: the corpus already has posts from that UTC day."
                )
            for offset in range(start_offset, FILL_MAX_LOOKBACK_DAYS):
                if len(result) >= target:
                    stop_reason = "quality posts"
                    break
                if fill_past_safe_margin(tick()):
                    stop_reason = (
                        f"job time margin ({FILL_JOB_MARGIN_MINUTES} minutes left "
                        f"of {PIPELINE_JOB_LIMIT_MINUTES})"
                    )
                    print(
                        f"Fill stopped: the {PIPELINE_JOB_LIMIT_MINUTES}-minute job limit "
                        f"has {FILL_JOB_MARGIN_MINUTES} minutes or less left. "
                        f"{len(result)} quality posts so far."
                    )
                    break
                since = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(days=offset)
                until = since + timedelta(days=1)
                try:
                    incoming = _extract_skipping_cached(
                        cache_only,
                        sample_size=max(target, 1),
                        window_hours=int(settings.get("window_hours") or 168),
                        queries=fetch_queries,
                        rng=rng,
                        now=moment,
                        skip_uris=seen,
                        since=since,
                        until=until,
                        pages=MAX_SEARCH_PAGES,
                        subsample=False,
                    )
                except RuntimeError as exc:
                    print(
                        f"Fill window {format_search_time(since)} .. {format_search_time(until)} "
                        f"failed ({exc})."
                    )
                    incoming = []
                fresh = []
                for post in drop_near_duplicates(clean_posts(incoming)):
                    uri = post.get("uri")
                    if not uri or uri in seen:
                        continue
                    seen.add(uri)
                    fresh.append(post)
                windows += 1
                if oldest_since is None or since < oldest_since:
                    oldest_since = since
                if newest_until is None or until > newest_until:
                    newest_until = until
                if not incoming:
                    empty_streak += 1
                    _log_window(since, until, 0)
                    if empty_streak >= FILL_EMPTY_WINDOWS_STOP:
                        stop_reason = f"{FILL_EMPTY_WINDOWS_STOP} empty days"
                        print(
                            f"Fill stopped: {FILL_EMPTY_WINDOWS_STOP} date windows in a row "
                            "returned no posts."
                        )
                        break
                    continue
                if not fresh:
                    # Search returned posts, but every URI was already seen.
                    # Keep walking. The 120-day lookback, the $15 fill total,
                    # and the job-time margin still bound the walk.
                    empty_streak = 0
                    _log_window(
                        since,
                        until,
                        0,
                        note=f"({len(incoming)} from search, none new)",
                    )
                    continue
                empty_streak = 0
                # Paid scoring starts here. Refuse the batch once fill spend
                # is already at the cap, before another Jev call.
                try:
                    guard_before_paid_call("Jev")
                except SpendCapExceeded:
                    stop_reason = "fill spend cap"
                    _log_window(since, until, len(fresh))
                    raise
                batch = list(fresh)
                corpus_posts.extend(batch)
                try:
                    apply_jev(
                        batch,
                        connection=connection,
                        batch=_jev_batch(settings),
                        update_input=True,
                    )
                except SpendCapExceeded:
                    stop_reason = "fill spend cap"
                    new_claims = [post for post in batch if is_quality_post(post)]
                    result.extend(new_claims)
                    _log_window(since, until, len(fresh))
                    raise
                new_claims = [post for post in batch if is_quality_post(post)]
                result.extend(new_claims)
                batch_uris = {post.get("uri") for post in batch}
                corpus_posts[:] = [
                    post
                    for post in corpus_posts
                    if post.get("uri") not in batch_uris or is_quality_post(post)
                ]
                if connection is not None:
                    record_fetched_days(
                        connection,
                        [since.date().isoformat()],
                        fetched_at=moment.isoformat(),
                        kept=len(result),
                    )
                _log_window(since, until, len(fresh))
            else:
                stop_reason = f"lookback limit ({FILL_MAX_LOOKBACK_DAYS} days)"
    finally:
        _log_range()

    span_hours = 0
    if oldest_since is not None and len(result) > len(claims):
        span_hours = int((moment - oldest_since).total_seconds() // 3600) + 24
    return result, corpus_posts, span_hours


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
    verdicts = known_scored_uris(connection, existing, now=moment)
    cache_only = verdicts - seen
    seen.update(verdicts)
    rounds = 0
    while len(pulled) < quota and rounds < 6:
        rounds += 1
        try:
            incoming = _extract_skipping_cached(
                cache_only,
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
        "prompt_sample_size": int(settings.get("prompt_sample_size") or 40),
        "draft_prompt_sample_size": int(settings.get("draft_prompt_sample_size") or 12),
        "planet_prompt_sample_size": int(settings.get("planet_prompt_sample_size") or 20),
        "seed": int(settings["seed"]),
        "workers": workers,
        "min_planet_posts": _planet_post_floor(settings),
        "stance_second_face_share": settings.get("stance_second_face_share"),
    }


# A planet whose labels collapse below MIN_FACES may try this many other
# passing face counts (best fit first) before it is dropped.
_FACE_RETRIES = 1
# A glued candidate is split into stories, and each story is split again
# the same way. This stops a grab-bag from being cut one post at a time.
_STORY_SPLIT_LIMIT = 3
# A catch-all re-split drafts the largest specific stories, not every speck.
_CATCHALL_CHILD_CAP = 8
# A split child this small does not take a global catalog slot ahead of a
# later candidate. It is published only if the catalog still has room after
# those candidates. Section catalogs are unchanged: that is where a catch-all
# such as Technology "Think" is supposed to become specific planets.
_SPLIT_CATALOG_POSTS = 15

_coherence_lock = threading.Lock()
_coherence_stats = {
    "shared_planets": 0,
    "shared_uris": set(),
    "blocked_planets": 0,
    "blocked_uris": set(),
    "leftover_uris": set(),
    "held_uris": set(),
    "drops": [],
}
_unshared_pending_planets: list[tuple[str, int]] = []


def reset_coherence_stats() -> None:
    """Clear the per-run catch-all counters. Called at the start of a live run."""
    global _coherence_stats, _unshared_pending_planets
    with _coherence_lock:
        _coherence_stats = {
            "shared_planets": 0,
            "shared_uris": set(),
            "blocked_planets": 0,
            "blocked_uris": set(),
            "leftover_uris": set(),
            "held_uris": set(),
            "drops": [],
        }
        _unshared_pending_planets = []


def note_unshared_pending_planet(name: str, post_count: int) -> None:
    """One catalog planet kept with the pending reader line after every face failed the shared-claim check."""
    with _coherence_lock:
        _unshared_pending_planets.append((str(name or "").strip() or "?", int(post_count or 0)))


def unshared_pending_planet_count() -> int:
    """Planets kept as pending after every face failed the shared-claim check."""
    with _coherence_lock:
        return len(_unshared_pending_planets)


def report_unshared_pending_planets() -> int:
    """Stderr summary for planets published as pending instead of dropped."""
    with _coherence_lock:
        rows = list(_unshared_pending_planets)
    count = len(rows)
    if not count:
        return 0
    largest = max(rows, key=lambda row: row[1])
    print(
        f"Kept as pending (no shared claim on any face): {count} planet(s); "
        f"largest {largest[0]!r} ({largest[1]} posts).",
        file=sys.stderr,
    )
    return count


def _note_uris(key_planets: str | None, key_uris: str, uris: list[str]) -> None:
    cleaned = [uri for uri in uris if uri]
    with _coherence_lock:
        if key_planets is not None:
            _coherence_stats[key_planets] += 1
            _coherence_stats["drops"].append((key_uris, cleaned))
        _coherence_stats[key_uris].update(cleaned)


def _forget_uris(uris: list[str]) -> None:
    """A rescued story is published, so its posts are not a vanished drop."""
    cleaned = {uri for uri in uris if uri}
    if not cleaned:
        return
    planet_key = {"blocked_uris": "blocked_planets", "shared_uris": "shared_planets"}
    with _coherence_lock:
        for key_uris in ("leftover_uris", "held_uris", "blocked_uris", "shared_uris"):
            _coherence_stats[key_uris].difference_update(cleaned)
        kept_drops = []
        removed: dict[str, int] = {}
        for key_uris, dropped in _coherence_stats["drops"]:
            remaining = [uri for uri in dropped if uri not in cleaned]
            if len(remaining) == len(dropped):
                kept_drops.append((key_uris, dropped))
                continue
            if remaining:
                kept_drops.append((key_uris, remaining))
                continue
            removed[key_uris] = removed.get(key_uris, 0) + 1
        _coherence_stats["drops"] = kept_drops
        for key_uris, count in removed.items():
            key_planets = planet_key.get(key_uris)
            if key_planets:
                _coherence_stats[key_planets] = max(0, int(_coherence_stats[key_planets]) - count)


def report_coherence_stats() -> dict:
    """Stderr summary. Separate from stance-check failures and from each other."""
    with _coherence_lock:
        shared_planets = int(_coherence_stats["shared_planets"])
        shared_posts = len(_coherence_stats["shared_uris"])
        blocked_planets = int(_coherence_stats["blocked_planets"])
        blocked_posts = len(_coherence_stats["blocked_uris"])
        real_stories: set[str] = set()
        small_drops: set[str] = set()
        for key_uris, dropped in _coherence_stats["drops"]:
            target = real_stories if len(dropped) >= MIN_PLANET_POSTS else small_drops
            target.update(dropped)
        held = set(_coherence_stats["held_uris"]) - real_stories
        leftovers = (set(_coherence_stats["leftover_uris"]) | held | small_drops) - real_stories
        vanished = real_stories | leftovers
    print(
        f"No face kept a shared claim: {shared_planets} planet(s), {shared_posts} unique posts.",
        file=sys.stderr,
    )
    print(
        f"Coherence blocked: {blocked_planets} planet(s), {blocked_posts} unique posts.",
        file=sys.stderr,
    )
    print(
        f"Vanished posts: {len(vanished)} unique. "
        f"Real stories with 5 or more posts: {len(real_stories)}. "
        f"Leftovers: {len(leftovers)} "
        f"({len(held)} in thin fragments held below 8 posts).",
        file=sys.stderr,
    )
    return {
        "shared_claim_planets": shared_planets,
        "shared_claim_posts": shared_posts,
        "coherence_blocked_planets": blocked_planets,
        "coherence_blocked_posts": blocked_posts,
        "vanished_posts": len(vanished),
        "vanished_real_stories": len(real_stories),
        "vanished_leftovers": len(leftovers),
        "vanished_held_fragments": len(held),
    }


def _planet_post_floor(settings: dict) -> int:
    """Posts a planet must already have before it is labeled. 0 disables the floor."""
    raw = settings.get("min_planet_posts")
    if raw is None:
        return MIN_PLANET_POSTS
    return max(0, int(raw))


def _below_planet_floor(count: int, context: dict) -> bool:
    floor = _planet_post_floor(context)
    return floor > 0 and count < floor


def _floor_log(context: dict, label: str, count: int) -> str:
    """One INFO line: section, label hint, and how many posts were left out."""
    section = str(context.get("section") or "All topics")
    noun = "post" if count == 1 else "posts"
    return f"INFO {section}: not publishing {label} ({count} {noun})."


def _exclude_for_floor(context: dict, log: list[str], label: str, count: int, samples: list[str]):
    """Leave a planet out. Nested splits return a count the parent can add up.

    A top-level miss is a drop, so the next candidate fills the catalog slot.
    Face labels already spent stay in the call counter. Name and brief calls
    have not been made.
    """
    log.append(_floor_log(context, label, count))
    excluded = [
        {
            "section": str(context.get("section") or "All topics"),
            "label": label,
            "posts": count,
            "samples": samples,
        }
    ]
    if int(context.get("story_depth") or 0) == 0:
        return _emit_draft(
            context,
            None,
            log,
            split=False,
            detection_faces=int(context["story_calls"]["faces"]),
            skipped=1,
            floor_excluded=1,
            excluded=excluded,
        )
    return {
        "planets": [],
        "skipped": 1,
        "floor_excluded": 1,
        "excluded": excluded,
        "detection_faces": int(context["story_calls"]["faces"]),
    }, log


def _post_samples(posts: list[dict], limit: int = 2) -> list[str]:
    samples = []
    for post in posts[:limit]:
        text = " ".join(str(post.get("text") or post.get("clean_text") or "").split())
        if text:
            samples.append(text[:220])
    return samples


def _label_faces(
    members: list[dict],
    split: dict,
    terms: list[str],
    context: dict,
    *,
    member_matrix=None,
    lock_floor: bool = False,
    prompt_cap: int | None = None,
) -> tuple[list[tuple[dict, list[tuple[str, int, float]], int]], int]:
    """Label each face of one split. Returns surviving drafts and how many were labeled.

    A face that admits no shared claim is dropped. That decision uses a spread
    of the face, not the few posts closest to the centroid. Faces whose titles
    are the same stance are merged. One remaining face is kept. ``lock_floor``
    skips that drop.
    """
    backend = context["backend"]
    model = context["model"]
    limit = context["limit"]
    if prompt_cap is None:
        prompt_cap = int(context.get("draft_prompt_sample_size") or 12)
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
        face_vectors = None
        if member_matrix is not None:
            face_vectors = member_matrix[face["member_indices"]]
        if context.get("chosen") == "heuristic":
            labeling_posts = select_representatives(
                face_posts,
                face_distances,
                limit=min(int(limit), len(face_posts)),
                matches=face_cosines,
            )
            representatives = labeling_posts[: max(int(limit), 1)]
            labeling_limit = len(labeling_posts)
        else:
            prompt_posts = select_prompt_posts(
                face_posts,
                face_cosines,
                limit=min(prompt_cap, len(face_posts)),
                vectors=face_vectors,
            )
            representatives = sorted(
                prompt_posts[: max(int(limit), 1)],
                key=lambda post: (
                    -(float(post["match"]) if post.get("match") is not None else 0.0),
                    -int(post.get("likes") or 0),
                ),
            )
            labeling_posts = prompt_posts
            labeling_limit = len(prompt_posts)
        label = label_perspective(
            labeling_posts,
            face["terms"] or terms,
            backend=backend,
            model=model,
            post_limit=labeling_limit,
        )
        arguments = label.get("arguments") or []
        title = str(label.get("title") or "")
        on_claim = [
            (index, post, score)
            for index, (post, score) in enumerate(zip(face_posts, face_cosines))
            if shares_claim_word(str(post.get("text") or post.get("clean_text") or ""), title)
        ]
        if len(on_claim) >= 3:
            claim_posts = [post for _index, post, _score in on_claim]
            claim_scores = [score for _index, _post, score in on_claim]
            claim_member_indices = [index for index, _post, _score in on_claim]
            if context.get("chosen") == "heuristic":
                representatives = select_representatives(
                    claim_posts,
                    [0.0] * len(claim_posts),
                    limit=int(limit),
                    matches=claim_scores,
                )
            else:
                claim_vectors = (
                    face_vectors[claim_member_indices] if face_vectors is not None else None
                )
                representatives = select_prompt_posts(
                    claim_posts,
                    claim_scores,
                    limit=min(prompt_cap, len(claim_posts)),
                    vectors=claim_vectors,
                )
                representatives = sorted(
                    representatives[: max(int(limit), 1)],
                    key=lambda post: (
                        -(float(post["match"]) if post.get("match") is not None else 0.0),
                        -int(post.get("likes") or 0),
                    ),
                )
        focus = " ".join([str(label.get("title") or ""), str(label.get("summary") or ""), *arguments])
        representatives = _align_representatives(representatives, focus)
        summary = _without_ungrounded_tail(str(label.get("summary") or ""), representatives)
        label["summary"] = summary
        # Judge the face on a spread of its posts, not the few closest to the centroid.
        sample = _claim_sample(face_posts, face_cosines)
        shares = _posts_share_a_subject(sample)
        if len(sample) >= 2 and not shares:
            label = {
                "title": "Mixed remarks",
                "summary": "These posts do not share a claim.",
                "label_source": "heuristic",
            }
            arguments = []
            representatives = _align_representatives(representatives, label["title"])
        elif _face_has_no_shared_claim(label) and shares:
            renamed = topic_name(list(face.get("terms") or terms))
            if renamed and _title_covers_posts(renamed, sample):
                label = {
                    "title": renamed,
                    "summary": summary or f"These posts are about {renamed}.",
                    "label_source": "heuristic",
                }
                arguments = []
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
        perspective["_draft_face_label"] = {
            "title": perspective["title"],
            "summary": perspective["summary"],
            "representative_posts": list(perspective["representative_posts"]),
            **({"arguments": list(perspective["arguments"])} if perspective.get("arguments") else {}),
        }
        rows = [
            (members[index]["uri"], position, float(split["distances"][index]))
            for index in face["member_indices"]
        ]
        perspective["_face_member_uris"] = [str(uri) for uri, _position, _distance in rows]
        drafted.append((perspective, rows, int(face["size"])))
    labeled = len(drafted)
    # Local to this draft (the caller copied context). Parallel planets do not share it.
    context["_raw_face_drafts"] = list(drafted)
    if lock_floor:
        return drafted[:MAX_FACES], labeled
    kept = [item for item in drafted if not _face_has_no_shared_claim(item[0])]
    dropped = [item for item in drafted if _face_has_no_shared_claim(item[0])]
    kept, restored = return_same_story_posts(kept, dropped, members)
    left_out = sum(int(item[2]) for item in dropped) - restored
    if left_out > 0 and kept:
        published = sum(int(item[2]) for item in kept)
        print(
            f"INFO {topic_name(terms)}: {left_out} of {len(members)} posts stayed off "
            f"the published face count ({published}). They were on a dropped face "
            "and did not match the kept face."
        )
    drafted = _merge_alike_drafts(kept, limit)
    return drafted, labeled


def _restore_draft_face(face: dict, draft: dict) -> None:
    face["title"] = draft["title"]
    face["summary"] = draft["summary"]
    face["representative_posts"] = list(draft.get("representative_posts") or [])
    if draft.get("arguments"):
        face["arguments"] = list(draft["arguments"])
    else:
        face.pop("arguments", None)


def _draft_needs_priority_relabel(draft: dict) -> bool:
    """Wide relabel first when the 12-post draft is thin or unshared."""
    args = draft.get("arguments") or []
    return _face_has_no_shared_claim(draft) or len(args) < 2


def _should_apply_wide_label(draft: dict, wide: dict) -> bool:
    """Never replace a named (non-Mixed) draft with a Mixed wide relabel."""
    if not _face_has_no_shared_claim(wide):
        return True
    return _face_has_no_shared_claim(draft)


class _FinalizeFaceJob:
    """One wide 40-post relabel for a published face."""

    __slots__ = (
        "section",
        "face",
        "draft",
        "face_posts",
        "face_vectors",
        "face_cosines",
        "face_terms",
        "context",
        "limit",
        "priority",
    )

    def __init__(
        self,
        *,
        section: str,
        face: dict,
        draft: dict,
        face_posts: list[dict],
        face_vectors,
        face_cosines: list[float],
        face_terms: list[str],
        context: dict,
        limit: int,
    ):
        self.section = section
        self.face = face
        self.draft = draft
        self.face_posts = face_posts
        self.face_vectors = face_vectors
        self.face_cosines = face_cosines
        self.face_terms = face_terms
        self.context = context
        self.limit = limit
        self.priority = 0 if _draft_needs_priority_relabel(draft) else 1


def _collect_finalize_face_jobs(
    topics: list[dict],
    posts: list[dict],
    clustered: dict,
    context: dict,
    *,
    section: str,
) -> list[_FinalizeFaceJob]:
    post_by_uri = {str(post.get("uri") or ""): post for post in posts}
    uri_to_row = {str(post.get("uri") or ""): index for index, post in enumerate(posts)}
    matrix = clustered.get("matrix")
    limit = int(context.get("limit") or 36)
    jobs: list[_FinalizeFaceJob] = []
    for topic in topics:
        member_uris = list(topic.get("_member_uris") or [])
        if not member_uris:
            continue
        row_indices = [uri_to_row[uri] for uri in member_uris if uri in uri_to_row]
        member_matrix = matrix[row_indices] if matrix is not None and row_indices else None
        for face in topic.get("perspectives") or []:
            draft = face.get("_draft_face_label")
            face_uris = list(face.get("_face_member_uris") or [])
            if face.get("stance_locked"):
                continue
            if not draft or not face_uris:
                continue
            local_indices = []
            face_posts = []
            for uri in face_uris:
                if uri not in post_by_uri or uri not in member_uris:
                    continue
                local_indices.append(member_uris.index(uri))
                face_posts.append(post_by_uri[uri])
            if not face_posts:
                continue
            face_vectors = member_matrix[local_indices] if member_matrix is not None else None
            face_cosines = (
                cosines_to_matrix_centroid(face_vectors)
                if face_vectors is not None
                else [0.0] * len(face_posts)
            )
            face_terms = list(face.get("top_terms") or [])
            jobs.append(
                _FinalizeFaceJob(
                    section=section,
                    face=face,
                    draft=dict(draft),
                    face_posts=face_posts,
                    face_vectors=face_vectors,
                    face_cosines=face_cosines,
                    face_terms=face_terms,
                    context=context,
                    limit=limit,
                )
            )
    return jobs


def _fair_finalize_order(jobs: list[_FinalizeFaceJob]) -> list[_FinalizeFaceJob]:
    """Priority relabels first; within each tier, round-robin sections fairly."""
    ordered: list[_FinalizeFaceJob] = []
    for priority in (0, 1):
        tier = [job for job in jobs if job.priority == priority]
        by_section: dict[str, deque[_FinalizeFaceJob]] = defaultdict(deque)
        for job in sorted(tier, key=lambda item: (item.section, str(item.face.get("id") or ""))):
            by_section[job.section].append(job)
        sections = sorted(by_section)
        while any(by_section[name] for name in sections):
            for name in sections:
                if by_section[name]:
                    ordered.append(by_section[name].popleft())
    return ordered


def _apply_wide_label_to_face(face: dict, draft: dict, wide: dict) -> None:
    if not _should_apply_wide_label(draft, wide):
        return
    face["title"] = wide["title"]
    face["summary"] = wide["summary"]
    face["representative_posts"] = wide["representative_posts"]
    if wide.get("arguments"):
        face["arguments"] = wide["arguments"]
    else:
        face.pop("arguments", None)


def _run_one_finalize_job(job: _FinalizeFaceJob) -> dict | None:
    return _wide_label_face_from_posts(
        job.face_posts,
        job.face_vectors,
        job.face_cosines,
        job.face_terms,
        job.context,
        limit=job.limit,
    )


def _bump_finalize_calls(context: dict) -> None:
    calls = context.setdefault("story_calls", {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0})
    lock = context.setdefault("_finalize_lock", threading.Lock())
    with lock:
        calls["finalize_faces"] = int(calls.get("finalize_faces") or 0) + 1
        calls["faces"] = int(calls.get("faces") or 0) + 1


def _empty_face_relabel() -> dict:
    return {
        "sections_queued": 0,
        "sections_incomplete": 0,
        "calls_queued": 0,
        "calls_completed": 0,
        "budget_exhausted": False,
    }


_section_face_relabel = _empty_face_relabel()


def reset_section_face_relabel() -> None:
    """Test seam. ``_cluster_sections`` also resets this at the start of a run."""
    global _section_face_relabel
    _section_face_relabel = _empty_face_relabel()


def section_face_relabel() -> dict:
    """Section wide-relabel counts for this process. Global relabel is not included."""
    return {
        "sections_queued": int(_section_face_relabel["sections_queued"]),
        "sections_incomplete": int(_section_face_relabel["sections_incomplete"]),
        "calls_queued": int(_section_face_relabel["calls_queued"]),
        "calls_completed": int(_section_face_relabel["calls_completed"]),
        "budget_exhausted": bool(_section_face_relabel["budget_exhausted"]),
    }


def _record_section_face_relabel(
    jobs: list[_FinalizeFaceJob],
    incomplete: set[str],
    completed_calls: int,
    budget_exhausted: bool,
) -> None:
    _section_face_relabel["sections_queued"] += len({job.section for job in jobs})
    _section_face_relabel["sections_incomplete"] += len(incomplete)
    _section_face_relabel["calls_queued"] += len(jobs)
    _section_face_relabel["calls_completed"] += int(completed_calls)
    if budget_exhausted:
        _section_face_relabel["budget_exhausted"] = True


def _run_finalize_faces_parallel(
    jobs: list[_FinalizeFaceJob],
    workers: int,
    deadline: float | None,
    *,
    scope: str,
    record: bool = False,
) -> set[str]:
    """Run wide relabels with a bounded pool. Returns sections with queued calls left."""
    if not jobs:
        return set()
    workers = max(1, int(workers))
    order = _fair_finalize_order(jobs)
    started = time.monotonic()
    completed_calls = 0
    incomplete: set[str] = set()
    print(f"Wide face relabel: {len(order)} call(s) queued, {workers} in flight ({scope}).")
    executor = ThreadPoolExecutor(max_workers=workers)
    inflight: dict = {}
    cursor = 0
    budget_exhausted = False
    last_finish_at: float | None = None
    try:
        while cursor < len(order) or inflight:
            while not budget_exhausted and cursor < len(order) and len(inflight) < workers:
                if deadline is not None and time.monotonic() >= deadline:
                    budget_exhausted = True
                    break
                job = order[cursor]
                cursor += 1
                future = executor.submit(_run_one_finalize_job, job)
                inflight[future] = job
            if not inflight:
                break
            done, _pending = wait(set(inflight), return_when=FIRST_COMPLETED)
            for future in done:
                job = inflight.pop(future)
                try:
                    wide = future.result()
                except SpendCapExceeded:
                    raise
                except Exception as exc:  # noqa: BLE001 - keep draft label on failure
                    print(f"Wide face relabel failed ({type(exc).__name__}); keeping draft label.")
                    continue
                completed_calls += 1
                last_finish_at = time.monotonic()
                _bump_finalize_calls(job.context)
                _apply_wide_label_to_face(job.face, job.draft, wide)
        if budget_exhausted:
            for job in order[cursor:]:
                incomplete.add(job.section)
    finally:
        executor.shutdown(wait=True)
    elapsed = time.monotonic() - started
    if budget_exhausted and deadline is not None and last_finish_at is not None:
        past = last_finish_at - deadline
        if past > 0:
            print(f"Wide face relabel: last in-flight call finished {past:.1f}s past the section deadline.")
    if incomplete:
        sections = ", ".join(sorted(incomplete))
        print(
            f"Wide face relabel: {completed_calls} call(s) in {elapsed:.1f}s; "
            f"time budget spent before finishing {sections}."
        )
    else:
        print(f"Wide face relabel: {completed_calls} call(s) in {elapsed:.1f}s.")
    if record:
        _record_section_face_relabel(jobs, incomplete, completed_calls, budget_exhausted)
        stats = section_face_relabel()
        print(
            "Wide face relabel sections: "
            f"{stats['sections_queued']} queued, {stats['sections_incomplete']} unfinished, "
            f"{stats['calls_queued']} call(s) queued, {stats['calls_completed']} completed."
        )
    return incomplete


def _wide_label_face_from_posts(
    face_posts: list[dict],
    face_vectors,
    face_cosines: list[float],
    face_terms: list[str],
    context: dict,
    *,
    limit: int,
) -> dict:
    """One wide MMR labeling pass. Raises on network failure."""
    final_cap = int(context.get("prompt_sample_size") or 40)
    backend = context["backend"]
    model = context["model"]
    prompt_posts = select_prompt_posts(
        face_posts,
        face_cosines,
        limit=min(final_cap, len(face_posts)),
        vectors=face_vectors,
    )
    representatives = sorted(
        prompt_posts[: max(int(limit), 1)],
        key=lambda post: (
            -(float(post["match"]) if post.get("match") is not None else 0.0),
            -int(post.get("likes") or 0),
        ),
    )
    label = label_perspective(
        prompt_posts,
        face_terms,
        backend=backend,
        model=model,
        post_limit=len(prompt_posts),
    )
    arguments = label.get("arguments") or []
    title = str(label.get("title") or "")
    on_claim = [
        (index, post, score)
        for index, (post, score) in enumerate(zip(face_posts, face_cosines))
        if shares_claim_word(str(post.get("text") or post.get("clean_text") or ""), title)
    ]
    if len(on_claim) >= 3:
        claim_posts = [post for _index, post, _score in on_claim]
        claim_scores = [score for _index, _post, score in on_claim]
        claim_member_indices = [index for index, _post, _score in on_claim]
        claim_vectors = face_vectors[claim_member_indices] if face_vectors is not None else None
        representatives = select_prompt_posts(
            claim_posts,
            claim_scores,
            limit=min(final_cap, len(claim_posts)),
            vectors=claim_vectors,
        )
        representatives = sorted(
            representatives[: max(int(limit), 1)],
            key=lambda post: (
                -(float(post["match"]) if post.get("match") is not None else 0.0),
                -int(post.get("likes") or 0),
            ),
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
    return {
        "title": label["title"],
        "summary": label["summary"],
        "representative_posts": representatives,
        "arguments": arguments[:6] if len(arguments) >= 2 else None,
    }


def _strip_internal_planet_fields(topics: list[dict]) -> None:
    for topic in topics:
        topic.pop("_member_uris", None)
        for face in topic.get("perspectives") or []:
            face.pop("_draft_face_label", None)
            face.pop("_face_member_uris", None)
            face.pop("stance_locked", None)


def _finalize_published_planets(
    topics: list[dict],
    posts: list[dict],
    clustered: dict,
    context: dict,
    *,
    deadline: float | None = None,
) -> set[str]:
    """Wide 40-post relabel for catalog planets only (after slot selection)."""
    section = str(context.get("section") or "All topics")
    if context.get("chosen") == "heuristic" or not topics:
        merge_alike_published_faces(topics)
        _strip_internal_planet_fields(topics)
        return set()
    jobs = _collect_finalize_face_jobs(topics, posts, clustered, context, section=section)
    workers = _section_pool_size(context)
    incomplete = _run_finalize_faces_parallel(jobs, workers, deadline, scope=section)
    # Relabel can rename two faces onto one title after the draft merge already ran.
    merge_alike_published_faces(topics)
    _strip_internal_planet_fields(topics)
    return incomplete


def _finalize_section_planets_batch(jobs: list[_SectionLabelJob], deadline: float | None) -> set[str]:
    """One shared pool for every section's wide relabel after all drafts finish."""
    if not jobs:
        return set()
    if jobs[0].context.get("chosen") == "heuristic":
        for job in jobs:
            merge_alike_published_faces(job.built)
            _strip_internal_planet_fields(job.built)
        return set()
    face_jobs: list[_FinalizeFaceJob] = []
    for job in jobs:
        section = job.name
        face_jobs.extend(
            _collect_finalize_face_jobs(job.built, job.posts, job.clustered, job.context, section=section)
        )
    workers = _section_pool_size(jobs[0].context)
    incomplete = _run_finalize_faces_parallel(
        face_jobs,
        workers,
        deadline,
        scope=f"{len(jobs)} section(s)",
        record=True,
    )
    for job in jobs:
        merge_alike_published_faces(job.built)
        _strip_internal_planet_fields(job.built)
    return incomplete


def _draft_planet(posts: list[dict], clustered: dict, topic: dict, context: dict) -> tuple[dict | None, list[str]]:
    """Split, label, and check one candidate planet. Returns (draft or None, log lines).

    Only this planet's posts are touched, so drafts can run in parallel.
    The face count is the best fit in 2..6 (``split_perspectives``). If no
    count passes, the planet is one perspective and carries
    ``opposing_note``, unless the stance check failed. A second face is not
    forced. A "Mixed remarks" face
    is dropped; if one real face remains, the planet is still published. When
    every face fails the shared-claim check, the planet is kept as pending
    (#158). The planet is not dropped for having one face. When the faces are different stories
    (no specific shared subject word, or a smaller face whose posts mostly
    lack the largest face's top stem), the candidate is split into one
    planet per story and each story goes through this same split (#78).
    A catch-all (more than one story bucket, no shared claim, or a label
    term in under 30% of posts) is re-split into specific stories instead
    of being dropped (#104).
    A planet, or a story inside one, with fewer than ``min_planet_posts``
    posts is left out before any label, name, or brief call. It is not
    glued onto a sibling and it does not fill a catalog slot. The planet
    name and level summaries are written only for a planet that survives.
    A single-planet draft keeps the ``planet`` / ``membership`` /
    ``face_rows`` keys. A split draft returns ``planets`` instead.
    """
    depth = int(context.get("story_depth") or 0)
    if "story_calls" not in context:
        context = dict(context)
        context["story_calls"] = {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}
    log: list[str] = []
    members = [posts[index] for index in topic["member_indices"]]
    label = topic_name(list(topic.get("terms") or []))
    if _below_planet_floor(len(members), context):
        return _exclude_for_floor(context, log, label, len(members), _post_samples(members))
    backend = context["backend"]
    model = context["model"]
    member_texts = [post["clean_text"] for post in members]
    matrix = clustered.get("matrix")
    member_matrix = None
    if matrix is not None:
        member_matrix = matrix[topic["member_indices"]]
    terms = list(topic["terms"])
    split = split_perspectives(member_texts, seed=context["seed"], matrix=member_matrix)
    if not split["faces"]:
        log.append(f"Dropping {topic_name(terms)}: {split.get('reason') or 'no faces'}.")
        return _emit_draft(context, None, log, split=False, detection_faces=0)
    attempts = [split, *(split.get("alternatives") or [])[:_FACE_RETRIES]]
    drafted: list = []
    tried: list[str] = []
    chosen_split = split
    for attempt in attempts:
        drafted, labeled = _label_faces(members, attempt, terms, context, member_matrix=member_matrix)
        context["story_calls"]["faces"] += int(labeled)
        tried.append(f"k={attempt.get('k', len(attempt['faces']))}: {len(drafted)} of {labeled}")
        chosen_split = attempt
        if drafted:
            break
    raw_faces = _coherence_faces(context.pop("_raw_face_drafts", None) or drafted)
    cluster_label = topic_name(terms)
    reasons = catchall_reasons(raw_faces, members, cluster_label)
    if not drafted:
        split_return = _return_catchall_split(
            posts, clustered, topic, context, members, reasons, log, depth
        )
        if split_return is not None:
            return split_return
        section = str(context.get("section") or "All topics")
        return _emit_unshared_pending_draft(
            context,
            cluster_label,
            members,
            terms,
            member_texts,
            member_matrix,
            log,
            tried=tried,
            section=section,
            detection_faces=int(context["story_calls"]["faces"]),
        )
    drafted = drafted[:MAX_FACES]
    perspectives = [item[0] for item in drafted]
    story_faces = _story_faces_from_draft(members, drafted)
    if len(perspectives) >= 2 and _faces_are_different_stories(story_faces):
        if depth < _STORY_SPLIT_LIMIT:
            detection_faces = int(context["story_calls"]["faces"])
            handled, split_result, split_log = _split_different_stories(
                posts, clustered, topic, context, members, drafted, log
            )
            log.extend(split_log)
            if handled:
                if split_result is not None:
                    split_result["detection_faces"] = detection_faces
                return _emit_draft(
                    context,
                    split_result,
                    log,
                    split=True,
                    detection_faces=detection_faces,
                    skipped=0 if split_result is None else int(split_result.get("skipped") or 0),
                    floor_excluded=0 if split_result is None else int(split_result.get("floor_excluded") or 0),
                    excluded=[] if split_result is None else list(split_result.get("excluded") or []),
                )
            log.append(
                f"Keeping {cluster_label}: faces share no single subject word, "
                "but they do not separate into stories."
            )
        else:
            log.append(
                f"Publishing {cluster_label}: further cuts still share no subject word, "
                "so this is the smallest planet."
            )
    elif "label term in under 30% of posts" in reasons and depth < _STORY_SPLIT_LIMIT:
        # Faces kept a claim, but the label word is not what the posts are about.
        # Re-split only when that produces specific planets; otherwise publish.
        split_return = _return_catchall_split(
            posts, clustered, topic, context, members, reasons, log, depth, keep_on_miss=True
        )
        if split_return is not None:
            return split_return
    shown = sum(int(item[2]) for item in drafted)
    if _below_planet_floor(shown, context):
        # Faces already labeled. Skip the name and the briefs, and do not publish.
        return _exclude_for_floor(context, log, topic_name(terms), shown, _post_samples(members))
    drafted, stance_lines = apply_stance_pass(
        drafted, members, context, subject=topic_name(terms), terms=list(terms)
    )
    stance_failed = bool(context.pop("stance_check_failed", None))
    stance_incoherent = bool(context.pop("stance_check_incoherent", None))
    log.extend(stance_lines)
    perspectives = [item[0] for item in drafted]
    planet_prompt_cap = int(context.get("planet_prompt_sample_size") or 20)
    if context.get("chosen") == "heuristic":
        planet_prompt_posts = members
        planet_post_limit = 16
    else:
        member_cosines = planet_member_cosines(member_matrix, list(range(len(members))))
        planet_prompt_posts = select_prompt_posts(
            members,
            member_cosines,
            limit=min(planet_prompt_cap, len(members)),
            vectors=member_matrix,
        )
        planet_post_limit = len(planet_prompt_posts)
    print(
        f"Planet naming sample for {topic_name(terms)}: "
        f"{min(planet_post_limit, len(members))} of {len(members)} posts."
    )
    planet = label_topic(
        planet_prompt_posts,
        terms,
        backend=backend,
        model=model,
        post_limit=planet_post_limit,
    )
    context["story_calls"]["names"] += 1
    name = str(planet.get("name") or topic_name(terms))
    # Yes from either existing naming response. No, or a missing field, does not override a high share.
    model_chitchat = chitchat_flag(planet)
    if (
        planet.get("label_source") == "heuristic"
        or topic_name_is_weak(name, members, terms)
        or _name_misses_faces(name, perspectives)
    ):
        renamed, rename_flag = name_from_perspectives(
            planet_prompt_posts,
            perspectives,
            terms,
            backend=backend,
            model=model,
            post_limit=planet_post_limit,
        )
        # Heuristic naming returns before any model call. A network backend
        # spends the call even when the answer is unusable.
        if context.get("chosen") != "heuristic":
            context["story_calls"]["names"] += 1
        if rename_flag is True:
            model_chitchat = True
        fallback = str(perspectives[0].get("title") or "") if perspectives else ""
        if renamed and not _name_misses_faces(renamed, perspectives):
            name = renamed
        elif fallback and not _title_needs_repair(fallback) and not _is_camp_title(fallback):
            name = fallback
    chit = planet_chitchat_reason(members, terms, name=name, model_chitchat=model_chitchat)
    if chit:
        log.append(
            f"INFO {context.get('section') or 'All topics'}: not publishing chit-chat planet "
            f"{name} ({len(members)} posts). {chit}"
        )
        return _exclude_for_floor(context, log, name, len(members), _post_samples(members))
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
        "_member_uris": [str(post.get("uri") or "") for post in members],
    }
    if stance_failed:
        planet_out["stance_check"] = STANCE_CHECK_FAILED
    elif stance_incoherent:
        planet_out["stance_check"] = STANCE_CHECK_INCOHERENT
    apply_opposing_note(planet_out)
    apply_level_summaries(planet_out, generate=context["summary_model"])
    if context.get("summary_model") is not None and perspectives:
        context["story_calls"]["briefs"] += len(perspectives) + 1
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
    return _emit_draft(
        context,
        {
            "planet": planet_out,
            "membership": [post["uri"] for post in members],
            "face_rows": face_rows,
            "split": False,
            "detection_faces": int(context["story_calls"]["faces"]),
        },
        log,
        split=False,
        detection_faces=int(context["story_calls"]["faces"]),
    )


def _emit_draft(context: dict, result: dict | None, log: list[str], **meta):
    """Record one top-level draft. Nested story splits share the call counter."""
    if int(context.get("story_depth") or 0) != 0:
        return result, log
    calls = dict(
        context.get("story_calls") or {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0}
    )
    if result is not None:
        result["label_calls"] = calls
    stats = context.get("draft_stats")
    if isinstance(stats, list):
        stats.append(
            {
                "kind": "drop" if result is None else ("split" if result.get("split") else "keep"),
                "label_calls": calls,
                "planets": len(_bundles_from(result)),
                **meta,
            }
        )
    return result, log


def _bundles_from(result: dict | None) -> list[dict]:
    """Planet bundles inside one draft. A split carries ``planets``; one planet does not."""
    if not result:
        return []
    planets = result.get("planets")
    if planets:
        return list(planets)
    if result.get("planet") is not None:
        return [result]
    return []


def _coherence_faces(drafted: list) -> list[dict]:
    """Face records for the coherence test. Membership rows are not required."""
    faces = []
    for item in drafted or []:
        perspective = item[0] if isinstance(item, tuple) else item
        if not isinstance(perspective, dict):
            continue
        faces.append(
            {
                "title": perspective.get("title") or "",
                "summary": perspective.get("summary") or "",
                "representative_posts": perspective.get("representative_posts") or [],
            }
        )
    return faces


def _draft_index_buckets(
    posts: list[dict],
    clustered: dict,
    topic: dict,
    context: dict,
    members: list[dict],
    buckets: list[list[int]],
    log: list[str],
    *,
    header: str,
    cap: int | None = None,
) -> tuple[bool, dict | None, list[str]]:
    """Draft one planet per index bucket. ``handled`` is true when we split.

    A bucket under the planet-post floor is logged and left out. ``cap``
    keeps only the largest buckets; the rest are logged the same way.
    """
    terms = list(topic.get("terms") or [])
    ordered = sorted(buckets, key=len, reverse=True)
    if cap is not None and len(ordered) > cap:
        for indices in ordered[cap:]:
            texts = [str(members[index].get("clean_text") or members[index].get("text") or "") for index in indices]
            hint = topic_name(salient_terms(texts, limit=6) or list(terms))
            log.append(_floor_log(context, hint, len(indices)))
        ordered = ordered[:cap]
    eligible: list[list[int]] = []
    skipped = 0
    floor_excluded = 0
    excluded: list[dict] = []
    for indices in ordered:
        if not _below_planet_floor(len(indices), context):
            eligible.append(indices)
            continue
        texts = [str(members[index].get("clean_text") or members[index].get("text") or "") for index in indices]
        hint = topic_name(salient_terms(texts, limit=6) or list(terms))
        log.append(_floor_log(context, hint, len(indices)))
        skipped += 1
        floor_excluded += 1
        excluded.append(
            {
                "section": str(context.get("section") or "All topics"),
                "label": hint,
                "posts": len(indices),
                "samples": _post_samples([{"text": text} for text in texts]),
            }
        )
    log.insert(0, header)
    if not eligible:
        return True, {
            "planets": [],
            "split": True,
            "stories": len(buckets),
            "skipped": skipped,
            "floor_excluded": floor_excluded,
            "excluded": excluded,
        }, log
    child_context = dict(context)
    child_context["story_depth"] = int(context.get("story_depth") or 0) + 1
    child_context.pop("_raw_face_drafts", None)
    bundles = []
    for indices in eligible:
        texts = [str(members[index].get("clean_text") or "") for index in indices]
        sub_terms = salient_terms(texts, limit=6) or list(terms)
        subtopic = {
            "id": topic.get("id"),
            "terms": sub_terms,
            "member_indices": [topic["member_indices"][index] for index in indices],
            "size": len(indices),
        }
        child, child_log = _draft_planet(posts, clustered, subtopic, child_context)
        log.extend(child_log)
        bundles.extend(_bundles_from(child))
        if child is not None:
            skipped += int(child.get("skipped") or 0)
            floor_excluded += int(child.get("floor_excluded") or 0)
            excluded.extend(child.get("excluded") or [])
    return True, {
        "planets": bundles,
        "split": True,
        "stories": len(buckets),
        "skipped": skipped,
        "floor_excluded": floor_excluded,
        "excluded": excluded,
    }, log


def _resplit_catchall(
    posts: list[dict],
    clustered: dict,
    topic: dict,
    context: dict,
    members: list[dict],
    reasons: list[str],
) -> tuple[bool, dict | None, list[str]]:
    """Break a catch-all into specific stories. ``handled`` is false when it stays one blob."""
    log: list[str] = []
    floor = _planet_post_floor(context)
    if floor <= 0:
        floor = MIN_PLANET_POSTS
    held_buckets: list[list[int]] = []
    buckets = split_catchall_posts(members, floor=floor, notes=log, held_buckets=held_buckets)
    held = [
        str(members[index].get("uri") or "")
        for indexes in held_buckets
        for index in indexes
    ]
    if held:
        _note_uris(None, "held_uris", held)
    if len(buckets) < 1:
        if held or repeated_stems_below_floor(members, floor) >= 2:
            # Every piece is under the floor, or the stems that do repeat are
            # each too small to be a planet. Leave the grab-bag out. Do not
            # publish it as one planet.
            return True, {
                "planets": [],
                "split": True,
                "stories": 0,
                "held_only": True,
                "skipped": 0,
                "floor_excluded": 0,
                "excluded": [],
            }, log
        return False, None, log
    assigned = {index for bucket in buckets for index in bucket}
    leftover = [str(members[index].get("uri") or "") for index in range(len(members)) if index not in assigned]
    if leftover:
        _note_uris(None, "leftover_uris", leftover)
        section = str(context.get("section") or "All topics")
        log.append(
            f"INFO {section}: catch-all leftover {len(leftover)} posts not in a specific story."
        )
    label = topic_name(list(topic.get("terms") or []))
    why = "; ".join(reasons) if reasons else "no face kept a shared claim"
    return _draft_index_buckets(
        posts,
        clustered,
        topic,
        context,
        members,
        buckets,
        log,
        header=f"Splitting {label}: catch-all ({why}).",
        cap=_CATCHALL_CHILD_CAP,
    )


def _rescue_named_story(
    posts: list[dict],
    clustered: dict,
    topic: dict,
    context: dict,
    members: list[dict],
    label: str,
    log: list[str],
):
    """Publish a story the re-split could not cut, when it already has enough posts.

    Returns the ``_draft_planet`` return value, or None when the cluster is
    under the planet floor. Callers use None to coherence-block.
    """
    del posts, clustered
    if _below_planet_floor(len(members), context):
        return None
    texts = [str(post.get("clean_text") or post.get("text") or "") for post in members]
    terms = salient_terms(texts, limit=6) or list(topic.get("terms") or [])
    title = topic_name(terms) or label or "Story"
    limit = max(1, int(context.get("limit") or 6))
    ranked = sorted(members, key=lambda post: -int(post.get("likes") or 0))
    representatives = []
    for post in ranked[: min(limit, EXAMPLE_POST_CAP)]:
        text = str(post.get("text") or post.get("clean_text") or "").strip()
        if not text:
            continue
        representatives.append(
            {
                "author": str(post.get("author") or "unknown"),
                "text": text,
                "likes": int(post.get("likes") or 0),
            }
        )
    if not representatives:
        return None
    top_terms = [str(term) for term in terms[:TOP_TERMS_LIMIT] if str(term).strip()] or [title]
    perspective = {
        "id": face_id(1, 0),
        "title": title,
        "summary": f"These posts are about {title}.",
        "volume_percent": 100.0,
        "post_count": len(members),
        "representative_posts": representatives,
        "top_terms": top_terms,
    }
    calls = context.setdefault(
        "story_calls",
        {"faces": 0, "names": 0, "briefs": 0, "finalize_faces": 0},
    )
    named = label_topic(
        representatives,
        terms or [title],
        backend=context["backend"],
        model=context.get("model"),
        post_limit=len(representatives),
    )
    if context.get("chosen") != "heuristic":
        calls["names"] += 1
    name = str(named.get("name") or title)
    if topic_name_is_weak(name, members, terms):
        name = title
    planet_out = {
        "id": 1,
        "name": name,
        "category": category_for_members(name, terms, texts, members),
        "total_volume_percent": 0.0,
        "post_count": len(members),
        "perspectives": [perspective],
        "_member_uris": [str(post.get("uri") or "") for post in members],
        "face_distinctness": 0.0,
    }
    apply_opposing_note(planet_out)
    apply_level_summaries(planet_out, generate=context.get("summary_model"))
    if context.get("summary_model") is not None:
        calls["briefs"] += 2
    log.append(
        f"Keeping {label}: re-split published no planet, so this {len(members)}-post story stays ({name})."
    )
    _forget_uris([str(post.get("uri") or "") for post in members])
    rows = [(str(post.get("uri") or ""), 0, 0.0) for post in members]
    return _emit_draft(
        context,
        {
            "planet": planet_out,
            "membership": [str(post.get("uri") or "") for post in members],
            "face_rows": rows,
            "split": False,
        },
        log,
        split=False,
        detection_faces=int(calls.get("faces") or 0),
    )


def _return_catchall_split(
    posts: list[dict],
    clustered: dict,
    topic: dict,
    context: dict,
    members: list[dict],
    reasons: list[str],
    log: list[str],
    depth: int,
    *,
    keep_on_miss: bool = False,
):
    """Re-split when the coherence test fires and the depth limit allows it.

    Returns the ``_draft_planet`` return value when the split is what we
    publish, or None when the caller should keep its own path. A story of at
    least ``min_planet_posts`` whose re-split publishes nothing is kept, not
    coherence-blocked. Only a cluster under that floor is blocked.
    """
    if depth >= _STORY_SPLIT_LIMIT or not reasons:
        return None
    label = topic_name(list(topic.get("terms") or []))
    handled, split_result, split_log = _resplit_catchall(
        posts, clustered, topic, context, members, reasons
    )
    log.extend(split_log)
    if not handled:
        if keep_on_miss:
            log.append(
                f"Keeping {label}: label term is in under 30% of posts, "
                "but the posts do not separate into specific stories."
            )
            return None
        rescued = _rescue_named_story(posts, clustered, topic, context, members, label, log)
        if rescued is not None:
            return rescued
        section = str(context.get("section") or "All topics")
        log.append(
            f"Coherence blocked on {label}: {'; '.join(reasons)}. "
            f"{section}, {len(members)} posts."
        )
        _note_uris("blocked_planets", "blocked_uris", [str(post.get("uri") or "") for post in members])
        return _emit_draft(
            context,
            None,
            log,
            split=False,
            detection_faces=int(context["story_calls"]["faces"]),
        )
    published = _bundles_from(split_result)
    child_blocked = any(line.startswith("Coherence blocked") for line in split_log)
    held_only = bool(split_result and split_result.get("held_only"))
    if held_only and not published:
        if keep_on_miss:
            log.append(
                f"Keeping {label}: thin fragments were held, so the shared claim stays."
            )
            return None
        return _emit_draft(
            context,
            split_result,
            log,
            split=True,
            detection_faces=int(context["story_calls"]["faces"]),
        )
    if not published and not keep_on_miss and not child_blocked:
        rescued = _rescue_named_story(posts, clustered, topic, context, members, label, log)
        if rescued is not None:
            return rescued
        section = str(context.get("section") or "All topics")
        log.append(
            f"Coherence blocked on {label}: {'; '.join(reasons)}. "
            f"{section}, {len(members)} posts."
        )
        _note_uris("blocked_planets", "blocked_uris", [str(post.get("uri") or "") for post in members])
    if not published and keep_on_miss:
        log.append(
            f"Keeping {label}: catch-all re-split produced no planet, so the shared claim stays."
        )
        return None
    detection_faces = int(context["story_calls"]["faces"])
    if split_result is not None:
        split_result["detection_faces"] = detection_faces
    return _emit_draft(
        context,
        split_result,
        log,
        split=True,
        detection_faces=detection_faces,
        skipped=0 if split_result is None else int(split_result.get("skipped") or 0),
        floor_excluded=0 if split_result is None else int(split_result.get("floor_excluded") or 0),
        excluded=[] if split_result is None else list(split_result.get("excluded") or []),
    )


def _faces_are_different_stories(faces: list[dict]) -> bool:
    """True when the faces should not stay on one planet.

    ``specific_shared_words`` is looked up on this module so tests can patch it.
    """
    groups = majority_story_groups(faces)
    if groups is not None:
        return len(groups) >= 2
    return len(faces) >= 2 and not specific_shared_words(faces)


def _story_faces_from_draft(members: list[dict], drafted: list) -> list[dict]:
    """Face records for the story split, with the member texts the stem check reads."""
    uri_index = {str(post.get("uri") or ""): index for index, post in enumerate(members)}
    faces = []
    for perspective, rows, size in drafted:
        indices: list[int] = []
        seen: set[int] = set()
        for uri, _position, _distance in rows:
            index = uri_index.get(str(uri))
            if index is None or index in seen:
                continue
            seen.add(index)
            indices.append(index)
        texts = [
            str(members[index].get("clean_text") or members[index].get("text") or "")
            for index in indices
        ]
        faces.append(
            {
                "title": perspective.get("title") or "",
                "summary": perspective.get("summary") or "",
                "representative_posts": perspective.get("representative_posts") or [],
                "member_indices": indices,
                "member_texts": [text for text in texts if text.strip()],
                "post_count": len(indices) or int(size),
            }
        )
    return faces


def _split_different_stories(
    posts: list[dict],
    clustered: dict,
    topic: dict,
    context: dict,
    members: list[dict],
    drafted: list,
    parent_log: list[str],
) -> tuple[bool, dict | None, list[str]]:
    """Turn one glued candidate into a planet per story.

    Returns ``(handled, result, log)``. ``handled`` is false when the faces
    do not separate, and the caller publishes the original planet. A story
    under the planet-post floor is not labeled, not published, and not glued
    onto a sibling. The log has one INFO line per story left out.
    """
    del parent_log
    log: list[str] = []
    faces = _story_faces_from_draft(members, drafted)
    groups = majority_story_groups(faces)
    if groups is None:
        groups = story_groups(faces)
    buckets: list[list[int]] = []
    for group in groups:
        indices = []
        seen = set()
        for face_index in group:
            for index in faces[face_index]["member_indices"]:
                if index in seen:
                    continue
                seen.add(index)
                indices.append(index)
        if indices:
            buckets.append(indices)
    if len(buckets) < 2:
        return False, None, log
    label = topic_name(list(topic.get("terms") or []))
    return _draft_index_buckets(
        posts,
        clustered,
        topic,
        context,
        members,
        buckets,
        log,
        header=f"Splitting {label}: its faces are different stories ({len(buckets)} stories).",
    )


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


def _section_draft_deadline(deadline: float | None) -> float | None:
    """When drafts must stop so wide relabel still has a slice of the window.

    ``None`` stays ``None`` (no ceiling). A deadline that is already due is
    unchanged. A long window reserves ``SECTION_RELABEL_RESERVE_SECONDS``.
    A short one reserves half of what is left, so drafts are not squeezed
    out of a test ceiling or a budget that is already almost gone.
    """
    if deadline is None:
        return None
    remaining = float(deadline) - time.monotonic()
    if remaining <= 0:
        return deadline
    reserve = min(float(SECTION_RELABEL_RESERVE_SECONDS), remaining / 2.0)
    return float(deadline) - reserve


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
    """Draft one candidate. A raised error is a log line, not a failed snapshot.

    A spend-cap stop is not a bad planet. Swallowing it would publish anyway.
    """
    try:
        return _draft_planet(posts, clustered, topic, context)
    except SpendCapExceeded:
        raise
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
    logged and skipped instead of failing the snapshot. A split child under
    ``_SPLIT_CATALOG_POSTS`` posts does not fill a slot ahead of a later
    candidate. Those children fill a slot only when the catalog is not already
    full of the candidates that outrank the scraps.
    """
    context = dict(context or _label_context(settings))
    context.setdefault("section", "All topics")
    context.setdefault("min_planet_posts", _planet_post_floor(settings))
    candidates = list(clustered["topics"])
    target = len(candidates) if keep is None else max(int(keep), 1)
    workers = int(context.get("workers") or 1)
    built: list[dict] = []
    membership: list[tuple[str, int]] = []
    face_rows: list[tuple[str, int, int, float]] = []
    seen_names: set[str] = set()
    deferred: list[dict] = []

    def draft(topic: dict):
        return _safe_draft(posts, clustered, topic, context)

    def stage_bundle(bundle: dict) -> None:
        if len(built) >= target:
            name = str((bundle.get("planet") or {}).get("name") or "story")
            print(f"Not publishing {name}: the catalog already has {target} planets.")
            return
        planet = _stage_planet(built, seen_names, bundle)
        topic_id = int(planet["id"])
        membership.extend((uri, topic_id) for uri in bundle["membership"])
        face_rows.extend(
            (uri, topic_id, position, distance)
            for uri, position, distance in bundle["face_rows"]
        )

    def stage_result(result: dict | None) -> None:
        bundles = _bundles_from(result)
        split = bool(result and result.get("split"))
        if not split:
            for bundle in bundles:
                stage_bundle(bundle)
            return
        for bundle in bundles:
            size = len(bundle.get("membership") or [])
            if size >= _SPLIT_CATALOG_POSTS:
                stage_bundle(bundle)
            else:
                deferred.append(bundle)

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
                for line in log:
                    print(line)
                stage_result(result)
        deferred.sort(
            key=lambda bundle: (
                -len(bundle.get("membership") or []),
                str((bundle.get("planet") or {}).get("name") or ""),
            )
        )
        for bundle in deferred:
            stage_bundle(bundle)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    built = _drop_unshared_planets(built)
    face_rows = _align_face_rows(built, face_rows)
    built = _publishable_planets(built)
    _finalize_published_planets(built, posts, clustered, context)
    publish_volumes(built)
    return _renumber_planets(built, membership, face_rows)


def _publishable_planets(topics: list[dict]) -> list[dict]:
    """Last guard before validation: a planet outside 1..6 faces is dropped and logged.

    One perspective is allowed. Drafting already enforces the ceiling. If a
    later step ever breaks it, one planet is lost instead of the whole snapshot.
    ``validate_payload`` stays strict.
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
        self.context = dict(context)
        self.context["section"] = name
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
        if len(self.built) >= self.keep:
            # A split candidate can fill the catalog mid-wave. Do not label
            # another candidate just to throw it away.
            self.wave_left = 0
            self.wave_open = False
            self.done = True
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
            for bundle in _bundles_from(result):
                if len(self.built) >= self.keep:
                    name = str((bundle.get("planet") or {}).get("name") or "story")
                    print(f"Not publishing {name}: the catalog already has {self.keep} planets.")
                    continue
                _stage_planet(self.built, self.seen, bundle)
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
    """Fill free slots from the section with the fewest planets in flight.

    Post volume breaks a tie, so a larger section still goes first when
    every section is even. One section cannot take every free slot before
    the others have started. A section that has not started by ``deadline``
    is skipped. One that has started stops submitting and lets in-flight
    drafts finish.
    """
    for job in jobs:
        if job.done:
            continue
        if job.cursor == 0 and job.inflight == 0 and deadline is not None and time.monotonic() >= deadline:
            print(f"Section {job.name}: skipped, the section time budget is spent.")
            job.skipped_budget = True
            job.done = True

    while len(inflight) < workers:
        if deadline is not None and time.monotonic() >= deadline:
            for job in jobs:
                if not job.done:
                    job.mark_budget()
            break
        ready = [job for job in jobs if job.can_submit()]
        if not ready:
            break
        ready.sort(key=lambda job: (job.inflight, -job.post_count, job.name))
        job = ready[0]
        index, topic = job.take()
        future = executor.submit(_safe_draft, job.posts, job.clustered, topic, job.context)
        inflight[future] = (job, index)


def _label_section_jobs(jobs: list[_SectionLabelJob], workers: int, deadline) -> None:
    """Label every section through one pool. Fewest-in-flight sections take the next slot."""
    if not jobs:
        return
    workers = max(1, int(workers))
    print(
        f"Section labels: {workers} call(s) in flight, shared by {len(jobs)} section(s). "
        "Slots go to the section with the fewest planets in flight."
    )
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


def _finish_section_planets(
    built: list[dict],
    posts: list[dict],
    clustered: dict,
    context: dict,
    *,
    deadline: float | None = None,
    finalize: bool = True,
) -> list[dict]:
    """Same last guards as the global catalog: drop collapses, renumber, volumes."""
    if finalize:
        built = _drop_unshared_planets(built)
        built = _publishable_planets(built)
        _finalize_published_planets(built, posts, clustered, context, deadline=deadline)
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
    *embed* hook, which short-circuits the fastembed call. Sections stay
    ordered by post volume, and that order only breaks a tie: a free slot
    goes to the section with the fewest planets already in flight, so one
    large section cannot use the whole pool before the others have started.
    Drafts stop ``SECTION_RELABEL_RESERVE_SECONDS`` before ``deadline`` so
    the wide face relabel still has time. Past the draft deadline no new
    planet is labeled; a section that never started is skipped, and one that
    raises is logged and skipped, so the global snapshot still publishes.
    """
    import numpy as np

    section_indices: dict[str, list[int]] = {}
    for idx, post in enumerate(planet_posts):
        section = str(post.get("section") or "")
        if section in CATEGORIES:
            section_indices.setdefault(section, []).append(idx)

    order = sorted(section_indices, key=lambda name: (-len(section_indices[name]), name))
    reset_section_face_relabel()
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
        # Same fixed floor as the global catalog. A small section is not given
        # a formula that grows with its post count.
        section_floor = max(2, int(floor) if floor else base_min)
        if len(indices) < section_floor:
            print(f"Section {section}: {len(indices)} posts, skipping (need {section_floor}).")
            continue

        section_posts = [planet_posts[i] for i in indices]
        section_texts = [p["clean_text"] for p in section_posts]
        sub_matrix = matrix[indices]

        try:
            pool = CANDIDATE_POOL
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
        except SpendCapExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - one section must not block the snapshot
            print(f"Section {section}: skipped ({type(exc).__name__}: {exc}).")
            continue
        if not section_clustered.get("topics"):
            print(f"Section {section}: no natural group from {len(indices)} posts.")
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

    draft_deadline = _section_draft_deadline(deadline)
    if deadline is not None and draft_deadline is not None and draft_deadline < deadline:
        reserve = deadline - draft_deadline
        print(
            f"Section drafts stop {reserve:.0f}s before the section ceiling "
            "so wide relabel can run."
        )
    set_label_deadline(draft_deadline)
    try:
        _label_section_jobs(jobs, _section_pool_size(context), draft_deadline)
        active_jobs = [job for job in jobs if not job.skipped_budget]
        for job in active_jobs:
            job.built = _drop_unshared_planets(job.built)
            job.built = _publishable_planets(job.built)
        # Relabel may use the rest of the section window, including the reserve.
        set_label_deadline(deadline)
        if active_jobs:
            _finalize_section_planets_batch(active_jobs, deadline)
    finally:
        set_label_deadline(None)
    relocated: dict[str, list[dict]] = {}
    for job in jobs:
        if job.skipped_budget:
            continue
        topics = _finish_section_planets(
            job.built,
            job.posts,
            job.clustered,
            job.context,
            deadline=deadline,
            finalize=False,
        )
        if job.name == "Politics" and topics:
            topics, moved = partition_politics_planets(topics, job.posts)
            for dest, planets in moved.items():
                for planet in planets:
                    print(
                        f"Section Politics: moved planet {planet.get('name')} "
                        f"({planet.get('post_count')} posts) to {dest} (post-label sanity)."
                    )
                relocated.setdefault(dest, []).extend(planets)
        if topics:
            result[job.name] = _assign_section_topic_ids(job.name, topics)
            print(f"Section {job.name}: {len(topics)} planet(s) from {job.post_count} posts.")
        elif job.budget_hit:
            print(f"Section {job.name}: stopped, the section time budget is spent.")
        else:
            print(f"Section {job.name}: no publishable planet from {job.post_count} posts.")

    for dest, planets in relocated.items():
        if not planets:
            continue
        base = len(result.get(dest, []))
        for offset, topic in enumerate(planets, start=1):
            topic["id"] = base + offset
        assigned = _assign_section_topic_ids(dest, planets)
        result.setdefault(dest, []).extend(assigned)
        print(f"Section {dest}: accepted {len(assigned)} planet(s) relocated from Politics.")

    renormalize_section_catalogs(result)

    return {name: result[name] for name in CATEGORIES if name in result}


def renormalize_section_catalogs(sections: dict[str, list[dict]]) -> None:
    """Recompute section topic shares after post-label planets move between catalogs."""
    for section_topics in sections.values():
        publish_volumes(section_topics)


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


def _claim_sample(posts: list[dict], scores: list[float] | None, limit: int = 40) -> list[dict]:
    """A spread of the face, not only the posts closest to the centroid.

    The closest posts are often the same sentence. Evenly stepping through the
    ranked list lets a shared claim show up when it is not in the top five.
    """
    count = len(posts)
    if count <= limit:
        return list(posts)
    ranked = sorted(
        range(count),
        key=lambda index: (
            -(float(scores[index]) if scores is not None and index < len(scores) else 0.0),
            index,
        ),
    )
    if limit <= 1:
        return [posts[ranked[0]]]
    chosen: list[int] = []
    seen: set[int] = set()
    for step in range(limit):
        index = ranked[round(step * (count - 1) / (limit - 1))]
        if index in seen:
            continue
        seen.add(index)
        chosen.append(index)
    return [posts[index] for index in chosen]


def _coverage_needed(count: int) -> int:
    """At least two posts, and about 40% of the sample."""
    return max(2, math.ceil(0.40 * count - 1e-9))


def _title_covers_posts(title: str, posts: list[dict]) -> bool:
    """True when the claim's words show up in about 40% of the sample."""
    title_stems = {subject_stem(token) for token in content_tokens(title)}
    title_stems = {stem for stem in title_stems if len(stem) >= 3}
    if len(posts) < 2 or not title_stems:
        return True
    hits = 0
    for post in posts:
        text = str(post.get("text") or post.get("clean_text") or "")
        stems = {subject_stem(token) for token in content_tokens(text)}
        if title_stems & stems:
            hits += 1
    return hits >= _coverage_needed(len(posts))


def _posts_share_a_subject(posts: list[dict]) -> bool:
    """False when no content stem shows up in about 40% of the sample.

    The sample is the whole list the caller passed (a spread of the face, not
    the first five posts). A grab bag fails. A face that repeats one claim
    passes even when the closest posts use different wording.
    """
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
    if len(posts) < 2:
        return True
    counts: dict[str, int] = {}
    for post in posts:
        text = str(post.get("text") or post.get("clean_text") or "")
        stems = {
            subject_stem(token)
            for token in content_tokens(text)
            if token not in glue and len(token) >= 4
        }
        for stem in stems:
            if len(stem) < 3:
                continue
            counts[stem] = counts.get(stem, 0) + 1
    if not counts:
        return False
    return max(counts.values()) >= _coverage_needed(len(posts))


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


def _pending_face_from_members(
    planet_name: str,
    members: list[dict],
    member_texts: list[str],
    member_matrix,
) -> tuple[dict, list[tuple[str, int, float]]]:
    """One publishable face for every member when no shared-claim label survived."""
    cosines = (
        planet_member_cosines(member_matrix, list(range(len(members))))
        if member_matrix is not None
        else [0.0] * len(members)
    )
    representatives = select_prompt_posts(
        members,
        cosines,
        limit=min(int(EXAMPLE_POST_CAP), len(members)),
        vectors=member_matrix,
    )
    perspective = {
        "id": face_id(1, 0),
        "title": planet_name,
        "summary": f"Posts grouped under {planet_name}.",
        "volume_percent": 100.0,
        "post_count": len(members),
        "representative_posts": representatives,
        "top_terms": salient_terms(member_texts, limit=TOP_TERMS_LIMIT),
    }
    face_rows = [
        (str(post.get("uri") or ""), 0, float(cosines[index]) if index < len(cosines) else 0.0)
        for index, post in enumerate(members)
    ]
    return perspective, face_rows


def _planet_out_pending(
    name: str,
    members: list[dict],
    terms: list[str],
    member_texts: list[str],
    member_matrix,
) -> tuple[dict, list[tuple[str, int, float]]]:
    perspective, face_rows = _pending_face_from_members(name, members, member_texts, member_matrix)
    planet_out = {
        "id": 1,
        "name": name,
        "category": category_for_members(name, terms, member_texts, members),
        "total_volume_percent": 0.0,
        "post_count": len(members),
        "perspectives": [perspective],
        "_member_uris": [str(post.get("uri") or "") for post in members],
        "stance_check": STANCE_CHECK_UNSHARED,
        "face_distinctness": 0.0,
    }
    apply_opposing_note(planet_out)
    return planet_out, face_rows


def _emit_unshared_pending_draft(
    context: dict,
    name: str,
    members: list[dict],
    terms: list[str],
    member_texts: list[str],
    member_matrix,
    log: list[str],
    *,
    tried: list[str],
    section: str,
    detection_faces: int,
):
    """Publish a draft planet as pending instead of dropping it from the catalog."""
    log.append(
        f"Keeping {name} as pending: no face kept a shared claim "
        f"({'; '.join(tried)}). {section}, {len(members)} posts."
    )
    note_unshared_pending_planet(name, len(members))
    planet_out, face_rows = _planet_out_pending(name, members, terms, member_texts, member_matrix)
    log.append(f"Planet {name}: 100.0% {name} (pending shared-claim check)")
    return _emit_draft(
        context,
        {
            "planet": planet_out,
            "membership": [post["uri"] for post in members],
            "face_rows": face_rows,
            "split": False,
            "detection_faces": detection_faces,
        },
        log,
        split=False,
        detection_faces=detection_faces,
    )


def _salvage_unshared_pending_faces(topic: dict, faces: list[dict]) -> list[dict]:
    """Publish one face under the planet name when every face failed the shared-claim check."""
    if not faces:
        return []
    best = max(faces, key=lambda face: int(face.get("post_count") or 0))
    salvaged = {key: value for key, value in best.items() if not str(key).startswith("_")}
    planet_name = str(topic.get("name") or "").strip() or str(salvaged.get("title") or "Topic")
    salvaged["title"] = planet_name
    salvaged["summary"] = f"Posts grouped under {planet_name}."
    salvaged.pop("arguments", None)
    return [salvaged]


def _keep_unshared_pending_planet(topic: dict, original: list[dict]) -> bool:
    """Keep a planet that would have been dropped for having no shared-claim face."""
    faces = _salvage_unshared_pending_faces(topic, original)
    if not faces:
        return False
    counts = [int(face.get("post_count") or 0) for face in original]
    total = sum(counts) or int(topic.get("post_count") or 0)
    if total <= 0:
        return False
    if not int(faces[0].get("post_count") or 0):
        faces[0]["post_count"] = total
    faces[0]["volume_percent"] = 100.0
    topic["post_count"] = total
    topic["perspectives"] = faces
    topic["stance_check"] = STANCE_CHECK_UNSHARED
    topic.pop("opposing_note", None)
    apply_opposing_note(topic)
    return True


def _assign_section_topic_ids(section: str, topics: list[dict]) -> list[dict]:
    """Give each section planet a globally unique id (e.g. Technology-5)."""
    for topic in topics:
        rank = int(topic["id"])
        new_id = f"{section}-{rank}"
        topic["id"] = new_id
        topic["perspectives"] = [
            {**face, "id": face_id(new_id, position)}
            for position, face in enumerate(topic.get("perspectives") or [])
        ]
    return topics


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
    """Remove a face with no shared claim. One real face still publishes.

    A "Mixed remarks" leftover is not kept to pad the planet to two views.
    One remaining face gets ``opposing_note``, unless the stance check failed.
    When every face fails the check, the planet stays with ``stance_check`` set
    and readers see the pending line (#129). Different stories are split before
    this guard. More than six faces is still dropped.
    """
    kept = []
    for topic in topics:
        original = list(topic.get("perspectives") or [])
        faces = [
            face
            for face in original
            if face.get("stance_locked") or not _face_has_no_shared_claim(face)
        ]
        if not faces:
            if _keep_unshared_pending_planet(topic, original):
                note_unshared_pending_planet(
                    str(topic.get("name") or ""),
                    int(topic.get("post_count") or 0),
                )
                kept.append(topic)
            else:
                print(
                    f"Dropping {topic.get('name')}: 0 faces left after "
                    f"removing unshared claims (need {MIN_FACES}-{MAX_FACES})."
                )
            continue
        if len(faces) > MAX_FACES:
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
        apply_opposing_note(topic)
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
