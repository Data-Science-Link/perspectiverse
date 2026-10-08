"""Paid-call cost meter, Jev price, and the weekly ledger."""

from __future__ import annotations

import io
import threading
import urllib.error
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from pipeline.costs import (
    CHART_PATH,
    LEDGER_COLUMNS,
    LEDGER_PATH,
    LEGACY_LEDGER_COLUMNS,
    README_PATH,
    SERVICE_DEEPINFRA,
    SERVICE_JEV,
    SERVICE_R2,
    CostLedgerError,
    append_ledger,
    append_run_files,
    count_published_planets,
    format_axis_tick_usd,
    format_chart_usd,
    format_ledger_usd,
    format_usd,
    get_meter,
    iso_week_label,
    jev_cost_usd,
    main,
    r2_billed_increment_usd,
    r2_ledger_row,
    r2_list_price_usd,
    r2_month_bill_usd,
    read_ledger,
    render_daily_spend_svg,
    render_readme,
    reset_meter,
    rows_for_attempts,
    run_identity,
    weekly_rollup,
    write_cost_run,
)
from pipeline.http_json import read_json
from pipeline.jev import _post_systemone
from pipeline.label import _openai_generate


@pytest.fixture(autouse=True)
def _clean_meter(monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    reset_meter()
    yield
    reset_meter()


def test_meter_totals_under_threads():
    threads = 8
    per_thread = 200
    barrier = threading.Barrier(threads, timeout=5)
    failures_each = per_thread // 5

    def work():
        barrier.wait()
        for n in range(per_thread):
            from pipeline.costs import record_attempt

            failed = n % 5 == 0
            record_attempt(
                service=SERVICE_DEEPINFRA,
                model="unit-test-llm",
                input_tokens=2,
                output_tokens=1,
                cost_usd=Decimal("0.0000001"),
                cost_source="reported",
                status="failure" if failed else "success",
            )

    workers = [threading.Thread(target=work) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    rows = rows_for_attempts(
        get_meter().attempts(),
        identity=run_identity(datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)),
        posts_processed=1000,
        planets_published=4,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["calls"] == str(threads * per_thread)
    assert row["failed_calls"] == str(threads * failures_each)
    assert row["input_tokens"] == str(threads * per_thread * 2)
    assert row["output_tokens"] == str(threads * per_thread)
    assert Decimal(row["cost_usd"]) == Decimal("0.0000001") * threads * per_thread
    assert row["service"] == SERVICE_DEEPINFRA
    assert row["posts_processed"] == "1000"
    assert row["planets_published"] == "4"


def test_jev_cost_uses_input_tokens_only(monkeypatch):
    assert jev_cost_usd(1_000_000) == Decimal("0.042")
    assert jev_cost_usd(500_000) == Decimal("0.021")
    assert jev_cost_usd(0) == Decimal("0")
    assert jev_cost_usd(500) == Decimal("0.000021")

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("JEV_MODEL", "jev-latest")

    def fake(url, **kwargs):
        return {
            "model": "jev-1.13.0",
            "usage": {"input_tokens": 1_000_000, "output_tokens": 80},
            "answers": {},
        }

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    payload = _post_systemone("a public claim about housing")
    assert payload["model"] == "jev-1.13.0"
    attempt = get_meter().attempts()[0]
    assert attempt.service == SERVICE_JEV
    assert attempt.model == "jev-1.13.0"
    assert attempt.input_tokens == 1_000_000
    assert attempt.output_tokens == 80
    assert attempt.cost_usd == Decimal("0.042")
    assert attempt.cost_source == "computed"
    assert attempt.status == "success"


def test_jev_missing_usage_counts_the_call_at_zero(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("JEV_MODEL", "jev-latest")

    def fake(url, **kwargs):
        return {"model": "jev-1.13.0", "answers": {}}

    monkeypatch.setattr("pipeline.jev.read_json", fake)
    _post_systemone("hello")
    attempt = get_meter().attempts()[0]
    assert attempt.cost_usd == Decimal("0")
    assert attempt.input_tokens == 0
    assert attempt.output_tokens == 0
    assert attempt.model == "jev-1.13.0"


def test_openai_generate_parses_estimated_cost_and_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unit-test.deepinfra.com/v1")
    responses = [
        {
            "model": "unit-test-llm",
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "estimated_cost": 0.00125,
            },
            "choices": [{"message": {"content": "one"}}],
        },
        {
            "model": "unit-test-llm",
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
            "choices": [{"message": {"content": "two"}}],
        },
    ]

    def fake(url, *, timeout, data=None, headers=None):
        return responses.pop(0)

    monkeypatch.setattr("pipeline.label.read_json", fake)
    assert _openai_generate("a", "requested-model") == "one"
    assert _openai_generate("b", "requested-model") == "two"
    first, second = get_meter().attempts()
    assert first.service == SERVICE_DEEPINFRA
    assert first.model == "unit-test-llm"
    assert first.input_tokens == 12
    assert first.output_tokens == 4
    assert first.cost_usd == Decimal("0.00125")
    assert first.cost_source == "reported"
    assert first.status == "success"
    assert second.cost_usd == Decimal("0")
    assert second.input_tokens == 8
    assert second.output_tokens == 3
    assert second.status == "success"


def test_openai_generate_counts_retries_and_keeps_reported_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unit-test.deepinfra.com/v1")
    calls = {"n": 0}

    def fake(url, *, timeout, data=None, headers=None):
        calls["n"] += 1
        if calls["n"] < 3:
            error = RuntimeError("HTTP 429 from api.deepinfra.com")
            error.payload = {
                "model": "unit-test-llm",
                "usage": {"prompt_tokens": 5, "completion_tokens": 0, "estimated_cost": "0.0001"},
            }
            raise error
        return {
            "model": "unit-test-llm",
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "estimated_cost": "0.0004"},
            "choices": [{"message": {"content": "ok"}}],
        }

    monkeypatch.setattr("pipeline.label.read_json", fake)
    monkeypatch.setattr("pipeline.label.time.sleep", lambda seconds: None)
    assert _openai_generate("hello", "unit-test-llm") == "ok"
    attempts = get_meter().attempts()
    assert [item.status for item in attempts] == ["retry", "retry", "success"]
    rows = rows_for_attempts(
        attempts,
        identity=run_identity(datetime(2026, 10, 8, tzinfo=timezone.utc)),
        posts_processed=10,
        planets_published=2,
    )
    assert rows[0]["calls"] == "3"
    assert rows[0]["failed_calls"] == "2"
    assert Decimal(rows[0]["cost_usd"]) == Decimal("0.0006")
    assert rows[0]["input_tokens"] == "15"


def test_meter_failure_does_not_fail_the_label_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")

    def boom(**kwargs):
        raise RuntimeError("meter down")

    def fake(url, *, timeout, data=None, headers=None):
        return {"choices": [{"message": {"content": "still labeled"}}]}

    monkeypatch.setattr("pipeline.costs.record_llm_attempt", boom)
    monkeypatch.setattr("pipeline.label.read_json", fake)
    assert _openai_generate("hello", "model") == "still labeled"


def test_append_preserves_earlier_rows(tmp_path):
    ledger = tmp_path / "ledger.csv"
    earlier = {
        "run_id": "earlier-run",
        "run_started_utc": "2026-10-01T06:00:00Z",
        "date_utc": "2026-10-01",
        "trigger": "schedule",
        "service": SERVICE_DEEPINFRA,
        "model": "unit-test-llm",
        "calls": 4,
        "failed_calls": 1,
        "input_tokens": 100,
        "output_tokens": 40,
        "cost_usd": Decimal("0.0100"),
        "cost_source": "reported",
        "posts_processed": 800,
        "planets_published": 6,
    }
    append_ledger(ledger, [earlier])
    original = ledger.read_text(encoding="utf-8")
    added = dict(earlier)
    added["run_id"] = "later-run"
    added["date_utc"] = "2026-10-08"
    added["cost_usd"] = Decimal("0.0200")
    append_ledger(ledger, [added])
    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(original)
    rows = read_ledger(ledger)
    assert [row["run_id"] for row in rows] == ["earlier-run", "later-run"]
    assert rows[0]["cost_usd"] == "0.01"
    assert rows[0]["posts_processed"] == "800"
    assert rows[1]["cost_usd"] == "0.02"
    assert list(rows[0]) == LEDGER_COLUMNS


def test_append_refuses_to_rewrite_a_foreign_header(tmp_path):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("not,the,header\n1,2,3\n", encoding="utf-8")
    before = ledger.read_bytes()
    with pytest.raises(CostLedgerError):
        append_ledger(
            ledger,
            [
                {
                    "run_id": "new",
                    "run_started_utc": "2026-10-08T00:00:00Z",
                    "date_utc": "2026-10-08",
                    "trigger": "local",
                    "service": SERVICE_JEV,
                    "model": "jev-1.13.0",
                    "calls": 1,
                    "failed_calls": 0,
                    "input_tokens": 10,
                    "output_tokens": 0,
                    "cost_usd": Decimal("0"),
                    "cost_source": "computed",
                    "posts_processed": 1,
                    "planets_published": 1,
                }
            ],
        )
    assert ledger.read_bytes() == before


def test_weekly_rollup_counts_each_run_once():
    rows = [
        _row("run-a", "2026-10-05", SERVICE_DEEPINFRA, "1.50", 1000, 10),
        _row("run-a", "2026-10-05", SERVICE_JEV, "0.042", 1000, 10),
        _row("run-b", "2026-10-06", SERVICE_DEEPINFRA, "0.50", 500, 2),
        _row("old", "2026-08-01", SERVICE_DEEPINFRA, "9.00", 4000, 8),
    ]
    weeks, recent = weekly_rollup(rows, today=date(2026, 10, 8))
    assert [label for label, _totals in weeks] == [
        iso_week_label(date(2026, 10, 5)),
        iso_week_label(date(2026, 8, 1)),
    ]
    assert iso_week_label(date(2026, 10, 5)) == iso_week_label(date(2026, 10, 6))
    current = weeks[0][1]
    assert current.runs == 2
    assert current.llm_usd == Decimal("2.00")
    assert current.jev_usd == Decimal("0.042")
    assert current.total_usd == Decimal("2.042")
    assert current.posts_processed == 1500
    assert current.planets_published == 12
    assert current.per_thousand_posts == Decimal("2.042") / Decimal(1500) * Decimal(1000)
    assert current.per_planet == Decimal("2.042") / Decimal(12)
    assert weeks[1][1].runs == 1
    assert weeks[1][1].total_usd == Decimal("9.00")
    assert recent.runs == 2
    assert recent.total_usd == Decimal("2.042")
    assert recent.posts_processed == 1500
    assert recent.llm_usd + recent.jev_usd + recent.r2_usd == recent.total_usd

    readme = render_readme(rows, today=date(2026, 10, 8))
    assert "input tokens × $0.042 per 1,000,000" in readme
    assert "2026-10-08" in readme
    assert "2026-09-08" in readme
    assert iso_week_label(date(2026, 10, 5)) in readme
    assert "1.36133333" in readme
    assert "public/" in readme


def test_run_file_appends_without_dropping_history(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "sample-run-80")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    started = datetime(2026, 10, 8, 6, 1, 2, tzinfo=timezone.utc)
    from pipeline.costs import record_attempt

    record_attempt(
        service=SERVICE_DEEPINFRA,
        model="unit-test-llm",
        input_tokens=100,
        output_tokens=20,
        cost_usd=Decimal("0.00125"),
        cost_source="reported",
        status="success",
    )
    record_attempt(
        service=SERVICE_JEV,
        model="jev-1.13.0",
        input_tokens=1_000_000,
        output_tokens=4,
        cost_usd=jev_cost_usd(1_000_000),
        cost_source="computed",
        status="success",
    )
    run_path = tmp_path / "cost_run.json"
    write_cost_run(
        posts_processed=1000,
        planets_published=4,
        started_at=started,
        path=run_path,
    )
    ledger = tmp_path / "ledger.csv"
    readme = tmp_path / "README.md"
    append_ledger(
        ledger,
        [
            _row("already-there", "2026-10-01", SERVICE_JEV, "0.021", 200, 3),
        ],
    )
    assert append_run_files(run_path, ledger, readme) == 0
    rows = read_ledger(ledger)
    assert [row["run_id"] for row in rows] == ["already-there", "sample-run-80", "sample-run-80"]
    assert rows[0]["cost_usd"] == "0.021"
    fresh = [row for row in rows if row["run_id"] == "sample-run-80"]
    assert {row["service"] for row in fresh} == {SERVICE_DEEPINFRA, SERVICE_JEV}
    assert fresh[0]["trigger"] == "workflow_dispatch"
    assert fresh[0]["posts_processed"] == "1000"
    assert fresh[0]["planets_published"] == "4"
    text = readme.read_text(encoding="utf-8")
    assert "MOCK" not in text
    assert "0.042" in text
    assert main(["append", "--run", str(run_path), "--ledger", str(ledger), "--readme", str(readme)]) == 0
    assert [row["run_id"] for row in read_ledger(ledger)].count("sample-run-80") == 4


def test_empty_run_does_not_create_a_ledger(tmp_path):
    run_path = tmp_path / "cost_run.json"
    write_cost_run(
        posts_processed=3,
        planets_published=1,
        started_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        path=run_path,
        attempts=(),
    )
    ledger = tmp_path / "ledger.csv"
    readme = tmp_path / "README.md"
    assert append_run_files(run_path, ledger, readme) == 0
    assert not ledger.exists()
    assert not readme.exists()


def test_run_identity_github_and_local(monkeypatch):
    moment = datetime(2026, 10, 8, 6, 0, 1, tzinfo=timezone.utc)
    monkeypatch.setenv("GITHUB_RUN_ID", "4242")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    github = run_identity(moment)
    assert github == {
        "run_id": "4242",
        "run_started_utc": "2026-10-08T06:00:01Z",
        "date_utc": "2026-10-08",
        "trigger": "schedule",
    }
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    assert run_identity(moment)["run_id"] == "4242"
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert run_identity(moment)["run_id"] == "4242.2"
    monkeypatch.delenv("GITHUB_RUN_ID")
    monkeypatch.delenv("GITHUB_EVENT_NAME")
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT")
    local = run_identity(moment)
    assert local["run_id"] == "local-20261008T060001Z"
    assert local["trigger"] == "local"


def test_published_planets_include_sections_and_files_stay_off_the_site():
    payload = {
        "total_posts": 40,
        "topics": [{}, {}],
        "sections": {"Health": [{}], "Sports": [{}, {}]},
    }
    assert count_published_planets(payload) == 5
    assert count_published_planets({"topics": []}) == 0
    assert LEDGER_PATH.parts[0] == "costs"
    assert README_PATH.parts[0] == "costs"
    assert CHART_PATH.parts[0] == "costs"
    assert CHART_PATH.name == "daily_spend_14d.svg"
    assert "public" not in LEDGER_PATH.parts
    assert "public" not in README_PATH.parts
    assert "public" not in CHART_PATH.parts
    readme = Path("README.md").read_text(encoding="utf-8")
    assert (
        "https://raw.githubusercontent.com/Data-Science-Link/perspectiverse/data-snapshot/costs/daily_spend_14d.svg"
        in readme
    )
    assert "costs/README.md" in readme
    assert "appears after the next pipeline run" not in readme
    assert "live chart" in readme


def test_http_error_keeps_usage_for_the_meter(monkeypatch):
    body = io.BytesIO(
        b'{"model":"unit-test-llm",'
        b'"usage":{"prompt_tokens":9,"completion_tokens":1,"estimated_cost":0.0002},'
        b'"choices":[{"message":{"content":"should not be required"}}]}'
    )
    error = urllib.error.HTTPError(
        "https://api.deepinfra.com/v1/chat/completions",
        429,
        "Too Many Requests",
        hdrs=None,
        fp=body,
    )

    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr("pipeline.http_json.urllib.request.urlopen", boom)
    with pytest.raises(RuntimeError, match="HTTP 429 from api.deepinfra.com") as caught:
        read_json("https://api.deepinfra.com/v1/chat/completions", timeout=1, data=b"{}")
    payload = caught.value.payload
    assert payload["model"] == "unit-test-llm"
    assert payload["usage"]["estimated_cost"] == 0.0002
    assert "choices" not in payload


def test_zero_posts_render_as_not_applicable():
    rows = [_row("run-a", "2026-10-08", SERVICE_DEEPINFRA, "1.00", 0, 0)]
    _weeks, recent = weekly_rollup(rows, today=date(2026, 10, 8))
    assert recent.per_thousand_posts is None
    assert recent.per_planet is None
    assert "n/a" in render_readme(rows, today=date(2026, 10, 8))
    assert format_usd(Decimal("0.042")) == "0.042"
    assert format_usd(Decimal("2")) == "2.00"


def test_format_chart_usd_prefixes_dollars_and_rounds():
    assert format_chart_usd(Decimal("0")) == "$0.00"
    assert format_chart_usd(Decimal("0.20")) == "$0.20"
    assert format_chart_usd(Decimal("0.20065354")) == "$0.20"
    assert format_chart_usd(Decimal("1.542")) == "$1.54"
    assert format_chart_usd(Decimal("0.000021")) == "$0.000021"
    assert format_chart_usd(Decimal("0.00999")) == "$0.01"
    assert format_axis_tick_usd(Decimal("0.125")) == "$0.125"
    assert format_axis_tick_usd(Decimal("0.375")) == "$0.375"
    assert format_axis_tick_usd(Decimal("0.5")) == "$0.50"


def test_ledger_usd_rounds_to_eight_decimals_on_write(tmp_path):
    ledger = tmp_path / "ledger.csv"
    noisy = Decimal("0.101658500000000001872")
    append_ledger(
        ledger,
        [
            {
                "run_id": "noise-run",
                "run_started_utc": "2026-10-08T06:00:00Z",
                "date_utc": "2026-10-08",
                "trigger": "schedule",
                "service": SERVICE_DEEPINFRA,
                "model": "unit-test-llm",
                "calls": 1,
                "failed_calls": 0,
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": noisy,
                "cost_source": "reported",
                "posts_processed": 1,
                "planets_published": 1,
                "list_price_usd": noisy,
            }
        ],
    )
    assert format_ledger_usd(noisy) == "0.1016585"
    rows = read_ledger(ledger)
    assert rows[0]["cost_usd"] == "0.1016585"
    assert rows[0]["list_price_usd"] == "0.1016585"
    assert "000000001872" not in ledger.read_text(encoding="utf-8")


def test_r2_list_price_prorates_a_gb_month_and_prices_operations():
    from pipeline.costs import (
        R2_USD_PER_GB_MONTH,
        R2_USD_PER_MILLION_CLASS_A,
        R2_USD_PER_MILLION_CLASS_B,
    )

    one_gb_day = r2_list_price_usd(storage_bytes=1_000_000_000, class_a_ops=0, class_b_ops=0)
    assert one_gb_day == R2_USD_PER_GB_MONTH / Decimal(30)
    assert r2_list_price_usd(storage_bytes=0, class_a_ops=1_000_000, class_b_ops=0) == R2_USD_PER_MILLION_CLASS_A
    assert r2_list_price_usd(storage_bytes=0, class_a_ops=0, class_b_ops=1_000_000) == R2_USD_PER_MILLION_CLASS_B
    combined = r2_list_price_usd(storage_bytes=1_000_000_000, class_a_ops=1_000_000, class_b_ops=1_000_000)
    assert combined == one_gb_day + R2_USD_PER_MILLION_CLASS_A + R2_USD_PER_MILLION_CLASS_B


def test_r2_free_tier_bills_only_the_increment_above_the_allowance():
    fifteen_gb = 15_000_000_000
    first = _r2_row("2026-10-01", fifteen_gb, class_a=0, class_b=0)
    assert r2_month_bill_usd([first], as_of=date(2026, 10, 1)) == 0
    # 15 GB for 20 days is exactly 10 GB-month, still inside the free tier.
    assert (
        r2_billed_increment_usd(
            [first],
            run_day=date(2026, 10, 20),
            storage_bytes=fifteen_gb,
            class_a_ops=0,
            class_b_ops=0,
        )
        == 0
    )
    prior = [first, _r2_row("2026-10-20", fifteen_gb, class_a=0, class_b=0)]
    # The 21st day is 0.5 GB-month over the 10 GB-month allowance.
    assert r2_billed_increment_usd(
        prior,
        run_day=date(2026, 10, 21),
        storage_bytes=fifteen_gb,
        class_a_ops=0,
        class_b_ops=0,
    ) == Decimal("0.015") * Decimal("0.5")

    class_a_prior = [_r2_row("2026-10-01", 0, class_a=900_000, class_b=0)]
    assert r2_billed_increment_usd(
        class_a_prior,
        run_day=date(2026, 10, 2),
        storage_bytes=0,
        class_a_ops=200_000,
        class_b_ops=0,
    ) == Decimal("4.50") * Decimal(100_000) / Decimal(1_000_000)

    class_b_prior = [_r2_row("2026-10-01", 0, class_a=0, class_b=10_000_000)]
    assert r2_billed_increment_usd(
        class_b_prior,
        run_day=date(2026, 10, 2),
        storage_bytes=0,
        class_a_ops=0,
        class_b_ops=1_000_000,
    ) == Decimal("0.36")

    # A measurement from the previous month still occupies the bucket.
    september = [_r2_row("2026-09-30", 20_000_000_000, class_a=0, class_b=0)]
    october = r2_billed_increment_usd(
        september,
        run_day=date(2026, 10, 30),
        storage_bytes=20_000_000_000,
        class_a_ops=0,
        class_b_ops=0,
    )
    assert october == Decimal("0.15")

    identity = {
        "run_id": "r2-free",
        "run_started_utc": "2026-10-08T06:00:00Z",
        "date_utc": "2026-10-08",
        "trigger": "schedule",
    }
    row = r2_ledger_row(
        [],
        identity=identity,
        posts_processed=10,
        planets_published=1,
        usage={
            "class_a_ops": 1,
            "class_b_ops": 2,
            "storage_bytes": 1_000_000_000,
            "storage_known": True,
        },
    )
    assert row is not None
    assert row["service"] == SERVICE_R2
    assert row["model"] == "r2-standard"
    assert row["cost_source"] == "computed"
    assert Decimal(row["cost_usd"]) == 0
    assert Decimal(row["list_price_usd"]) > 0
    assert row["storage_bytes"] == "1000000000"
    assert row["class_a_ops"] == "1"
    assert row["class_b_ops"] == "2"


def test_r2_increments_reconstruct_the_month_bill_and_same_day_replacement():
    events = [
        (date(2026, 10, 1), 15_000_000_000, 900_000, 0),
        (date(2026, 10, 20), 15_000_000_000, 200_000, 0),
        (date(2026, 10, 21), 15_000_000_000, 0, 50),
    ]
    rows: list[dict[str, str]] = []
    billed = Decimal(0)
    for day, storage, class_a, class_b in events:
        billed += r2_billed_increment_usd(
            rows,
            run_day=day,
            storage_bytes=storage,
            class_a_ops=class_a,
            class_b_ops=class_b,
        )
        rows.append(_r2_row(day.isoformat(), storage, class_a=class_a, class_b=class_b))
    assert billed == r2_month_bill_usd(rows, as_of=date(2026, 10, 21))

    first = _r2_row("2026-10-08", 600_000_000_000, class_a=0, class_b=0)
    assert r2_month_bill_usd([first], as_of=date(2026, 10, 8)) == Decimal("0.15")
    shrunk = r2_billed_increment_usd(
        [first],
        run_day=date(2026, 10, 8),
        storage_bytes=300_000_000_000,
        class_a_ops=10,
        class_b_ops=0,
    )
    assert shrunk == Decimal("-0.15")
    recorded = r2_ledger_row(
        [first],
        identity={
            "run_id": "r2-shrink",
            "run_started_utc": "2026-10-08T07:00:00Z",
            "date_utc": "2026-10-08",
            "trigger": "schedule",
        },
        posts_processed=1,
        planets_published=1,
        usage={
            "class_a_ops": 10,
            "class_b_ops": 0,
            "storage_bytes": 300_000_000_000,
            "storage_known": True,
        },
    )
    assert recorded is not None
    assert Decimal(recorded["cost_usd"]) == 0
    assert Decimal(recorded["list_price_usd"]) > 0
    assert "rather than a credit" in render_readme([first, recorded], today=date(2026, 10, 8))
    poison = dict(recorded)
    poison["run_id"] = "poison"
    poison["cost_usd"] = "-4"
    _weeks, recent = weekly_rollup([poison], today=date(2026, 10, 8))
    assert recent.r2_usd == 0
    assert recent.total_usd == 0
    from pipeline.costs import daily_spend

    series = daily_spend([poison], today=date(2026, 10, 8))
    assert all(Decimal(item["r2"]) >= 0 for item in series)


def test_daily_spend_svg_is_fourteen_days_with_gaps_and_valid_xml():
    import xml.etree.ElementTree as ET

    today = date(2026, 10, 8)
    rows = [
        _row("run-a", "2026-10-08", SERVICE_DEEPINFRA, "1.50", 10, 1),
        _row("run-a", "2026-10-08", SERVICE_JEV, "0.042", 10, 1),
        _row("run-b", "2026-10-03", SERVICE_R2, "0.25", 10, 1),
    ]
    text = render_daily_spend_svg(rows, today=today)
    root = ET.parse(io.StringIO(text)).getroot()
    assert root.tag.endswith("svg")
    groups = [element for element in root.iter() if element.tag.endswith("g") and element.get("data-date")]
    assert len(groups) == 14
    by_date = {element.get("data-date"): element for element in groups}
    assert list(by_date)[0] == "2026-09-25"
    assert list(by_date)[-1] == "2026-10-08"
    gap = by_date["2026-10-01"]
    assert gap.get("data-llm") == "0"
    assert gap.get("data-jev") == "0"
    assert gap.get("data-r2") == "0"
    assert gap.get("data-total") == "0"
    present = by_date["2026-10-08"]
    assert Decimal(present.get("data-llm")) == Decimal("1.50")
    assert Decimal(present.get("data-jev")) == Decimal("0.042")
    assert Decimal(present.get("data-r2")) == Decimal("0")
    assert Decimal(present.get("data-total")) == Decimal("1.542")
    assert Decimal(by_date["2026-10-03"].get("data-r2")) == Decimal("0.25")
    labels = [element.text for element in root.iter() if element.tag.endswith("text")]
    assert "LLM labeling" in labels
    assert "Jev" in labels
    assert "R2" in labels
    assert "UTC day" in labels
    assert "$1.54" in labels
    assert "$0.25" in labels
    assert _money_chart_labels(labels) == {label for label in labels if label and label.startswith("$")}
    assert text.startswith("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")


def test_daily_spend_svg_axis_ticks_show_unrounded_scale_at_half_dollar_max():
    import xml.etree.ElementTree as ET

    today = date(2026, 10, 8)
    rows = [_row("run-a", "2026-10-08", SERVICE_R2, "0.40", 10, 1)]
    text = render_daily_spend_svg(rows, today=today)
    labels = [
        element.text
        for element in ET.parse(io.StringIO(text)).getroot().iter()
        if element.tag.endswith("text")
    ]
    assert "$0.125" in labels
    assert "$0.375" in labels
    assert "$0.50" in labels
    assert _money_chart_labels(labels) == {label for label in labels if label and label.startswith("$")}


def test_legacy_header_migrates_without_dropping_rows(tmp_path):
    import csv

    ledger = tmp_path / "ledger.csv"

    def line(run_id: str, cost: str) -> dict[str, str]:
        return {
            "run_id": run_id,
            "run_started_utc": "2026-10-01T06:00:00Z",
            "date_utc": "2026-10-01",
            "trigger": "schedule",
            "service": SERVICE_JEV,
            "model": "jev-1.13.0",
            "calls": "1",
            "failed_calls": "0",
            "input_tokens": "500000",
            "output_tokens": "2",
            "cost_usd": cost,
            "cost_source": "computed",
            "posts_processed": "200",
            "planets_published": "3",
        }

    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEGACY_LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(line("old-a", "0.021"))
        writer.writerow(line("old-b", "0.0100"))
    before = ledger.read_bytes()
    peeked = read_ledger(ledger)
    assert ledger.read_bytes() == before
    assert [row["run_id"] for row in peeked] == ["old-a", "old-b"]
    assert peeked[0]["list_price_usd"] == "0.021"
    assert peeked[0]["storage_bytes"] == "0"
    assert peeked[0]["class_a_ops"] == "0"
    assert peeked[1]["cost_usd"] == "0.0100"
    assert peeked[1]["list_price_usd"] == "0.0100"

    append_ledger(ledger, [_row("new-run", "2026-10-08", SERVICE_DEEPINFRA, "0.0200", 10, 1)])
    rows = read_ledger(ledger)
    assert [row["run_id"] for row in rows] == ["old-a", "old-b", "new-run"]
    assert rows[0]["cost_usd"] == "0.021"
    assert rows[0]["list_price_usd"] == "0.021"
    assert rows[2]["list_price_usd"] == "0.02"
    assert rows[2]["service"] == SERVICE_DEEPINFRA
    migrated = ledger.read_text(encoding="utf-8")
    assert migrated.splitlines()[0].split(",") == LEDGER_COLUMNS
    append_ledger(ledger, [_row("newer", "2026-10-08", SERVICE_JEV, "0.042", 10, 1)])
    assert ledger.read_text(encoding="utf-8").startswith(migrated)
    assert [row["run_id"] for row in read_ledger(ledger)] == ["old-a", "old-b", "new-run", "newer"]


def test_chart_failure_still_publishes_the_ledger_and_table(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("svg down")

    monkeypatch.setattr("pipeline.costs.write_daily_spend_svg", boom)
    run_path = tmp_path / "cost_run.json"
    write_cost_run(
        posts_processed=4,
        planets_published=1,
        started_at=datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc),
        path=run_path,
        attempts=(),
    )
    usage = tmp_path / "r2_usage.json"
    usage.write_text(
        '{"class_a_ops": 1, "class_b_ops": 1, "storage_bytes": 1000, "storage_known": true}\n',
        encoding="utf-8",
    )
    ledger = tmp_path / "costs" / "ledger.csv"
    readme = tmp_path / "costs" / "README.md"
    assert append_run_files(run_path, ledger, readme, r2_usage_path=usage, today=date(2026, 10, 8)) == 0
    assert ledger.is_file()
    assert "rather than a credit" in readme.read_text(encoding="utf-8")
    assert not (tmp_path / "costs" / "daily_spend_14d.svg").exists()


def test_r2_usage_appends_a_row_and_notes_the_free_tier(tmp_path):
    run_path = tmp_path / "cost_run.json"
    write_cost_run(
        posts_processed=4,
        planets_published=1,
        started_at=datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc),
        path=run_path,
        attempts=(),
    )
    usage = tmp_path / "r2_usage.json"
    usage.write_text(
        '{"class_a_ops": 1, "class_b_ops": 2, "storage_bytes": 2000000000, "storage_known": true}\n',
        encoding="utf-8",
    )
    ledger = tmp_path / "costs" / "ledger.csv"
    readme = tmp_path / "costs" / "README.md"
    assert append_run_files(
        run_path,
        ledger,
        readme,
        r2_usage_path=usage,
        today=date(2026, 10, 8),
    ) == 0
    rows = read_ledger(ledger)
    assert len(rows) == 1
    assert rows[0]["service"] == SERVICE_R2
    assert Decimal(rows[0]["cost_usd"]) == 0
    assert Decimal(rows[0]["list_price_usd"]) > 0
    text = readme.read_text(encoding="utf-8")
    assert "R2 is currently inside the monthly free tier" in text
    assert "daily_spend_14d.svg" in text
    assert "R2 $" in text
    chart = (tmp_path / "costs" / "daily_spend_14d.svg").read_text(encoding="utf-8")
    import xml.etree.ElementTree as ET

    root = ET.parse(io.StringIO(chart)).getroot()
    assert root.tag.endswith("svg")
    assert len([element for element in root.iter() if element.tag.endswith("g") and element.get("data-date")]) == 14


def _money_chart_labels(labels: list[str | None]) -> set[str]:
    skip = {"LLM labeling", "Jev", "R2", "UTC day"}
    money: set[str] = set()
    for label in labels:
        if not label or label in skip:
            continue
        if len(label) == 5 and label[2] == "-" and label[:2].isdigit() and label[3:].isdigit():
            continue
        money.add(label)
        assert label.startswith("$")
    return money


def _r2_row(day: str, storage_bytes: int, *, class_a: int, class_b: int) -> dict[str, str]:
    return {
        "run_id": f"r2-{day}",
        "run_started_utc": f"{day}T06:00:00Z",
        "date_utc": day,
        "trigger": "schedule",
        "service": SERVICE_R2,
        "model": "r2-standard",
        "calls": str(class_a + class_b),
        "failed_calls": "0",
        "input_tokens": "0",
        "output_tokens": "0",
        "cost_usd": "0",
        "cost_source": "computed",
        "posts_processed": "1",
        "planets_published": "1",
        "storage_bytes": str(storage_bytes),
        "class_a_ops": str(class_a),
        "class_b_ops": str(class_b),
        "list_price_usd": "0",
    }


def _row(run_id, day, service, cost, posts, planets):
    model = "jev-1.13.0" if service == SERVICE_JEV else "unit-test-llm"
    source = "computed" if service == SERVICE_JEV else "reported"
    return {
        "run_id": run_id,
        "run_started_utc": f"{day}T06:00:00Z",
        "date_utc": day,
        "trigger": "schedule",
        "service": service,
        "model": model,
        "calls": "1",
        "failed_calls": "0",
        "input_tokens": "1",
        "output_tokens": "1",
        "cost_usd": cost,
        "cost_source": source,
        "posts_processed": str(posts),
        "planets_published": str(planets),
    }

