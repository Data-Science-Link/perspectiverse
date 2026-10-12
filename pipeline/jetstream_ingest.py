"""Jetstream firehose ingest (#27).

The readiness gate imports this module. Until #27 lands, ``is_configured`` stays
false and paid readiness runs must not start.
"""

from __future__ import annotations


def is_configured() -> bool:
    """True when this deployment can ingest Jetstream at the target volume."""
    return False


def claims_available_without_topup(target: int) -> int:
    """Claims one run can retain without top-up rounds chasing ``target``.

    When Jetstream is configured, the ingest path is responsible for filling
    the window. Until then this returns 0.
    """
    if not is_configured():
        return 0
    return max(0, int(target))
