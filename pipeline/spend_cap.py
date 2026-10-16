"""Hard daily cap on paid production calls (#148).

Michael, 2026-10-12 8:44 AM CT, Option A: hard stop at $1.00 and do not publish.
Michael, 2026-10-16 11:35 AM CT: warn and stop both at $1.00 for the 100K ingest
window. The site keeps yesterday's edition.
Michael, 2026-10-16 1:29 PM CT / 2:46 PM CT: up to $15.00 paid across tagged fill
runs to reach 100K posts (#187). Fill spend is summed from ``tags=fill`` ledger rows
(per-call checkpoints in #186), not UTC-day boundaries. After the fill campaign
ends, the normal UTC-day cap returns (warn then hard stop; see
``DAILY_STOP_AFTER_FILL_USD``).

The total is every paid call this UTC day: labeling, Jev, and top-ups (top-up
rounds are more Jev calls). It includes every run that day — scheduled, push,
and manual — not only this process. R2 storage is not a call and is not counted.

The stop is on by default. ``PERSPECTIVERSE_DAILY_SPEND_WARN`` and
``PERSPECTIVERSE_DAILY_SPEND_STOP`` exist so a test can use a tiny cap.
A bad setting stops the run; it does not turn the cap off.

``SpendCapExceeded`` is raised after the call that crosses $1.00 has been
metered, and before any later paid call. Handlers that swallow a bad planet
or a metering error re-raise it so the run cannot publish anyway.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import threading
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.corpus import TARGET_POSTS
from pipeline.costs import (
    LLM_SERVICES,
    SERVICE_JEV,
    SERVICE_R2,
    Attempt,
    format_usd,
)

# Michael, 2026-10-16. Warn and stop both at $1.00 while the fill campaign is open (#182).
DAILY_WARN_USD = Decimal("1.00")
DAILY_STOP_USD = Decimal("1.00")
# Normal daily cap after the fill campaign ends (100K quality posts or fill budget spent).
# Michael may lower this to $0.50 once a measured 100K day is logged (#187).
DAILY_WARN_AFTER_FILL_USD = Decimal("0.50")
DAILY_STOP_AFTER_FILL_USD = Decimal("1.00")
# Michael, 2026-10-16 1:29 PM CT: hard stop on total fill-tagged paid spend.
FILL_BUDGET_TOTAL_USD = Decimal("15.00")
ENV_WARN = "PERSPECTIVERSE_DAILY_SPEND_WARN"
ENV_STOP = "PERSPECTIVERSE_DAILY_SPEND_STOP"
ENV_FILL_RUN = "PERSPECTIVERSE_FILL_RUN"
ENV_CORPUS_CLAIMS = "PERSPECTIVERSE_CORPUS_CLAIM_COUNT"
ENV_LEDGER = "PERSPECTIVERSE_COST_LEDGER"
ENV_COST_RUN = "PERSPECTIVERSE_COST_RUN"
ENV_MARKER = "PERSPECTIVERSE_SPEND_CAP_MARKER"

# Distinct from the publish guard's exit 10 (keep the edition, labeling degraded).
STOP_EXIT = 14

PAID_CALL_SERVICES = frozenset({SERVICE_JEV, *LLM_SERVICES})
EDITION_GIT_PATH = "public/data.json"
COST_GIT_PATHS = (
    "costs/ledger.csv",
    "costs/README.md",
    "costs/daily_spend_14d.svg",
)

_lock = threading.Lock()
_prior = Decimal("0")
_prior_loaded = False
_run_paid = Decimal("0")
_warned = False


class SpendCapExceeded(Exception):
    """Today's paid calls reached the hard stop. Do not publish."""

    exit_code = STOP_EXIT

    def __init__(self, message: str, *, spent_usd: Decimal) -> None:
        super().__init__(message)
        self.spent_usd = spent_usd


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def reset_day_state() -> None:
    """Forget this process's running total. The ledger is read again on the next call."""
    global _prior, _prior_loaded, _run_paid, _warned
    with _lock:
        _prior = Decimal("0")
        _prior_loaded = False
        _run_paid = Decimal("0")
        _warned = False


def marker_path() -> Path:
    override = (os.getenv(ENV_MARKER) or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "data" / "spend_cap_stop.json"


def cost_run_path() -> Path:
    override = (os.getenv(ENV_COST_RUN) or "").strip()
    if override:
        return Path(override)
    from pipeline.costs import COST_RUN_PATH

    return COST_RUN_PATH


def _money(raw: str, *, fallback: Decimal) -> Decimal:
    text = raw.strip()
    if not text:
        return fallback
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise SpendCapExceeded(
            f"Daily spend cap setting is not a dollar amount ({text!r}). Not publishing.",
            spent_usd=Decimal("0"),
        ) from exc
    if value < 0:
        raise SpendCapExceeded(
            f"Daily spend cap setting is negative ({text}). Not publishing.",
            spent_usd=Decimal("0"),
        )
    return value


def _env_count(name: str) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def corpus_claim_count() -> int:
    """Quality posts already in ``live_corpus.db``.

    The workflow sets this from ``count_quality_posts`` before the live step.
    The fill is done at ``TARGET_POSTS`` of these, the one corpus constant.
    """
    return _env_count(ENV_CORPUS_CLAIMS)


def _ledger_path() -> Path | None:
    path = (os.getenv(ENV_LEDGER) or "").strip()
    return Path(path) if path else None


def is_fill_run() -> bool:
    raw = (os.getenv(ENV_FILL_RUN) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def fill_paid_usd(ledger: Path) -> Decimal:
    """Paid-call dollars on fill-tagged ledger rows, every UTC day."""
    from pipeline.costs import read_ledger, row_has_fill_tag

    if not ledger.is_file() or ledger.stat().st_size == 0:
        return Decimal("0")
    total = Decimal("0")
    for row in read_ledger(ledger):
        if not row_has_fill_tag(row):
            continue
        if row.get("service") == SERVICE_R2 or row.get("service") not in PAID_CALL_SERVICES:
            continue
        total += _row_usd(row)
    return total


def fill_campaign_spent() -> Decimal:
    path = _ledger_path()
    if path is None:
        return Decimal("0")
    try:
        return fill_paid_usd(path)
    except Exception:
        return Decimal("0")


def fill_campaign_complete() -> bool:
    """True when quality posts hit ``TARGET_POSTS`` or fill-tagged spend hits $15.

    Quality posts are Jev claims kept in the database. Raw fetches and
    non-claims do not finish the fill.
    """
    if corpus_claim_count() >= TARGET_POSTS:
        return True
    return fill_campaign_spent() >= FILL_BUDGET_TOTAL_USD


def fill_dispatch_allowed() -> bool:
    return not fill_campaign_complete()


def _baseline_stop_usd() -> Decimal:
    if fill_campaign_complete():
        return DAILY_STOP_AFTER_FILL_USD
    return DAILY_STOP_USD


def warn_usd() -> Decimal:
    if is_fill_run():
        return _money(os.getenv(ENV_WARN) or "", fallback=DAILY_WARN_USD)
    if fill_campaign_complete():
        return _money(os.getenv(ENV_WARN) or "", fallback=DAILY_WARN_AFTER_FILL_USD)
    return _money(os.getenv(ENV_WARN) or "", fallback=DAILY_WARN_USD)


def stop_usd() -> Decimal:
    if is_fill_run():
        limit = FILL_BUDGET_TOTAL_USD
    else:
        limit = _money(os.getenv(ENV_STOP) or "", fallback=_baseline_stop_usd())
    if warn_usd() > limit:
        raise SpendCapExceeded(
            f"Daily spend warn ${format_usd(warn_usd())} is above the stop "
            f"${format_usd(limit)}. Not publishing.",
            spent_usd=Decimal("0"),
        )
    return limit


def _log_fill_shortfall(total: Decimal) -> None:
    claims = corpus_claim_count()
    if claims >= TARGET_POSTS:
        return
    gap = TARGET_POSTS - claims
    message = (
        f"Fill budget exhausted: paid ${format_usd(total)} of ${format_usd(FILL_BUDGET_TOTAL_USD)} "
        f"across fill-tagged runs; corpus at {claims:,} quality posts, "
        f"{gap:,} short of {TARGET_POSTS:,}. "
        f"Keeping paid posts from this run. Daily cap returns to warn ${format_usd(DAILY_WARN_AFTER_FILL_USD)} "
        f"/ stop ${format_usd(DAILY_STOP_AFTER_FILL_USD)} until the corpus is full."
    )
    print(message, file=sys.stderr)
    print(f"::warning::{message}")


def _row_usd(row: dict[str, str]) -> Decimal:
    try:
        value = Decimal(str(row.get("cost_usd") or "0"))
    except InvalidOperation:
        return Decimal("0")
    if value < 0:
        return Decimal("0")
    return value


def prior_paid_usd(ledger: Path, *, today: date) -> Decimal:
    """Paid-call dollars already on the ledger for this UTC day, every trigger."""
    from pipeline.costs import read_ledger

    if not ledger.is_file() or ledger.stat().st_size == 0:
        return Decimal("0")
    total = Decimal("0")
    for row in read_ledger(ledger):
        if row.get("service") == SERVICE_R2 or row.get("service") not in PAID_CALL_SERVICES:
            continue
        try:
            row_day = date.fromisoformat(row.get("date_utc") or "")
        except ValueError:
            continue
        if row_day != today:
            continue
        total += _row_usd(row)
    return total


def _load_prior_locked() -> None:
    global _prior, _prior_loaded
    if _prior_loaded:
        return
    _prior_loaded = True
    path = (os.getenv(ENV_LEDGER) or "").strip()
    if not path:
        _prior = Decimal("0")
        return
    ledger = Path(path)
    try:
        if is_fill_run():
            _prior = fill_paid_usd(ledger)
        else:
            _prior = prior_paid_usd(ledger, today=utc_today())
    except Exception as exc:
        _prior = Decimal("0")
        message = (
            "Could not read the cost ledger for the daily spend cap; "
            f"this run's calls still count ({exc})."
        )
        print(f"WARNING: {message}", file=sys.stderr)
        print(f"::warning::{message}")


def day_paid_usd() -> Decimal:
    """Paid calls already counted toward the active cap, plus this process.

    A fill run sums every fill-tagged row in ``costs/ledger.csv`` (every UTC
    day, including per-call checkpoints from earlier fill runs). It does not
    start again at $0. Any other run sums this UTC day only.
    """
    with _lock:
        _load_prior_locked()
        return _prior + _run_paid


def _maybe_warn_locked(total: Decimal) -> None:
    global _warned
    if _warned:
        return
    threshold = warn_usd()
    if total < threshold:
        return
    _warned = True
    message = (
        f"Daily spend reached ${format_usd(total)} "
        f"(warn ${format_usd(threshold)}, stop ${format_usd(stop_usd())})."
    )
    print(f"WARNING: {message}", file=sys.stderr)
    print(f"::warning::{message}")


def _raise_if_stopped(total: Decimal, *, where: str) -> None:
    """Warn at the active threshold. Raise once paid calls reach the hard stop."""
    _maybe_warn_locked(total)
    limit = stop_usd()
    if total < limit:
        return
    if is_fill_run():
        _log_fill_shortfall(total)
        message = (
            f"Fill spend cap stop: fill-tagged paid calls are ${format_usd(total)} "
            f"({where}), at the ${format_usd(limit)} hard stop. "
            "Not publishing; yesterday's edition stays."
        )
    else:
        message = (
            f"Daily spend cap stop: today's paid calls are ${format_usd(total)} "
            f"({where}), at the ${format_usd(limit)} hard stop. "
            "Not publishing; yesterday's edition stays."
        )
    print(message, file=sys.stderr)
    print(f"::error::{message}")
    raise SpendCapExceeded(message, spent_usd=total)


def guard_before_paid_call(kind: str) -> None:
    """Refuse another labeling, Jev, or top-up call when the day is already at the stop."""
    with _lock:
        _load_prior_locked()
        _raise_if_stopped(_prior + _run_paid, where=f"before another {kind} call")


def account_recorded_attempt(attempt: Attempt) -> None:
    """Count one metered paid call, then warn or stop. The call is already on the meter."""
    if attempt.service not in PAID_CALL_SERVICES:
        return
    added = attempt.cost_usd if isinstance(attempt.cost_usd, Decimal) else Decimal(str(attempt.cost_usd))
    if added < 0:
        added = Decimal("0")
    with _lock:
        _load_prior_locked()
        global _run_paid
        _run_paid += added
        try:
            from pipeline.costs import flush_cost_checkpoint

            flush_cost_checkpoint()
        except Exception as exc:
            print(f"WARNING: Cost checkpoint after a paid call skipped: {exc}", file=sys.stderr)
        kind = "Jev" if attempt.service == SERVICE_JEV else "labeling"
        _raise_if_stopped(_prior + _run_paid, where=f"after a {kind} call")


def enforce_before_paid_work() -> None:
    """Stop before Bluesky, Jev, or labeling when earlier runs today already hit $1.00."""
    with _lock:
        _load_prior_locked()
        _raise_if_stopped(_prior + _run_paid, where="before paid work")


def write_stop_marker(exc: SpendCapExceeded) -> Path:
    """Gitignored flag the workflow reads so a non-cap failure does not take this path."""
    destination = marker_path()
    payload = {
        "stopped": True,
        "spent_usd": format_usd(exc.spent_usd),
        "warn_usd": format_usd(warn_usd()) if _thresholds_ok() else "",
        "stop_usd": format_usd(stop_usd()) if _thresholds_ok() else "",
        "date_utc": utc_today().isoformat(),
        "exit_code": STOP_EXIT,
        "message": str(exc),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    print(f"Spend cap stop marker: {destination}")
    return destination


def _thresholds_ok() -> bool:
    try:
        warn_usd()
        stop_usd()
    except SpendCapExceeded:
        return False
    return True


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
    )


PUSH_RETRY = 2


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stage_ledger_from_cost_run(
    repo: Path,
    run_file: Path,
) -> tuple[dict[str, bytes], bytes | None] | None:
    """Build cost files to commit on ``data-snapshot``. ``None`` when append fails."""
    fetched = _git(repo, "fetch", "origin", "data-snapshot", check=False)
    if fetched.returncode != 0:
        print(
            "Ledger commit: data-snapshot is not available; not updating the cost ledger.",
            file=sys.stderr,
        )
        return None

    shown = _git(repo, "show", "origin/data-snapshot:public/data.json", check=False)
    before = shown.stdout if shown.returncode == 0 else None
    ledger_bytes = _git(repo, "show", "origin/data-snapshot:costs/ledger.csv", check=False)
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        costs_dir = temp / "costs"
        costs_dir.mkdir()
        ledger_path = costs_dir / "ledger.csv"
        readme_path = costs_dir / "README.md"
        if ledger_bytes.returncode == 0 and ledger_bytes.stdout:
            ledger_path.write_bytes(ledger_bytes.stdout)
        if not run_file.is_file():
            return ({}, before)
        from pipeline.costs import append_run_files, load_run_rows

        if not load_run_rows(run_file):
            return ({}, before)
        if append_run_files(run_file, ledger_path, readme_path) != 0:
            print(
                "::warning::Could not append this run to the cost ledger.",
                file=sys.stderr,
            )
            return None
        staged = {
            "costs/ledger.csv": ledger_path,
            "costs/README.md": readme_path,
            "costs/daily_spend_14d.svg": costs_dir / "daily_spend_14d.svg",
        }
        present = {name: path.read_bytes() for name, path in staged.items() if path.is_file()}
    return present, before


def _commit_ledger_only(
    repo: Path,
    present: dict[str, bytes],
    before: bytes | None,
    *,
    push: bool,
    commit_message: str,
    log_prefix: str,
) -> int:
    repo = Path(repo).resolve()
    _git(repo, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    _git(repo, "config", "user.name", "github-actions[bot]")
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "checkout", "--force", "-B", "data-snapshot", "origin/data-snapshot")

    edition = repo / EDITION_GIT_PATH
    if before is not None:
        current = edition.read_bytes() if edition.is_file() else b""
        if current != before:
            print(f"::error::{log_prefix} found public/data.json already changed. Not pushing.", file=sys.stderr)
            _git(repo, "reset", "--hard", "origin/data-snapshot")
            return 1
        print(f"{log_prefix}: edition sha256 before {_sha256(before)}")

    if present:
        for name, payload in present.items():
            destination = repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            _git(repo, "add", "--", name)

    if before is not None and edition.read_bytes() != before:
        print(f"::error::{log_prefix} would replace public/data.json. Not pushing.", file=sys.stderr)
        _git(repo, "reset", "--hard", "origin/data-snapshot")
        return 1

    cached = _git(repo, "diff", "--cached", "--name-only")
    names = [line.decode().strip() for line in cached.stdout.splitlines() if line.strip()]
    if any(name == EDITION_GIT_PATH or name.startswith("public/") for name in names):
        print(f"::error::{log_prefix} staged the edition. Not pushing.", file=sys.stderr)
        _git(repo, "reset", "--hard", "origin/data-snapshot")
        return 1

    if names:
        _git(repo, "commit", "-m", commit_message)
    else:
        print(f"{log_prefix}: no new cost rows. Edition unchanged.")
        return 0

    if before is not None:
        after = edition.read_bytes()
        if after != before:
            print(f"::error::{log_prefix} changed public/data.json after commit. Not pushing.", file=sys.stderr)
            _git(repo, "reset", "--hard", "origin/data-snapshot")
            return 1
        print(f"{log_prefix}: edition sha256 after {_sha256(after)} unchanged")

    if push and names:
        pushed = _git(repo, "push", "origin", "data-snapshot", check=False)
        if pushed.returncode != 0:
            return PUSH_RETRY
        print(f"{log_prefix}: pushed the cost ledger only.")
    elif names:
        print(f"{log_prefix}: cost ledger committed locally; push not requested.")
    return 0


def _commit_ledger_with_push_retry(
    repo: Path,
    run_file: Path,
    *,
    push: bool,
    commit_message: str,
    log_prefix: str,
    attempts: int = 4,
) -> int:
    """Stage from ``cost_run``, commit on ``data-snapshot``, and push with reset retries."""
    repo = Path(repo).resolve()
    run_file = Path(run_file)
    for attempt in range(attempts):
        staged = _stage_ledger_from_cost_run(repo, run_file)
        if staged is None:
            return 1
        present, before = staged
        if not present:
            print(f"{log_prefix}: no new cost rows. Edition unchanged.")
            return 0
        status = _commit_ledger_only(
            repo,
            present,
            before,
            push=push,
            commit_message=commit_message,
            log_prefix=log_prefix,
        )
        if status != PUSH_RETRY:
            return status
        if attempt + 1 < attempts:
            time.sleep(min(16, 2**attempt))
    print(f"::error::{log_prefix} could not push data-snapshot after retries.", file=sys.stderr)
    return 1


def record_partial_ledger(repo: Path, *, push: bool = False, cost_run: Path | None = None) -> int:
    """Append metered spend from a cancelled, crashed, or killed run.

    Uses ``cost_run.json``, which the pipeline flushes after each paid call.
    Does not replace ``public/data.json``.
    """
    repo = Path(repo).resolve()
    run_file = Path(cost_run) if cost_run is not None else repo / "pipeline" / "data" / "cost_run.json"
    return _commit_ledger_with_push_retry(
        repo,
        run_file,
        push=push,
        commit_message="Record partial spend from an interrupted pipeline run",
        log_prefix="Partial ledger",
    )


def hold_edition(repo: Path, *, push: bool = False, cost_run: Path | None = None, marker: Path | None = None) -> int:
    """Record this run's paid calls on data-snapshot. Do not replace ``public/data.json``.

    Returns 14 when the edition bytes are unchanged. Returns 1 when they would
    have changed (nothing is pushed in that case). A ledger commit is the only
    write, so the next run the same UTC day counts a stopped run. Pages does
    not deploy: the pipeline job still fails, and a ``GITHUB_TOKEN`` push does
    not start the Pages workflow.
    """
    repo = Path(repo).resolve()
    flag = Path(marker) if marker is not None else repo / "pipeline" / "data" / "spend_cap_stop.json"
    if not flag.is_file():
        print("Spend cap hold: no stop marker; not touching data-snapshot.", file=sys.stderr)
        return 1
    run_file = Path(cost_run) if cost_run is not None else repo / "pipeline" / "data" / "cost_run.json"
    status = _commit_ledger_with_push_retry(
        repo,
        run_file,
        push=push,
        commit_message="Record spend from a capped run; keep the previous discourse edition",
        log_prefix="Spend cap hold",
    )
    if status == 1:
        return 1
    return STOP_EXIT


def check_fill_dispatch() -> int:
    """Exit 1 when a fill dispatch was requested but the fill campaign is already done."""
    if not is_fill_run():
        return 0
    if fill_dispatch_allowed():
        return 0
    claims = corpus_claim_count()
    spent = fill_campaign_spent()
    if claims >= TARGET_POSTS:
        reason = f"corpus already has {claims:,} quality posts (target {TARGET_POSTS:,})"
    else:
        reason = (
            f"fill-tagged spend is ${format_usd(spent)} "
            f"(cap ${format_usd(FILL_BUDGET_TOTAL_USD)}) with {claims:,} quality posts"
        )
    message = (
        f"Fill dispatch refused: {reason}. Use a normal run; daily cap is warn "
        f"${format_usd(DAILY_WARN_AFTER_FILL_USD)} / stop ${format_usd(DAILY_STOP_AFTER_FILL_USD)}."
    )
    print(f"::error::{message}", file=sys.stderr)
    print(message, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep yesterday's edition when the daily spend cap stops a run")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser(
        "check-fill-dispatch",
        help="Refuse workflow_dispatch fill when the corpus is full or fill spend is exhausted",
    )
    hold = sub.add_parser("hold-edition", help="Append the cost ledger and do not replace public/data.json")
    hold.add_argument("--repo", type=Path, required=True)
    hold.add_argument("--push", action="store_true")
    hold.add_argument("--cost-run", type=Path, default=None)
    hold.add_argument("--marker", type=Path, default=None)
    partial = sub.add_parser(
        "record-partial-ledger",
        help="Append partial metered spend when a run was cancelled or crashed",
    )
    partial.add_argument("--repo", type=Path, required=True)
    partial.add_argument("--push", action="store_true")
    partial.add_argument("--cost-run", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "check-fill-dispatch":
        return check_fill_dispatch()
    if args.command == "hold-edition":
        return hold_edition(args.repo, push=args.push, cost_run=args.cost_run, marker=args.marker)
    if args.command == "record-partial-ledger":
        return record_partial_ledger(args.repo, push=args.push, cost_run=args.cost_run)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
