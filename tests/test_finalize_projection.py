"""Projection helper for #93 (measured run 37853153723, not locked targets)."""

from pipeline.finalize_projection import (
    OBSERVED_SECTION_FACES_RELABELED,
    project_section_phase,
    project_section_phase_table,
    serial_seconds_per_face_from_overrun,
)


def test_serial_per_face_from_measured_overrun():
    per_face = serial_seconds_per_face_from_overrun()
    assert round(per_face, 1) == 13.5
    assert OBSERVED_SECTION_FACES_RELABELED == 43


def test_projection_table_scales_drafting_with_planets():
    rows = project_section_phase_table(face_count=199, planet_scale=1.5)
    assert len(rows) == 2
    assert round(rows[0]["draft_sec"], 1) == 630.8
    assert round(rows[1]["draft_sec"], 1) == 946.2
    assert rows[1]["face_count"] == 299.0


def test_parallel_relabel_is_cheaper_than_serial_all_faces():
    row = project_section_phase(face_count=199)
    serial_all = 199 * serial_seconds_per_face_from_overrun()
    assert row["relabel_sec"] < serial_all
