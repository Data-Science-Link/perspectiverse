"""Skip redundant scheduled Daily Discourse Pipeline runs via the Actions API."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

WORKFLOW_FILE = "pipeline.yml"
DEFAULT_BRANCH = "main"
DEFAULT_PER_PAGE = 30
COUNTABLE_EVENTS = frozenset({"schedule", "workflow_dispatch"})


@dataclass(frozen=True)
class WorkflowRun:
    run_id: int
    conclusion: str | None
    created_at: datetime
    event: str | None
    head_branch: str | None

    @classmethod
    def from_api(cls, payload: dict) -> WorkflowRun:
        raw = payload.get("created_at") or ""
        created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return cls(
            run_id=int(payload.get("id") or 0),
            conclusion=payload.get("conclusion"),
            created_at=created,
            event=payload.get("event"),
            head_branch=payload.get("head_branch"),
        )


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _run_utc_date(run: WorkflowRun) -> date:
    return run.created_at.astimezone(timezone.utc).date()


def counts_toward_daily_success(
    run: WorkflowRun,
    *,
    today: date,
    current_run_id: str | None,
) -> bool:
    if current_run_id and str(run.run_id) == str(current_run_id):
        return False
    if run.head_branch != DEFAULT_BRANCH:
        return False
    if run.event not in COUNTABLE_EVENTS:
        return False
    if _run_utc_date(run) != today:
        return False
    return run.conclusion == "success"


def daily_success_already_today(
    runs: list[WorkflowRun],
    *,
    today: date,
    current_run_id: str | None = None,
) -> bool:
    for run in runs:
        run_day = _run_utc_date(run)
        if run_day < today:
            return False
        if counts_toward_daily_success(run, today=today, current_run_id=current_run_id):
            return True
    return False


def _api_url(
    repository: str,
    workflow_file: str,
    page: int,
    per_page: int,
    branch: str,
) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    owner, repo = repository.split("/", 1)
    path = (
        f"/repos/{owner}/{repo}/actions/workflows/"
        f"{urllib.parse.quote(workflow_file, safe='')}/runs"
    )
    query = urllib.parse.urlencode(
        {
            "per_page": per_page,
            "page": page,
            "status": "completed",
            "branch": branch,
        }
    )
    return f"{base}{path}?{query}"


def _read_page(
    url: str,
    token: str,
    opener: Callable[..., object],
) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=60) as response:  # type: ignore[call-arg]
            status = getattr(response, "status", 200)
            if status and int(status) >= 400:
                return None
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError:
        return None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def fetch_workflow_runs(
    repository: str,
    *,
    token: str,
    today: date,
    workflow_file: str = WORKFLOW_FILE,
    branch: str = DEFAULT_BRANCH,
    per_page: int = DEFAULT_PER_PAGE,
    opener: Callable[..., object] | None = None,
) -> list[WorkflowRun] | None:
    """Return main-branch runs for today and newer pages, or None on API/parse failure."""
    if opener is None:
        opener = urllib.request.urlopen

    runs: list[WorkflowRun] = []
    page = 1
    while True:
        url = _api_url(repository, workflow_file, page, per_page, branch)
        payload = _read_page(url, token, opener)
        if payload is None:
            return None

        batch = payload.get("workflow_runs") or []
        if not batch:
            break

        stop_pagination = False
        for item in batch:
            run = WorkflowRun.from_api(item)
            run_day = _run_utc_date(run)
            if run_day < today:
                stop_pagination = True
                break
            if run.head_branch == branch:
                runs.append(run)

        if stop_pagination:
            break
        if len(batch) < per_page:
            break
        page += 1
    return runs


def should_skip_scheduled_run(
    *,
    event_name: str,
    repository: str,
    token: str,
    today: date | None = None,
    current_run_id: str | None = None,
    fetch_runs: Callable[[date], list[WorkflowRun] | None] | None = None,
) -> bool:
    if event_name != "schedule":
        return False
    if today is None:
        today = utc_today()
    if current_run_id is None:
        current_run_id = os.environ.get("GITHUB_RUN_ID")
    if fetch_runs is None:
        fetch_runs = lambda day: fetch_workflow_runs(repository, token=token, today=day)
    runs = fetch_runs(today)
    if runs is None:
        return False
    return daily_success_already_today(runs, today=today, current_run_id=current_run_id)


def write_github_output(skip: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    line = f"skip={'true' if skip else 'false'}\n"
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
        if len(argv) < 2:
            print(
                "usage: python -m pipeline.schedule_guard --dry-run "
                "<event_name> [YYYY-MM-DD]",
                file=sys.stderr,
            )
            return 2
        event_name = argv[1]
        today = date.fromisoformat(argv[2]) if len(argv) > 2 else utc_today()
        if event_name != "schedule":
            print("skip=false")
            return 0
        if not repository or not token:
            print("skip=false")
            return 0
        skip = should_skip_scheduled_run(
            event_name=event_name,
            repository=repository,
            token=token,
            today=today,
        )
        print(f"skip={'true' if skip else 'false'}")
        return 0

    if event_name != "schedule":
        write_github_output(False)
        return 0

    if not repository or not token:
        print(
            "Schedule guard: missing GITHUB_REPOSITORY or GITHUB_TOKEN; proceeding (fail-open).",
            file=sys.stderr,
        )
        write_github_output(False)
        return 0

    skip = should_skip_scheduled_run(
        event_name=event_name,
        repository=repository,
        token=token,
    )
    write_github_output(skip)
    if skip:
        print(
            "Daily Discourse Pipeline already succeeded today (UTC) "
            "via schedule or workflow_dispatch on main; skipping scheduled run."
        )
    else:
        print(
            "No qualifying successful Daily Discourse Pipeline run yet today (UTC); proceeding."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
