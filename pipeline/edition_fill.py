"""Bounded fetch loop until the edition holds exactly ``target`` quality posts (#213).

Fetching is free; this module never calls Jev or labeling. Stop reasons are
logged once at the end and attached to the preview summary and cost run.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pipeline.chitchat_guard import (
    clustering_topup_shortfall,
    drop_link_and_language_at_ingest,
    edition_posts_for_clustering,
    get_chitchat_log,
    reset_chitchat_log,
)

# When link/language stay in the stored corpus (main / switch off), the edition
# cannot be topped up for clustering-only skips. Not a fetch stall.
STOP_EDITION_GAP = "edition_quality_shortfall"
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
# Sized for ~26 min worst-case ingest passes: 260 min ingest budget / ~26 ≈ 10, but
# rounds are shortfall-bounded (not full 7-day walks), so 5 is a safety valve.
DEFAULT_MAX_ROUNDS = 5
STORED_OVERFETCH_MARGIN = 200
NO_PROGRESS_STREAK = 2
PROGRESS_FRACTION = 0.005
# Observed downstream wall time after ingest (cluster + labels + sections).
POST_INGEST_RESERVE_MINUTES = 55


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
    carried_cluster_skips: dict[str, int] = field(default_factory=dict)

    def pipeline_dict(self) -> dict:
        return {
            "target_quality_posts": self.target,
            "ingest_stored": self.ingest_stored,
            "before_language_filter": self.before_language_filter,
            "skipped_non_english": self.skipped_non_english,
            "skipped_link_only": self.skipped_link_only,
            "skipped_chitchat_cluster_pass": self.skipped_chitchat_cluster_pass,
            "edition_posts_for_clustering": len(self.planet_posts),
            "carried_cluster_skips": dict(self.carried_cluster_skips),
            "chitchat_ingest": get_chitchat_log().to_dict(),
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


def edition_fill_past_safe_margin(clock: Callable[[], datetime]) -> bool:
    """True when ingest must stop so clustering, labels, and sections can finish.

    Uses the Actions job start (``PERSPECTIVERSE_JOB_STARTED_AT``), the 360-minute
    job limit, the 45-minute fill margin, and a 55-minute downstream reserve.
    """
    from pipeline.live import FILL_JOB_MARGIN_MINUTES, PIPELINE_JOB_LIMIT_MINUTES, _job_started_at

    now = clock()
    started = _job_started_at(now)
    ingest_budget = (
        PIPELINE_JOB_LIMIT_MINUTES - FILL_JOB_MARGIN_MINUTES - POST_INGEST_RESERVE_MINUTES
    )
    deadline = started + timedelta(minutes=ingest_budget)
    return now.astimezone(timezone.utc) >= deadline.astimezone(timezone.utc)


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


def measure_edition(
    cleaned: list[dict],
    *,
    carried_uris: set[str] | None = None,
    carried_skips: dict[str, int] | None = None,
) -> tuple[list[dict], dict]:
    """Edition-quality posts for clustering plus skip counts from the clustering pass."""
    from pipeline.live import posts_for_planets

    planet_posts = posts_for_planets(cleaned, require_claims=False)
    before_filter = len(planet_posts)
    cluster_skips = carried_skips if carried_skips is not None else {}
    planet_posts, skipped_language, skipped_links, skipped_chitchat = edition_posts_for_clustering(
        planet_posts,
        carried_uris=carried_uris or set(),
        carried_skips=cluster_skips,
    )
    if cluster_skips:
        print(
            "Carried-over clustering filters: "
            f"chitchat={cluster_skips.get('chitchat', 0)}, "
            f"link_only={cluster_skips.get('link_only', 0)}, "
            f"language={cluster_skips.get('language', 0)}."
        )
    return planet_posts, {
        "before_language_filter": before_filter,
        "skipped_non_english": skipped_language,
        "skipped_link_only": skipped_links,
        "skipped_chitchat_cluster_pass": skipped_chitchat,
    }


def apply_window_eviction(
    posts: list[dict],
    *,
    clock: Callable[[], datetime],
    window_hours: int,
) -> list[dict]:
    """Drop posts outside the rolling window before the first edition measure."""
    moment = clock()
    return retire_oldest(
        posts,
        now=moment,
        window_hours=window_hours,
        target=len(posts),
    )


def trim_to_target(
    cleaned: list[dict],
    planet_posts: list[dict],
    *,
    target: int,
    window_hours: int,
    clock: Callable[[], datetime],
    edition_uris_before: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Cap edition posts to ``target`` with ``retire_oldest``, then align stored corpus."""
    moment = clock()
    if len(planet_posts) <= target:
        return cleaned, planet_posts
    trimmed_posts = retire_oldest(
        planet_posts,
        now=moment,
        window_hours=window_hours,
        target=target,
    )
    trim_uris = {str(post.get("uri") or "") for post in trimmed_posts if post.get("uri")}
    if drop_link_and_language_at_ingest():
        aligned = [post for post in cleaned if str(post.get("uri") or "") in trim_uris]
        aligned = retire_oldest(
            aligned,
            now=moment,
            window_hours=window_hours,
            target=target,
        )
        return aligned, trimmed_posts
    before = edition_uris_before or {str(post.get("uri") or "") for post in planet_posts if post.get("uri")}
    aligned = []
    for post in cleaned:
        uri = str(post.get("uri") or "")
        if not uri:
            continue
        if uri in trim_uris:
            aligned.append(post)
            continue
        if uri not in before:
            aligned.append(post)
    aligned = retire_oldest(
        aligned,
        now=moment,
        window_hours=window_hours,
        target=len(aligned),
    )
    return aligned, trimmed_posts


def _try_reach_exact_target(
    cleaned: list[dict],
    planet_posts: list[dict],
    meta: dict,
    *,
    target: int,
    window_hours: int,
    clock: Callable[[], datetime],
    carried_uris: set[str] | None = None,
    carried_cluster_skips: dict[str, int] | None = None,
) -> tuple[bool, list[dict], list[dict], dict]:
    """Trim overshoot and re-measure. Success only when edition count equals ``target``."""
    if len(planet_posts) < target:
        return False, cleaned, planet_posts, meta
    edition_before = {str(post.get("uri") or "") for post in planet_posts if post.get("uri")}
    cleaned, planet_posts = trim_to_target(
        cleaned,
        planet_posts,
        target=target,
        window_hours=window_hours,
        clock=clock,
        edition_uris_before=edition_before,
    )
    planet_posts, meta = measure_edition(
        cleaned,
        carried_uris=carried_uris,
        carried_skips=carried_cluster_skips,
    )
    return len(planet_posts) == target, cleaned, planet_posts, meta


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


def _run_switch_off_one_shot(
    existing: list[dict],
    settings: dict,
    queries: list[str] | None,
    *,
    target: int,
    tick: Callable[[], datetime],
    window_hours: int,
    loop_started: float,
    carried_uris: set[str],
    carried_cluster_skips: dict[str, int],
) -> EditionFillResult:
    """Main's one-shot top-up: initial ingest only when stored < target; fetch when shortfall > 0."""
    cleaned = apply_window_eviction(list(existing), clock=tick, window_hours=window_hours)
    planet_posts, meta = measure_edition(
        cleaned,
        carried_uris=carried_uris,
        carried_skips=carried_cluster_skips,
    )
    reached, cleaned, planet_posts, meta = _try_reach_exact_target(
        cleaned,
        planet_posts,
        meta,
        target=target,
        window_hours=window_hours,
        clock=tick,
        carried_uris=carried_uris,
        carried_cluster_skips=carried_cluster_skips,
    )
    if reached:
        row = _round_log(
            round_num=1,
            delta={key: 0 for key in _log_snapshot()},
            near_dup=0,
            meta=meta,
            stored_count=len(cleaned),
            edition_count=len(planet_posts),
            elapsed=time.monotonic() - loop_started,
        )
        _print_round(row)
        return EditionFillResult(
            cleaned=cleaned,
            planet_posts=planet_posts,
            target=target,
            stop_reason=STOP_REACHED_TARGET,
            rounds=[row],
            skipped_non_english=int(meta.get("skipped_non_english") or 0),
            skipped_link_only=int(meta.get("skipped_link_only") or 0),
            skipped_chitchat_cluster_pass=int(meta.get("skipped_chitchat_cluster_pass") or 0),
            ingest_stored=len(cleaned),
            before_language_filter=int(meta.get("before_language_filter") or 0),
            carried_cluster_skips=dict(carried_cluster_skips),
        )

    near_dup_total = 0
    if len(cleaned) < target:
        cleaned, _exhausted, near_dup = ingest_free(
            existing,
            settings,
            queries,
            target=target,
            now=tick(),
            reset_log=True,
        )
        near_dup_total += near_dup
        planet_posts, meta = measure_edition(
            cleaned,
            carried_uris=carried_uris,
            carried_skips=carried_cluster_skips,
        )

    shortfall = clustering_topup_shortfall(
        target,
        len(planet_posts),
        int(meta.get("skipped_non_english") or 0),
        int(meta.get("skipped_link_only") or 0),
    )
    if shortfall > 0:
        cleaned, _exhausted, near_dup = ingest_free(
            cleaned,
            settings,
            queries,
            target=len(cleaned) + shortfall,
            now=tick(),
            reset_log=False,
        )
        near_dup_total += near_dup
        planet_posts, meta = measure_edition(
            cleaned,
            carried_uris=carried_uris,
            carried_skips=carried_cluster_skips,
        )

    reached, cleaned, planet_posts, meta = _try_reach_exact_target(
        cleaned,
        planet_posts,
        meta,
        target=target,
        window_hours=window_hours,
        clock=tick,
        carried_uris=carried_uris,
        carried_cluster_skips=carried_cluster_skips,
    )
    stop_reason = STOP_REACHED_TARGET if reached else STOP_EDITION_GAP
    row = _round_log(
        round_num=1,
        delta={key: 0 for key in _log_snapshot()},
        near_dup=near_dup_total,
        meta=meta,
        stored_count=len(cleaned),
        edition_count=len(planet_posts),
        elapsed=time.monotonic() - loop_started,
    )
    _print_round(row)
    result = EditionFillResult(
        cleaned=cleaned,
        planet_posts=planet_posts,
        target=target,
        stop_reason=stop_reason,
        rounds=[row],
        skipped_non_english=int(meta.get("skipped_non_english") or 0),
        skipped_link_only=int(meta.get("skipped_link_only") or 0),
        skipped_chitchat_cluster_pass=int(meta.get("skipped_chitchat_cluster_pass") or 0),
        ingest_stored=len(cleaned),
        before_language_filter=int(meta.get("before_language_filter") or 0),
        carried_cluster_skips=dict(carried_cluster_skips),
    )
    print(result.summary_line())
    if stop_reason != STOP_REACHED_TARGET:
        print(
            f"Edition fill shortfall: {len(planet_posts)} of {target} "
            f"(stop_reason={stop_reason}).",
            file=__import__("sys").stderr,
        )
    return result


def _round_log(
    *,
    round_num: int,
    delta: dict[str, int],
    near_dup: int,
    meta: dict,
    stored_count: int,
    edition_count: int,
    elapsed: float,
) -> EditionRoundLog:
    return EditionRoundLog(
        round=round_num,
        posts_fetched=int(delta.get("fetched", 0)),
        spam_blocked=int(delta.get("spam_blocked", 0)),
        chitchat_blocked=int(delta.get("chitchat_blocked", 0)),
        language_blocked=int(delta.get("language_blocked", 0)),
        link_blocked=int(delta.get("link_blocked", 0)),
        near_duplicate_dropped=int(near_dup),
        late_chitchat_skipped=int(meta.get("skipped_chitchat_cluster_pass") or 0),
        stored_count=stored_count,
        edition_quality_count=edition_count,
        elapsed_seconds=elapsed,
    )


def run_edition_fill_loop(
    existing: list[dict],
    settings: dict,
    queries: list[str] | None,
    *,
    target: int,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> EditionFillResult:
    """Fetch, filter, dedupe, and evict until the edition reaches ``target`` or a stop fires."""
    if clock is not None:
        tick = clock
    elif now is not None:
        fixed = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        fixed = fixed.astimezone(timezone.utc)

        def tick() -> datetime:
            return fixed

    else:

        def tick() -> datetime:
            return datetime.now(timezone.utc)
    window_hours = int(settings.get("window_hours") or 168)
    carried_uris = {str(post.get("uri") or "") for post in existing if post.get("uri")}
    carried_cluster_skips: dict[str, int] = {}
    reset_chitchat_log()
    loop_started = time.monotonic()
    if not drop_link_and_language_at_ingest():
        return _run_switch_off_one_shot(
            existing,
            settings,
            queries,
            target=target,
            tick=tick,
            window_hours=window_hours,
            loop_started=loop_started,
            carried_uris=carried_uris,
            carried_cluster_skips=carried_cluster_skips,
        )
    cleaned = apply_window_eviction(list(existing), clock=tick, window_hours=window_hours)
    planet_posts: list[dict] = []
    meta: dict = {}
    stop_reason = STOP_MAX_ROUNDS
    rounds: list[EditionRoundLog] = []
    no_progress_streak = 0
    progress_min = progress_threshold(target)
    max_rounds = max_fetch_rounds()
    fetch_exhausted = False
    for round_num in range(1, max_rounds + 1):
        before_log = _log_snapshot()
        before_edition = len(planet_posts)
        near_dup_dropped = 0

        planet_posts, meta = measure_edition(
            cleaned,
            carried_uris=carried_uris,
            carried_skips=carried_cluster_skips,
        )
        elapsed = time.monotonic() - loop_started

        reached, cleaned, planet_posts, meta = _try_reach_exact_target(
            cleaned,
            planet_posts,
            meta,
            target=target,
            window_hours=window_hours,
            clock=tick,
            carried_uris=carried_uris,
            carried_cluster_skips=carried_cluster_skips,
        )
        if reached:
            stop_reason = STOP_REACHED_TARGET
            row = _round_log(
                round_num=round_num,
                delta={key: 0 for key in before_log},
                near_dup=0,
                meta=meta,
                stored_count=len(cleaned),
                edition_count=len(planet_posts),
                elapsed=time.monotonic() - loop_started,
            )
            rounds.append(row)
            _print_round(row)
            break

        if at_spend_stop():
            stop_reason = STOP_SPEND
            row = _round_log(
                round_num=round_num,
                delta={key: 0 for key in before_log},
                near_dup=0,
                meta=meta,
                stored_count=len(cleaned),
                edition_count=len(planet_posts),
                elapsed=elapsed,
            )
            rounds.append(row)
            _print_round(row)
            break

        if edition_fill_past_safe_margin(tick):
            stop_reason = STOP_WALL_TIME
            row = _round_log(
                round_num=round_num,
                delta={key: 0 for key in before_log},
                near_dup=0,
                meta=meta,
                stored_count=len(cleaned),
                edition_count=len(planet_posts),
                elapsed=elapsed,
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
        fetch_budget = max(shortfall, 1) + STORED_OVERFETCH_MARGIN
        stored_cap = len(cleaned) + fetch_budget
        cleaned, fetch_exhausted, near_dup_dropped = ingest_free(
            cleaned,
            settings,
            queries,
            target=stored_cap,
            now=tick(),
            reset_log=round_num == 1,
            max_new_posts=fetch_budget,
        )

        after_log = _log_snapshot()
        delta = _delta(before_log, after_log)
        planet_posts, meta = measure_edition(
            cleaned,
            carried_uris=carried_uris,
            carried_skips=carried_cluster_skips,
        )
        edition_added = len(planet_posts) - before_edition
        elapsed = time.monotonic() - loop_started

        reached, cleaned, planet_posts, meta = _try_reach_exact_target(
            cleaned,
            planet_posts,
            meta,
            target=target,
            window_hours=window_hours,
            clock=tick,
            carried_uris=carried_uris,
            carried_cluster_skips=carried_cluster_skips,
        )
        row = _round_log(
            round_num=round_num,
            delta=delta,
            near_dup=near_dup_dropped,
            meta=meta,
            stored_count=len(cleaned),
            edition_count=len(planet_posts),
            elapsed=elapsed,
        )
        rounds.append(row)
        _print_round(row)

        if reached:
            stop_reason = STOP_REACHED_TARGET
            break

        if fetch_exhausted:
            stop_reason = STOP_WINDOW_EXHAUSTED
            break

        if edition_added < progress_min:
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
        carried_cluster_skips=dict(carried_cluster_skips),
    )
    print(result.summary_line())
    if stop_reason != STOP_REACHED_TARGET:
        print(
            f"Edition fill shortfall: {len(planet_posts)} of {target} "
            f"(stop_reason={stop_reason}).",
            file=__import__("sys").stderr,
        )
    return result
