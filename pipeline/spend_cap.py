"""Hard daily cap on paid production calls (#148).

Michael, 2026-10-12 8:44 AM CT, Option A: warn at $0.50, stop at $1.00, and do
not publish. The site keeps yesterday's edition.

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
import threading
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.costs import (
    LLM_SERVICES,
    SERVICE_JEV,
    SERVICE_R2,
    Attempt,
    format_usd,
)

# Michael, 2026-10-12. Warn is the old $0.50 target. Stop is the hard cap.
DAILY_WARN_USD = Decimal("0.50")
DAILY_STOP_USD = Decimal("1.00")
ENV_WARN = "PERSPECTIVERSE_DAILY_SPEND_WARN"
ENV_STOP = "PERSPECTIVERSE_DAILY_SPEND_STOP"
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


def warn_usd() -> Decimal:
    return _money(os.getenv(ENV_WARN) or "", fallback=DAILY_WARN_USD)


def stop_usd() -> Decimal:
    limit = _money(os.getenv(ENV_STOP) or "", fallback=DAILY_STOP_USD)
    if warn_usd() > limit:
        raise SpendCapExceeded(
            f"Daily spend warn ${format_usd(warn_usd())} is above the stop "
            f"${format_usd(limit)}. Not publishing.",
            spent_usd=Decimal("0"),
        )
    return limit


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
    """Ledger rows for today plus paid calls metered in this process."""
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
    """Warn at $0.50. Raise once today's paid calls are at $1.00."""
    _maybe_warn_locked(total)
    limit = stop_usd()
    if total < limit:
        return
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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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

    fetched = _git(repo, "fetch", "origin", "data-snapshot", check=False)
    if fetched.returncode != 0:
        print(
            "Spend cap hold: data-snapshot is not available; not publishing an edition.",
            file=sys.stderr,
        )
        return STOP_EXIT

    shown = _git(repo, "show", "origin/data-snapshot:public/data.json", check=False)
    before = shown.stdout if shown.returncode == 0 else None
    if before is None:
        print("Spend cap hold: data-snapshot has no public/data.json; not creating one.")
    else:
        print(f"Spend cap hold: edition sha256 before {_sha256(before)}")

    ledger_bytes = _git(repo, "show", "origin/data-snapshot:costs/ledger.csv", check=False)
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        costs_dir = temp / "costs"
        costs_dir.mkdir()
        ledger_path = costs_dir / "ledger.csv"
        readme_path = costs_dir / "README.md"
        if ledger_bytes.returncode == 0 and ledger_bytes.stdout:
            ledger_path.write_bytes(ledger_bytes.stdout)
        if run_file.is_file():
            from pipeline.costs import append_run_files

            if append_run_files(run_file, ledger_path, readme_path) != 0:
                print(
                    "::warning::Could not append the capped run to the cost ledger. "
                    "The edition will not be published.",
                    file=sys.stderr,
                )
                present = {}
                return STOP_EXIT
        staged = {
            "costs/ledger.csv": ledger_path,
            "costs/README.md": readme_path,
            "costs/daily_spend_14d.svg": costs_dir / "daily_spend_14d.svg",
        }
        present = {name: path.read_bytes() for name, path in staged.items() if path.is_file()}

    _git(repo, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    _git(repo, "config", "user.name", "github-actions[bot]")
    _git(repo, "reset", "--hard", "HEAD")
    _git(repo, "checkout", "--force", "-B", "data-snapshot", "origin/data-snapshot")

    edition = repo / EDITION_GIT_PATH
    if before is not None:
        current = edition.read_bytes() if edition.is_file() else b""
        if current != before:
            print("::error::Spend cap hold found public/data.json already changed. Not pushing.", file=sys.stderr)
            _git(repo, "reset", "--hard", "origin/data-snapshot")
            return 1

    if present:
        for name, payload in present.items():
            destination = repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            _git(repo, "add", "--", name)

    if before is not None and edition.read_bytes() != before:
        print("::error::Spend cap hold would replace public/data.json. Not pushing.", file=sys.stderr)
        _git(repo, "reset", "--hard", "origin/data-snapshot")
        return 1

    cached = _git(repo, "diff", "--cached", "--name-only")
    names = [line.decode().strip() for line in cached.stdout.splitlines() if line.strip()]
    if any(name == EDITION_GIT_PATH or name.startswith("public/") for name in names):
        print("::error::Spend cap hold staged the edition. Not pushing.", file=sys.stderr)
        _git(repo, "reset", "--hard", "origin/data-snapshot")
        return 1

    if names:
        _git(
            repo,
            "commit",
            "-m",
            "Record spend from a capped run; keep the previous discourse edition",
        )
    else:
        print("Spend cap hold: no new cost rows. Edition unchanged.")

    if before is not None:
        after = edition.read_bytes()
        if after != before:
            print("::error::Spend cap hold changed public/data.json after commit. Not pushing.", file=sys.stderr)
            _git(repo, "reset", "--hard", "origin/data-snapshot")
            return 1
        print(f"Spend cap hold: edition sha256 after {_sha256(after)} unchanged")

    if push and names:
        _git(repo, "push", "origin", "data-snapshot")
        print("Spend cap hold: pushed the cost ledger only.")
    elif names:
        print("Spend cap hold: cost ledger committed locally; push not requested.")
    return STOP_EXIT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep yesterday's edition when the daily spend cap stops a run")
    sub = parser.add_subparsers(dest="command", required=True)
    hold = sub.add_parser("hold-edition", help="Append the cost ledger and do not replace public/data.json")
    hold.add_argument("--repo", type=Path, required=True)
    hold.add_argument("--push", action="store_true")
    hold.add_argument("--cost-run", type=Path, default=None)
    hold.add_argument("--marker", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "hold-edition":
        return hold_edition(args.repo, push=args.push, cost_run=args.cost_run, marker=args.marker)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
