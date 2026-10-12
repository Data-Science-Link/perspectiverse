#!/usr/bin/env python3
"""Postflight checks for the #87 Jetstream readiness workflow.

Hard preflight lives in ``python -m pipeline.readiness_gate`` (requires
``PERSPECTIVERSE_READINESS_GATE=1``).
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
from pipeline.readiness_gate import SPEND_CAP_USD  # noqa: E402


def _sum_cost_rows(rows: list[dict]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    jev = deep = other = Decimal(0)
    for row in rows:
        service = str(row.get("service") or "")
        amount = Decimal(str(row.get("cost_usd") or "0"))
        if service == SERVICE_JEV:
            jev += amount
        elif service == SERVICE_DEEPINFRA:
            deep += amount
        else:
            other += amount
    return jev, deep, other, jev + deep + other


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
    parser = argparse.ArgumentParser(description="Jetstream readiness postflight (#87)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    post = sub.add_parser("postflight", help="Validate cost_run.json after the pipeline")
    post.add_argument("--cost-run", type=Path, required=True)
    post.set_defaults(func=cmd_postflight)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
