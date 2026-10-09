from __future__ import annotations

import json
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

from pipeline.schedule_guard import (
    WorkflowRun,
    fetch_workflow_runs,
    should_skip_scheduled_run,
    success_already_today,
)


def test_success_already_today_stops_at_older_runs():
    today = date(2026, 10, 9)
    runs = [
        WorkflowRun(
            conclusion="failure",
            created_at=datetime(2026, 10, 9, 7, 0, tzinfo=timezone.utc),
        ),
        WorkflowRun(
            conclusion="success",
            created_at=datetime(2026, 10, 9, 6, 30, tzinfo=timezone.utc),
        ),
        WorkflowRun(
            conclusion="success",
            created_at=datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc),
        ),
    ]
    assert success_already_today(runs, today=today) is True


def test_success_already_today_false_when_only_failures_today():
    today = date(2026, 10, 9)
    runs = [
        WorkflowRun(
            conclusion="failure",
            created_at=datetime(2026, 10, 9, 7, 0, tzinfo=timezone.utc),
        ),
        WorkflowRun(
            conclusion="success",
            created_at=datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc),
        ),
    ]
    assert success_already_today(runs, today=today) is False


def test_should_skip_never_for_push_or_dispatch():
    def fetch() -> list[WorkflowRun]:
        return [
            WorkflowRun(
                conclusion="success",
                created_at=datetime(2026, 10, 9, 6, 30, tzinfo=timezone.utc),
            )
        ]

    today = date(2026, 10, 9)
    assert (
        should_skip_scheduled_run(
            event_name="push",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=fetch,
        )
        is False
    )
    assert (
        should_skip_scheduled_run(
            event_name="workflow_dispatch",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=fetch,
        )
        is False
    )


def test_should_skip_schedule_when_success_today():
    today = date(2026, 10, 9)

    def fetch() -> list[WorkflowRun]:
        return [
            WorkflowRun(
                conclusion="success",
                created_at=datetime(2026, 10, 9, 6, 17, tzinfo=timezone.utc),
            )
        ]

    assert (
        should_skip_scheduled_run(
            event_name="schedule",
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=fetch,
        )
        is True
    )


def test_fetch_workflow_runs_parses_api_payload():
    payload = {
        "workflow_runs": [
            {
                "conclusion": "success",
                "created_at": "2026-10-09T06:17:23Z",
            }
        ]
    }

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request, timeout=60):
        assert request.get_method() == "GET"
        assert "pipeline.yml" in request.full_url
        return FakeResponse()

    runs = fetch_workflow_runs("Data-Science-Link/perspectiverse", token="ghs_test", opener=opener)
    assert len(runs) == 1
    assert runs[0].conclusion == "success"


def test_daily_workflow_has_backup_cron_and_schedule_guard():
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert 'cron: "17 6 * * *"' in workflow
    assert 'cron: "17 8 * * *"' in workflow
    assert "pipeline.schedule_guard" in workflow
    assert "actions: read" in workflow
    assert "discourse-pipeline" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "pull_request" not in workflow
