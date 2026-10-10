"""See whether a Daily Discourse Pipeline run is queued or in progress.

Paid labeling tests share the production DeepInfra key. They must not start
while that workflow is running. This check uses the GitHub Actions API only.
It does not call DeepInfra.

Exit 0: clear to start.
Exit 2: a run is queued or in progress. Wait.
Exit 3: the check itself failed. Do not start a paid test.

A missing token is fine on this public repository. ``GITHUB_RUN_ID``, when
set, is ignored so the pipeline does not count itself.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

WORKFLOW_FILE = "pipeline.yml"
DEFAULT_REPOSITORY = "Data-Science-Link/perspectiverse"
BLOCKING_STATUSES = ("in_progress", "queued")
EXIT_CLEAR = 0
EXIT_OVERLAP = 2
EXIT_UNKNOWN = 3


@dataclass(frozen=True)
class PipelineRun:
    run_id: int
    status: str
    html_url: str
    event: str


@dataclass(frozen=True)
class OverlapCheck:
    clear: bool
    runs: tuple[PipelineRun, ...]
    error: str | None


def _api_url(repository: str, status: str) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    owner, repo = repository.split("/", 1)
    path = (
        f"/repos/{owner}/{repo}/actions/workflows/"
        f"{urllib.parse.quote(WORKFLOW_FILE, safe='')}/runs"
    )
    query = urllib.parse.urlencode({"status": status, "per_page": 20})
    return f"{base}{path}?{query}"


def _read_page(url: str, token: str, opener: Callable[..., object]) -> dict | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
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
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def blocking_runs(
    repository: str,
    *,
    token: str = "",
    ignore_run_id: str | None = None,
    opener: Callable[..., object] | None = None,
) -> OverlapCheck:
    """Return queued or in-progress pipeline runs. ``error`` is set when the API failed."""
    if opener is None:
        opener = urllib.request.urlopen
    found: list[PipelineRun] = []
    seen: set[int] = set()
    for status in BLOCKING_STATUSES:
        url = _api_url(repository, status)
        payload = _read_page(url, token, opener)
        if payload is None:
            return OverlapCheck(False, (), f"GitHub Actions API failed for status={status}")
        batch = payload.get("workflow_runs")
        if batch is None:
            return OverlapCheck(False, (), f"GitHub Actions API returned no workflow_runs for status={status}")
        if not isinstance(batch, list):
            return OverlapCheck(False, (), f"GitHub Actions API returned a bad workflow_runs list for status={status}")
        for item in batch:
            if not isinstance(item, dict):
                continue
            run_id = int(item.get("id") or 0)
            if ignore_run_id and str(run_id) == str(ignore_run_id):
                continue
            if run_id in seen:
                continue
            run_status = str(item.get("status") or status)
            if run_status not in BLOCKING_STATUSES:
                continue
            seen.add(run_id)
            found.append(
                PipelineRun(
                    run_id=run_id,
                    status=run_status,
                    html_url=str(item.get("html_url") or ""),
                    event=str(item.get("event") or ""),
                )
            )
    return OverlapCheck(not found, tuple(found), None)


def check_pipeline_overlap(
    *,
    repository: str | None = None,
    token: str | None = None,
    ignore_run_id: str | None = None,
    opener: Callable[..., object] | None = None,
) -> OverlapCheck:
    repo = (repository or os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPOSITORY).strip()
    if "/" not in repo:
        return OverlapCheck(False, (), f"GITHUB_REPOSITORY is not owner/name: {repo!r}")
    auth = token if token is not None else (os.environ.get("GITHUB_TOKEN") or "").strip()
    current = ignore_run_id if ignore_run_id is not None else (os.environ.get("GITHUB_RUN_ID") or "").strip()
    return blocking_runs(repo, token=auth, ignore_run_id=current or None, opener=opener)


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("usage: python -m pipeline.pipeline_overlap", file=sys.stderr)
        return EXIT_UNKNOWN
    result = check_pipeline_overlap()
    if result.error:
        print(f"Pipeline overlap check failed: {result.error}", file=sys.stderr)
        print("Do not start a paid labeling test until this check succeeds.", file=sys.stderr)
        return EXIT_UNKNOWN
    if not result.clear:
        for run in result.runs:
            where = f" {run.html_url}" if run.html_url else ""
            print(
                f"Daily Discourse Pipeline run {run.run_id} is {run.status} "
                f"(event {run.event or 'unknown'}).{where}"
            )
        print("Paid labeling tests must wait until that run finishes. They share the DeepInfra key.")
        return EXIT_OVERLAP
    print("No Daily Discourse Pipeline run is queued or in progress.")
    return EXIT_CLEAR


if __name__ == "__main__":
    raise SystemExit(main())
