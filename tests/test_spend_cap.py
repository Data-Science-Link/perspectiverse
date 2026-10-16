"""Daily spend cap: warn and hard stop at $1.00 UTC-day total, do not publish (#148, #182)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from pipeline.costs import (
    SERVICE_DEEPINFRA,
    SERVICE_JEV,
    SERVICE_R2,
    append_ledger,
    get_meter,
    record_attempt,
    reset_meter,
)
from pipeline.live import _safe_draft, _topup_claims
from pipeline.run_pipeline import main
from pipeline.spend_cap import (
    DAILY_STOP_AFTER_FILL_USD,
    DAILY_STOP_USD,
    DAILY_WARN_AFTER_FILL_USD,
    DAILY_WARN_USD,
    FILL_BUDGET_TOTAL_USD,
    STOP_EXIT,
    SpendCapExceeded,
    check_fill_dispatch,
    enforce_before_paid_work,
    fill_campaign_complete,
    fill_paid_usd,
    guard_before_paid_call,
    is_fill_run,
    hold_edition,
    record_partial_ledger,
    stop_usd,
    warn_usd,
)
from pipeline.costs import LEDGER_TAG_FILL


@pytest.fixture(autouse=True)
def _isolated_cap(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_DAILY_SPEND_WARN", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_DAILY_SPEND_STOP", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_COST_LEDGER", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_COST_RUN", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_SPEND_CAP_MARKER", raising=False)
    reset_meter()
    yield
    reset_meter()


def _attempt(**overrides):
    payload = {
        "service": SERVICE_DEEPINFRA,
        "model": "unit-test-llm",
        "input_tokens": 10,
        "output_tokens": 4,
        "cost_usd": Decimal("0.01"),
        "cost_source": "reported",
        "status": "success",
    }
    payload.update(overrides)
    record_attempt(**payload)


def _ledger_row(
    *,
    run_id: str,
    trigger: str,
    service: str,
    cost: str,
    day: date,
    model: str = "unit",
    tags: str = "",
) -> dict:
    return {
        "run_id": run_id,
        "run_started_utc": f"{day.isoformat()}T06:00:00Z",
        "date_utc": day.isoformat(),
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
        "storage_bytes": 0,
        "class_a_ops": 0,
        "class_b_ops": 0,
        "list_price_usd": Decimal(cost),
        "retried_calls": 0,
        "final_failures": 0,
        "tags": tags,
    }


def test_defaults_are_the_production_thresholds():
    assert DAILY_WARN_USD == Decimal("1.00")
    assert DAILY_STOP_USD == Decimal("1.00")
    assert STOP_EXIT == 14


def test_warn_threshold_logs_and_annotation(capsys):
    _attempt(cost_usd=Decimal("0.99"))
    captured = capsys.readouterr()
    assert "::warning::" not in captured.out
    assert "WARNING:" not in captured.err

    with pytest.raises(SpendCapExceeded):
        _attempt(cost_usd=Decimal("0.01"))
    captured = capsys.readouterr()
    assert "::warning::" in captured.out
    assert "Daily spend reached $1.00" in captured.out
    assert "warn $1.00" in captured.out
    assert "stop $1.00" in captured.out
    assert "WARNING: Daily spend reached $1.00" in captured.err
    assert "::error::" in captured.out
    assert len(get_meter().attempts()) == 2


def test_prior_same_day_ledger_at_stop_halts_before_first_paid_call(tmp_path, monkeypatch):
    """Earlier runs today already at $1.00: no paid call in this process."""
    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(run_id="38894377011", trigger="schedule", service=SERVICE_JEV, cost="0.60", day=today),
            _ledger_row(
                run_id="38930594047",
                trigger="push",
                service=SERVICE_DEEPINFRA,
                cost="0.40",
                day=today,
            ),
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    with pytest.raises(SpendCapExceeded) as caught:
        enforce_before_paid_work()
    assert caught.value.spent_usd == Decimal("1.00")
    with pytest.raises(SpendCapExceeded):
        guard_before_paid_call("labeling")
    assert len(get_meter().attempts()) == 0


def test_mid_run_crossing_stop_halts_before_next_paid_call(capsys):
    _attempt(cost_usd=Decimal("0.99"))
    capsys.readouterr()
    with pytest.raises(SpendCapExceeded) as caught:
        _attempt(cost_usd=Decimal("0.01"))
    assert caught.value.exit_code == 14
    assert caught.value.spent_usd == Decimal("1.00")
    assert "Not publishing" in str(caught.value)
    assert "yesterday's edition" in str(caught.value)
    captured = capsys.readouterr()
    assert "::error::" in captured.out
    assert len(get_meter().attempts()) == 2
    with pytest.raises(SpendCapExceeded):
        guard_before_paid_call("labeling")
    assert len(get_meter().attempts()) == 2


def test_cross_run_accumulation_counts_every_trigger_and_skips_r2(tmp_path, monkeypatch, capsys):
    today = date(2026, 10, 12)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(run_id="push-jev", trigger="push", service=SERVICE_JEV, cost="0.40", day=today),
            _ledger_row(
                run_id="schedule-label",
                trigger="schedule",
                service=SERVICE_DEEPINFRA,
                cost="0.30",
                day=today,
            ),
            _ledger_row(
                run_id="dispatch-topup",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                model="jev-topup",
                cost="0.20",
                day=today,
            ),
            _ledger_row(run_id="r2", trigger="push", service=SERVICE_R2, cost="5.00", day=today),
            _ledger_row(
                run_id="yesterday",
                trigger="push",
                service=SERVICE_JEV,
                cost="0.80",
                day=date(2026, 10, 11),
            ),
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    enforce_before_paid_work()
    captured = capsys.readouterr()
    assert "::warning::" not in captured.out
    with pytest.raises(SpendCapExceeded) as caught:
        _attempt(cost_usd=Decimal("0.10"))
    assert caught.value.spent_usd == Decimal("1.00")
    assert "::error::" in capsys.readouterr().out
    assert len(get_meter().attempts()) == 1
    with pytest.raises(SpendCapExceeded):
        guard_before_paid_call("Jev")
    assert len(get_meter().attempts()) == 1


def test_topup_does_not_swallow_the_stop(monkeypatch):
    def _fetch(**kwargs):
        del kwargs
        return [
            {
                "uri": "at://fixture/topup/1",
                "author": "reader",
                "text": "Housing costs keep rising and the city should build more homes now.",
                "created_at": "2026-10-12T12:00:00Z",
            }
        ]

    def _boom(*args, **kwargs):
        del args, kwargs
        raise SpendCapExceeded("stop", spent_usd=Decimal("1.00"))

    monkeypatch.setattr("pipeline.live.extract_posts", _fetch)
    monkeypatch.setattr("pipeline.live.apply_jev", _boom)
    with pytest.raises(SpendCapExceeded):
        _topup_claims(
            [{"uri": "at://fixture/old", "is_claim": True}],
            target=10,
            settings={"neutral_queries": ["the"], "refresh_hours": 24, "seed": 0},
            connection=None,
        )


def test_safe_draft_does_not_swallow_the_stop(monkeypatch):
    def _boom(*args, **kwargs):
        del args, kwargs
        raise SpendCapExceeded("stop", spent_usd=Decimal("1.00"))

    monkeypatch.setattr("pipeline.live._draft_planet", _boom)
    with pytest.raises(SpendCapExceeded):
        _safe_draft([], {}, {"id": 1}, {})


def test_already_stopped_day_does_not_publish(tmp_path, monkeypatch):
    today = date(2026, 10, 12)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(run_id="earlier-push", trigger="push", service=SERVICE_DEEPINFRA, cost="0.60", day=today),
            _ledger_row(run_id="earlier-schedule", trigger="schedule", service=SERVICE_JEV, cost="0.40", day=today),
        ],
    )
    edition = tmp_path / "data.json"
    edition.write_bytes(b'{"edition":"yesterday"}\n')
    before = edition.read_bytes()
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    monkeypatch.setenv("PERSPECTIVERSE_COST_RUN", str(tmp_path / "cost_run.json"))
    monkeypatch.setenv("PERSPECTIVERSE_SPEND_CAP_MARKER", str(tmp_path / "spend_cap_stop.json"))
    database = tmp_path / "posts.db"
    with pytest.raises(SystemExit) as caught:
        main(
            [
                "--live",
                "--fixture",
                str(tmp_path / "missing.json"),
                "--output",
                str(edition),
                "--db",
                str(database),
            ]
        )
    assert caught.value.code == 14
    assert edition.read_bytes() == before
    marker = json.loads((tmp_path / "spend_cap_stop.json").read_text(encoding="utf-8"))
    assert marker["stopped"] is True
    assert marker["exit_code"] == 14


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


def test_partial_ledger_after_data_snapshot_checkout(tmp_path):
    """Pinned PYTHONPATH still imports spend_cap after hold-edition's checkout."""
    import shutil

    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    staged = tmp_path / "workflow-pipeline"
    shutil.copytree(Path("pipeline"), staged / "pipeline")
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Spend Cap Test")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "README").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "main")
    _git(repo, "checkout", "-b", "data-snapshot")
    edition = b'{"edition":"yesterday"}\n'
    public = repo / "public"
    public.mkdir()
    (public / "data.json").write_bytes(edition)
    _git(repo, "add", "public/data.json")
    _git(repo, "commit", "-m", "snapshot")
    _git(repo, "push", "-u", "origin", "data-snapshot")
    _git(repo, "checkout", "main")
    _git(repo, "checkout", "--force", "-B", "data-snapshot", "origin/data-snapshot")
    assert not (repo / "pipeline" / "spend_cap.py").is_file()

    cost_run = tmp_path / "cost_run.json"
    today = date(2026, 10, 16)
    cost_run.write_text(
        json.dumps(
            {
                "rows": [
                    _ledger_row(
                        run_id="after-checkout",
                        trigger="push",
                        service=SERVICE_DEEPINFRA,
                        cost="0.12",
                        day=today,
                    )
                ],
                "run_id": "after-checkout",
                "run_started_utc": "2026-10-16T17:00:00Z",
                "date_utc": today.isoformat(),
                "trigger": "push",
            },
            default=str,
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(staged)}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipeline.spend_cap",
            "record-partial-ledger",
            "--repo",
            str(repo),
            "--push",
            "--cost-run",
            str(cost_run),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    ledger = subprocess.run(
        ["git", "show", "origin/data-snapshot:costs/ledger.csv"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "after-checkout" in ledger


def test_hold_edition_keeps_data_json_and_records_spend(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Spend Cap Test")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "README").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "main")
    _git(repo, "checkout", "-b", "data-snapshot")
    edition = b'{"edition":"yesterday"}\n'
    public = repo / "public"
    public.mkdir()
    (public / "data.json").write_bytes(edition)
    _git(repo, "add", "public/data.json")
    _git(repo, "commit", "-m", "snapshot")
    _git(repo, "push", "-u", "origin", "data-snapshot")
    _git(repo, "checkout", "main")

    data = repo / "pipeline" / "data"
    data.mkdir(parents=True)
    (data / "spend_cap_stop.json").write_text('{"stopped": true}\n', encoding="utf-8")
    cost_run = data / "cost_run.json"
    cost_run.write_text(
        json.dumps(
            {
                "rows": [
                    _ledger_row(
                        run_id="capped-run",
                        trigger="push",
                        service=SERVICE_DEEPINFRA,
                        cost="0.25",
                        day=date(2026, 10, 12),
                    )
                ],
                "run_id": "capped-run",
                "run_started_utc": "2026-10-12T12:00:00Z",
                "date_utc": "2026-10-12",
                "trigger": "push",
            },
            default=str,
        ),
        encoding="utf-8",
    )
    assert hold_edition(repo, push=True, cost_run=cost_run, marker=data / "spend_cap_stop.json") == 14
    shown = subprocess.run(
        ["git", "show", "origin/data-snapshot:public/data.json"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    assert shown == edition
    ledger = subprocess.run(
        ["git", "show", "origin/data-snapshot:costs/ledger.csv"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "capped-run" in ledger
    names = _git(repo, "show", "--name-only", "--format=", "origin/data-snapshot")
    assert "public/data.json" not in names.split()
    assert "costs/ledger.csv" in names.split()


def _pipeline_workflow_steps() -> list[dict]:
    import yaml

    document = yaml.safe_load(Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8"))
    return document["jobs"]["pipeline"]["steps"]


def test_jev_cache_workflow_uses_explicit_restore_and_save():
    steps = _pipeline_workflow_steps()
    restore = next(step for step in steps if step.get("name") == "Restore Jev verdict cache")
    save = next(step for step in steps if step.get("name") == "Save Jev verdict cache")
    live_at = next(index for index, step in enumerate(steps) if step.get("id") == "live")
    restore_at = steps.index(restore)
    save_at = steps.index(save)
    assert restore_at < live_at < save_at
    assert restore["uses"] == "actions/cache/restore@v4"
    assert save["uses"] == "actions/cache/save@v4"
    assert "always()" in save["if"]
    assert restore["with"]["key"] == save["with"]["key"]
    assert restore["with"]["key"].endswith("github.run_id }}")
    assert "jev-verdict-cache-" in save["with"]["restore-keys"]
    workflow_text = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "save-always" not in workflow_text


def test_cancelled_live_stages_corpus_and_uploads_to_r2():
    steps = _pipeline_workflow_steps()
    names = [step.get("name") for step in steps]
    live_at = next(index for index, step in enumerate(steps) if step.get("id") == "live")
    save_at = names.index("Save Jev verdict cache")
    stage_at = names.index("Stage corpus after cancelled live")
    upload_at = names.index("Upload corpus to R2 after cancelled live")
    assert live_at < save_at < stage_at < upload_at
    assert "steps.live.outcome == 'cancelled'" in steps[stage_at]["if"]
    assert "corpus_persist upload-staged" in steps[upload_at]["run"]


def _write_cost_run(path: Path, *, run_id: str, cost: str, day: date | None = None) -> None:
    when = day or date(2026, 10, 16)
    path.write_text(
        json.dumps(
            {
                "rows": [
                    _ledger_row(
                        run_id=run_id,
                        trigger="push",
                        service=SERVICE_DEEPINFRA,
                        cost=cost,
                        day=when,
                    )
                ],
                "run_id": run_id,
                "run_started_utc": f"{when.isoformat()}T12:00:00Z",
                "date_utc": when.isoformat(),
                "trigger": "push",
            },
            default=str,
        ),
        encoding="utf-8",
    )


def _init_data_snapshot_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "config", "user.email", "dev@example.com")
    _git(seed, "config", "user.name", "Spend Cap Test")
    _git(seed, "remote", "add", "origin", str(remote))
    (seed / "README").write_text("main\n", encoding="utf-8")
    _git(seed, "add", "README")
    _git(seed, "commit", "-m", "main")
    _git(seed, "push", "-u", "origin", "main")
    _git(seed, "checkout", "-b", "data-snapshot")
    public = seed / "public"
    public.mkdir()
    (public / "data.json").write_text('{"edition":"yesterday"}\n', encoding="utf-8")
    costs = seed / "costs"
    costs.mkdir()
    (costs / "ledger.csv").write_text(
        "run_id,run_started_utc,date_utc,trigger,service,model,calls,failed_calls,"
        "input_tokens,output_tokens,cost_usd,cost_source,posts_processed,planets_published\n",
        encoding="utf-8",
    )
    _git(seed, "add", "public/data.json", "costs/ledger.csv")
    _git(seed, "commit", "-m", "snapshot")
    _git(seed, "push", "-u", "origin", "data-snapshot")
    _git(seed, "checkout", "main")
    return remote, seed


def _clone_snapshot(tmp_path: Path, remote: Path, name: str) -> Path:
    clone = tmp_path / name
    subprocess.run(["git", "clone", str(remote), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "dev@example.com")
    _git(clone, "config", "user.name", "Spend Cap Test")
    _git(clone, "checkout", "main")
    return clone


def test_two_clones_push_both_run_rows_after_push_retry(tmp_path, monkeypatch):
    """Clone A and B both land on the remote ledger when B's first push is rejected."""
    from pipeline.spend_cap import record_partial_ledger

    remote, _seed = _init_data_snapshot_remote(tmp_path)
    repo_a = _clone_snapshot(tmp_path, remote, "clone-a")
    repo_b = _clone_snapshot(tmp_path, remote, "clone-b")
    cost_a = tmp_path / "run-a.json"
    cost_b = tmp_path / "run-b.json"
    _write_cost_run(cost_a, run_id="run-a", cost="0.21")
    _write_cost_run(cost_b, run_id="run-b", cost="0.33")

    assert record_partial_ledger(repo_a, push=True, cost_run=cost_a) == 0

    import pipeline.spend_cap as spend_cap_module

    original_git = spend_cap_module._git
    push_attempts = {"b": 0}

    def fake_git(repo: Path, *args: str, check: bool = True):
        if (
            Path(repo).resolve() == repo_b.resolve()
            and args
            and args[0] == "push"
            and push_attempts["b"] == 0
        ):
            push_attempts["b"] += 1
            return subprocess.CompletedProcess(args, 1, b"", b"rejected")
        return original_git(repo, *args, check=check)

    monkeypatch.setattr(spend_cap_module, "_git", fake_git)
    assert record_partial_ledger(repo_b, push=True, cost_run=cost_b) == 0
    assert push_attempts["b"] == 1

    _git(repo_a, "fetch", "origin", "data-snapshot")
    ledger = subprocess.run(
        ["git", "show", "origin/data-snapshot:costs/ledger.csv"],
        cwd=repo_a,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "run-a" in ledger
    assert "run-b" in ledger


def test_partial_ledger_step_runs_before_hold_edition():
    steps = _pipeline_workflow_steps()
    names = [step.get("name") for step in steps]
    partial_at = names.index("Record partial spend when the run ends early")
    hold_at = names.index("Keep yesterday's edition when the daily spend cap stops the run")
    assert partial_at < hold_at
    partial = steps[partial_at]
    assert partial["env"]["PYTHONPATH"] == "${{ env.PERSPECTIVERSE_LEDGER_PYTHONPATH }}"
    assert "--cost-run" in partial["run"]


def test_workflow_stops_publish_unless_the_live_step_succeeds():
    text = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "PERSPECTIVERSE_COST_LEDGER" in text
    assert "pipeline.spend_cap hold-edition" in text
    assert "record-partial-ledger" in text
    assert "spend_cap_stop.json" in text
    assert "steps.live.outcome == 'success'" in text
    assert "PERSPECTIVERSE_LEDGER_PYTHONPATH" in text
    stage_at = text.index("name: Stage halted corpus before ledger git checkout")
    hold_at = text.index("name: Keep yesterday's edition when the daily spend cap stops the run")
    upload_at = text.index("name: Upload halted corpus to R2")
    assert stage_at < upload_at < hold_at
    assert "corpus_persist upload-staged" in text
    assert "steps.live.outcome == 'cancelled'" in text
    test_partial_ledger_step_runs_before_hold_edition()
    test_jev_cache_workflow_uses_explicit_restore_and_save()


def _heuristic_config(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "min_cluster_size: 8",
                "cluster_backend: lexical",
                "label_backend: heuristic",
                "sample_size: 200",
                "window_hours: 168",
                "representative_posts: 12",
                "seed: 0",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_paid_call_flushes_cost_run_checkpoint(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from pipeline.costs import bind_cost_checkpoint

    monkeypatch.setenv("PERSPECTIVERSE_COST_RUN", str(tmp_path / "cost_run.json"))
    started = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    bind_cost_checkpoint(started)
    record_attempt(
        service=SERVICE_DEEPINFRA,
        model="unit",
        input_tokens=1,
        output_tokens=1,
        cost_usd=Decimal("0.12"),
        cost_source="reported",
        status="success",
    )
    payload = json.loads((tmp_path / "cost_run.json").read_text(encoding="utf-8"))
    assert payload["rows"]
    assert Decimal(payload["rows"][0]["cost_usd"]) == Decimal("0.12")


def test_killed_run_partial_ledger_counts_on_next_run(tmp_path, monkeypatch):
    """Interrupted run appends spend; the next run's cap sees it on the ledger."""
    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)

    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Partial Ledger Test")
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "README").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "main")
    _git(repo, "checkout", "-b", "data-snapshot")
    edition = b'{"edition":"yesterday"}\n'
    public = repo / "public"
    public.mkdir()
    (public / "data.json").write_bytes(edition)
    ledger = repo / "costs" / "ledger.csv"
    ledger.parent.mkdir(parents=True)
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="38894377011",
                trigger="schedule",
                service=SERVICE_JEV,
                cost="0.40",
                day=today,
            )
        ],
    )
    _git(repo, "add", "public/data.json", "costs/ledger.csv")
    _git(repo, "commit", "-m", "snapshot")
    _git(repo, "push", "-u", "origin", "data-snapshot")
    _git(repo, "checkout", "main")

    data = repo / "pipeline" / "data"
    data.mkdir(parents=True)
    cost_run = data / "cost_run.json"
    cost_run.write_text(
        json.dumps(
            {
                "rows": [
                    _ledger_row(
                        run_id="killed-mid-run",
                        trigger="push",
                        service=SERVICE_DEEPINFRA,
                        cost="0.35",
                        day=today,
                    )
                ],
                "run_id": "killed-mid-run",
                "run_started_utc": "2026-10-16T16:58:00Z",
                "date_utc": today.isoformat(),
                "trigger": "push",
            },
            default=str,
        ),
        encoding="utf-8",
    )
    assert record_partial_ledger(repo, push=True, cost_run=cost_run) == 0
    ledger_text = subprocess.run(
        ["git", "show", "origin/data-snapshot:costs/ledger.csv"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "killed-mid-run" in ledger_text

    ledger_copy = tmp_path / "ledger.csv"
    ledger_copy.write_text(ledger_text, encoding="utf-8")
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger_copy))
    reset_meter()
    enforce_before_paid_work()
    with pytest.raises(SpendCapExceeded) as caught:
        record_attempt(
            service=SERVICE_DEEPINFRA,
            model="unit",
            input_tokens=1,
            output_tokens=1,
            cost_usd=Decimal("0.26"),
            cost_source="reported",
            status="success",
        )
    assert caught.value.spent_usd == Decimal("1.01")


def _jev_posts() -> list[dict]:
    return [
        {
            "uri": f"at://fixture/jev/{index}",
            "author": f"reader{index}",
            "text": (
                f"Policy debate number {index} about buses, housing, and city council funding today."
            ),
            "clean_text": (
                f"Policy debate number {index} about buses, housing, and city council funding today."
            ),
            "likes": index,
            "created_at": "2026-10-16T12:00:00Z",
        }
        for index in range(3)
    ]


def test_apply_jev_spend_cap_mid_batch_persists_paid_verdicts(tmp_path, monkeypatch):
    """The first paid Jev answer is stored before the cap unwinds the batch."""
    import sqlite3

    from pipeline.jev import apply_jev, reset_jev_state
    from pipeline.store import connect
    from tests.test_jev import _answer

    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("pipeline.jev._WORKERS", 1)
    database = tmp_path / "live_corpus.db"
    connection = connect(database)
    posts = _jev_posts()
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise SpendCapExceeded("stop", spent_usd=Decimal("1.00"))
        return _answer(0.1, "Politics", claim=0.92 if calls["n"] == 1 else 0.08)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    with pytest.raises(SpendCapExceeded):
        apply_jev(posts, connection=connection, update_input=True)
    rows = connection.execute("SELECT uri FROM jev_verdicts").fetchall()
    connection.close()
    assert calls["n"] >= 2
    assert {row[0] for row in rows} >= {"at://fixture/jev/0"}


def test_spend_cap_halt_mid_jev_persists_corpus_and_reuses_verdicts(tmp_path, monkeypatch):
    """Halt inside Jev keeps the scored claim and its verdict. Unscored posts are not inserted."""
    import sqlite3

    from pipeline.jev import apply_jev, reset_jev_state
    from pipeline.live import run_live
    from pipeline.store import connect
    from tests.test_jev import _answer

    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    database = tmp_path / "live_corpus.db"
    edition = tmp_path / "data.json"
    edition.write_text('{"edition":"yesterday"}\n', encoding="utf-8")
    posts = _jev_posts()

    def collect(*_args, **_kwargs):
        return list(posts), "bluesky", True

    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise SpendCapExceeded("stop", spent_usd=Decimal("1.00"))
        return _answer(0.1, "Politics", claim=0.92)

    monkeypatch.setattr("pipeline.live._collect_posts", collect)
    monkeypatch.setattr("pipeline.jev.read_json", fake)
    config = _heuristic_config(tmp_path / "pipeline.yaml")
    with pytest.raises(SpendCapExceeded):
        run_live(output=edition, config=config, db_path=database)
    assert edition.read_bytes() == b'{"edition":"yesterday"}\n'

    connection = connect(database)
    assert connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM posts WHERE is_claim = 1").fetchone()[0] == 1
    connection.close()

    reset_meter()
    calls["n"] = 0
    connection = connect(database)
    from pipeline.store import load_posts

    stored = [post for post in load_posts(connection) if post.get("section")]
    assert len(stored) == 1
    apply_jev(stored, connection=connection, update_input=True)
    connection.close()
    assert calls["n"] == 0


def test_spend_cap_halt_requires_persist_for_post_rows(tmp_path, monkeypatch):
    """Without persist on halt, paid verdicts exist but the post table stays empty."""
    from pipeline.jev import reset_jev_state
    from pipeline.live import run_live
    from pipeline.store import connect
    from tests.test_jev import _answer

    reset_jev_state()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    database = tmp_path / "live_corpus.db"
    posts = _jev_posts()

    monkeypatch.setattr("pipeline.live._collect_posts", lambda *_a, **_k: (list(posts), "bluesky", True))
    calls = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise SpendCapExceeded("stop", spent_usd=Decimal("1.00"))
        return _answer(0.1, "Politics", claim=0.92)

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    monkeypatch.setattr("pipeline.corpus_persist.persist_paid_corpus", lambda *_a, **_k: None)
    config = _heuristic_config(tmp_path / "pipeline.yaml")
    with pytest.raises(SpendCapExceeded):
        run_live(output=tmp_path / "data.json", config=config, db_path=database)
    connection = connect(database)
    assert connection.execute("SELECT COUNT(*) FROM jev_verdicts").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
    connection.close()


def test_hold_edition_git_reset_leaves_staged_halt_corpus(tmp_path, monkeypatch):
    """Staging copies the corpus before hold-edition can restore the git seed."""
    import sqlite3

    from pipeline.corpus_persist import staging_root, stage_halted_corpus, verify_staged_corpus
    from pipeline.store import connect, replace_posts

    monkeypatch.setenv("PERSPECTIVERSE_HALT_STAGING", str(tmp_path / "halt-staging"))
    database = tmp_path / "pipeline" / "data" / "live_corpus.db"
    connection = connect(database)
    replace_posts(
        connection,
        [
            {
                "uri": "at://staged/only",
                "author": "ada",
                "text": "Staged corpus must survive git reset.",
                "clean_text": "Staged corpus must survive git reset.",
                "likes": 1,
                "created_at": "2026-10-16T12:00:00Z",
                "section": "Politics",
                "is_claim": True,
            }
        ],
    )
    connection.close()
    staged_path = stage_halted_corpus(database)
    assert staged_path is not None
    database.unlink()
    assert not database.is_file()
    staged = staging_root() / "live_corpus.db"
    assert verify_staged_corpus(staged)
    rows = sqlite3.connect(staged).execute("SELECT uri FROM posts").fetchall()
    assert rows == [("at://staged/only",)]


def test_prior_fill_rows_of_14_90_halt_the_call_that_would_cross_15(tmp_path, monkeypatch, capsys):
    """$15 is one total for the whole fill. Earlier fill-tagged ledger rows count.

    Per-call checkpoints from earlier fill runs (#186/#188) are already on
    ``costs/ledger.csv``. This run must not start at $0. The paid call that
    would push the total across $15 halts. Once that spend is on the ledger,
    a normal run uses the $0.50 warning and the $1.00 hard stop.
    """
    from datetime import datetime, timezone

    from pipeline.live import _fill_claims_by_day
    from pipeline.spend_cap import day_paid_usd

    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "20000")
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-run-1",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="10.00",
                day=date(2026, 10, 14),
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="fill-run-1-call",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="4.40",
                day=date(2026, 10, 14),
                model="jev-call",
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="fill-run-2-call",
                trigger="workflow_dispatch",
                service=SERVICE_DEEPINFRA,
                cost="0.50",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="schedule-today",
                trigger="schedule",
                service=SERVICE_JEV,
                cost="0.40",
                day=today,
            ),
        ],
    )
    assert fill_paid_usd(ledger) == Decimal("14.90")
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    assert day_paid_usd() == Decimal("14.90")
    guard_before_paid_call("Jev")

    costs = [Decimal("0.09"), Decimal("0.02")]

    def fake_extract(**kwargs):
        since = kwargs["since"]
        day = since.strftime("%Y-%m-%d")
        return [
            {
                "uri": f"at://fill/{day}",
                "author": "ada",
                "text": f"The city should fund public housing on {day} because rents jumped again.",
                "likes": 2,
                "created_at": since.strftime("%Y-%m-%dT12:00:00Z"),
            }
        ]

    def fake_jev(posts, **_kwargs):
        record_attempt(
            service=SERVICE_JEV,
            model="jev-latest",
            input_tokens=100,
            output_tokens=0,
            cost_usd=costs.pop(0),
            cost_source="computed",
            status="success",
        )
        for post in posts:
            post["is_claim"] = True
            post["section"] = "Politics"
        return posts

    monkeypatch.setattr("pipeline.live.extract_posts", fake_extract)
    monkeypatch.setattr("pipeline.live.apply_jev", fake_jev)
    now = datetime(2026, 10, 16, 18, tzinfo=timezone.utc)
    corpus: list[dict] = []
    with pytest.raises(SpendCapExceeded) as caught:
        _fill_claims_by_day(
            [],
            target=100_000,
            settings={"neutral_queries": ["the"], "seed": 0, "window_hours": 168, "jev_batch": False},
            connection=None,
            corpus_posts=corpus,
            now=now,
            clock=lambda: now,
        )
    assert caught.value.spent_usd == Decimal("15.01")
    assert day_paid_usd() == Decimal("15.01")
    assert len(get_meter().attempts()) == 2
    assert [post["uri"] for post in corpus] == ["at://fill/2026-10-16", "at://fill/2026-10-15"]
    with pytest.raises(SpendCapExceeded):
        guard_before_paid_call("Jev")
    assert len(get_meter().attempts()) == 2
    logged = capsys.readouterr().out
    assert "spend $14.99 of $15.00" in logged
    assert "spend $15.01 of $15.00" in logged

    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-run-3",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="0.11",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    reset_meter()
    assert fill_campaign_complete()
    assert warn_usd() == DAILY_WARN_AFTER_FILL_USD == Decimal("0.50")
    assert stop_usd() == DAILY_STOP_AFTER_FILL_USD == Decimal("1.00")
    enforce_before_paid_work()
    _attempt(cost_usd=Decimal("0.10"))
    warned = capsys.readouterr().out
    assert "warn $0.50" in warned
    assert "stop $1.00" in warned
    with pytest.raises(SpendCapExceeded) as daily:
        _attempt(cost_usd=Decimal("0.50"))
    assert daily.value.spent_usd == Decimal("1.00")


def test_fill_cap_sums_tagged_ledger_across_utc_days(tmp_path, monkeypatch):
    """Fill spend is the fill-tagged ledger total, not one UTC day."""
    today = date(2026, 10, 16)
    yesterday = date(2026, 10, 15)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-yesterday",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="12.00",
                day=yesterday,
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="not-fill",
                trigger="schedule",
                service=SERVICE_JEV,
                cost="0.90",
                day=today,
            ),
        ],
    )
    assert fill_paid_usd(ledger) == Decimal("12.00")
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    with pytest.raises(SpendCapExceeded) as caught:
        _attempt(cost_usd=Decimal("3.01"))
    assert caught.value.spent_usd == Decimal("15.01")
    assert FILL_BUDGET_TOTAL_USD == Decimal("15.00")


def test_fill_run_hard_stop_is_the_15_dollar_total(tmp_path, monkeypatch):
    """A fill run that is already past $1 keeps calling. The hard stop is $15."""
    from pipeline.spend_cap import day_paid_usd

    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-past-daily",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="1.50",
                day=today,
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    assert is_fill_run()
    assert stop_usd() == FILL_BUDGET_TOTAL_USD == Decimal("15.00")
    guard_before_paid_call("Jev")
    _attempt(cost_usd=Decimal("0.10"))
    assert day_paid_usd() == Decimal("1.60")


def test_fill_dispatch_refused_when_corpus_full_or_fill_spent(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-done",
                trigger="workflow_dispatch",
                service=SERVICE_DEEPINFRA,
                cost="15.00",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "12000")
    assert check_fill_dispatch() == 1
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    assert stop_usd() == DAILY_STOP_AFTER_FILL_USD
    assert warn_usd() == DAILY_WARN_AFTER_FILL_USD

    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "100000")
    assert check_fill_dispatch() == 1
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    assert stop_usd() == DAILY_STOP_AFTER_FILL_USD
    assert warn_usd() == DAILY_WARN_AFTER_FILL_USD


def test_fill_exhausted_before_100k_halts_and_returns_normal_daily_cap(tmp_path, monkeypatch, capsys):
    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "25000")
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-partial",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="14.99",
                day=today,
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    with pytest.raises(SpendCapExceeded):
        _attempt(cost_usd=Decimal("0.02"))
    captured = capsys.readouterr()
    assert "Fill budget exhausted" in captured.err
    assert "25,000 quality posts" in captured.err
    assert "75,000 short of 100,000" in captured.err
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-final",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="0.02",
                day=today,
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.delenv("PERSPECTIVERSE_FILL_RUN", raising=False)
    assert stop_usd() == DAILY_STOP_AFTER_FILL_USD
    assert warn_usd() == DAILY_WARN_AFTER_FILL_USD


def test_after_fill_campaign_utc_day_warns_at_fifty_cents_stops_at_one_dollar(
    tmp_path, monkeypatch, capsys
):
    """Post-fill daily cap: UTC-day ledger spend warns at $0.50 and hard-stops at $1.00."""
    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-done",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="15.00",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="schedule-today",
                trigger="schedule",
                service=SERVICE_DEEPINFRA,
                cost="0.50",
                day=today,
            ),
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "50000")
    assert fill_campaign_complete()
    assert stop_usd() == DAILY_STOP_AFTER_FILL_USD
    assert warn_usd() == DAILY_WARN_AFTER_FILL_USD

    reset_meter()
    enforce_before_paid_work()
    captured = capsys.readouterr()
    assert "::warning::" in captured.out
    assert "warn $0.50" in captured.out
    assert "stop $1.00" in captured.out

    _attempt(cost_usd=Decimal("0.49"))
    capsys.readouterr()
    with pytest.raises(SpendCapExceeded) as caught:
        _attempt(cost_usd=Decimal("0.01"))
    assert caught.value.spent_usd == Decimal("1.00")
    assert len(get_meter().attempts()) == 2


def test_non_fill_run_still_uses_daily_cap_not_fill_total(tmp_path, monkeypatch):
    today = date(2026, 10, 16)
    monkeypatch.setattr("pipeline.spend_cap.utc_today", lambda: today)
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-yesterday",
                trigger="workflow_dispatch",
                service=SERVICE_JEV,
                cost="4.50",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            ),
            _ledger_row(
                run_id="schedule-today",
                trigger="schedule",
                service=SERVICE_JEV,
                cost="0.50",
                day=today,
            ),
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    reset_meter()
    enforce_before_paid_work()
    with pytest.raises(SpendCapExceeded):
        _attempt(cost_usd=Decimal("0.51"))
    assert stop_usd() == DAILY_STOP_USD


def test_fill_run_logs_planet_count_and_labeling_calls(monkeypatch, capsys):
    from pipeline.live import _log_fill_run_summary

    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    record_attempt(
        service=SERVICE_DEEPINFRA,
        model="unit",
        input_tokens=1,
        output_tokens=1,
        cost_usd=Decimal("0.01"),
        cost_source="reported",
        status="success",
    )
    payload = {"topics": [{"id": 1}], "sections": {"Politics": [{"id": 2}]}}
    _log_fill_run_summary(payload)
    captured = capsys.readouterr()
    assert "Fill run: 2 published planet(s), 1 labeling call(s)." in captured.out


def test_fill_done_check_is_quality_posts(monkeypatch, capsys):
    """The fill is done at 100K quality posts. A lower claim count does not finish it."""
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "30000")
    assert fill_campaign_complete() is False
    assert check_fill_dispatch() == 0

    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "100000")
    assert fill_campaign_complete() is True
    assert check_fill_dispatch() == 1
    logged = capsys.readouterr().err
    assert "100,000 quality posts" in logged
    assert "target 100,000" in logged


def test_fill_dispatch_check_runs_after_ledger_load():
    """Fill refusal must see fill-tagged spend on data-snapshot, not an empty ledger."""
    steps = _pipeline_workflow_steps()
    names = [step.get("name") for step in steps]
    ledger_at = names.index("Load today's cost ledger for the spend cap")
    refuse_at = names.index("Refuse fill dispatch when the fill campaign is complete")
    live_at = next(index for index, step in enumerate(steps) if step.get("id") == "live")
    assert ledger_at < refuse_at < live_at
    ledger_step = steps[ledger_at]
    assert "PERSPECTIVERSE_COST_LEDGER" in ledger_step["run"]
    assert "data-snapshot:costs/ledger.csv" in ledger_step["run"]
    workflow_text = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "timeout-minutes: 360" in workflow_text
    drop_at = names.index("Drop stored spam and non-claims whose verdicts are cached")
    counts_at = names.index("Corpus quality-post count for the fill done check")
    assert drop_at < counts_at < refuse_at
    assert "drop-non-quality" in steps[drop_at]["run"]
    assert "count-quality" in steps[counts_at]["run"]
    assert "PERSPECTIVERSE_CORPUS_CLAIM_COUNT=$count" in steps[counts_at]["run"]


def test_check_fill_dispatch_refuses_when_ledger_shows_five_dollars_fill_spend(
    tmp_path, monkeypatch
):
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-done",
                trigger="workflow_dispatch",
                service=SERVICE_DEEPINFRA,
                cost="15.00",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "12000")
    assert check_fill_dispatch() == 1


def test_check_fill_dispatch_without_ledger_env_ignores_prior_fill_spend(monkeypatch, tmp_path):
    """Documents why the workflow must set PERSPECTIVERSE_COST_LEDGER before the check step."""
    ledger = tmp_path / "ledger.csv"
    append_ledger(
        ledger,
        [
            _ledger_row(
                run_id="fill-done",
                trigger="workflow_dispatch",
                service=SERVICE_DEEPINFRA,
                cost="15.00",
                day=date(2026, 10, 15),
                tags=LEDGER_TAG_FILL,
            )
        ],
    )
    monkeypatch.setenv("PERSPECTIVERSE_FILL_RUN", "1")
    monkeypatch.setenv("PERSPECTIVERSE_CORPUS_CLAIM_COUNT", "12000")
    monkeypatch.delenv("PERSPECTIVERSE_COST_LEDGER", raising=False)
    assert check_fill_dispatch() == 0
    monkeypatch.setenv("PERSPECTIVERSE_COST_LEDGER", str(ledger))
    assert check_fill_dispatch() == 1


def test_over_cap_e2e_halts_before_publish():
    script = Path("scripts/spend_cap_over_cap_e2e.py")
    result = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode == 14, combined
    assert "pipeline_exit: 14" in result.stdout
    assert "edition_unchanged: yes" in result.stdout
    assert "remote_edition_unchanged: yes" in result.stdout
    assert "e2e_result: halted_before_publish" in result.stdout
    assert "pipeline_complete_logged: no" in result.stdout
