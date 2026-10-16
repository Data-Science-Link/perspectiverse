#!/usr/bin/env python3
"""Count planets that would keep a label across published editions.

Reads ``public/data.json`` from git. No paid calls. The default editions are
the last data-snapshot commit of each UTC day from 2026-10-13 through
2026-10-16.

Same planet and changed are defined in ``pipeline.planet_reuse``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.costs import format_usd, project_measured_daily_usd, reuse_daily_usd
from pipeline.planet_reuse import match_planets, planets_from_payload, share_changed

# Last public/data.json on data-snapshot for that UTC date.
EDITIONS = (
    ("2026-10-13", "8a4ad56"),
    ("2026-10-14", "6f2e23a"),
    ("2026-10-15", "c1c5b20"),
    ("2026-10-16", "86cae83"),
)
THRESHOLDS = (Decimal("0.5"), Decimal("0.8"))
# Oct 16 scheduled run, planets grown to 300. Same inputs as the projection.
OCT_16 = {
    "measured_posts": 9985,
    "jev_usd": Decimal("0.03808182"),
    "label_usd": Decimal("0.11712596"),
    "jev_calls": 1362,
    "measured_planets": 110,
}


def load_payload(revision: str) -> dict:
    raw = subprocess.check_output(["git", "show", f"{revision}:public/data.json"])
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{revision} data.json is not an object")
    return payload


def main() -> int:
    loaded = [(day, revision, planets_from_payload(load_payload(revision))) for day, revision in EDITIONS]
    projected = project_measured_daily_usd(**OCT_16)
    grown = next(item["label_usd"] for item in projected["assumptions"] if item["id"] == "planets")
    jev = projected["steady_jev_usd"]
    print(
        f"Steady Jev ${format_usd(jev)}. "
        f"300-planet labeling ${format_usd(grown)}. "
        "Option 1 and option 1+3 are this steady day."
    )
    for (yesterday_day, yesterday_rev, yesterday), (today_day, today_rev, today) in zip(loaded, loaded[1:]):
        matches = match_planets(today, yesterday)
        print(
            f"{yesterday_day} {yesterday_rev} -> {today_day} {today_rev}: "
            f"yesterday {len(yesterday)} planets, today {len(today)}"
        )
        for threshold in THRESHOLDS:
            counts = share_changed(matches, threshold)
            priced = reuse_daily_usd(
                jev,
                grown,
                changed=int(counts["changed"]),
                planets=int(counts["planets"]),
            )
            print(
                f"  threshold {threshold}: changed {counts['changed']}/{counts['planets']} "
                f"share {format_usd(counts['share'])} "
                f"option 1 ${format_usd(priced['option_1_usd'])}/day "
                f"option 1+3 ${format_usd(priced['option_1_plus_3_usd'])}/day"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
