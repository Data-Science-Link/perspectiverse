"""Paid-test overlap check. No network and no DeepInfra calls."""

from __future__ import annotations

import json

from pipeline.pipeline_overlap import (
    EXIT_OVERLAP,
    EXIT_UNKNOWN,
    check_pipeline_overlap,
    main,
)


class _Response:
    status = 200

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _opener_for(pages: dict[str, dict]):
    seen: list[str] = []

    def opener(request, timeout=60):
        seen.append(request.full_url)
        for status, payload in pages.items():
            if f"status={status}" in request.full_url:
                return _Response(payload)
        raise AssertionError(request.full_url)

    opener.seen = seen  # type: ignore[attr-defined]
    return opener


def test_clear_when_nothing_is_running():
    opener = _opener_for(
        {
            "in_progress": {"workflow_runs": []},
            "queued": {"workflow_runs": []},
        }
    )
    result = check_pipeline_overlap(
        repository="Data-Science-Link/perspectiverse",
        token="ghs_test",
        ignore_run_id="",
        opener=opener,
    )
    assert result.clear is True
    assert result.error is None
    assert result.runs == ()
    assert "status=in_progress" in opener.seen[0]
    assert "status=queued" in opener.seen[1]


def test_in_progress_run_blocks_a_paid_test(monkeypatch, capsys):
    opener = _opener_for(
        {
            "in_progress": {
                "workflow_runs": [
                    {
                        "id": 37946621071,
                        "status": "in_progress",
                        "event": "push",
                        "html_url": "https://github.com/Data-Science-Link/perspectiverse/actions/runs/37946621071",
                    }
                ]
            },
            "queued": {"workflow_runs": []},
        }
    )
    monkeypatch.setattr(
        "pipeline.pipeline_overlap.check_pipeline_overlap",
        lambda: check_pipeline_overlap(
            repository="Data-Science-Link/perspectiverse",
            token="",
            ignore_run_id="",
            opener=opener,
        ),
    )
    assert main([]) == EXIT_OVERLAP
    text = capsys.readouterr().out
    assert "37946621071" in text
    assert "in_progress" in text
    assert "must wait" in text


def test_queued_run_blocks_and_the_current_run_is_ignored():
    opener = _opener_for(
        {
            "in_progress": {
                "workflow_runs": [
                    {"id": 42, "status": "in_progress", "event": "schedule", "html_url": ""}
                ]
            },
            "queued": {
                "workflow_runs": [
                    {"id": 99, "status": "queued", "event": "schedule", "html_url": "https://example.test/99"}
                ]
            },
        }
    )
    result = check_pipeline_overlap(
        repository="Data-Science-Link/perspectiverse",
        token="ghs_test",
        ignore_run_id="42",
        opener=opener,
    )
    assert result.clear is False
    assert [run.run_id for run in result.runs] == [99]
    assert result.runs[0].status == "queued"


def test_api_failure_does_not_say_the_coast_is_clear():
    def opener(request, timeout=60):
        raise TimeoutError("timed out")

    result = check_pipeline_overlap(
        repository="Data-Science-Link/perspectiverse",
        token="",
        ignore_run_id="",
        opener=opener,
    )
    assert result.clear is False
    assert result.error is not None
    assert "in_progress" in result.error


def test_main_exits_3_when_the_api_fails(monkeypatch, capsys):
    def opener(request, timeout=60):
        raise OSError("down")

    monkeypatch.setattr(
        "pipeline.pipeline_overlap.check_pipeline_overlap",
        lambda: check_pipeline_overlap(
            repository="Data-Science-Link/perspectiverse",
            token="",
            ignore_run_id="",
            opener=opener,
        ),
    )
    assert main([]) == EXIT_UNKNOWN
    error = capsys.readouterr().err
    assert "Do not start a paid labeling test" in error


def test_script_module_does_not_call_deepinfra():
    source = open("scripts/check_pipeline_overlap.py", encoding="utf-8").read()
    module = open("pipeline/pipeline_overlap.py", encoding="utf-8").read()
    assert "api.deepinfra.com" not in source
    assert "api.deepinfra.com" not in module
    assert "OPENAI_API_KEY" not in module
    assert "pipeline.pipeline_overlap" in source
