"""Precision and recall of the duplicate threshold on the held-out labels.

The threshold is tuned on two-thirds of docs/evidence/275/oct19-pairs.csv
(seed 273). This script reports agreement only on the held-out third plus
Michael's spot-check pairs. It does not score the tune rows.

Exit 0 when the sample is not in the tree yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.duplicate_rate import LABELED_SAMPLE, SPOT_CHECK_SAMPLE, duplicate_rates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out agreement for the duplicate-rate threshold")
    parser.add_argument("data", nargs="?", default="public/data.json")
    parser.add_argument("--labeled", default=str(LABELED_SAMPLE))
    parser.add_argument("--spot-checks", default=str(SPOT_CHECK_SAMPLE))
    parser.add_argument("--floor", type=int, default=0)
    args = parser.parse_args(argv)
    labeled = Path(args.labeled)
    if not labeled.is_file():
        print(
            f"No labeled sample at {labeled}. Agreement is not computed. "
            "The daily rate does not grade itself."
        )
        return 0
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    report = duplicate_rates(
        payload,
        labeled_path=labeled,
        spot_path=Path(args.spot_checks),
        floor=args.floor,
    )
    agreement = report["agreement"]
    print(
        "DUPLICATE_AGREEMENT "
        f"weighted={agreement.get('weighted')} "
        f"precision={agreement.get('precision')} recall={agreement.get('recall')} "
        f"tuned_on={agreement.get('tuned_on')} holdout={agreement.get('holdout')} "
        f"spot_checks={agreement.get('spot_checks')} scored_on={agreement.get('scored_on')} "
        f"title_min={agreement.get('title_min')} centroid_min={agreement.get('centroid_min')} "
        f"seed={agreement.get('seed')}"
    )
    for band in agreement.get("bands") or []:
        print(
            f"BAND {band.get('band')} share={band.get('share')} "
            f"precision={band.get('precision')} recall={band.get('recall')} "
            f"matched={band.get('matched')}"
        )
    print(agreement.get("note") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
