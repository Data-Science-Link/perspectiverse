from __future__ import annotations

import json
from datetime import datetime, timezone

import urllib.error

from pipeline.pages_publish_gate import (
    evaluate_gate,
    fetch_snapshot_commit_time,
    main,
    should_deploy,
)


def test_new_snapshot_since_run_deploys():
    started = datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc)
    snapshot = datetime(2026, 10, 9, 12, 30, tzinfo=timezone.utc)
    assert should_deploy(run_started_at=started, snapshot_commit_at=snapshot) is True


def test_old_snapshot_skips():
    started = datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc)
    snapshot = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)
    assert should_deploy(run_started_at=started, snapshot_commit_at=snapshot) is False


def test_api_error_fail_open_deploys():
    started = datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc)
    assert should_deploy(run_started_at=started, snapshot_commit_at=None) is True


def test_missing_branch_skips():
    started = datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc)
    assert (
        should_deploy(run_started_at=started, snapshot_commit_at=None, branch_missing=True)
        is False
    )


def test_evaluate_gate_fail_open_on_fetch_error():
    started = "2026-10-09T11:00:00Z"

    def boom() -> tuple[datetime | None, bool]:
        return None, False

    assert (
        evaluate_gate(
            run_started_at=started,
            repository="org/repo",
            token="t",
            fetch_commit_time=boom,
        )
        is True
    )


def test_fetch_snapshot_commit_time_parses_api():
    payload = [
        {
            "commit": {
                "committer": {"date": "2026-10-09T12:00:00Z"},
            }
        }
    ]

    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=60):
        assert "sha=data-snapshot" in request.full_url
        return FakeResponse()

    commit_at, missing = fetch_snapshot_commit_time("org/repo", token="t", opener=opener)
    assert missing is False
    assert commit_at == datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def test_fetch_snapshot_http_error_fail_open():
    def opener(request, timeout=60):
        raise urllib.error.HTTPError(request.full_url, 503, "nope", hdrs=None, fp=None)

    commit_at, missing = fetch_snapshot_commit_time("org/repo", token="t", opener=opener)
    assert commit_at is None
    assert missing is False


def test_main_missing_env_fail_open(capsys, monkeypatch):
    monkeypatch.delenv("RUN_STARTED_AT", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert main([]) == 0
    assert "should_deploy=true" in capsys.readouterr().out


def test_pages_workflow_uses_publish_gate_helper():
    from pathlib import Path

    pages = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "pipeline.pages_publish_gate" in pages
    assert "pipeline_publish_gate" in pages
