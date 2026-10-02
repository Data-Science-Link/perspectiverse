"""Local MiniLM embeddings for planet membership.

The model is ONNX via fastembed, so the daily job does not install torch.
Tests pass their own ``embed`` callable and never download this file's model.
"""

from __future__ import annotations

import numpy as np

_MODEL = None
_MODEL_NAME = ""
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def embed_minilm(texts: list[str], *, model_name: str = DEFAULT_MODEL) -> np.ndarray:
    """Return one row per text. The caller normalizes."""
    global _MODEL, _MODEL_NAME
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "cluster_backend embedding needs fastembed (ONNX MiniLM). "
            "The daily job installs it; unit tests should pass embed=."
        ) from exc
    chosen = model_name if "/" in model_name else DEFAULT_MODEL
    if _MODEL is None or _MODEL_NAME != chosen:
        _MODEL = TextEmbedding(chosen)
        _MODEL_NAME = chosen
    rows = [np.asarray(vector, dtype=float) for vector in _MODEL.embed(list(texts))]
    if not rows:
        return np.zeros((0, 0), dtype=float)
    return np.vstack(rows)
