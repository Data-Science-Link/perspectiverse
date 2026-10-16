"""Daily spend cap: warn and hard stop at $1.00 UTC-day total, do not publish (#148, #182)."""

from __future__ import annotations

import json
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
    DAILY_STOP_USD,
    DAILY_WARN_USD,
    STOP_EXIT,
    SpendCapExceeded,
    enforce_before_paid_work,
    guard_before_paid_call,
    hold_edition,
    record_partial_ledger,
)


@pytest.fixture(autouse=True)
def _isolated_cap(monkeypatch):
    monkeypatch.delenv("PERSPECTIVERSE_DAILY_SPEND_WARN", raising=False)
    monkeypatch.delenv("PERSPECTIVERSE_DAILY_SPEND_STOP", raising=False)
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


def _ledger_row(*, run_id: str, trigger: str, service: str, cost: str, day: date, model: str = "unit") -> dict:
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


def test_workflow_stops_publish_unless_the_live_step_succeeds():
    text = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "PERSPECTIVERSE_COST_LEDGER" in text
    assert "pipeline.spend_cap hold-edition" in text
    assert "record-partial-ledger" in text
    assert "spend_cap_stop.json" in text
    assert "steps.live.outcome == 'success'" in text
    assert "save-always: true" in text
    stage_at = text.index("name: Stage halted corpus before ledger git checkout")
    hold_at = text.index("name: Keep yesterday's edition when the daily spend cap stops the run")
    upload_at = text.index("name: Upload halted corpus to R2")
    assert stage_at < upload_at < hold_at
    assert "corpus_persist upload-staged" in text
    assert "steps.live.outcome == 'cancelled'" in text


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
    assert calls["n"] == 2
    assert {row[0] for row in rows} == {"at://fixture/jev/0"}


def test_spend_cap_halt_mid_jev_persists_corpus_and_reuses_verdicts(tmp_path, monkeypatch):
    """Halt inside Jev keeps posts and verdicts; the next apply_jev makes no paid calls."""
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
    assert connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 3
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
