"""Perspectiverse pipeline entry point.

--demo writes the synthetic universe. --live extracts, clusters, labels, and
writes public/data.json. With no flag, the command stays on --demo so the
existing local workflow keeps working.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_path() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main(argv: list[str] | None = None) -> None:
    _ensure_path()
    parser = argparse.ArgumentParser(description="Run the Perspectiverse pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="Write the synthetic demo universe")
    mode.add_argument("--live", action="store_true", help="Extract, cluster, label, and write a live snapshot")
    parser.add_argument("--fixture", type=Path, default=None, help="JSON posts used instead of Bluesky (requires --live)")
    parser.add_argument("--output", type=Path, default=None, help="Destination data.json path")
    parser.add_argument("--config", type=Path, default=None, help="YAML settings file")
    parser.add_argument("--db", type=Path, default=None, help="SQLite path (default pipeline/data/posts.db)")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        metavar="TEXT",
        help="Override Bluesky search queries. Repeat to stack terms. Requires --live; ignored with --fixture.",
    )
    args = parser.parse_args(argv)

    if args.fixture and not args.live:
        parser.error("--fixture requires --live")
    if args.queries and not args.live:
        parser.error("--query requires --live")

    if args.live:
        from pipeline.live import run_live

        print("Starting Perspectiverse pipeline (live mode)...")
        run_live(
            fixture=args.fixture,
            output=args.output,
            config=args.config,
            db_path=args.db,
            queries=args.queries,
        )
        print("Pipeline complete.")
        return

    from pipeline.generate_demo_data import write_demo_data

    if not args.demo:
        print("No mode flag given; defaulting to --demo.")
    print("Starting Perspectiverse pipeline (demo mode)...")
    output = write_demo_data(args.output)
    print(f"Wrote {output}")
    print("Pipeline complete. public/data.json is ready for the observatory.")


if __name__ == "__main__":
    main()
