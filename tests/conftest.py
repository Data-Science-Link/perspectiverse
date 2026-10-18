"""Pytest defaults: paid API calls stay off unless a test opts in."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _paid_calls_off_and_track_blocked(request, monkeypatch):
    """Clear the opt-in flag; fail the test if a paid call was attempted and swallowed."""
    monkeypatch.delenv("PERSPECTIVERSE_ALLOW_PAID", raising=False)
    sites: list[str] = []
    import pipeline.spend_cap as spend_cap

    original = spend_cap.require_paid_opt_in

    def tracking(where: str) -> None:
        try:
            original(where)
        except spend_cap.PaidCallsBlocked:
            sites.append(where)
            raise

    monkeypatch.setattr(spend_cap, "require_paid_opt_in", tracking)
    yield
    if sites and "expect_paid_blocked" not in request.node.keywords:
        pytest.fail(
            "PaidCallsBlocked was raised during the test (possibly swallowed by a caller): "
            + ", ".join(sites)
        )
