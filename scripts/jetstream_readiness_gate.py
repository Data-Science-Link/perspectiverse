#!/usr/bin/env python3
"""Preflight and postflight checks for the #87 Jetstream readiness workflow.

Does not call paid APIs except reading cost_run.json after the pipeline finishes.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.costs import SERVICE_DEEPINFRA, SERVICE_JEV, format_usd  # noqa: E402

SPEND_CAP_USD = Decimal("0.50")
# #87 planning: ~663 tokens/call, ~1 call per daily claim slot at steady state.
JEV_TOKENS_PER_CALL = Decimal("663")
JEV_USD_PER_M = Decimal("0.042")
LABELING_USD_DAY = Decimal("0.12")


def projected_daily_usd(sample_size: int, *, cache_hit_rate: Decimal = Decimal("0")) -> Decimal:
    """Conservative preflight projection for a window size (0% cache by default)."""
    slots = Decimal(max(sample_size, 1)) / Decimal(7)
    jev = slots * JEV_TOKENS_PER_CALL * JEV_USD_PER_M / Decimal(1_000_000)
    jev *= Decimal(1) - cache_hit_rate
    return jev + LABELING_USD_DAY


def _sum_cost_rows(rows: list[dict]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    jev = deep = stance = Decimal(0)
    for row in rows:
        service = str(row.get("service") or "")
        amount = Decimal(str(row.get("cost_usd") or "0"))
        if service == SERVICE_JEV:
            jev += amount
        elif service == SERVICE_DEEPINFRA:
            deep += amount
        else:
            stance += amount
    return jev, deep, stance, jev + deep + stance


def cmd_preflight(args: argparse.Namespace) -> int:
    sample = int(args.sample_size)
    projected = projected_daily_usd(sample)
    print(f"Preflight sample_size={sample}: projected daily spend ≈ {format_usd(projected)} (cap {format_usd(SPEND_CAP_USD)}).")
    if projected > SPEND_CAP_USD:
        print(
            f"ABORT: projected {format_usd(projected)} exceeds cap {format_usd(SPEND_CAP_USD)}.",
            file=sys.stderr,
        )
        return 11
    return 0


def cmd_postflight(args: argparse.Namespace) -> int:
    path = Path(args.cost_run)
    if not path.is_file():
        print(f"Missing cost run file: {path}", file=sys.stderr)
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    jev, deep, other, total = _sum_cost_rows(rows)
    print(f"Postflight total {format_usd(total)} (Jev {format_usd(jev)}, labeling {format_usd(deep)}, other {format_usd(other)}).")
    if total > SPEND_CAP_USD:
        print(f"FAIL: spend {format_usd(total)} exceeded cap {format_usd(SPEND_CAP_USD)}.", file=sys.stderr)
        return 12
    cache_hits = int(payload.get("jev_cache_hits") or 0)
    dedup = int(payload.get("jev_dedup_skips") or 0)
    pre = payload.get("jev_prefilter_skips") or {}
    pre_total = sum(int(pre.get(k) or 0) for k in ("short", "language", "link", "duplicate"))
    print(
        f"Jev filters: true cache hits={cache_hits}, dedup skips={dedup}, pre-filter skips={pre_total}."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Jetstream readiness spend gates (#87)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("preflight", help="Abort before paid work if projection exceeds cap")
    pre.add_argument("--sample-size", type=int, default=50_000)
    pre.set_defaults(func=cmd_preflight)
    post = sub.add_parser("postflight", help="Validate cost_run.json after the pipeline")
    post.add_argument("--cost-run", type=Path, required=True)
    post.set_defaults(func=cmd_postflight)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
