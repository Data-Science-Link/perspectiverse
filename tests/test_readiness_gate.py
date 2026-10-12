"""Jetstream readiness hard gates (#87 / PR #145)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.costs import SERVICE_JEV, get_meter, record_jev_attempt, reset_meter
from pipeline.readiness_gate import (
    ReadinessAbort,
    SpendCapExceeded,
    metered_jev_labeling_usd,
    verify_supply_before_paid,
)
from pipeline.settings import load_settings


def _jev_payload(input_tokens: int) -> dict:
    return {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": input_tokens, "output_tokens": 0},
    }


def test_missing_jetstream_supply_aborts_at_zero_spend(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_READINESS_GATE", "1")
    reset_meter()
    settings = load_settings()
    settings["sample_size"] = 50_000
    with pytest.raises(ReadinessAbort, match="#27"):
        verify_supply_before_paid(target=50_000, settings=settings)
    assert metered_jev_labeling_usd() == Decimal("0")
    assert not get_meter().attempts()


def test_spend_cap_stops_before_second_paid_jev_call(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_READINESS_GATE", "1")
    monkeypatch.setenv("PERSPECTIVERSE_READINESS_SPEND_CAP", "0.01")
    reset_meter()
    record_jev_attempt(requested_model="jev-1.13.0", payload=_jev_payload(150_000), status="success")
    assert len(get_meter().attempts()) == 1
    first_spend = metered_jev_labeling_usd()
    assert first_spend > Decimal("0")
    assert first_spend < Decimal("0.01")
    with pytest.raises(SpendCapExceeded) as caught:
        record_jev_attempt(requested_model="jev-1.13.0", payload=_jev_payload(150_000), status="success")
    assert caught.value.spent_usd == first_spend
    assert len(get_meter().attempts()) == 1
    assert get_meter().attempts()[0].service == SERVICE_JEV


def test_readiness_gate_cli_exits_before_paid(monkeypatch):
    monkeypatch.setenv("PERSPECTIVERSE_READINESS_GATE", "1")
    monkeypatch.setenv("PERSPECTIVERSE_SAMPLE_SIZE", "50000")
    reset_meter()
    from pipeline.readiness_gate import main

    code = main(["--sample-size", "50000"])
    assert code == ReadinessAbort.exit_code
    assert metered_jev_labeling_usd() == Decimal("0")
