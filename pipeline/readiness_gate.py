"""Hard gates for the #87 Jetstream readiness workflow (no production publish).

When ``PERSPECTIVERSE_READINESS_GATE`` is on:

- Preflight verifies ingest supply **before any paid call** (Jev or labeling).
- Top-up rounds that chase a claim target are disabled in ``live.py``.
- ``record_attempt`` aborts mid-run if Jev + labeling spend would exceed the cap.
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal

from pipeline.costs import (
    LLM_SERVICES,
    SERVICE_JEV,
    Attempt,
    format_usd,
    get_meter,
    jev_cost_usd,
)
from pipeline.data_sources import extract_bluesky
from pipeline.jetstream_ingest import claims_available_without_topup, is_configured

SPEND_CAP_USD = Decimal("0.50")
# Conservative search-only yield when Jetstream is absent (#27).
_SEARCH_CLAIM_YIELD = Decimal("0.22")

ENV_GATE = "PERSPECTIVERSE_READINESS_GATE"
ENV_SPEND_CAP = "PERSPECTIVERSE_READINESS_SPEND_CAP"


class ReadinessAbort(RuntimeError):
    """Preflight failed before paid work."""

    exit_code = 10


class SpendCapExceeded(ReadinessAbort):
    """Running Jev + labeling spend hit the readiness cap."""

    exit_code = 13

    def __init__(self, message: str, *, spent_usd: Decimal) -> None:
        super().__init__(message)
        self.spent_usd = spent_usd


def gate_enabled() -> bool:
    raw = (os.getenv(ENV_GATE) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def spend_cap_usd() -> Decimal:
    override = (os.getenv(ENV_SPEND_CAP) or "").strip()
    if override:
        return Decimal(override)
    return SPEND_CAP_USD


def _neutral_query_count(settings: dict) -> int:
    neutral = [item for item in (settings.get("neutral_queries") or []) if item]
    return max(len(neutral), 1)


def search_claim_ceiling(sample_size: int, settings: dict) -> int:
    """Upper bound on claims neutral search can supply without top-up."""
    queries = _neutral_query_count(settings)
    pages = extract_bluesky.page_budget(sample_size, queries)
    raw_posts = pages * queries * 100
    return int(Decimal(raw_posts) * _SEARCH_CLAIM_YIELD)


def verify_supply_before_paid(*, target: int, settings: dict) -> None:
    """Raise ``ReadinessAbort`` when the run cannot fill ``target`` without top-up."""
    if is_configured():
        available = claims_available_without_topup(target)
        if available < target:
            raise ReadinessAbort(
                f"Jetstream ingest is configured but reports only {available} claims "
                f"available without top-up; need {target}."
            )
        return

    ceiling = search_claim_ceiling(target, settings)
    if ceiling < target:
        raise ReadinessAbort(
            "Jetstream ingest is not available on this commit (#27 required). "
            f"Neutral search can supply at most ~{ceiling} claims without top-up; "
            f"target is {target}. Refusing to start paid work."
        )


def metered_jev_labeling_usd(attempts: tuple[Attempt, ...] | None = None) -> Decimal:
    total = Decimal("0")
    for attempt in attempts if attempts is not None else get_meter().attempts():
        if attempt.service == SERVICE_JEV or attempt.service in LLM_SERVICES:
            total += attempt.cost_usd
    return total


def projected_attempt_usd(attempt: Attempt) -> Decimal:
    if attempt.service == SERVICE_JEV:
        return jev_cost_usd(attempt.input_tokens)
    if attempt.service in LLM_SERVICES:
        return attempt.cost_usd if attempt.cost_usd > 0 else Decimal("0")
    return Decimal("0")


def enforce_before_recording(attempt: Attempt) -> None:
    """Called from ``record_attempt`` before the meter accepts a paid call."""
    if not gate_enabled():
        return
    cap = spend_cap_usd()
    spent = metered_jev_labeling_usd()
    add = projected_attempt_usd(attempt)
    if spent + add > cap:
        raise SpendCapExceeded(
            f"Readiness spend cap {format_usd(cap)}: already {format_usd(spent)}, "
            f"next {attempt.service} call would add {format_usd(add)}.",
            spent_usd=spent,
        )


def projected_steady_state_usd(sample_size: int) -> Decimal:
    """Jev + labeling estimate for one day at ``sample_size`` (0% cache)."""
    slots = Decimal(max(sample_size, 1)) / Decimal(7)
    from pipeline.costs import JEV_USD_PER_MILLION_INPUT_TOKENS

    jev = slots * Decimal("663") * JEV_USD_PER_MILLION_INPUT_TOKENS / Decimal(1_000_000)
    return jev + Decimal("0.12")


def preflight_cli(sample_size: int, settings: dict) -> int:
    verify_supply_before_paid(target=sample_size, settings=settings)
    cap = spend_cap_usd()
    projected = projected_steady_state_usd(sample_size)
    if projected > cap:
        raise ReadinessAbort(
            f"Projected steady-state spend {format_usd(projected)} exceeds cap {format_usd(cap)}."
        )
    print(
        f"Readiness preflight OK: target={sample_size}, "
        f"jetstream={'yes' if is_configured() else 'no'}, "
        f"projected≈{format_usd(projected)}, cap={format_usd(cap)}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    from pipeline.settings import load_dotenv, load_settings

    load_dotenv()
    parser = argparse.ArgumentParser(description="Jetstream readiness hard preflight (#87)")
    parser.add_argument("--sample-size", type=int, default=None)
    args = parser.parse_args(argv)
    if not gate_enabled():
        print("Readiness gate env is off; nothing to verify.", file=sys.stderr)
        return 0
    settings = load_settings()
    target = int(args.sample_size or settings.get("sample_size") or 10_000)
    try:
        return preflight_cli(target, settings)
    except ReadinessAbort as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
