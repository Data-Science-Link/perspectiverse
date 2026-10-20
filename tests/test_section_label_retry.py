import time

from pipeline.live import _SectionLabelJob, _draft_timed_out, _retry_section_labeling


def test_draft_timed_out_detects_timeout_log():
    assert _draft_timed_out(["Dropping candidate 3: drafting failed (RuntimeError: timed out)."])
    assert not _draft_timed_out(["Dropping candidate 3: drafting failed (RuntimeError: HTTP 500)."])


def test_retry_section_labeling_restarts_skipped_sections(monkeypatch):
    job = _SectionLabelJob("Tech", [], {"topics": []}, 1, {}, 10)
    job.skipped_budget = True
    called = {"n": 0}

    def fake_label(jobs, workers, deadline):
        called["n"] += 1
        assert jobs == [job]
        job.skipped_budget = False

    monkeypatch.setattr("pipeline.live._label_section_jobs", fake_label)
    _retry_section_labeling([job], 4, time.monotonic() + 60)
    assert called["n"] == 1
