"""Score one fixed post list twice with a mocked Jev. No network and no Jetstream.

Run 2 reopens the database. A third pass opens an empty database and uses only
the cache file, which is the fresh-runner case.

    python scripts/jev_cache_replay.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.jev_cache import replay_same_posts


def main() -> None:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/jev-cache-replay")
    report = replay_same_posts(directory)
    print(f"posts {report['posts']}")
    print(f"run 1  {report['run1']['line']}  http_calls {report['run1']['http_calls']}")
    print(f"run 2  {report['run2']['line']}  http_calls {report['run2']['http_calls']}")
    print(f"file   {report['file_only']['line']}  http_calls {report['file_only']['http_calls']}")
    run2 = report["run2"]
    if run2["hits"] != report["posts"] or run2["paid_calls"] != 0 or run2["http_calls"] != 0:
        raise SystemExit("run 2 did not reuse the cache")
    if report["file_only"]["paid_calls"] != 0 or report["file_only"]["hits"] != report["posts"]:
        raise SystemExit("cache file did not warm a fresh database")


if __name__ == "__main__":
    main()
