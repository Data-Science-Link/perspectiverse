"""Best-effort meter for paid production calls.

DeepInfra labeling reports ``usage.estimated_cost``. TypeSafe Jev does not
report a dollar amount; input tokens are priced with
``JEV_USD_PER_MILLION_INPUT_TOKENS`` (output tokens are free). The daily
workflow appends one row per service and model to ``costs/ledger.csv`` on
``data-snapshot`` and regenerates ``costs/README.md``. A metering or ledger
error is a warning. It must not fail the pipeline.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Published TypeSafe price for Jev. Dated 2026-10-08.
# Output tokens are free. Change this only when the published price changes,
# and append a .factory/DECISIONS.md entry. Do not edit older entries.
JEV_PRICE_AS_OF = "2026-10-08"
JEV_USD_PER_MILLION_INPUT_TOKENS = Decimal("0.042")

SERVICE_DEEPINFRA = "deepinfra"
SERVICE_OPENAI_COMPATIBLE = "openai-compatible"
SERVICE_JEV = "typesafe-jev"
LLM_SERVICES = frozenset({SERVICE_DEEPINFRA, SERVICE_OPENAI_COMPATIBLE})

LEDGER_COLUMNS = [
    "run_id",
    "run_started_utc",
    "date_utc",
    "trigger",
    "service",
    "model",
    "calls",
    "failed_calls",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "cost_source",
    "posts_processed",
    "planets_published",
]

# Repo-relative paths. These stay off public/ so Pages does not deploy them.
LEDGER_PATH = Path("costs/ledger.csv")
README_PATH = Path("costs/README.md")
COST_RUN_PATH = Path(__file__).resolve().parent / "data" / "cost_run.json"

_INTEGER_COLUMNS = (
    "calls",
    "failed_calls",
    "input_tokens",
    "output_tokens",
    "posts_processed",
    "planets_published",
)


class CostLedgerError(RuntimeError):
    """The on-disk ledger cannot be appended to safely."""


@dataclass(frozen=True)
class Attempt:
    service: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    cost_source: str
    status: str


class CostMeter:
    """Thread-safe list of paid-call attempts. One process, one run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: list[Attempt] = []

    def record(self, attempt: Attempt) -> None:
        with self._lock:
            self._attempts.append(attempt)

    def attempts(self) -> tuple[Attempt, ...]:
        with self._lock:
            return tuple(self._attempts)


_meter = CostMeter()


def get_meter() -> CostMeter:
    return _meter


def reset_meter() -> None:
    """Test seam. Production runs start a fresh process."""
    global _meter
    _meter = CostMeter()


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def jev_cost_usd(input_tokens: int) -> Decimal:
    """Dollar cost of one Jev call. Output tokens are not billed."""
    tokens = Decimal(max(0, int(input_tokens)))
    return tokens * JEV_USD_PER_MILLION_INPUT_TOKENS / Decimal(1_000_000)


def parse_token_count(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        try:
            number = int(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return 0
    return max(0, number)


def parse_estimated_cost(value: object) -> Decimal | None:
    """Provider-reported dollars. ``None`` means the field was missing or unusable."""
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def llm_service_for_base_url(base_url: str) -> str:
    if "deepinfra.com" in (base_url or ""):
        return SERVICE_DEEPINFRA
    return SERVICE_OPENAI_COMPATIBLE


def record_attempt(
    *,
    service: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    cost_source: str,
    status: str,
) -> None:
    try:
        get_meter().record(
            Attempt(
                service=str(service or "unknown"),
                model=str(model or "unknown"),
                input_tokens=max(0, int(input_tokens)),
                output_tokens=max(0, int(output_tokens)),
                cost_usd=cost_usd if isinstance(cost_usd, Decimal) else Decimal(str(cost_usd)),
                cost_source=str(cost_source or ""),
                status=status if status in {"success", "retry", "failure"} else "failure",
            )
        )
    except Exception as exc:
        warn(f"Cost meter dropped an attempt: {exc}")


def _usage_dict(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}
    usage = payload.get("usage")
    return usage if isinstance(usage, dict) else {}


def _model_name(payload: dict | None, requested_model: str) -> str:
    if isinstance(payload, dict):
        responded = payload.get("model")
        if responded:
            return str(responded)
    return str(requested_model or "unknown")


def record_llm_attempt(
    *,
    service: str,
    requested_model: str,
    payload: dict | None,
    status: str,
) -> None:
    """Record one DeepInfra (or other OpenAI-compatible) attempt. Never raises."""
    try:
        usage = _usage_dict(payload)
        reported = parse_estimated_cost(usage.get("estimated_cost"))
        record_attempt(
            service=service,
            model=_model_name(payload, requested_model),
            input_tokens=parse_token_count(usage.get("prompt_tokens")),
            output_tokens=parse_token_count(usage.get("completion_tokens")),
            cost_usd=reported if reported is not None else Decimal("0"),
            cost_source="reported",
            status=status,
        )
    except Exception as exc:
        warn(f"Cost log skipped for a labeling call: {exc}")


def record_jev_attempt(
    *,
    requested_model: str,
    payload: dict | None,
    status: str,
) -> None:
    """Record one Jev attempt. Cost is computed from input tokens. Never raises."""
    try:
        usage = _usage_dict(payload)
        input_tokens = parse_token_count(usage.get("input_tokens"))
        record_attempt(
            service=SERVICE_JEV,
            model=_model_name(payload, requested_model),
            input_tokens=input_tokens,
            output_tokens=parse_token_count(usage.get("output_tokens")),
            cost_usd=jev_cost_usd(input_tokens),
            cost_source="computed",
            status=status,
        )
    except Exception as exc:
        warn(f"Cost log skipped for a Jev call: {exc}")


def run_identity(now: datetime | None = None) -> dict[str, str]:
    """GitHub Actions run id and trigger, with local fallbacks.

    Actions exposes ``GITHUB_RUN_ID`` and ``GITHUB_EVENT_NAME``. It does not
    expose a start timestamp, so ``run_started_utc`` is the pipeline clock.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    run_id = (os.getenv("GITHUB_RUN_ID") or "").strip()
    attempt = (os.getenv("GITHUB_RUN_ATTEMPT") or "").strip()
    # A re-run of the same Actions run spends again. Keep attempt 1 as the
    # bare run id; later attempts get a suffix so the ledger does not mix them.
    if run_id and attempt and attempt != "1":
        run_id = f"{run_id}.{attempt}"
    if not run_id:
        run_id = "local-" + moment.strftime("%Y%m%dT%H%M%SZ")
    trigger = (os.getenv("GITHUB_EVENT_NAME") or "").strip() or "local"
    return {
        "run_id": run_id,
        "run_started_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date_utc": moment.strftime("%Y-%m-%d"),
        "trigger": trigger,
    }


def count_published_planets(payload: dict) -> int:
    """Planets written into this run's data.json, including section solar systems."""
    total = len(payload.get("topics") or [])
    sections = payload.get("sections") or {}
    if isinstance(sections, dict):
        for planets in sections.values():
            if isinstance(planets, list):
                total += len(planets)
    return total


def rows_for_attempts(
    attempts: tuple[Attempt, ...] | list[Attempt],
    *,
    identity: dict[str, str],
    posts_processed: int,
    planets_published: int,
) -> list[dict[str, str]]:
    """One row per service and model. Empty when this run made no paid calls."""
    grouped: dict[tuple[str, str], dict] = {}
    for attempt in attempts:
        key = (attempt.service, attempt.model)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "calls": 0,
                "failed_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal("0"),
                "sources": set(),
            }
            grouped[key] = bucket
        bucket["calls"] += 1
        if attempt.status != "success":
            bucket["failed_calls"] += 1
        bucket["input_tokens"] += attempt.input_tokens
        bucket["output_tokens"] += attempt.output_tokens
        bucket["cost_usd"] += attempt.cost_usd
        if attempt.cost_source:
            bucket["sources"].add(attempt.cost_source)
    rows = []
    for service, model in sorted(grouped):
        bucket = grouped[(service, model)]
        sources = sorted(bucket["sources"])
        rows.append(
            {
                "run_id": identity["run_id"],
                "run_started_utc": identity["run_started_utc"],
                "date_utc": identity["date_utc"],
                "trigger": identity["trigger"],
                "service": service,
                "model": model,
                "calls": bucket["calls"],
                "failed_calls": bucket["failed_calls"],
                "input_tokens": bucket["input_tokens"],
                "output_tokens": bucket["output_tokens"],
                "cost_usd": bucket["cost_usd"],
                "cost_source": "+".join(sources),
                "posts_processed": int(posts_processed),
                "planets_published": int(planets_published),
            }
        )
    return [_stringify_row(row) for row in rows]


def write_cost_run(
    *,
    posts_processed: int,
    planets_published: int,
    started_at: datetime,
    path: Path | None = None,
    attempts: tuple[Attempt, ...] | None = None,
) -> Path | None:
    """Write this run's rows to a gitignored file. Never raises."""
    try:
        destination = Path(path) if path is not None else COST_RUN_PATH
        recorded = attempts if attempts is not None else get_meter().attempts()
        rows = rows_for_attempts(
            recorded,
            identity=run_identity(started_at),
            posts_processed=posts_processed,
            planets_published=planets_published,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rows": rows}
        _atomic_write(destination, json.dumps(payload, indent=2) + "\n")
        if rows:
            print(f"Cost run file: {destination} ({len(rows)} service row(s)).")
        else:
            print(f"Cost run file: {destination} (no paid calls).")
        return destination
    except Exception as exc:
        warn(f"Cost log skipped: {exc}")
        return None


def _stringify_row(row: dict) -> dict[str, str]:
    missing = [column for column in LEDGER_COLUMNS if column not in row or row[column] is None]
    if missing:
        raise CostLedgerError(f"cost row missing {', '.join(missing)}")
    out: dict[str, str] = {}
    for column in LEDGER_COLUMNS:
        value = row[column]
        if isinstance(value, Decimal):
            out[column] = "0" if value == 0 else format(value, "f")
        else:
            out[column] = str(value)
    for column in _INTEGER_COLUMNS:
        out[column] = str(int(Decimal(out[column])))
    return out


def read_ledger(path: Path) -> list[dict[str, str]]:
    """Read ledger rows. A foreign header raises so the file is left untouched."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if fieldnames != LEDGER_COLUMNS:
            raise CostLedgerError(
                f"{path} header {fieldnames} does not match the cost ledger; refusing to rewrite it"
            )
        rows: list[dict[str, str]] = []
        for raw in reader:
            if raw is None:
                continue
            if all(not (value or "").strip() for value in raw.values()):
                continue
            rows.append({column: raw.get(column) or "" for column in LEDGER_COLUMNS})
        return rows


def _csv_body(rows: list[dict[str, str]], *, header: bool) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
    if header:
        writer.writeheader()
    for row in rows:
        writer.writerow({column: row[column] for column in LEDGER_COLUMNS})
    return buffer.getvalue()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def append_ledger(path: Path, new_rows: list[dict]) -> list[dict[str, str]]:
    """Append rows. Existing bytes are kept. A bad header is not rewritten."""
    normalized = [_stringify_row(row) for row in new_rows]
    if not normalized:
        return read_ledger(path) if path.exists() else []
    if not path.exists() or path.stat().st_size == 0:
        _atomic_write(path, _csv_body(normalized, header=True))
        return list(normalized)
    # Validate before any write. A mismatch leaves the file unchanged.
    existing = read_ledger(path)
    original = path.read_text(encoding="utf-8")
    prefix = original if original.endswith("\n") else original + "\n"
    _atomic_write(path, prefix + _csv_body(normalized, header=False))
    return existing + normalized


@dataclass(frozen=True)
class CostTotals:
    runs: int
    llm_usd: Decimal
    jev_usd: Decimal
    total_usd: Decimal
    posts_processed: int
    planets_published: int

    @property
    def per_thousand_posts(self) -> Decimal | None:
        if self.posts_processed <= 0:
            return None
        return self.total_usd / Decimal(self.posts_processed) * Decimal(1000)

    @property
    def per_planet(self) -> Decimal | None:
        if self.planets_published <= 0:
            return None
        return self.total_usd / Decimal(self.planets_published)


def iso_week_label(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _accumulate(rows: list[dict[str, str]]) -> CostTotals:
    """Sum money by service. Count posts and planets once per run_id."""
    per_run: dict[str, dict[str, int]] = {}
    llm = Decimal("0")
    jev = Decimal("0")
    total = Decimal("0")
    for row in rows:
        cost = Decimal(row["cost_usd"] or "0")
        total += cost
        service = row["service"]
        if service == SERVICE_JEV:
            jev += cost
        elif service in LLM_SERVICES:
            llm += cost
        run = per_run.setdefault(row["run_id"], {"posts": 0, "planets": 0})
        run["posts"] = max(run["posts"], int(row["posts_processed"] or 0))
        run["planets"] = max(run["planets"], int(row["planets_published"] or 0))
    return CostTotals(
        runs=len(per_run),
        llm_usd=llm,
        jev_usd=jev,
        total_usd=total,
        posts_processed=sum(item["posts"] for item in per_run.values()),
        planets_published=sum(item["planets"] for item in per_run.values()),
    )


def weekly_rollup(
    rows: list[dict[str, str]],
    *,
    today: date,
) -> tuple[list[tuple[str, CostTotals]], CostTotals]:
    """ISO-week totals, newest week first, plus a last-30-days total.

    ``today`` is included. A row dated more than 30 days earlier is in its
    week but not in the trailing total.
    """
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    recent: list[dict[str, str]] = []
    cutoff = today - timedelta(days=30)
    for row in rows:
        day = date.fromisoformat(row["date_utc"])
        buckets[iso_week_label(day)].append(row)
        if day >= cutoff:
            recent.append(row)
    weeks = [(label, _accumulate(buckets[label])) for label in sorted(buckets, reverse=True)]
    return weeks, _accumulate(recent)


def format_usd(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.00000001"))
    text = format(quantized, "f")
    if "." in text:
        whole, fraction = text.split(".", 1)
        fraction = fraction.rstrip("0")
        if len(fraction) < 2:
            fraction = fraction.ljust(2, "0")
        return f"{whole}.{fraction}"
    return text + ".00"


def _table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _totals_cells(totals: CostTotals) -> list[str]:
    per_posts = "n/a" if totals.per_thousand_posts is None else format_usd(totals.per_thousand_posts)
    per_planet = "n/a" if totals.per_planet is None else format_usd(totals.per_planet)
    return [
        str(totals.runs),
        format_usd(totals.llm_usd),
        format_usd(totals.jev_usd),
        format_usd(totals.total_usd),
        str(totals.posts_processed),
        str(totals.planets_published),
        per_posts,
        per_planet,
    ]


def render_readme(rows: list[dict[str, str]], *, today: date | None = None) -> str:
    moment = today or datetime.now(timezone.utc).date()
    weeks, recent = weekly_rollup(rows, today=moment)
    price = format(JEV_USD_PER_MILLION_INPUT_TOKENS, "f")
    week_header = [
        "ISO week",
        "runs",
        "LLM $",
        "Jev $",
        "total $",
        "posts processed",
        "planets published",
        "$ per 1,000 posts",
        "$ per planet",
    ]
    summary_header = week_header[1:]
    lines = [
        "# Production call costs",
        "",
        "Paid calls from each successful daily pipeline run. One row per service and model is appended to `costs/ledger.csv` on the `data-snapshot` branch. This page is regenerated from that ledger. It is not in `public/` and is not deployed to GitHub Pages.",
        "",
        f"DeepInfra labeling dollars are the provider's `usage.estimated_cost` on each response. Jev dollars are computed, not reported by the API: input tokens × ${price} per 1,000,000 (published price dated {JEV_PRICE_AS_OF}). Jev output tokens are free. Local embeddings, GitHub Actions, and Bluesky reads are not listed.",
        "",
        "Posts are the `total_posts` figure in that run's `data.json` (claims that entered clustering). Planets are every planet written into that file, including section solar systems. Both are counted once per run, even when the run has a DeepInfra row and a Jev row. `$ per 1,000 posts` is total dollars ÷ posts × 1,000. `$ per planet` is total dollars ÷ planets published.",
        "",
        "## By ISO week",
        "",
    ]
    if not weeks:
        lines.append("No paid calls recorded yet.")
        lines.append("")
    else:
        lines.append(_table_row(week_header))
        lines.append(_table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]))
        for label, totals in weeks:
            lines.append(_table_row([label, *_totals_cells(totals)]))
        lines.append("")
    lines.extend(
        [
            "## Last 30 days",
            "",
            f"Runs whose `date_utc` is on or after {(moment - timedelta(days=30)).isoformat()} (through {moment.isoformat()}).",
            "",
            _table_row(summary_header),
            _table_row(["---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]),
            _table_row(_totals_cells(recent)),
            "",
        ]
    )
    return "\n".join(lines)


def write_readme(path: Path, rows: list[dict[str, str]], *, today: date | None = None) -> str:
    text = render_readme(rows, today=today)
    _atomic_write(path, text)
    return text


def load_run_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise CostLedgerError(f"{path} does not contain a rows list")
    return rows


def append_run_files(run_path: Path, ledger_path: Path, readme_path: Path) -> int:
    """Append one run and regenerate the weekly table. Returns 0 on success."""
    try:
        new_rows = load_run_rows(run_path)
        if not new_rows:
            print("No paid calls in this run; cost ledger left unchanged.")
            return 0
        combined = append_ledger(ledger_path, new_rows)
        write_readme(readme_path, combined)
    except Exception as exc:
        warn(f"Cost ledger update failed: {exc}")
        return 1
    print(f"Appended {len(new_rows)} cost row(s) to {ledger_path}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a pipeline cost run to the data-snapshot ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    append = sub.add_parser("append", help="Append costs/ledger.csv and regenerate costs/README.md")
    append.add_argument("--run", type=Path, required=True, help="cost_run.json written by the pipeline")
    append.add_argument("--ledger", type=Path, required=True)
    append.add_argument("--readme", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "append":
        return append_run_files(args.run, args.ledger, args.readme)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
