"""Opt-in stored-row deletion for ingest filter reasons (#224 / #228 / #238).

``PERSPECTIVERSE_PURGE_STORED_REASONS`` is a comma-separated list of purge keys.
Valid keys: ``chitchat``, ``link_only``, ``language``, ``weather_bot``. The
``chitchat`` key covers every ``chitchat:*`` ingest block reason.

Cached Jev spam and ingest reasons outside those keys keep main behavior (always
purge when ingest would refuse). Listed keys purge stored rows only when named
in the env; with the env unset, only the always-on paths run.
"""

from __future__ import annotations

import os

PURGE_STORED_REASONS_ENV = "PERSPECTIVERSE_PURGE_STORED_REASONS"

VALID_PURGE_KEYS = frozenset({"chitchat", "link_only", "language", "weather_bot"})


def purge_stored_reasons_list() -> frozenset[str]:
    raw = os.environ.get(PURGE_STORED_REASONS_ENV)
    if raw is None or not str(raw).strip():
        return frozenset()
    return frozenset(
        part.strip()
        for part in str(raw).split(",")
        if part.strip() in VALID_PURGE_KEYS
    )


def stored_purge_key_for_ingest_reason(reason: str) -> str | None:
    """Map an ``ingest_block_reason`` to an env purge key, or None if always-on."""
    if reason.startswith("chitchat:"):
        return "chitchat"
    if reason in VALID_PURGE_KEYS:
        return reason
    return None


def should_purge_stored_for_ingest_reason(reason: str) -> bool:
    """Whether an existing row with this ``ingest_block_reason`` may be dropped."""
    key = stored_purge_key_for_ingest_reason(reason)
    if key is None:
        return True
    return key in purge_stored_reasons_list()
