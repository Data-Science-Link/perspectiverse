from __future__ import annotations

from datetime import date, datetime, timezone

from pipeline.merge_relabel_guard import (
    git_changed_paths,
    is_docs_or_factory_path,
    only_docs_or_factory,
    should_skip_full_relabel,
    touches_labeling_or_grouping,
)
from pipeline.schedule_guard import WorkflowRun


def _run(when: datetime, *, event: str = "schedule") -> WorkflowRun:
    return WorkflowRun(
        run_id=1,
        conclusion="success",
        created_at=when,
        updated_at=when,
        event=event,
        head_branch="main",
    )


def test_docs_and_factory_path_rules():
    assert is_docs_or_factory_path(".factory/FACTORY.md")
    assert is_docs_or_factory_path("docs/architecture.md")
    assert is_docs_or_factory_path("README.md")
    assert not is_docs_or_factory_path("pipeline/label.py")
    assert not is_docs_or_factory_path("public/data.json")


def test_labeling_paths_exclude_pipeline_readmes():
    assert not touches_labeling_or_grouping("pipeline/README.md")
    assert not touches_labeling_or_grouping("pipeline/data_sources/README.md")
    assert touches_labeling_or_grouping("pipeline/label.py")
    assert touches_labeling_or_grouping("pipeline/grouping.py")
    assert touches_labeling_or_grouping("pyproject.toml")
    assert touches_labeling_or_grouping(".github/workflows/pipeline.yml")
    assert not touches_labeling_or_grouping("pipeline/data/live_corpus.db")


def test_only_docs_or_factory_requires_every_path():
    assert only_docs_or_factory([".factory/FACTORY.md", "docs/foo.md"])
    assert not only_docs_or_factory([".factory/FACTORY.md", "pipeline/label.py"])
    assert not only_docs_or_factory([])


def test_skip_when_docs_only_and_daily_success():
    today = date(2026, 10, 14)
    runs = [_run(datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc))]
    assert (
        should_skip_full_relabel(
            event_name="push",
            changed_paths=[".factory/FACTORY.md"],
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is True
    )


def test_no_skip_when_pipeline_code_in_merge():
    today = date(2026, 10, 14)
    runs = [_run(datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc))]
    assert (
        should_skip_full_relabel(
            event_name="push",
            changed_paths=[".factory/FACTORY.md", "pipeline/live.py"],
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is False
    )


def test_no_skip_when_no_success_yet_today():
    today = date(2026, 10, 14)
    assert (
        should_skip_full_relabel(
            event_name="push",
            changed_paths=["docs/architecture.md"],
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: [],
        )
        is False
    )


def test_no_skip_for_schedule_even_with_docs_paths():
    today = date(2026, 10, 14)
    runs = [_run(datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc))]
    assert (
        should_skip_full_relabel(
            event_name="schedule",
            changed_paths=[".factory/FACTORY.md"],
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: runs,
        )
        is False
    )


def test_fail_open_when_fetch_returns_none():
    today = date(2026, 10, 14)
    assert (
        should_skip_full_relabel(
            event_name="push",
            changed_paths=["README.md"],
            repository="org/repo",
            token="t",
            today=today,
            fetch_runs=lambda _day: None,
        )
        is False
    )


def test_git_changed_paths_ignores_zero_before():
    assert git_changed_paths("0" * 40, "abc") is None


def test_daily_workflow_has_merge_relabel_guard():
    from pathlib import Path

    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "pipeline.merge_relabel_guard" in workflow
    assert ".factory/**" in workflow
    assert "skip_full_relabel" in workflow
