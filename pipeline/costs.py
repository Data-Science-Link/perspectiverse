"""Best-effort meter for paid production calls.

DeepInfra labeling reports ``usage.estimated_cost``. TypeSafe Jev does not
report a dollar amount; input tokens are priced with
``JEV_USD_PER_MILLION_INPUT_TOKENS`` (output tokens are free). Cloudflare R2
Standard is priced from the published rates in this file. The daily workflow
appends one row per service and model to ``costs/ledger.csv`` on
``data-snapshot`` and regenerates ``costs/README.md`` plus a 14-day SVG.
A metering or ledger error is a warning. It must not fail the pipeline.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import threading
import xml.etree.ElementTree as ET
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

# Cloudflare R2 Standard, https://developers.cloudflare.com/r2/pricing/
# Page last updated 2026-10-01. Constant dated 2026-10-08.
# Storage is USD per GB-month. A GB-month is the average of daily peak
# storage over a 30-day billing period, so one day is price / 30.
# 1 GB is 1e9 bytes (the pricing page's 100,000 x 100 KB example is 10 GB).
# Class A and Class B are USD per million requests. Egress is free.
# The published page also rounds usage up to the next whole billing unit.
# These constants follow the Standard worked example, which subtracts the
# free tier from the exact quantity (990 GB-month x $0.015 = $14.85).
R2_PRICE_AS_OF = "2026-10-08"
R2_USD_PER_GB_MONTH = Decimal("0.015")
R2_USD_PER_MILLION_CLASS_A = Decimal("4.50")
R2_USD_PER_MILLION_CLASS_B = Decimal("0.36")
R2_BILLING_DAYS = Decimal(30)
R2_BYTES_PER_GB = Decimal(1_000_000_000)
R2_FREE_STORAGE_GB_MONTH = Decimal("10")
R2_FREE_CLASS_A = 1_000_000
R2_FREE_CLASS_B = 10_000_000

SERVICE_DEEPINFRA = "deepinfra"
SERVICE_OPENAI_COMPATIBLE = "openai-compatible"
SERVICE_JEV = "typesafe-jev"
SERVICE_R2 = "cloudflare-r2"
R2_MODEL = "r2-standard"
LLM_SERVICES = frozenset({SERVICE_DEEPINFRA, SERVICE_OPENAI_COMPATIBLE})

# Columns appended for #80. A ledger that still has this header is migrated
# in place: every existing row is kept, and the new fields are filled.
LEGACY_LEDGER_COLUMNS = [
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
LEDGER_COLUMNS = [
    *LEGACY_LEDGER_COLUMNS,
    "storage_bytes",
    "class_a_ops",
    "class_b_ops",
    "list_price_usd",
]

# Repo-relative paths. These stay off public/ so Pages does not deploy them.
LEDGER_PATH = Path("costs/ledger.csv")
README_PATH = Path("costs/README.md")
CHART_PATH = Path("costs/daily_spend_14d.svg")
COST_RUN_PATH = Path(__file__).resolve().parent / "data" / "cost_run.json"
R2_USAGE_PATH = Path(__file__).resolve().parent / "data" / "r2_usage.json"

_INTEGER_COLUMNS = (
    "calls",
    "failed_calls",
    "input_tokens",
    "output_tokens",
    "posts_processed",
    "planets_published",
    "storage_bytes",
    "class_a_ops",
    "class_b_ops",
)

_CHART_DAYS = 14
_LLM_COLOR = "#3b6ea5"
_JEV_COLOR = "#2f7d4a"
_R2_COLOR = "#c46b1a"


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
_r2_lock = threading.Lock()


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


def note_r2_usage(
    *,
    class_a: int = 0,
    class_b: int = 0,
    storage_bytes: int | None = None,
    path: Path | None = None,
) -> None:
    """Add one R2 response to the gitignored usage file. Never raises.

    Restore and upload are separate processes. Each one updates the same
    file, and the publish step reads the total. A request that never
    returned a response is not recorded. Storage is the current corpus
    object size, not a sum of uploads.
    """
    try:
        destination = Path(path) if path is not None else R2_USAGE_PATH
        with _r2_lock:
            current = _empty_r2_usage()
            if destination.exists() and destination.stat().st_size > 0:
                loaded = json.loads(destination.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    current = _coerce_r2_usage(loaded)
            current["class_a_ops"] += max(0, int(class_a))
            current["class_b_ops"] += max(0, int(class_b))
            if storage_bytes is not None:
                current["storage_bytes"] = max(0, int(storage_bytes))
                current["storage_known"] = True
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(destination, json.dumps(current, indent=2) + "\n")
    except Exception as exc:
        warn(f"R2 usage log skipped: {exc}")


def _empty_r2_usage() -> dict:
    return {"class_a_ops": 0, "class_b_ops": 0, "storage_bytes": 0, "storage_known": False}


def _coerce_r2_usage(loaded: dict) -> dict:
    current = _empty_r2_usage()
    current["class_a_ops"] = max(0, parse_token_count(loaded.get("class_a_ops")))
    current["class_b_ops"] = max(0, parse_token_count(loaded.get("class_b_ops")))
    current["storage_bytes"] = max(0, parse_token_count(loaded.get("storage_bytes")))
    current["storage_known"] = bool(loaded.get("storage_known"))
    return current


def load_r2_usage(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return _empty_r2_usage()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise CostLedgerError(f"{path} is not an R2 usage object")
    return _coerce_r2_usage(loaded)


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
                "storage_bytes": 0,
                "class_a_ops": 0,
                "class_b_ops": 0,
                "list_price_usd": bucket["cost_usd"],
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
        identity = run_identity(started_at)
        payload = {
            "rows": rows,
            "run_id": identity["run_id"],
            "run_started_utc": identity["run_started_utc"],
            "date_utc": identity["date_utc"],
            "trigger": identity["trigger"],
            "posts_processed": int(posts_processed),
            "planets_published": int(planets_published),
        }
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
    filled = dict(row)
    for column in ("storage_bytes", "class_a_ops", "class_b_ops"):
        if column not in filled or filled[column] is None:
            filled[column] = 0
    if "list_price_usd" not in filled or filled["list_price_usd"] is None:
        filled["list_price_usd"] = filled.get("cost_usd", "0")
    missing = [column for column in LEDGER_COLUMNS if column not in filled or filled[column] is None]
    if missing:
        raise CostLedgerError(f"cost row missing {', '.join(missing)}")
    row = filled
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


def _header_kind(fieldnames: list[str]) -> str:
    if fieldnames == LEDGER_COLUMNS:
        return "current"
    if fieldnames == LEGACY_LEDGER_COLUMNS:
        return "legacy"
    return "foreign"


def _peek_header(path: Path) -> str:
    with path.open(newline="", encoding="utf-8") as handle:
        fieldnames = list(next(csv.reader(handle), []))
    return _header_kind(fieldnames)


def _upgrade_legacy_row(raw: dict) -> dict[str, str]:
    row = {column: raw.get(column) or "" for column in LEGACY_LEDGER_COLUMNS}
    row["storage_bytes"] = "0"
    row["class_a_ops"] = "0"
    row["class_b_ops"] = "0"
    row["list_price_usd"] = row["cost_usd"]
    return row


def read_ledger(path: Path) -> list[dict[str, str]]:
    """Read ledger rows. A foreign header raises so the file is left untouched.

    The pre-R2 header is accepted. Those rows stay in memory with the new
    columns filled. Reading does not rewrite the file.
    """
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        kind = _header_kind(fieldnames)
        if kind == "foreign":
            raise CostLedgerError(
                f"{path} header {fieldnames} does not match the cost ledger; refusing to rewrite it"
            )
        rows: list[dict[str, str]] = []
        for raw in reader:
            if raw is None:
                continue
            if all(not (value or "").strip() for value in raw.values()):
                continue
            if kind == "legacy":
                rows.append(_upgrade_legacy_row(raw))
            else:
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
    """Append rows. A matching header keeps the existing bytes.

    A legacy header is rewritten once with every old row plus the new ones.
    A foreign header raises and the file is not opened for writing.
    """
    normalized = [_stringify_row(row) for row in new_rows]
    if not normalized:
        return read_ledger(path) if path.exists() else []
    if not path.exists() or path.stat().st_size == 0:
        _atomic_write(path, _csv_body(normalized, header=True))
        return list(normalized)
    kind = _peek_header(path)
    if kind == "foreign":
        raise CostLedgerError(
            f"{path} header does not match the cost ledger; refusing to rewrite it"
        )
    existing = read_ledger(path)
    if kind == "legacy":
        combined = existing + normalized
        _atomic_write(path, _csv_body(combined, header=True))
        return combined
    original = path.read_text(encoding="utf-8")
    prefix = original if original.endswith("\n") else original + "\n"
    _atomic_write(path, prefix + _csv_body(normalized, header=False))
    return existing + normalized


@dataclass(frozen=True)
class CostTotals:
    runs: int
    llm_usd: Decimal
    jev_usd: Decimal
    r2_usd: Decimal
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
    r2 = Decimal("0")
    total = Decimal("0")
    for row in rows:
        cost = Decimal(row["cost_usd"] or "0")
        total += cost
        service = row["service"]
        if service == SERVICE_JEV:
            jev += cost
        elif service == SERVICE_R2:
            r2 += cost
        elif service in LLM_SERVICES:
            llm += cost
        run = per_run.setdefault(row["run_id"], {"posts": 0, "planets": 0})
        run["posts"] = max(run["posts"], int(row["posts_processed"] or 0))
        run["planets"] = max(run["planets"], int(row["planets_published"] or 0))
    return CostTotals(
        runs=len(per_run),
        llm_usd=llm,
        jev_usd=jev,
        r2_usd=r2,
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
        format_usd(totals.r2_usd),
        format_usd(totals.total_usd),
        str(totals.posts_processed),
        str(totals.planets_published),
        per_posts,
        per_planet,
    ]


def r2_list_price_usd(*, storage_bytes: int, class_a_ops: int, class_b_ops: int) -> Decimal:
    """List price of one run's own R2 usage. The free tier is not applied.

    Storage is one day of the measured object: bytes / 1e9 × $0.015 / 30.
    Operations are the run's Class A and Class B counts. Egress is free.
    """
    storage = (
        Decimal(max(0, int(storage_bytes)))
        / R2_BYTES_PER_GB
        * R2_USD_PER_GB_MONTH
        / R2_BILLING_DAYS
    )
    class_a = Decimal(max(0, int(class_a_ops))) / Decimal(1_000_000) * R2_USD_PER_MILLION_CLASS_A
    class_b = Decimal(max(0, int(class_b_ops))) / Decimal(1_000_000) * R2_USD_PER_MILLION_CLASS_B
    return storage + class_a + class_b


def _bill_above_free_tier(gb_month: Decimal, class_a: int, class_b: int) -> Decimal:
    storage = max(Decimal(0), gb_month - R2_FREE_STORAGE_GB_MONTH) * R2_USD_PER_GB_MONTH
    class_a_cost = (
        max(Decimal(0), Decimal(class_a) - Decimal(R2_FREE_CLASS_A))
        / Decimal(1_000_000)
        * R2_USD_PER_MILLION_CLASS_A
    )
    class_b_cost = (
        max(Decimal(0), Decimal(class_b) - Decimal(R2_FREE_CLASS_B))
        / Decimal(1_000_000)
        * R2_USD_PER_MILLION_CLASS_B
    )
    return storage + class_a_cost + class_b_cost


def _r2_observations(rows: list[dict[str, str]]) -> tuple[dict[date, int], list[tuple[date, int, int]]]:
    """Last storage measurement per day, and one ops triple per R2 row.

    A row with ``storage_known`` false adds operations and does not change
    the stored size. Ledger rows omit that flag and always count as a
    measurement.
    """
    storage: dict[date, int] = {}
    ops: list[tuple[date, int, int]] = []
    for row in rows:
        if row.get("service") != SERVICE_R2:
            continue
        day = date.fromisoformat(row["date_utc"])
        if str(row.get("storage_known", "true")).lower() != "false":
            storage[day] = int(row.get("storage_bytes") or 0)
        ops.append(
            (
                day,
                int(row.get("class_a_ops") or 0),
                int(row.get("class_b_ops") or 0),
            )
        )
    return storage, ops


def r2_month_bill_usd(rows: list[dict[str, str]], *, as_of: date) -> Decimal:
    """Billed R2 Standard spend for the calendar month containing ``as_of``.

    Each day from the first of the month through ``as_of`` contributes
    ``bytes / 1e9 / 30`` GB-month. The size is the latest measurement on or
    before that day, including a measurement from an earlier month, because
    the corpus object stays in the bucket. Days before the first measurement
    contribute nothing. Operations sum only inside the month.
    """
    storage, ops = _r2_observations(rows)
    month_start = as_of.replace(day=1)
    known: int | None = None
    earlier = [day for day in storage if day < month_start]
    if earlier:
        known = storage[max(earlier)]
    gb_days = Decimal(0)
    cursor = month_start
    while cursor <= as_of:
        if cursor in storage:
            known = storage[cursor]
        if known is not None:
            gb_days += Decimal(known) / R2_BYTES_PER_GB
        cursor += timedelta(days=1)
    class_a = sum(count for day, count, _class_b in ops if month_start <= day <= as_of)
    class_b = sum(count for day, _class_a, count in ops if month_start <= day <= as_of)
    return _bill_above_free_tier(gb_days / R2_BILLING_DAYS, class_a, class_b)


def _previously_billed_day(prior_rows: list[dict[str, str]], run_day: date) -> date | None:
    """Last day this month that already has an R2 row, including ``run_day``."""
    month_start = run_day.replace(day=1)
    billed: list[date] = []
    for row in prior_rows:
        if row.get("service") != SERVICE_R2:
            continue
        day = date.fromisoformat(row["date_utc"])
        if month_start <= day <= run_day:
            billed.append(day)
    if not billed:
        return None
    return max(billed)


def r2_billed_increment_usd(
    prior_rows: list[dict[str, str]],
    *,
    run_day: date,
    storage_bytes: int | None,
    class_a_ops: int,
    class_b_ops: int,
) -> Decimal:
    """Increase in this month's R2 bill caused by one run.

    Days since the previous R2 row are included, at the last known object
    size, because those days were not in the earlier bill. A later run on
    the same UTC day replaces that day's storage measurement and adds its
    operations. The result can be negative when a smaller object reduces
    the month's bill. Summing these increments reconstructs the month bill.
    """
    before_day = _previously_billed_day(prior_rows, run_day)
    before = Decimal(0) if before_day is None else r2_month_bill_usd(prior_rows, as_of=before_day)
    synthetic = {
        "service": SERVICE_R2,
        "date_utc": run_day.isoformat(),
        "storage_bytes": "0" if storage_bytes is None else str(int(storage_bytes)),
        "storage_known": "true" if storage_bytes is not None else "false",
        "class_a_ops": str(max(0, int(class_a_ops))),
        "class_b_ops": str(max(0, int(class_b_ops))),
    }
    after = r2_month_bill_usd([*prior_rows, synthetic], as_of=run_day)
    return after - before


def _carried_storage_bytes(prior_rows: list[dict[str, str]], run_day: date) -> int:
    storage, _ops = _r2_observations(prior_rows)
    earlier = [day for day in storage if day <= run_day]
    if not earlier:
        return 0
    return storage[max(earlier)]


def r2_ledger_row(
    prior_rows: list[dict[str, str]],
    *,
    identity: dict[str, str],
    posts_processed: int,
    planets_published: int,
    usage: dict,
) -> dict[str, str] | None:
    """One R2 row for this run, or ``None`` when the run did not touch R2."""
    class_a = int(usage.get("class_a_ops") or 0)
    class_b = int(usage.get("class_b_ops") or 0)
    known = bool(usage.get("storage_known"))
    if class_a == 0 and class_b == 0 and not known:
        return None
    run_day = date.fromisoformat(identity["date_utc"])
    measured = int(usage.get("storage_bytes") or 0) if known else None
    stored = measured if measured is not None else _carried_storage_bytes(prior_rows, run_day)
    list_price = r2_list_price_usd(
        storage_bytes=0 if measured is None else measured,
        class_a_ops=class_a,
        class_b_ops=class_b,
    )
    billed = r2_billed_increment_usd(
        prior_rows,
        run_day=run_day,
        storage_bytes=measured,
        class_a_ops=class_a,
        class_b_ops=class_b,
    )
    return _stringify_row(
        {
            "run_id": identity["run_id"],
            "run_started_utc": identity["run_started_utc"],
            "date_utc": identity["date_utc"],
            "trigger": identity["trigger"],
            "service": SERVICE_R2,
            "model": R2_MODEL,
            "calls": class_a + class_b,
            "failed_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": billed,
            "cost_source": "computed",
            "posts_processed": int(posts_processed),
            "planets_published": int(planets_published),
            "storage_bytes": stored,
            "class_a_ops": class_a,
            "class_b_ops": class_b,
            "list_price_usd": list_price,
        }
    )


def _r2_pricing_sentence() -> str:
    storage = format(R2_USD_PER_GB_MONTH, "f")
    class_a = format(R2_USD_PER_MILLION_CLASS_A, "f")
    class_b = format(R2_USD_PER_MILLION_CLASS_B, "f")
    return (
        f"R2 Standard list prices, dated {R2_PRICE_AS_OF}: "
        f"${storage} per GB-month of storage (one day is that price ÷ 30), "
        f"${class_a} per million Class A operations, "
        f"${class_b} per million Class B operations, egress free."
    )


def _r2_free_tier_sentence(rows: list[dict[str, str]], *, today: date) -> str:
    has_r2 = any(row.get("service") == SERVICE_R2 for row in rows)
    allowance = (
        f"{format(R2_FREE_STORAGE_GB_MONTH, 'f')} GB-month storage, "
        f"{R2_FREE_CLASS_A:,} Class A operations, and "
        f"{R2_FREE_CLASS_B:,} Class B operations"
    )
    if not has_r2:
        return (
            "R2 is recorded when the corpus bucket is configured. "
            f"The R2 column is billed spend after the monthly free tier ({allowance})."
        )
    if r2_month_bill_usd(rows, as_of=today) == 0:
        return (
            f"R2 is currently inside the monthly free tier ({allowance}), "
            "so the R2 column and the chart show $0.00."
        )
    return (
        "The R2 column is billed spend above the monthly free tier "
        f"({allowance})."
    )


def daily_spend(rows: list[dict[str, str]], *, today: date) -> list[dict[str, Decimal | date]]:
    """Trailing 14 UTC days ending on ``today``. A missing day is zero."""
    start = today - timedelta(days=_CHART_DAYS - 1)
    series: list[dict[str, Decimal | date]] = []
    for offset in range(_CHART_DAYS):
        day = start + timedelta(days=offset)
        series.append(
            {
                "date": day,
                "llm": Decimal("0"),
                "jev": Decimal("0"),
                "r2": Decimal("0"),
            }
        )
    index = {item["date"]: item for item in series}
    for row in rows:
        day = date.fromisoformat(row["date_utc"])
        bucket = index.get(day)
        if bucket is None:
            continue
        cost = Decimal(row.get("cost_usd") or "0")
        service = row.get("service")
        if service == SERVICE_JEV:
            bucket["jev"] = Decimal(bucket["jev"]) + cost
        elif service == SERVICE_R2:
            bucket["r2"] = Decimal(bucket["r2"]) + cost
        elif service in LLM_SERVICES:
            bucket["llm"] = Decimal(bucket["llm"]) + cost
    return series


def _axis_max(peak: Decimal) -> Decimal:
    if peak <= 0:
        return Decimal("1")
    padded = peak * Decimal("1.25")
    exponent = padded.adjusted()
    base = Decimal(10) ** exponent
    fraction = padded / base
    if fraction <= 1:
        nice = Decimal(1)
    elif fraction <= 2:
        nice = Decimal(2)
    elif fraction <= 5:
        nice = Decimal(5)
    else:
        nice = Decimal(10)
    return nice * base


def _px(value: float) -> str:
    return format(value, ".2f")


def render_daily_spend_svg(rows: list[dict[str, str]], *, today: date | None = None) -> str:
    """Stacked 14-day spend chart. Standard-library SVG, valid XML."""
    moment = today or datetime.now(timezone.utc).date()
    series = daily_spend(rows, today=moment)
    totals = [
        Decimal(item["llm"]) + Decimal(item["jev"]) + Decimal(item["r2"])
        for item in series
    ]
    ymax = _axis_max(max(totals))
    width = 760
    height = 390
    left = 68
    right = 18
    top = 42
    bottom = 86
    plot_width = width - left - right
    plot_height = height - top - bottom
    slot = plot_width / _CHART_DAYS
    bar_width = slot * 0.62

    def y_of(amount: Decimal) -> float:
        return top + plot_height - float(amount / ymax) * plot_height

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
            "role": "img",
        },
    )
    ET.SubElement(svg, "title").text = "Production spend, last 14 UTC days"
    ET.SubElement(svg, "desc").text = (
        "Stacked bars of billed dollars for LLM labeling, Jev, and Cloudflare R2. "
        "A day with no ledger row is zero."
    )
    ET.SubElement(svg, "rect", {"width": str(width), "height": str(height), "fill": "#ffffff"})
    baseline = y_of(Decimal(0))
    for step in range(5):
        tick = ymax * Decimal(step) / Decimal(4)
        y = y_of(tick)
        ET.SubElement(
            svg,
            "line",
            {
                "x1": _px(left),
                "x2": _px(left + plot_width),
                "y1": _px(y),
                "y2": _px(y),
                "stroke": "#e6e6e6",
                "stroke-width": "1",
            },
        )
        label = ET.SubElement(
            svg,
            "text",
            {
                "x": _px(left - 8),
                "y": _px(y + 4),
                "text-anchor": "end",
                "font-family": "ui-sans-serif, system-ui, sans-serif",
                "font-size": "11",
                "fill": "#333333",
            },
        )
        label.text = f"${format_usd(tick)}"
    ET.SubElement(
        svg,
        "line",
        {
            "x1": _px(left),
            "x2": _px(left),
            "y1": _px(top),
            "y2": _px(baseline),
            "stroke": "#333333",
            "stroke-width": "1",
        },
    )
    ET.SubElement(
        svg,
        "line",
        {
            "x1": _px(left),
            "x2": _px(left + plot_width),
            "y1": _px(baseline),
            "y2": _px(baseline),
            "stroke": "#333333",
            "stroke-width": "1",
        },
    )
    for index, item in enumerate(series):
        llm = Decimal(item["llm"])
        jev = Decimal(item["jev"])
        r2 = Decimal(item["r2"])
        total = llm + jev + r2
        x = left + index * slot + (slot - bar_width) / 2
        group = ET.SubElement(
            svg,
            "g",
            {
                "data-date": item["date"].isoformat(),
                "data-llm": format(llm, "f"),
                "data-jev": format(jev, "f"),
                "data-r2": format(r2, "f"),
                "data-total": format(total, "f"),
            },
        )
        cursor = Decimal(0)
        for amount, color in ((llm, _LLM_COLOR), (jev, _JEV_COLOR), (r2, _R2_COLOR)):
            if amount <= 0:
                continue
            y = y_of(cursor + amount)
            rect_height = max(0.0, y_of(cursor) - y)
            ET.SubElement(
                group,
                "rect",
                {
                    "x": _px(x),
                    "y": _px(y),
                    "width": _px(bar_width),
                    "height": _px(rect_height),
                    "fill": color,
                },
            )
            cursor += amount
        total_text = ET.SubElement(
            group,
            "text",
            {
                "x": _px(x + bar_width / 2),
                "y": _px(y_of(total) - 4),
                "text-anchor": "middle",
                "font-family": "ui-sans-serif, system-ui, sans-serif",
                "font-size": "9",
                "fill": "#333333",
            },
        )
        total_text.text = format_usd(total)
        day_label = ET.SubElement(
            svg,
            "text",
            {
                "x": _px(x + bar_width / 2),
                "y": _px(baseline + 16),
                "text-anchor": "middle",
                "font-family": "ui-sans-serif, system-ui, sans-serif",
                "font-size": "10",
                "fill": "#333333",
            },
        )
        day_label.text = item["date"].strftime("%m-%d")
    axis_name = ET.SubElement(
        svg,
        "text",
        {
            "x": _px(left + plot_width / 2),
            "y": _px(baseline + 34),
            "text-anchor": "middle",
            "font-family": "ui-sans-serif, system-ui, sans-serif",
            "font-size": "12",
            "fill": "#333333",
        },
    )
    axis_name.text = "UTC day"
    legend_y = height - 22
    legend_x = left
    for color, name in ((_LLM_COLOR, "LLM labeling"), (_JEV_COLOR, "Jev"), (_R2_COLOR, "R2")):
        ET.SubElement(
            svg,
            "rect",
            {
                "x": _px(legend_x),
                "y": _px(legend_y - 10),
                "width": "12",
                "height": "12",
                "fill": color,
            },
        )
        legend = ET.SubElement(
            svg,
            "text",
            {
                "x": _px(legend_x + 16),
                "y": _px(legend_y),
                "font-family": "ui-sans-serif, system-ui, sans-serif",
                "font-size": "12",
                "fill": "#333333",
            },
        )
        legend.text = name
        legend_x += 130
    body = ET.tostring(svg, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def write_daily_spend_svg(path: Path, rows: list[dict[str, str]], *, today: date | None = None) -> str:
    text = render_daily_spend_svg(rows, today=today)
    _atomic_write(path, text)
    return text


def render_readme(rows: list[dict[str, str]], *, today: date | None = None) -> str:
    moment = today or datetime.now(timezone.utc).date()
    weeks, recent = weekly_rollup(rows, today=moment)
    price = format(JEV_USD_PER_MILLION_INPUT_TOKENS, "f")
    week_header = [
        "ISO week",
        "runs",
        "LLM $",
        "Jev $",
        "R2 $",
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
        "Paid calls from each successful daily pipeline run. One row per service and model is appended to `costs/ledger.csv` on the `data-snapshot` branch. This page and `daily_spend_14d.svg` are regenerated from that ledger. They are not in `public/` and are not deployed to GitHub Pages.",
        "",
        f"DeepInfra labeling dollars are the provider's `usage.estimated_cost` on each response. Jev dollars are computed, not reported by the API: input tokens × ${price} per 1,000,000 (published price dated {JEV_PRICE_AS_OF}). Jev output tokens are free. {_r2_pricing_sentence()} {_r2_free_tier_sentence(rows, today=moment)} Local embeddings, GitHub Actions, and Bluesky reads are not listed.",
        "",
        "Posts are the `total_posts` figure in that run's `data.json` (claims that entered clustering). Planets are every planet written into that file, including section solar systems. Both are counted once per run, even when the run has a DeepInfra row, a Jev row, and an R2 row. `$ per 1,000 posts` is total dollars ÷ posts × 1,000. `$ per planet` is total dollars ÷ planets published. The table uses billed `cost_usd`. For R2 that is spend above the monthly free tier. `list_price_usd` is the list price of that row.",
        "",
        "## Last 14 days",
        "",
        "[![Trailing 14 UTC days of billed production spend, stacked as LLM labeling, Jev, and Cloudflare R2. A day with no run is zero.](daily_spend_14d.svg)](#by-iso-week)",
        "",
        "One bar per UTC day. The label on a bar is that day's billed total. The chart is rewritten on this branch each run. It links to the weekly table below.",
        "",
        "## By ISO week",
        "",
    ]
    if not weeks:
        lines.append("No paid calls recorded yet.")
        lines.append("")
    else:
        lines.append(_table_row(week_header))
        lines.append(_table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]))
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
            _table_row(["---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]),
            _table_row(_totals_cells(recent)),
            "",
        ]
    )
    return "\n".join(lines)


def write_readme(path: Path, rows: list[dict[str, str]], *, today: date | None = None) -> str:
    text = render_readme(rows, today=today)
    _atomic_write(path, text)
    return text


def load_run_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"rows": payload}
    if not isinstance(payload, dict):
        raise CostLedgerError(f"{path} does not contain a cost run object")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise CostLedgerError(f"{path} does not contain a rows list")
    return payload


def load_run_rows(path: Path) -> list[dict]:
    return list(load_run_payload(path)["rows"])


def _identity_from_payload(payload: dict) -> dict[str, str]:
    needed = ("run_id", "run_started_utc", "date_utc", "trigger")
    if all(str(payload.get(key) or "").strip() for key in needed):
        return {key: str(payload[key]) for key in needed}
    return run_identity()


def _publish_cost_views(readme_path: Path, rows: list[dict[str, str]], *, today: date) -> None:
    write_readme(readme_path, rows, today=today)
    write_daily_spend_svg(readme_path.parent / CHART_PATH.name, rows, today=today)


def append_run_files(
    run_path: Path,
    ledger_path: Path,
    readme_path: Path,
    *,
    r2_usage_path: Path | None = None,
    today: date | None = None,
) -> int:
    """Append one run and regenerate the table and chart. Returns 0 on success."""
    try:
        payload = load_run_payload(run_path)
        new_rows = list(payload["rows"])
        identity = _identity_from_payload(payload)
        chart_day = date.fromisoformat(identity["date_utc"])
        if today is not None:
            chart_day = today
        prior = read_ledger(ledger_path) if ledger_path.exists() else []
        if r2_usage_path is not None and Path(r2_usage_path).exists():
            usage = load_r2_usage(Path(r2_usage_path))
            posts = int(payload.get("posts_processed") or 0)
            planets = int(payload.get("planets_published") or 0)
            if new_rows:
                posts = int(new_rows[0].get("posts_processed") or posts)
                planets = int(new_rows[0].get("planets_published") or planets)
            r2_row = r2_ledger_row(
                prior,
                identity=identity,
                posts_processed=posts,
                planets_published=planets,
                usage=usage,
            )
            if r2_row is not None:
                new_rows.append(r2_row)
        if not new_rows:
            if prior:
                _publish_cost_views(readme_path, prior, today=chart_day)
                print("No new paid calls; refreshed the cost table and chart.")
                return 0
            print("No paid calls in this run; cost ledger left unchanged.")
            return 0
        combined = append_ledger(ledger_path, new_rows)
        _publish_cost_views(readme_path, combined, today=chart_day)
    except Exception as exc:
        warn(f"Cost ledger update failed: {exc}")
        return 1
    print(f"Appended {len(new_rows)} cost row(s) to {ledger_path}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append a pipeline cost run to the data-snapshot ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    append = sub.add_parser("append", help="Append costs/ledger.csv and regenerate the weekly table and chart")
    append.add_argument("--run", type=Path, required=True, help="cost_run.json written by the pipeline")
    append.add_argument("--ledger", type=Path, required=True)
    append.add_argument("--readme", type=Path, required=True)
    append.add_argument("--r2-usage", type=Path, default=None, help="r2_usage.json written by the R2 client")
    args = parser.parse_args(argv)
    if args.command == "append":
        return append_run_files(args.run, args.ledger, args.readme, r2_usage_path=args.r2_usage)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
