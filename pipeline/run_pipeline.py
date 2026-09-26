"""Perspectiverse pipeline entry point.

The live Bluesky → BERTopic → Ollama path is not wired yet. Until that work
lands, this orchestrator writes the schema-compatible demo universe so the
frontend has a daily `public/data.json` to render.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _import_writer():
    try:
        from pipeline.generate_demo_data import write_demo_data
    except ImportError:  # script execution: python pipeline/run_pipeline.py
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from pipeline.generate_demo_data import write_demo_data
    return write_demo_data


def main() -> None:
    print("Starting Perspectiverse pipeline (demo universe mode)...")
    write_demo_data = _import_writer()
    output = write_demo_data()
    print(f"Wrote {output}")
    print("Pipeline complete. public/data.json is ready for the observatory.")


if __name__ == "__main__":
    main()
