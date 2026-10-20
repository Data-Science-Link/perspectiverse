#!/usr/bin/env python3
"""End-to-end over-cap run with mocked costs. Spends nothing.

Exits 14 when the live pipeline halts before publish, the prior edition is
byte-for-byte unchanged, and a snapshot checkout keeps that same ``data.json``.
Any other outcome exits 1.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EDITION = b'{"edition":"yesterday","note":"spend-cap-e2e-do-not-replace"}\n'
FAKE_CALL_USD = "0.00070"
WARN_USD = "0.00050"
STOP_USD = "0.00100"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _paid_row(*, run_id: str, trigger: str, service: str, model: str, cost: str, day: str) -> dict:
    return {
        "run_id": run_id,
        "run_started_utc": f"{day}T06:00:00Z",
        "date_utc": day,
        "trigger": trigger,
        "service": service,
        "model": model,
        "calls": 1,
        "failed_calls": 0,
        "input_tokens": 10,
        "output_tokens": 4,
        "cost_usd": Decimal(cost),
        "cost_source": "reported",
        "posts_processed": 0,
        "planets_published": 0,
    }


def _seed_snapshot(repo: Path, remote: Path, ledger: Path) -> None:
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Spend Cap E2E")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "README").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "main")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", "data-snapshot")
    public = repo / "public"
    public.mkdir()
    (public / "data.json").write_bytes(EDITION)
    costs = repo / "costs"
    costs.mkdir()
    (costs / "ledger.csv").write_bytes(ledger.read_bytes())
    _git(repo, "add", "public/data.json", "costs/ledger.csv")
    _git(repo, "commit", "-m", "yesterday's edition")
    _git(repo, "push", "-u", "origin", "data-snapshot")
    _git(repo, "checkout", "main")


def main() -> int:
    from pipeline.costs import SERVICE_DEEPINFRA, SERVICE_JEV, append_ledger
    from pipeline.run_pipeline import main as pipeline_main
    from pipeline.spend_cap import hold_edition
    from tests.corpus import build_tiny_posts

    today = datetime.now(timezone.utc).date().isoformat()
    work = Path(tempfile.mkdtemp(prefix="spend-cap-e2e-"))
    try:
        ledger = work / "prior-ledger.csv"
        append_ledger(
            ledger,
            [
                _paid_row(
                    run_id="e2e-prior-jev",
                    trigger="push",
                    service=SERVICE_JEV,
                    model="jev-score",
                    cost="0.00015",
                    day=today,
                ),
                _paid_row(
                    run_id="e2e-prior-topup",
                    trigger="push",
                    service=SERVICE_JEV,
                    model="jev-topup",
                    cost="0.00010",
                    day=today,
                ),
                _paid_row(
                    run_id="e2e-prior-label",
                    trigger="schedule",
                    service=SERVICE_DEEPINFRA,
                    model="e2e-fake",
                    cost="0.00015",
                    day=today,
                ),
            ],
        )
        edition = work / "data.json"
        edition.write_bytes(EDITION)
        snapshot_copy = work / "snapshot-data.json"
        snapshot_copy.write_bytes(EDITION)
        before = edition.read_bytes()
        before_sha = _sha(before)

        fixture = work / "posts.json"
        fixture.write_text(json.dumps(build_tiny_posts()), encoding="utf-8")
        config = work / "pipeline.yaml"
        config.write_text(
            "\n".join(
                [
                    "min_cluster_size: 8",
                    "min_planet_posts: 12",
                    "cluster_backend: lexical",
                    "label_backend: openai",
                    "label_workers: 1",
                    "section_budget_minutes: 0",
                    "sample_size: 200",
                    "window_hours: 168",
                    "representative_posts: 12",
                    "seed: 0",
                    "catalog_size: 10",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        database = work / "posts.db"
        cost_run = work / "cost_run.json"
        marker = work / "spend_cap_stop.json"
        os.environ["OPENAI_API_KEY"] = "e2e-not-a-secret"
        os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"
        os.environ["OPENAI_MODEL"] = "e2e-fake"
        os.environ["PERSPECTIVERSE_DAILY_SPEND_WARN"] = WARN_USD
        os.environ["PERSPECTIVERSE_DAILY_SPEND_STOP"] = STOP_USD
        os.environ["PERSPECTIVERSE_COST_LEDGER"] = str(ledger)
        os.environ["PERSPECTIVERSE_COST_RUN"] = str(cost_run)
        os.environ["PERSPECTIVERSE_SPEND_CAP_MARKER"] = str(marker)
        os.environ.pop("TYPESAFE_API_KEY", None)

        calls = {"n": 0}

        def fake_read(url, *, timeout, data=None, headers=None):
            calls["n"] += 1
            return {
                "model": "e2e-fake",
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "estimated_cost": FAKE_CALL_USD,
                },
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title": "Housing Alpha", '
                                '"summary": "Housing housing housing is the claim.", '
                                '"arguments": ["Housing housing housing matters.", '
                                '"Housing housing housing again."]}'
                            )
                        }
                    }
                ],
            }

        import pipeline.http_json as http_json
        import pipeline.label as label_mod

        http_json.read_json = fake_read
        label_mod.read_json = fake_read

        stdout = io.StringIO()
        stderr = io.StringIO()
        code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                pipeline_main(
                    [
                        "--live",
                        "--fixture",
                        str(fixture),
                        "--config",
                        str(config),
                        "--output",
                        str(edition),
                        "--db",
                        str(database),
                    ]
                )
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1

        after = edition.read_bytes()
        after_sha = _sha(after)
        log_out = stdout.getvalue()
        log_err = stderr.getvalue()
        published = "Pipeline complete." in log_out

        repo = work / "repo"
        remote = work / "remote.git"
        repo.mkdir()
        _seed_snapshot(repo, remote, ledger)
        data_dir = repo / "pipeline" / "data"
        data_dir.mkdir(parents=True)
        if marker.is_file():
            shutil.copy(marker, data_dir / "spend_cap_stop.json")
        if cost_run.is_file():
            shutil.copy(cost_run, data_dir / "cost_run.json")
        hold_code = hold_edition(
            repo,
            push=True,
            cost_run=data_dir / "cost_run.json" if cost_run.is_file() else None,
            marker=data_dir / "spend_cap_stop.json",
        )
        remote_edition = subprocess.run(
            ["git", "show", "origin/data-snapshot:public/data.json"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout
        remote_sha = _sha(remote_edition)
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s", "origin/data-snapshot"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        names = subprocess.run(
            ["git", "show", "--name-only", "--format=", "origin/data-snapshot"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        commit_left_edition = subject.startswith("Record spend") and "public/data.json" not in names.split()

        print("=== spend-cap over-cap e2e (mocked costs, no network spend) ===")
        print(f"warn=${WARN_USD} stop=${STOP_USD}")
        print(
            "prior ledger today: jev $0.00015 + top-up jev $0.00010 + labeling $0.00015 "
            f"= $0.00040 (push and schedule)"
        )
        print(f"fake labeling call cost=${FAKE_CALL_USD}")
        print("--- pipeline stdout ---")
        print(log_out, end="" if log_out.endswith("\n") or not log_out else "\n")
        print("--- pipeline stderr ---")
        print(log_err, end="" if log_err.endswith("\n") or not log_err else "\n")
        print("--- checks ---")
        print(f"mocked_label_calls: {calls['n']}")
        print(f"pipeline_exit: {code}")
        print(f"pipeline_complete_logged: {'yes' if published else 'no'}")
        print(f"edition_sha256_before: {before_sha}")
        print(f"edition_sha256_after: {after_sha}")
        print(f"edition_unchanged: {'yes' if after == before else 'no'}")
        print(f"snapshot_copy_unchanged: {'yes' if snapshot_copy.read_bytes() == EDITION else 'no'}")
        print(f"hold_edition_exit: {hold_code}")
        print(f"remote_data_json_sha256: {remote_sha}")
        print(f"remote_edition_unchanged: {'yes' if remote_edition == EDITION else 'no'}")
        print("latest data-snapshot commit:")
        print(subject)
        print(names.rstrip())
        print(f"ledger_commit_left_edition: {'yes' if commit_left_edition else 'no'}")
        print(f"stop_marker: {'yes' if marker.is_file() else 'no'}")

        ok = (
            code == 14
            and not published
            and after == before
            and snapshot_copy.read_bytes() == EDITION
            and calls["n"] >= 1
            and calls["n"] <= 5
            and hold_code == 14
            and remote_edition == EDITION
            and commit_left_edition
            and marker.is_file()
            and "::warning::" in log_out
            and "::error::" in log_out
            and "Not publishing" in log_err
        )
        print(f"e2e_result: {'halted_before_publish' if ok else 'FAILED'}")
        return 14 if ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
