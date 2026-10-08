"""Honest section-phase projections from measured run 37853153723 (post-#88).

Not a performance guarantee. Drafting time scales with planet count; relabel
uses the widened section pool (12 in flight when ``label_workers`` is 8).

Measured (run 37853153723):
- Section phase wall time: 1211.9s (was 630.8s before wide relabel).
- Only 43 section faces completed wide relabel before the 1200s deadline.
- If the ~581s overrun is attributed to those 43 serial relabels: ~13.5s per face.

Example table (``project_section_phase_table``):

| Workload | Drafting (s) | Relabel parallel est. (s) | Total est. (s) |
|----------|-------------|---------------------------|----------------|
| Oct 8 (199 faces) | 630.8 | ceil(199/12)*13.5 ≈ 229.5 | ≈ 860 |
| 1.5× planets | 630.8×1.5 ≈ 946 | ceil(299/12)*13.5 ≈ 337.5 | ≈ 1284 |
"""

from __future__ import annotations

import math

# Run 37853153723 (push after #88 merge).
OBSERVED_SECTION_PHASE_SEC = 1211.9
OBSERVED_DRAFT_SECTION_SEC = 630.8
OBSERVED_SECTION_FACES_RELABELED = 43
DEFAULT_SECTION_POOL = 12


def serial_seconds_per_face_from_overrun(
    *,
    section_phase_sec: float = OBSERVED_SECTION_PHASE_SEC,
    draft_sec: float = OBSERVED_DRAFT_SECTION_SEC,
    faces_relabeled: int = OBSERVED_SECTION_FACES_RELABELED,
) -> float:
    """Mean serial wide-relabel seconds per face if overrun equals relabel work."""
    overrun = max(section_phase_sec - draft_sec, 0.0)
    if faces_relabeled <= 0:
        return 0.0
    return overrun / faces_relabeled


def parallel_relabel_seconds(
    face_count: int,
    *,
    pool_size: int = DEFAULT_SECTION_POOL,
    seconds_per_face_wave: float | None = None,
) -> float:
    """Wall time if each pool wave waits for the slowest of ``pool_size`` calls."""
    if face_count <= 0:
        return 0.0
    if seconds_per_face_wave is None:
        seconds_per_face_wave = serial_seconds_per_face_from_overrun()
    waves = math.ceil(face_count / max(pool_size, 1))
    return waves * seconds_per_face_wave


def project_section_phase(
    *,
    face_count: int,
    draft_sec: float = OBSERVED_DRAFT_SECTION_SEC,
    pool_size: int = DEFAULT_SECTION_POOL,
    seconds_per_face_wave: float | None = None,
) -> dict[str, float]:
    relabel = parallel_relabel_seconds(
        face_count,
        pool_size=pool_size,
        seconds_per_face_wave=seconds_per_face_wave,
    )
    return {
        "draft_sec": draft_sec,
        "relabel_sec": relabel,
        "total_sec": draft_sec + relabel,
        "face_count": float(face_count),
        "pool_size": float(pool_size),
    }


def project_section_phase_table(
    *,
    face_count: int = 199,
    planet_scale: float = 1.0,
    pool_size: int = DEFAULT_SECTION_POOL,
) -> list[dict[str, float]]:
    """Rows for Oct 8 face count and scaled planet workloads."""
    per_face = serial_seconds_per_face_from_overrun()
    rows = [
        project_section_phase(
            face_count=face_count,
            draft_sec=OBSERVED_DRAFT_SECTION_SEC,
            pool_size=pool_size,
            seconds_per_face_wave=per_face,
        ),
    ]
    if planet_scale != 1.0:
        scaled_faces = math.ceil(face_count * planet_scale)
        rows.append(
            project_section_phase(
                face_count=scaled_faces,
                draft_sec=OBSERVED_DRAFT_SECTION_SEC * planet_scale,
                pool_size=pool_size,
                seconds_per_face_wave=per_face,
            )
        )
    return rows
