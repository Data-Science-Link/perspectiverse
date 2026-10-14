"""Skip a full relabel on merge pushes that only touch docs or factory playbooks.

Uses the same daily-success notion as ``schedule_guard`` (a qualifying successful
pipeline run already finished today on ``main``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import PurePosixPath
from typing import Callable

from pipeline.schedule_guard import (
    WorkflowRun,
    chicago_today,
    daily_success_already_today,
    fetch_workflow_runs,
    utc_today,
)

PIPELINE_DOC_ONLY = frozenset(
    {
        "pipeline/README.md",
        "pipeline/data_sources/README.md",
    }
)
PIPELINE_DATA_PREFIX = "pipeline/data/"
LABELING_EXACT = frozenset({"pyproject.toml", "uv.lock"})
LABELING_WORKFLOW = ".github/workflows/pipeline.yml"


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def touches_labeling_or_grouping(path: str) -> bool:
    """True when a path change can alter labeling, grouping, or pipeline wiring."""
    normalized = _normalize_path(path)
    if normalized in PIPELINE_DOC_ONLY:
        return False
    if normalized.startswith(PIPELINE_DATA_PREFIX):
        return False
    if normalized.startswith("pipeline/"):
        return True
    if normalized in LABELING_EXACT:
        return True
    if normalized == LABELING_WORKFLOW:
        return True
    return False


def is_docs_or_factory_path(path: str) -> bool:
    """True for markdown, ``docs/``, or ``.factory/`` paths."""
    normalized = _normalize_path(path)
    if normalized.startswith(".factory/"):
        return True
    if normalized.startswith("docs/"):
        return True
    if PurePosixPath(normalized).suffix.lower() == ".md":
        return True
    return False


def only_docs_or_factory(paths: list[str]) -> bool:
    if not paths:
        return False
    return all(is_docs_or_factory_path(item) for item in paths)


def git_changed_paths(before: str, after: str) -> list[str] | None:
    """Return paths changed between two SHAs, or None when git cannot diff."""
    before = (before or "").strip()
    after = (after or "").strip()
    if not before or not after:
        return None
    if before == "0" * 40:
        return None
    try:
        completed = subprocess.run(
            ["git", "diff", "--name-only", before, after],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def parse_changed_paths(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def should_skip_full_relabel(
    *,
    event_name: str,
    changed_paths: list[str],
    repository: str,
    token: str,
    today: date | None = None,
    current_run_id: str | None = None,
    ct_today: date | None = None,
    fetch_runs: Callable[[date], list[WorkflowRun] | None] | None = None,
) -> bool:
    if event_name != "push":
        return False
    if not changed_paths:
        return False
    if any(touches_labeling_or_grouping(path) for path in changed_paths):
        return False
    if not only_docs_or_factory(changed_paths):
        return False
    if today is None:
        today = utc_today()
    if ct_today is None:
        ct_today = chicago_today()
    if current_run_id is None:
        current_run_id = os.environ.get("GITHUB_RUN_ID")
    if fetch_runs is None:
        fetch_runs = lambda day: fetch_workflow_runs(repository, token=token, today=day)
    runs = fetch_runs(today)
    if runs is None:
        return False
    return daily_success_already_today(
        runs,
        today=today,
        current_run_id=current_run_id,
        ct_today=ct_today,
    )


def write_github_output(skip_full_relabel: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    value = "true" if skip_full_relabel else "false"
    line = f"skip_full_relabel={value}\n"
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
    else:
        sys.stdout.write(line)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")

    if argv and argv[0] == "--dry-run":
        if len(argv) < 4:
            print(
                "usage: python -m pipeline.merge_relabel_guard --dry-run "
                "<event_name> <repository> <token> [YYYY-MM-DD] <path>...",
                file=sys.stderr,
            )
            return 2
        event_name = argv[1]
        repository = argv[2]
        token = argv[3]
        today = date.fromisoformat(argv[4]) if len(argv) > 4 and "-" in argv[4] else utc_today()
        path_start = 5 if len(argv) > 4 and "-" in argv[4] else 4
        changed = argv[path_start:]
        skip = should_skip_full_relabel(
            event_name=event_name,
            changed_paths=changed,
            repository=repository,
            token=token,
            today=today,
        )
        print(f"skip_full_relabel={'true' if skip else 'false'}")
        return 0

    changed = parse_changed_paths(os.environ.get("CHANGED_FILES"))
    if not changed:
        before = os.environ.get("GITHUB_EVENT_BEFORE", "")
        after = os.environ.get("GITHUB_SHA", "")
        git_paths = git_changed_paths(before, after)
        if git_paths is not None:
            changed = git_paths

    if event_name != "push":
        write_github_output(False)
        return 0

    if not repository or not token:
        print(
            "Merge relabel guard: missing GITHUB_REPOSITORY or GITHUB_TOKEN; proceeding (fail-open).",
            file=sys.stderr,
        )
        write_github_output(False)
        return 0

    skip = should_skip_full_relabel(
        event_name=event_name,
        changed_paths=changed,
        repository=repository,
        token=token,
    )
    write_github_output(skip)
    if skip:
        print(
            "Today's posts are already labeled and this merge only touches docs or factory files; "
            "skipping the full relabel."
        )
    elif changed and only_docs_or_factory(changed):
        print(
            "Docs/factory-only merge, but no qualifying successful pipeline run yet today; "
            "running the full relabel."
        )
    else:
        print("Merge relabel guard: full pipeline relabel will run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
