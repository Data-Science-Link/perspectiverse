#!/usr/bin/env python3
"""Exit 0 when no Daily Discourse Pipeline run is queued or in progress.

Paid labeling tests call this before they spend the shared DeepInfra key.
Exit 2 means wait. Exit 3 means the GitHub API check failed: do not start.

    python scripts/check_pipeline_overlap.py
    python -m pipeline.pipeline_overlap
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.pipeline_overlap import main

if __name__ == "__main__":
    raise SystemExit(main())
