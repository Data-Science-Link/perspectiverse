"""Which labeled rows belong to each duplicate kind.

The kind counts do not import this module. These titles are the label
class for recall. They are not the feature the counts threshold.
"""

from __future__ import annotations

GREETING_TITLES = frozenset(
    {
        "good day",
        "good morning",
        "great day",
        "hope for the day",
        "wonderful day",
        "great time",
        "glad returns",
        "happy sunday",
        "good sunday",
    }
)

# Rebuilt spot-check sheet. Michael's column there is blank.
PLANET_SPOT_IDS = frozenset(
    {"p006", "p060", "p002", "p003", "p004", "p001", "p007", "p009", "p011", "p015"}
)
FACE_SPOT_IDS = frozenset(
    {"c001", "c003", "c005", "c010", "c018", "c020", "c022", "c023", "c026", "c027"}
)


def _normalize(value: str) -> str:
    import re

    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    while words and words[-1].isdigit():
        words.pop()
    return " ".join(words)


def greeting_pair_ids(rows: list[dict[str, str]]) -> set[str]:
    """Planet yes rows whose titles are both in the pleasantry label class."""
    found: set[str] = set()
    for row in rows:
        if str(row.get("level") or "") != "planet":
            continue
        if str(row.get("is_duplicate") or "").strip().lower() != "yes":
            continue
        left = _normalize(str(row.get("title_a") or ""))
        right = _normalize(str(row.get("title_b") or ""))
        if left in GREETING_TITLES and right in GREETING_TITLES:
            found.add(str(row.get("pair_id") or ""))
    return found
