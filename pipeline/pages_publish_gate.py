"""Fail-open gate: deploy Pages after pipeline only if data-snapshot advanced."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable

DEFAULT_BRANCH = "data-snapshot"


def _parse_github_time(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def should_deploy(
    *,
    run_started_at: datetime,
    snapshot_commit_at: datetime | None,
    branch_missing: bool = False,
) -> bool:
    """Return whether Pages should deploy for this workflow_run.

    Fail-open: when ``snapshot_commit_at`` is unknown (API/git error), deploy.
    Skip only when we know the branch exists and its tip is older than the run.
    """
    if branch_missing:
        return False
    if snapshot_commit_at is None:
        return True
    if snapshot_commit_at.tzinfo is None:
        snapshot_commit_at = snapshot_commit_at.replace(tzinfo=timezone.utc)
    started = run_started_at.astimezone(timezone.utc)
    return snapshot_commit_at >= started


def _commits_url(repository: str, branch: str, per_page: int = 1) -> str:
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    owner, repo = repository.split("/", 1)
    path = f"/repos/{owner}/{repo}/commits"
    query = urllib.parse.urlencode({"sha": branch, "per_page": per_page})
    return f"{base}{path}?{query}"


def fetch_snapshot_commit_time(
    repository: str,
    *,
    token: str,
    branch: str = DEFAULT_BRANCH,
    opener: Callable[..., object] | None = None,
) -> tuple[datetime | None, bool]:
    """Return (commit_time, branch_missing).

    On transport/parse errors, returns (None, False) so callers fail-open.
    On HTTP 404, returns (None, True) — branch does not exist.
    """
    if opener is None:
        opener = urllib.request.urlopen

    url = _commits_url(repository, branch)
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
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, True
        return None, False
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, False

    if status == 404:
        return None, True
    if status >= 400:
        return None, False

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None, False

    if not payload:
        return None, True

    commit = payload[0]
    raw = (commit.get("commit") or {}).get("committer", {}).get("date")
    if not raw:
        raw = (commit.get("commit") or {}).get("author", {}).get("date")
    if not raw:
        return None, False
    return _parse_github_time(raw), False


def evaluate_gate(
    *,
    run_started_at: str,
    repository: str,
    token: str,
    fetch_commit_time: Callable[[], tuple[datetime | None, bool]] | None = None,
) -> bool:
    started = _parse_github_time(run_started_at)
    if fetch_commit_time is None:
        fetch_commit_time = lambda: fetch_snapshot_commit_time(repository, token=token)
    commit_at, branch_missing = fetch_commit_time()
    return should_deploy(
        run_started_at=started,
        snapshot_commit_at=commit_at,
        branch_missing=branch_missing,
    )


def write_github_output(should_deploy_flag: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    line = f"should_deploy={'true' if should_deploy_flag else 'false'}\n"
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
    else:
        sys.stdout.write(line)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    run_started = os.environ.get("RUN_STARTED_AT", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")

    if argv and argv[0] == "--dry-run":
        if len(argv) != 4:
            print(
                "usage: python -m pipeline.pages_publish_gate --dry-run "
                "<run_started_iso> <snapshot_commit_iso|none> <missing:0|1>",
                file=sys.stderr,
            )
            return 2
        started = _parse_github_time(argv[1])
        branch_missing = argv[3] == "1"
        if argv[2].lower() == "none":
            commit_at = None
        else:
            commit_at = _parse_github_time(argv[2])
        deploy = should_deploy(
            run_started_at=started,
            snapshot_commit_at=commit_at,
            branch_missing=branch_missing,
        )
        print(f"should_deploy={'true' if deploy else 'false'}")
        return 0

    if not run_started or not repository or not token:
        print(
            "Pages publish gate: missing env; fail-open (deploy).",
            file=sys.stderr,
        )
        write_github_output(True)
        return 0

    try:
        deploy = evaluate_gate(
            run_started_at=run_started,
            repository=repository,
            token=token,
        )
    except Exception:
        deploy = True
    write_github_output(deploy)
    if deploy:
        print("Pages deploy gate: deploy (new snapshot or fail-open).")
    else:
        print("Pages deploy gate: skip (no new data-snapshot since pipeline run started).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
