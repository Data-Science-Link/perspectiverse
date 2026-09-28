"""Load pipeline/config YAML. Local pipeline.yaml overrides the checked-in example."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
EXAMPLE_PATH = ROOT / "config" / "pipeline.example.yaml"
LOCAL_PATH = ROOT / "config" / "pipeline.yaml"

DEFAULTS: dict[str, Any] = {
    "window_hours": 168,
    "sample_size": 200,
    "min_cluster_size": 2,
    "embedding_model": "all-MiniLM-L6-v2",
    "cluster_backend": "lexical",
    "label_backend": "auto",
    "ollama_model": "llama3.2",
    "openai_model": "gpt-4o-mini",
    "representative_posts": 12,
    "language": "en",
    "seed": 0,
    "catalog_size": 10,
    "queries": ["the", "people", "today", "because", "work", "city", "game", "health", "school", "news"],
}


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Return merged settings. Environment variables override the file."""
    chosen = path
    if chosen is None:
        chosen = LOCAL_PATH if LOCAL_PATH.exists() else EXAMPLE_PATH
    data: dict[str, Any] = {}
    if chosen and Path(chosen).exists():
        loaded = yaml.safe_load(Path(chosen).read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Pipeline config must be a mapping: {chosen}")
        data = loaded

    settings = dict(DEFAULTS)
    settings.update({key: value for key, value in data.items() if value is not None})

    if os.getenv("PERSPECTIVERSE_SAMPLE_SIZE"):
        settings["sample_size"] = int(os.environ["PERSPECTIVERSE_SAMPLE_SIZE"])
    if os.getenv("PERSPECTIVERSE_CLUSTER_BACKEND"):
        settings["cluster_backend"] = os.environ["PERSPECTIVERSE_CLUSTER_BACKEND"]
    if os.getenv("PERSPECTIVERSE_LABEL_BACKEND"):
        settings["label_backend"] = os.environ["PERSPECTIVERSE_LABEL_BACKEND"]
    if os.getenv("OLLAMA_MODEL"):
        settings["ollama_model"] = os.environ["OLLAMA_MODEL"]
    if os.getenv("OPENAI_MODEL"):
        settings["openai_model"] = os.environ["OPENAI_MODEL"]
    return settings
