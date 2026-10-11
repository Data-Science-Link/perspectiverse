"""Publish guard: hold a failure-driven regression, publish a quieter real day."""

from __future__ import annotations

import json
import time

from pipeline.live import (
    _FinalizeFaceJob,
    _run_finalize_faces_parallel,
    reset_section_face_relabel,
    section_face_relabel,
)
from pipeline.publish_guard import (
    HOLD_EXIT,
    count_section_planets,
    decide_publish,
    final_failure_warning,
    format_deepinfra_error_log,
    main,
    section_planet_margin,
)


def _snapshot(section_counts: dict[str, int]) -> dict:
    sections = {
        name: [{"id": index + 1, "name": f"{name} {index}"} for index in range(count)]
        for name, count in section_counts.items()
    }
    return {"topics": [{"id": 1}] * 10, "sections": sections}


def _errors(*, calls: int, retried: int = 0, final: int = 0) -> dict:
    return {
        "calls": calls,
        "retried_calls": retried,
        "final_failures": final,
        "retried": {"429": retried, "5xx": 0, "timeout": 0, "other": 0},
        "final_failures_by_type": {"429": 0, "5xx": 0, "timeout": final, "other": 0},
    }


def _relabel(*, queued: int, incomplete: int) -> dict:
    return {
        "sections_queued": queued,
        "sections_incomplete": incomplete,
        "calls_queued": queued * 15,
        "calls_completed": (queued - incomplete) * 15,
        "budget_exhausted": incomplete > 0,
    }


def _label_run(errors: dict, face: dict | None = None) -> dict:
    return {"deepinfra_errors": errors, "face_relabel": face or _relabel(queued=10, incomplete=0)}


def test_margin_matches_the_incident_counts():
    assert section_planet_margin(98) == 5
    assert section_planet_margin(20) == 3
    assert section_planet_margin(0) == 3
    assert count_section_planets(_snapshot({"Politics": 10, "Sports": 7})) == 17
    assert count_section_planets({"topics": [{}] * 10}) == 0


def test_incident_shape_does_not_publish():
    """Run 37946621071: 90 section planets, relabel skipped in every section, 86 failures."""
    live = _snapshot({"Politics": 10, "World": 10, "Business": 10, "Technology": 10, "Other": 10, "Health": 10, "Culture": 10, "Environment": 10, "Sports": 9, "Education": 9})
    new = _snapshot({"Politics": 10, "World": 10, "Business": 10, "Technology": 10, "Other": 10, "Health": 10, "Culture": 8, "Environment": 9, "Sports": 7, "Education": 6})
    assert count_section_planets(live) == 98
    assert count_section_planets(new) == 90
    label_run = _label_run(_errors(calls=947, retried=60, final=26), _relabel(queued=10, incomplete=10))
    decision = decide_publish(live, new, label_run)
    assert decision.publish is False
    assert decision.code == "hold"
    assert "face relabel" in decision.reason
    assert "section planets fell from 98 to 90" in decision.reason


def test_mixed_ledger_count_still_holds_when_finals_are_unknown():
    """The old ledger mixed retries and finals. Either share over 5% is distress."""
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 90})
    only_retries = _label_run(_errors(calls=947, retried=86, final=0), _relabel(queued=10, incomplete=10))
    only_finals = _label_run(_errors(calls=947, retried=0, final=86), _relabel(queued=10, incomplete=0))
    assert decide_publish(live, new, only_retries).publish is False
    assert decide_publish(live, new, only_finals).publish is False


def test_clean_rerun_publishes_against_a_fuller_day():
    """Run 37954827855: 8 failures of 1,172, relabel finished, 97 vs an earlier 98."""
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 97})
    label_run = _label_run(_errors(calls=1172, retried=5, final=3), _relabel(queued=10, incomplete=0))
    decision = decide_publish(live, new, label_run)
    assert decision.publish is True
    assert decision.code == "publish"


def test_quiet_day_with_fewer_planets_still_publishes():
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 80})
    label_run = _label_run(_errors(calls=1000, retried=2, final=1), _relabel(queued=10, incomplete=0))
    decision = decide_publish(live, new, label_run)
    assert decision.publish is True
    assert "not in distress" in decision.reason


def test_relabel_skip_without_failures_publishes():
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 98})
    label_run = _label_run(_errors(calls=1000, retried=0, final=0), _relabel(queued=10, incomplete=8))
    assert decide_publish(live, new, label_run).publish is True


def test_relabel_skip_in_most_sections_holds_even_when_planet_count_holds():
    live = _snapshot({"Politics": 50, "World": 48})
    new = _snapshot({"Politics": 50, "World": 48})
    label_run = _label_run(_errors(calls=200, retried=4, final=12), _relabel(queued=10, incomplete=6))
    decision = decide_publish(live, new, label_run)
    assert decision.publish is False
    assert "face relabel" in decision.reason


def test_half_the_sections_unfinished_is_not_most():
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 98})
    label_run = _label_run(_errors(calls=100, retried=0, final=20), _relabel(queued=10, incomplete=5))
    assert decide_publish(live, new, label_run).publish is True


def test_drop_inside_the_margin_publishes_even_in_distress():
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 93})
    label_run = _label_run(_errors(calls=100, retried=0, final=20), _relabel(queued=10, incomplete=0))
    assert section_planet_margin(98) == 5
    assert decide_publish(live, new, label_run).publish is True


def test_exactly_five_percent_is_not_distress_and_does_not_warn():
    summary = _errors(calls=100, retried=0, final=5)
    assert final_failure_warning(summary) is None
    live = _snapshot({"Politics": 98})
    new = _snapshot({"Politics": 80})
    assert decide_publish(live, new, _label_run(summary, _relabel(queued=10, incomplete=10))).publish is True
    over = _errors(calls=100, retried=0, final=6)
    warning = final_failure_warning(over)
    assert warning is not None
    assert "6 of 100" in warning
    assert "over the 5% line" in warning
    assert decide_publish(live, new, _label_run(over)).publish is False


def test_missing_live_snapshot_or_label_report_fails_open():
    new = _snapshot({"Politics": 10})
    assert decide_publish(None, new, None).publish is True
    assert decide_publish({}, new, None).code == "publish"
    live = _snapshot({"Politics": 98})
    assert decide_publish(live, new, None).publish is True
    assert decide_publish(live, None, _label_run(_errors(calls=10, final=10))).publish is True


def test_error_log_keeps_retries_and_final_failures_apart():
    line = format_deepinfra_error_log(
        {
            "calls": 947,
            "retried": {"429": 40, "5xx": 2, "timeout": 10, "other": 0},
            "final_failures_by_type": {"429": 1, "5xx": 0, "timeout": 20, "other": 1},
            "retried_calls": 52,
            "final_failures": 22,
        }
    )
    assert line.startswith("DeepInfra labeling: 947 call(s).")
    assert "DeepInfra errors:" not in line
    assert "Retried attempts: 429=40, 5xx=2, timeout=10, other=0 (52)" in line
    assert "Final failures: 429=1, 5xx=0, timeout=20, other=1 (22)" in line


def test_cli_holds_with_exit_10_and_publishes_a_quiet_day(tmp_path, monkeypatch):
    live = tmp_path / "live.json"
    new = tmp_path / "new.json"
    report = tmp_path / "label_run.json"
    summary = tmp_path / "summary.md"
    live.write_text(json.dumps(_snapshot({"Politics": 98})), encoding="utf-8")
    new.write_text(json.dumps(_snapshot({"Politics": 90})), encoding="utf-8")
    report.write_text(
        json.dumps(_label_run(_errors(calls=947, retried=40, final=46), _relabel(queued=10, incomplete=10))),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["--live", str(live), "--new", str(new), "--label-run", str(report)]) == HOLD_EXIT
    text = summary.read_text(encoding="utf-8")
    assert "live snapshot kept" in text
    assert "did **not** replace" in text

    quiet = tmp_path / "quiet.json"
    quiet.write_text(
        json.dumps(_label_run(_errors(calls=1000, retried=1, final=1), _relabel(queued=10, incomplete=0))),
        encoding="utf-8",
    )
    fewer = tmp_path / "fewer.json"
    fewer.write_text(json.dumps(_snapshot({"Politics": 70})), encoding="utf-8")
    assert main(["--live", str(live), "--new", str(fewer), "--label-run", str(quiet)]) == 0


def test_cli_fail_open_when_the_live_file_cannot_be_read(tmp_path):
    live = tmp_path / "live.json"
    new = tmp_path / "new.json"
    live.write_text("{", encoding="utf-8")
    new.write_text(json.dumps(_snapshot({"Politics": 1})), encoding="utf-8")
    assert main(["--live", str(live), "--new", str(new)]) == 0
    missing = tmp_path / "missing.json"
    assert main(["--live", str(missing), "--new", str(new)]) == 0


def test_section_face_relabel_records_a_budget_skip_without_calling_out():
    reset_section_face_relabel()

    def job(section: str) -> _FinalizeFaceJob:
        return _FinalizeFaceJob(
            section=section,
            face={"id": section},
            draft={"title": "Draft"},
            face_posts=[{"text": "A claim about the section."}],
            face_vectors=None,
            face_cosines=[1.0],
            face_terms=["claim"],
            context={},
            limit=36,
        )

    incomplete = _run_finalize_faces_parallel(
        [job("Politics"), job("Health")],
        2,
        time.monotonic() - 1,
        scope="2 section(s)",
        record=True,
    )
    stats = section_face_relabel()
    assert incomplete == {"Politics", "Health"}
    assert stats["sections_queued"] == 2
    assert stats["sections_incomplete"] == 2
    assert stats["calls_queued"] == 2
    assert stats["calls_completed"] == 0
    assert stats["budget_exhausted"] is True
