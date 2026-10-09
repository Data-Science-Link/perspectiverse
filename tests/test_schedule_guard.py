from __future__ import annotations

import json
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.schedule_guard import (
    WorkflowRun,
    daily_success_already_today,
    fetch_workflow_runs,
    main,
    should_skip_scheduled_run,
)


def _run(
    *,
    run_id: int = 1,
    conclusion: str = "success",
    when: datetime,
    event: str = "schedule",
    head_branch: str = "main",
) -> WorkflowRun:
    return WorkflowRun(
        run_id=run_id,
        conclusion=conclusion,
        created_at=when,
        event=event,
        head_branch=head_branch,
    )


def test_daily_success_stops_at_older_runs():
    today = date(2026, 10, 9)
    runs = [
        _run(run_id=3, conclusion="failure", when=datetime(2026, 10, 9, 7, 0, tzinfo=timezone.utc)),
        _run(run_id=2, when=datetime(2026, 10, 9, 6, 30, tzinfo=timezone.utc)),
        _run(run_id=1, when=datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc)),
    ]
    assert daily_success_already_today(runs, today=today) is True


def test_daily_success_false_when_only_failures_today():
    today = date(2026, 10, 9)
    runs = [
        _run(run_id=2, conclusion="failure", when=datetime(2026, 10, 9, 7, 0, tzinfo=timezone.utc)),
        _run(run_id=1, when=datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc)),
    ]
    assert daily_success_already_today(runs, today=today) is False


def test_push_success_does_not_count_toward_skip():
    today = date(2026, 10, 9)
    runs = [
        _run(
            run_id=9,
            when=datetime(2026, 10, 9, 5, 0, tzinfo=timezone.utc),
            event="push",
        ),
    ]
    assert daily_success_already_today(runs, today=today) is False
    assert (
        should_skip_scheduled_run(
            event_name="schedule",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is False
    )


def test_workflow_dispatch_success_counts():
    today = date(2026, 10, 9)
    runs = [
        _run(
            run_id=4,
            when=datetime(2026, 10, 9, 8, 1, tzinfo=timezone.utc),
            event="workflow_dispatch",
        ),
    ]
    assert daily_success_already_today(runs, today=today) is True


def test_excludes_current_run_id():
    today = date(2026, 10, 9)
    runs = [
        _run(run_id=42, when=datetime(2026, 10, 9, 6, 17, tzinfo=timezone.utc)),
    ]
    assert daily_success_already_today(runs, today=today, current_run_id="42") is False


def test_non_main_branch_does_not_count():
    today = date(2026, 10, 9)
    runs = [
        _run(
            run_id=5,
            when=datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc),
            head_branch="cursor/feature",
        ),
    ]
    assert daily_success_already_today(runs, today=today) is False


def test_should_skip_never_for_push_or_dispatch_events():
    today = date(2026, 10, 9)
    runs = [_run(when=datetime(2026, 10, 9, 6, 30, tzinfo=timezone.utc))]

    assert (
        should_skip_scheduled_run(
            event_name="push",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is False
    )
    assert (
        should_skip_scheduled_run(
            event_name="workflow_dispatch",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is False
    )


def test_should_skip_schedule_when_daily_success_today():
    today = date(2026, 10, 9)
    runs = [_run(when=datetime(2026, 10, 9, 6, 17, tzinfo=timezone.utc))]

    assert (
        should_skip_scheduled_run(
            event_name="schedule",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is True
    )


def test_should_skip_fail_open_when_fetch_returns_none():
    today = date(2026, 10, 9)
    assert (
        should_skip_scheduled_run(
            event_name="schedule",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: None,
        )
        is False
    )


def test_fetch_workflow_runs_uses_branch_main_in_url():
    today = date(2026, 10, 9)
    payload = {
        "workflow_runs": [
            {
                "id": 1,
                "conclusion": "success",
                "created_at": "2026-10-09T06:17:23Z",
                "event": "schedule",
                "head_branch": "main",
            }
        ]
    }

    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    seen_urls: list[str] = []

    def opener(request, timeout=60):
        seen_urls.append(request.full_url)
        return FakeResponse()

    runs = fetch_workflow_runs(
        "Data-Science-Link/perspectiverse",
        token="ghs_test",
        today=today,
        opener=opener,
    )
    assert runs is not None
    assert len(runs) == 1
    assert "branch=main" in seen_urls[0]


def test_fetch_stops_pagination_at_first_run_older_than_today():
    today = date(2026, 10, 9)
    page1 = {
        "workflow_runs": [
            {
                "id": 2,
                "conclusion": "failure",
                "created_at": "2026-10-09T07:00:00Z",
                "event": "schedule",
                "head_branch": "main",
            },
            {
                "id": 1,
                "conclusion": "success",
                "created_at": "2026-10-08T06:00:00Z",
                "event": "schedule",
                "head_branch": "main",
            },
        ]
    }
    page2 = {"workflow_runs": [{"id": 99, "created_at": "2026-10-07T06:00:00Z"}]}
    calls = 0

    class FakeResponse:
        status = 200

        def __init__(self, body: dict):
            self._body = body

        def read(self) -> bytes:
            return json.dumps(self._body).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=60):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(page1)
        return FakeResponse(page2)

    runs = fetch_workflow_runs("org/repo", token="t", today=today, opener=opener)
    assert runs is not None
    assert len(runs) == 1
    assert calls == 1


def test_fetch_fail_open_on_http_error():
    today = date(2026, 10, 9)

    def opener(request, timeout=60):
        raise urllib.error.HTTPError(request.full_url, 503, "nope", hdrs=None, fp=None)

    assert fetch_workflow_runs("org/repo", token="t", today=today, opener=opener) is None


def test_fetch_fail_open_on_bad_json():
    today = date(2026, 10, 9)

    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=60):
        return FakeResponse()

    assert fetch_workflow_runs("org/repo", token="t", today=today, opener=opener) is None


def test_main_schedule_fail_open_on_missing_token(capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "skip=false" in captured.out


def test_daily_workflow_has_backup_cron_and_schedule_guard():
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert 'cron: "17 6 * * *"' in workflow
    assert 'cron: "17 8 * * *"' in workflow
    assert "pipeline.schedule_guard" in workflow
    assert "actions: read" in workflow
    assert "discourse-pipeline" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "pull_request" not in workflow
