"""Perspectiverse pipeline entry point.

--live rotates the retained Bluesky corpus, clusters, labels, and writes
public/data.json. --relabel skips Bluesky and rebuilds names from the saved
window. --demo still writes the synthetic universe. With no flag, the
command stays on --live.
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
    from pipeline.settings import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Perspectiverse pipeline")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="Write the synthetic demo universe")
    mode.add_argument("--live", action="store_true", help="Extract, cluster, label, and write a live snapshot")
    parser.add_argument("--fixture", type=Path, default=None, help="JSON posts used instead of Bluesky (requires --live)")
    parser.add_argument(
        "--relabel",
        action="store_true",
        help="Rebuild planet names and steelmans from the retained SQLite corpus without fetching Bluesky",
    )
    parser.add_argument("--output", type=Path, default=None, help="Destination data.json path")
    parser.add_argument("--config", type=Path, default=None, help="YAML settings file")
    parser.add_argument("--db", type=Path, default=None, help="SQLite path (default pipeline/data/live_corpus.db)")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        metavar="TEXT",
        help="Override Bluesky search queries. Repeat to stack terms. Requires --live; ignored with --fixture.",
    )
    args = parser.parse_args(argv)

    if args.fixture and args.demo:
        parser.error("--fixture requires live mode")
    if args.queries and args.demo:
        parser.error("--query requires live mode")
    if args.relabel and args.demo:
        parser.error("--relabel requires live mode")
    if args.relabel and args.fixture:
        parser.error("--relabel cannot be combined with --fixture")
    if args.relabel and args.queries:
        parser.error("--relabel cannot be combined with --query")

    if args.demo:
        from pipeline.generate_demo_data import write_demo_data

        print("Starting Perspectiverse pipeline (demo mode)...")
        output = write_demo_data(args.output)
        print(f"Wrote {output}")
        print("Pipeline complete. public/data.json is ready for the observatory.")
        return

    from pipeline.live import run_live

    if not args.live:
        print("No mode flag given; defaulting to --live.")
    print("Starting Perspectiverse pipeline (live mode)...")
    run_live(
        fixture=args.fixture,
        output=args.output,
        config=args.config,
        db_path=args.db,
        queries=args.queries,
        relabel=args.relabel,
    )
    print("Pipeline complete.")


if __name__ == "__main__":
    main()
