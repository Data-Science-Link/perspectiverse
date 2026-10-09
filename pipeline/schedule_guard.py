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
from typing import Callable, Iterable

WORKFLOW_FILE = "pipeline.yml"
DEFAULT_PER_PAGE = 30


@dataclass(frozen=True)
class WorkflowRun:
    conclusion: str | None
    created_at: datetime

    @classmethod
    def from_api(cls, payload: dict) -> WorkflowRun:
        raw = payload.get("created_at") or ""
        created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return cls(conclusion=payload.get("conclusion"), created_at=created)


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def success_already_today(
    runs: Iterable[WorkflowRun],
    *,
    today: date,
) -> bool:
    for run in runs:
        run_day = run.created_at.astimezone(timezone.utc).date()
        if run_day < today:
            return False
        if run_day == today and run.conclusion == "success":
            return True
    return False


def _api_url(repository: str, workflow_file: str, page: int, per_page: int) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    owner, repo = repository.split("/", 1)
    path = (
        f"/repos/{owner}/{repo}/actions/workflows/"
        f"{urllib.parse.quote(workflow_file, safe='')}/runs"
    )
    query = urllib.parse.urlencode({"per_page": per_page, "page": page, "status": "completed"})
    return f"{base}{path}?{query}"


def fetch_workflow_runs(
    repository: str,
    *,
    token: str,
    workflow_file: str = WORKFLOW_FILE,
    per_page: int = DEFAULT_PER_PAGE,
    opener: Callable[..., object] | None = None,
) -> list[WorkflowRun]:
    if opener is None:
        opener = urllib.request.urlopen

    runs: list[WorkflowRun] = []
    page = 1
    while True:
        url = _api_url(repository, workflow_file, page, per_page)
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
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API HTTP {exc.code} listing workflow runs") from exc

        batch = payload.get("workflow_runs") or []
        if not batch:
            break
        for item in batch:
            runs.append(WorkflowRun.from_api(item))
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
    fetch_runs: Callable[[], list[WorkflowRun]] | None = None,
) -> bool:
    if event_name != "schedule":
        return False
    if today is None:
        today = utc_today()
    if fetch_runs is None:
        fetch_runs = lambda: fetch_workflow_runs(repository, token=token)
    return success_already_today(fetch_runs(), today=today)


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
            print("GITHUB_REPOSITORY and GITHUB_TOKEN required for schedule dry-run", file=sys.stderr)
            return 2
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
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required for schedule runs", file=sys.stderr)
        return 1

    skip = should_skip_scheduled_run(
        event_name=event_name,
        repository=repository,
        token=token,
    )
    write_github_output(skip)
    if skip:
        print("Daily Discourse Pipeline already succeeded today (UTC); skipping scheduled run.")
    else:
        print("No successful Daily Discourse Pipeline run yet today (UTC); proceeding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
