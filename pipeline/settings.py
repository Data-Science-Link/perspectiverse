"""Load pipeline/config YAML. Local pipeline.yaml overrides the checked-in example."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from pipeline.corpus import TARGET_POSTS
from pipeline.grouping import MIN_PLANET_POSTS

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
EXAMPLE_PATH = ROOT / "config" / "pipeline.example.yaml"
LOCAL_PATH = ROOT / "config" / "pipeline.yaml"
DEFAULT_DEEPINFRA_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

# Representative posts kept on each perspective in the published snapshot.
# 36 sits in the roadmap's 20–50 band: enough evidence for readers and a future
# clerk without blowing up Pages payload (most faces are smaller than the cap).
EXAMPLE_POST_CAP = 36
# Posts shown to labeling prompts for faces (MMR sample cap).
DEFAULT_PROMPT_SAMPLE_SIZE = 40
DEFAULT_DRAFT_PROMPT_SAMPLE_SIZE = 12
# Planet / topic naming prompts use a smaller diverse slice.
DEFAULT_PLANET_PROMPT_SAMPLE_SIZE = 20
# Posts shown to the one-face stance check. The whole planet is used when it
# is smaller. This count, not every post on the planet, is what the share below
# is divided by.
STANCE_SAMPLE_LIMIT = 40
# One config value. 0.10 is what this build measures. It is not a decision
# that 10% is the right bar. Change this number, not the call sites.
STANCE_SECOND_FACE_SHARE = 0.10

DEFAULTS: dict[str, Any] = {
    "window_hours": 168,
    "refresh_hours": 24,
    "sample_size": TARGET_POSTS,
    "min_cluster_size": 5,
    "embedding_model": "all-MiniLM-L6-v2",
    "cluster_backend": "embedding",
    "label_backend": "auto",
    "ollama_model": "llama3.2",
    "openai_model": "gpt-4o-mini",
    "representative_posts": EXAMPLE_POST_CAP,
    "prompt_sample_size": DEFAULT_PROMPT_SAMPLE_SIZE,
    "draft_prompt_sample_size": DEFAULT_DRAFT_PROMPT_SAMPLE_SIZE,
    "planet_prompt_sample_size": DEFAULT_PLANET_PROMPT_SAMPLE_SIZE,
    "language": "en",
    "seed": 0,
    "catalog_size": 10,
    # Published planets, split stories, and global topics below this many
    # posts are left out before any label, name, or brief call. 0 disables it.
    "min_planet_posts": MIN_PLANET_POSTS,
    "stance_second_face_share": STANCE_SECOND_FACE_SHARE,
    # Planets labeled at once when a network label backend is on.
    # Section labeling shares one pool and widens this default of 8 to 12.
    "label_workers": 8,
    # Minutes the section solar systems may spend after the global system.
    # 0 skips sections. None (omit the key) uses this default.
    "section_budget_minutes": 20,
    "neutral_queries": ["the", "and", "to", "of", "in", "for"],
    # Phase 3 packs about 25 posts into one spam+claim request. It does not
    # ask for a section. The shadow test failed batched claims, so this stays
    # false. See scripts/jev_shadow_test.py. The planet-level section call is #90.
    "jev_batch": False,
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
    if os.getenv("PERSPECTIVERSE_LABEL_WORKERS"):
        settings["label_workers"] = int(os.environ["PERSPECTIVERSE_LABEL_WORKERS"])
    if os.getenv("PERSPECTIVERSE_MIN_PLANET_POSTS"):
        settings["min_planet_posts"] = int(os.environ["PERSPECTIVERSE_MIN_PLANET_POSTS"])
    share = (os.getenv("PERSPECTIVERSE_STANCE_SECOND_FACE_SHARE") or "").strip()
    if share:
        settings["stance_second_face_share"] = float(share)
    batch_flag = (os.getenv("PERSPECTIVERSE_JEV_BATCH") or "").strip().lower()
    if batch_flag:
        settings["jev_batch"] = batch_flag in {"1", "true", "yes", "on"}
    ollama_model = (os.getenv("OLLAMA_MODEL") or "").strip()
    if ollama_model:
        settings["ollama_model"] = ollama_model
    openai_model = (os.getenv("OPENAI_MODEL") or "").strip()
    openai_base = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if openai_model:
        settings["openai_model"] = openai_model
    elif "deepinfra.com" in openai_base:
        settings["openai_model"] = DEFAULT_DEEPINFRA_MODEL
    return settings


def load_dotenv(path: Path | None = None) -> Path | None:
    """Load KEY=VALUE pairs from a gitignored .env without overriding a real env.

    Non-empty process variables win. A local .env can fill names that are
    missing or blank. Never logs values.
    """
    chosen = Path(path) if path else REPO_ROOT / ".env"
    if not chosen.exists():
        return None
    for raw in chosen.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not key or not value:
            continue
        current = os.environ.get(key)
        if current is None or not str(current).strip():
            os.environ[key] = value
    return chosen
