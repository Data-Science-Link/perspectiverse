"""Bounded fetch loop until the edition holds exactly ``target`` quality posts (#213).

Fetching is free; this module never calls Jev or labeling. Stop reasons are
logged once at the end and attached to the preview summary and cost run.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pipeline.chitchat_guard import (
    clustering_topup_shortfall,
    edition_posts_for_clustering,
    get_chitchat_log,
    reset_chitchat_log,
)
from pipeline.corpus import retire_oldest
from pipeline.free_ingest import ingest_free
from pipeline.spend_cap import SpendCapExceeded, day_paid_usd, stop_usd

STOP_REACHED_TARGET = "reached_100000"
STOP_SPEND = "spend_stop"
STOP_WALL_TIME = "job_wall_time_budget"
STOP_MAX_ROUNDS = "max_fetch_rounds"
STOP_WINDOW_EXHAUSTED = "7_day_window_exhausted"
STOP_NO_PROGRESS = "no_progress"

ENV_MAX_ROUNDS = "PERSPECTIVERSE_EDITION_FILL_MAX_ROUNDS"
DEFAULT_MAX_ROUNDS = 24
STORED_OVERFETCH_MARGIN = 500
NO_PROGRESS_STREAK = 2
PROGRESS_FRACTION = 0.005


@dataclass
class EditionRoundLog:
    round: int
    posts_fetched: int
    spam_blocked: int
    chitchat_blocked: int
    language_blocked: int
    link_blocked: int
    near_duplicate_dropped: int
    late_chitchat_skipped: int
    stored_count: int
    edition_quality_count: int
    elapsed_seconds: float


@dataclass
class EditionFillResult:
    cleaned: list[dict]
    planet_posts: list[dict]
    target: int
    stop_reason: str
    rounds: list[EditionRoundLog] = field(default_factory=list)
    skipped_non_english: int = 0
    skipped_link_only: int = 0
    skipped_chitchat_cluster_pass: int = 0
    ingest_stored: int = 0
    before_language_filter: int = 0

    def pipeline_dict(self) -> dict:
        return {
            "target_quality_posts": self.target,
            "ingest_stored": self.ingest_stored,
            "before_language_filter": self.before_language_filter,
            "skipped_non_english": self.skipped_non_english,
            "skipped_link_only": self.skipped_link_only,
            "skipped_chitchat_cluster_pass": self.skipped_chitchat_cluster_pass,
            "edition_posts_for_clustering": len(self.planet_posts),
            "edition_fill_stop_reason": self.stop_reason,
            "edition_fill_rounds": [
                {
                    "round": row.round,
                    "posts_fetched": row.posts_fetched,
                    "spam_blocked": row.spam_blocked,
                    "chitchat_blocked": row.chitchat_blocked,
                    "language_blocked": row.language_blocked,
                    "link_blocked": row.link_blocked,
                    "near_duplicate_dropped": row.near_duplicate_dropped,
                    "late_chitchat_skipped": row.late_chitchat_skipped,
                    "stored_count": row.stored_count,
                    "edition_quality_count": row.edition_quality_count,
                    "elapsed_seconds": row.elapsed_seconds,
                }
                for row in self.rounds
            ],
        }

    def summary_line(self) -> str:
        return (
            f"Edition fill: {len(self.planet_posts)} of {self.target} quality posts; "
            f"stop_reason={self.stop_reason}."
        )


def max_fetch_rounds() -> int:
    raw = (os.getenv(ENV_MAX_ROUNDS) or "").strip()
    if not raw:
        return DEFAULT_MAX_ROUNDS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_ROUNDS


def progress_threshold(target: int) -> int:
    return max(1, int(int(target) * PROGRESS_FRACTION))


def at_spend_stop() -> bool:
    try:
        limit = stop_usd()
    except SpendCapExceeded:
        return True
    return day_paid_usd() >= limit


def _log_snapshot() -> dict[str, int]:
    log = get_chitchat_log()
    return {
        "fetched": log.fetched,
        "spam_blocked": log.spam_blocked,
        "chitchat_blocked": log.chitchat_blocked,
        "language_blocked": log.language_blocked,
        "link_blocked": log.link_blocked,
    }


def _delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in before}


def measure_edition(cleaned: list[dict]) -> tuple[list[dict], dict]:
    """Edition-quality posts for clustering plus skip counts from the clustering pass."""
    from pipeline.live import posts_for_planets

    planet_posts = posts_for_planets(cleaned, require_claims=False)
    before_filter = len(planet_posts)
    planet_posts, skipped_language, skipped_links, skipped_chitchat = edition_posts_for_clustering(
        planet_posts
    )
    return planet_posts, {
        "before_language_filter": before_filter,
        "skipped_non_english": skipped_language,
        "skipped_link_only": skipped_links,
        "skipped_chitchat_cluster_pass": skipped_chitchat,
    }


def trim_to_target(
    cleaned: list[dict],
    planet_posts: list[dict],
    *,
    target: int,
    window_hours: int,
    now: datetime,
) -> tuple[list[dict], list[dict]]:
    """Cap edition posts to ``target`` with ``retire_oldest``, then align stored corpus."""
    if len(planet_posts) <= target:
        return cleaned, planet_posts
    trimmed_posts = retire_oldest(
        planet_posts,
        now=now,
        window_hours=window_hours,
        target=target,
    )
    keep_uris = {str(post.get("uri") or "") for post in trimmed_posts if post.get("uri")}
    aligned = [post for post in cleaned if str(post.get("uri") or "") in keep_uris]
    aligned = retire_oldest(
        aligned,
        now=now,
        window_hours=window_hours,
        target=target,
    )
    return aligned, trimmed_posts


def _print_round(row: EditionRoundLog) -> None:
    print(
        "Edition fill round "
        f"{row.round}: fetched={row.posts_fetched}, "
        f"kept spam={row.spam_blocked} chitchat={row.chitchat_blocked} "
        f"language={row.language_blocked} link={row.link_blocked} "
        f"near_dup={row.near_duplicate_dropped} late_chitchat={row.late_chitchat_skipped}, "
        f"stored={row.stored_count}, edition_quality={row.edition_quality_count}, "
        f"elapsed={row.elapsed_seconds:.1f}s."
    )


def run_edition_fill_loop(
    existing: list[dict],
    settings: dict,
    queries: list[str] | None,
    *,
    target: int,
    now: datetime | None = None,
) -> EditionFillResult:
    """Fetch, filter, dedupe, and evict until the edition reaches ``target`` or a stop fires."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    window_hours = int(settings.get("window_hours") or 168)
    reset_chitchat_log()
    cleaned = list(existing)
    planet_posts: list[dict] = []
    meta: dict = {}
    stop_reason = STOP_MAX_ROUNDS
    rounds: list[EditionRoundLog] = []
    no_progress_streak = 0
    progress_min = progress_threshold(target)
    loop_started = time.monotonic()
    max_rounds = max_fetch_rounds()
    fetch_exhausted = False

    for round_num in range(1, max_rounds + 1):
        before_log = _log_snapshot()
        before_stored = len(cleaned)
        before_edition = len(planet_posts)
        near_dup_dropped = 0

        planet_posts, meta = measure_edition(cleaned)
        elapsed = time.monotonic() - loop_started

        if len(planet_posts) >= target:
            cleaned, planet_posts = trim_to_target(
                cleaned,
                planet_posts,
                target=target,
                window_hours=window_hours,
                now=moment,
            )
            stop_reason = STOP_REACHED_TARGET
            row = EditionRoundLog(
                round=round_num,
                posts_fetched=0,
                spam_blocked=0,
                chitchat_blocked=0,
                language_blocked=0,
                link_blocked=0,
                near_duplicate_dropped=near_dup_dropped,
                late_chitchat_skipped=int(meta.get("skipped_chitchat_cluster_pass") or 0),
                stored_count=len(cleaned),
                edition_quality_count=len(planet_posts),
                elapsed_seconds=elapsed,
            )
            rounds.append(row)
            _print_round(row)
            break

        if at_spend_stop():
            stop_reason = STOP_SPEND
            row = EditionRoundLog(
                round=round_num,
                posts_fetched=0,
                spam_blocked=0,
                chitchat_blocked=0,
                language_blocked=0,
                link_blocked=0,
                near_duplicate_dropped=near_dup_dropped,
                late_chitchat_skipped=int(meta.get("skipped_chitchat_cluster_pass") or 0),
                stored_count=len(cleaned),
                edition_quality_count=len(planet_posts),
                elapsed_seconds=elapsed,
            )
            rounds.append(row)
            _print_round(row)
            break

        from pipeline.live import fill_past_safe_margin

        if fill_past_safe_margin(moment):
            stop_reason = STOP_WALL_TIME
            row = EditionRoundLog(
                round=round_num,
                posts_fetched=0,
                spam_blocked=0,
                chitchat_blocked=0,
                language_blocked=0,
                link_blocked=0,
                near_duplicate_dropped=near_dup_dropped,
                late_chitchat_skipped=int(meta.get("skipped_chitchat_cluster_pass") or 0),
                stored_count=len(cleaned),
                edition_quality_count=len(planet_posts),
                elapsed_seconds=elapsed,
            )
            rounds.append(row)
            _print_round(row)
            break

        shortfall = clustering_topup_shortfall(
            target,
            len(planet_posts),
            int(meta.get("skipped_non_english") or 0),
            int(meta.get("skipped_link_only") or 0),
        )
        stored_target = len(cleaned) + max(shortfall, 1) + STORED_OVERFETCH_MARGIN
        if round_num == 1:
            cleaned, fetch_exhausted = ingest_free(
                existing,
                settings,
                queries,
                target=max(stored_target, target),
                now=moment,
                reset_log=True,
            )
        else:
            cleaned, fetch_exhausted = ingest_free(
                cleaned,
                settings,
                queries,
                target=stored_target,
                now=moment,
                reset_log=False,
            )

        after_log = _log_snapshot()
        delta = _delta(before_log, after_log)
        stored_added = len(cleaned) - before_stored
        planet_posts, meta = measure_edition(cleaned)
        edition_added = len(planet_posts) - before_edition
        if len(planet_posts) >= target:
            cleaned, planet_posts = trim_to_target(
                cleaned,
                planet_posts,
                target=target,
                window_hours=window_hours,
                now=moment,
            )
            stop_reason = STOP_REACHED_TARGET
        elapsed = time.monotonic() - loop_started

        row = EditionRoundLog(
            round=round_num,
            posts_fetched=int(delta["fetched"]),
            spam_blocked=int(delta["spam_blocked"]),
            chitchat_blocked=int(delta["chitchat_blocked"]),
            language_blocked=int(delta["language_blocked"]),
            link_blocked=int(delta["link_blocked"]),
            near_duplicate_dropped=near_dup_dropped,
            late_chitchat_skipped=int(meta.get("skipped_chitchat_cluster_pass") or 0),
            stored_count=len(cleaned),
            edition_quality_count=len(planet_posts),
            elapsed_seconds=elapsed,
        )
        rounds.append(row)
        _print_round(row)

        if stop_reason == STOP_REACHED_TARGET:
            break

        if fetch_exhausted:
            stop_reason = STOP_WINDOW_EXHAUSTED
            break

        if edition_added < progress_min and stored_added <= 0:
            no_progress_streak += 1
        else:
            no_progress_streak = 0
        if no_progress_streak >= NO_PROGRESS_STREAK:
            stop_reason = STOP_NO_PROGRESS
            break

        if round_num >= max_rounds:
            stop_reason = STOP_MAX_ROUNDS
            break

    else:
        stop_reason = STOP_MAX_ROUNDS

    result = EditionFillResult(
        cleaned=cleaned,
        planet_posts=planet_posts,
        target=target,
        stop_reason=stop_reason,
        rounds=rounds,
        skipped_non_english=int(meta.get("skipped_non_english") or 0),
        skipped_link_only=int(meta.get("skipped_link_only") or 0),
        skipped_chitchat_cluster_pass=int(meta.get("skipped_chitchat_cluster_pass") or 0),
        ingest_stored=len(cleaned),
        before_language_filter=int(meta.get("before_language_filter") or 0),
    )
    print(result.summary_line())
    if stop_reason != STOP_REACHED_TARGET:
        print(
            f"Edition fill shortfall: {len(planet_posts)} of {target} "
            f"(stop_reason={stop_reason}).",
            file=__import__("sys").stderr,
        )
    return result
