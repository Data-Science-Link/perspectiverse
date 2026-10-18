"""Opt-in guard for paid labeling and Jev calls (#246)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.costs import SERVICE_DEEPINFRA, SERVICE_JEV, get_meter, record_attempt, reset_meter
from pipeline.jev import _post_systemone
from pipeline.label import _openai_generate
from pipeline.spend_cap import (
    ENV_ALLOW_PAID,
    PaidCallsBlocked,
    guard_before_paid_call,
    paid_calls_allowed,
    require_paid_opt_in,
)


def test_paid_calls_allowed_truthy_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(ENV_ALLOW_PAID, value)
        assert paid_calls_allowed() is True


def test_paid_calls_blocked_when_unset(monkeypatch):
    monkeypatch.delenv(ENV_ALLOW_PAID, raising=False)
    assert paid_calls_allowed() is False
    with pytest.raises(PaidCallsBlocked):
        require_paid_opt_in("unit test")


def test_guard_before_paid_call_requires_opt_in(monkeypatch):
    monkeypatch.delenv(ENV_ALLOW_PAID, raising=False)
    with pytest.raises(PaidCallsBlocked):
        guard_before_paid_call("Jev")


def test_metering_paid_service_requires_opt_in(monkeypatch):
    monkeypatch.delenv(ENV_ALLOW_PAID, raising=False)
    reset_meter()
    with pytest.raises(PaidCallsBlocked):
        record_attempt(
            service=SERVICE_JEV,
            model="jev-test",
            input_tokens=1,
            output_tokens=0,
            cost_usd=Decimal("0"),
            cost_source="computed",
            status="success",
        )
    assert len(get_meter().attempts()) == 0


def test_openai_generate_raises_without_opt_in(monkeypatch):
    monkeypatch.delenv(ENV_ALLOW_PAID, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unit-test.deepinfra.com/v1")

    def fake(url, *, timeout, data=None, headers=None):
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    monkeypatch.setattr("pipeline.label.read_json", fake)
    with pytest.raises(PaidCallsBlocked):
        _openai_generate("hello", "model")


def test_post_systemone_raises_without_opt_in(monkeypatch):
    monkeypatch.delenv(ENV_ALLOW_PAID, raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    def fake(url, **kwargs):
        return {"model": "jev-test", "answers": {}}

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    with pytest.raises(PaidCallsBlocked):
        _post_systemone({"questions": {}, "state": "hello"})


def test_paid_guard_allows_when_opted_in(monkeypatch):
    monkeypatch.setenv(ENV_ALLOW_PAID, "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    reset_meter()

    def fake(url, **kwargs):
        return {"model": "jev-test", "usage": {"input_tokens": 0, "output_tokens": 0}, "answers": {}}

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    _post_systemone({"questions": {}, "state": "hello"})
    assert len(get_meter().attempts()) == 1
    assert get_meter().attempts()[0].service == SERVICE_JEV


def test_deepinfra_metering_with_opt_in(monkeypatch):
    monkeypatch.setenv(ENV_ALLOW_PAID, "1")
    reset_meter()
    record_attempt(
        service=SERVICE_DEEPINFRA,
        model="unit",
        input_tokens=1,
        output_tokens=1,
        cost_usd=Decimal("0"),
        cost_source="reported",
        status="success",
    )
    assert len(get_meter().attempts()) == 1
