"""Pytest defaults: paid API calls stay off unless a test opts in."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _paid_calls_off_by_default(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_ALLOW_PAID", raising=False)
