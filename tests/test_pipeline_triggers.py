"""Static checks for Daily Discourse Pipeline triggers. No network and no paid calls.

A push to main must not start this workflow. The live step's ``if`` is already
true for every non-schedule event, so the safe fix is to delete ``on.push``
rather than gate each paid step. ``free_ingest`` defaults to off and is set
only on a deliberate workflow_dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/pipeline.yml")
WORK_GATE = "github.event_name != 'schedule' || steps.schedule_guard.outputs.skip != 'true'"
FREE_INGEST_ENV = (
    "${{ github.event_name == 'workflow_dispatch' && inputs.free_ingest == true && '1' || '' }}"
)
FILL_RUN_ENV = (
    "${{ github.event_name == 'workflow_dispatch' && inputs.fill_budget_usd != '' && '1' || '' }}"
)
HOLD_TOPUPS_ENV = "${{ github.event_name == 'schedule' && '1' || '' }}"
# False on a schedule (the event check short-circuits) and on a normal dispatch.
NOT_FREE = "(github.event_name != 'workflow_dispatch' || inputs.free_ingest != true)"
FREE_PREVIEW = (
    "github.event_name == 'workflow_dispatch' && inputs.free_ingest == true "
    "&& steps.live.outcome == 'success'"
)

# Step ``if`` values on main before this change. Schedule behavior is these
# conditions plus the live command. A comment or the new env var may change;
# these strings may not.
EXPECTED_IF = {
    "Record job start for the fill time margin": None,
    "Checkout repository": None,
    "Skip scheduled run when pipeline already succeeded today (UTC)": "github.event_name == 'schedule'",
    "Scheduled run skipped (already succeeded today)": (
        "github.event_name == 'schedule' && steps.schedule_guard.outputs.skip == 'true'"
    ),
    "Restore retained corpus from git": WORK_GATE,
    "Install uv": WORK_GATE,
    "Set up Python": WORK_GATE,
    "Install pipeline": WORK_GATE,
    "Pin pipeline modules for ledger steps after git checkout": WORK_GATE,
    "Download corpus from R2": WORK_GATE,
    "Restore Jev verdict cache": WORK_GATE,
    "Drop stored spam and non-claims whose verdicts are cached": WORK_GATE,
    "Corpus quality-post count for the fill done check": WORK_GATE,
    "Load today's cost ledger for the spend cap": WORK_GATE,
    "Refuse fill dispatch when the fill campaign is complete": (
        f"({WORK_GATE}) && github.event_name == 'workflow_dispatch' && inputs.fill_budget_usd != ''"
    ),
    "Run live pipeline": WORK_GATE,
    "Save Jev verdict cache": f"always() && ({WORK_GATE})",
    "Stage corpus after cancelled live": f"always() && ({WORK_GATE}) && steps.live.outcome == 'cancelled'",
    "Upload corpus to R2 after cancelled live": (
        f"always() && ({WORK_GATE}) && steps.live.outcome == 'cancelled' && {NOT_FREE}"
    ),
    "Stage halted corpus before ledger git checkout": "failure() && steps.live.outcome == 'failure'",
    "Upload halted corpus to R2": f"failure() && steps.live.outcome == 'failure' && {NOT_FREE}",
    "Record partial spend when the run ends early": (
        "always() && (" + WORK_GATE + ") && steps.live.outcome != 'success' "
        "&& steps.live.outcome != 'skipped' && (steps.live.outcome == 'failure' "
        "|| steps.live.outcome == 'cancelled')"
    ),
    "Keep yesterday's edition when the daily spend cap stops the run": (
        "failure() && steps.live.outcome == 'failure'"
    ),
    "Upload corpus to R2": f"({WORK_GATE}) && steps.live.outcome == 'success' && {NOT_FREE}",
    "Upload data.json": f"({WORK_GATE}) && steps.live.outcome == 'success' && {NOT_FREE}",
    "Write free-ingest preview": FREE_PREVIEW,
    "Upload free-ingest preview": FREE_PREVIEW,
    "Record free-ingest spend": f"always() && {FREE_PREVIEW}",
    "Publish data-snapshot branch": (
        f"({WORK_GATE}) && steps.live.outcome == 'success' && steps.r2upload.outcome == 'success' && {NOT_FREE}"
    ),
}

# A free-ingest dispatch must not reach these. Spend recording is separate.
FREE_INGEST_BLOCKED = (
    "Upload corpus to R2",
    "Upload corpus to R2 after cancelled live",
    "Upload halted corpus to R2",
    "Upload data.json",
    "Publish data-snapshot branch",
)

# Steps that spend money or publish. A push must not be able to start any of them.
PAID_OR_PUBLISHING = (
    "Run live pipeline",
    "Download corpus from R2",
    "Upload corpus to R2",
    "Upload corpus to R2 after cancelled live",
    "Upload halted corpus to R2",
    "Upload data.json",
    "Publish data-snapshot branch",
    "Record partial spend when the run ends early",
    "Keep yesterday's edition when the daily spend cap stops the run",
)

EXPECTED_CRONS = (
    "17 6 * * *",
    "47 7 * * *",
    "17 9 * * *",
    "47 10 * * *",
    "17 12 * * *",
)


def _document(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _on_block(document: dict) -> dict:
    # PyYAML 1.1 parses the key ``on`` as boolean True.
    block = document["on"] if "on" in document else document[True]
    assert isinstance(block, dict)
    return block


def _steps() -> list[dict]:
    steps = _document(WORKFLOW)["jobs"]["pipeline"]["steps"]
    assert isinstance(steps, list)
    return steps


@dataclass(frozen=True)
class Ctx:
    event: str
    skip: str
    live: str
    r2: str
    fill: str
    failed: bool
    free_ingest: bool = False


def _work(ctx: Ctx) -> bool:
    return ctx.event != "schedule" or ctx.skip != "true"


def _not_free_preview(ctx: Ctx) -> bool:
    return ctx.event != "workflow_dispatch" or ctx.free_ingest is not True


def _free_preview(ctx: Ctx) -> bool:
    return ctx.event == "workflow_dispatch" and ctx.free_ingest is True and ctx.live == "success"


def step_runs(expr: str | None, ctx: Ctx) -> bool:
    """Evaluate the ``if`` strings this workflow actually uses."""
    if expr is None:
        return True
    if expr == "github.event_name == 'schedule'":
        return ctx.event == "schedule"
    if expr == "github.event_name == 'schedule' && steps.schedule_guard.outputs.skip == 'true'":
        return ctx.event == "schedule" and ctx.skip == "true"
    if expr == WORK_GATE:
        return _work(ctx)
    if expr == f"({WORK_GATE}) && github.event_name == 'workflow_dispatch' && inputs.fill_budget_usd != ''":
        return _work(ctx) and ctx.event == "workflow_dispatch" and ctx.fill != ""
    if expr == f"always() && ({WORK_GATE})":
        return _work(ctx)
    if expr == f"always() && ({WORK_GATE}) && steps.live.outcome == 'cancelled'":
        return _work(ctx) and ctx.live == "cancelled"
    if expr == f"always() && ({WORK_GATE}) && steps.live.outcome == 'cancelled' && {NOT_FREE}":
        return _work(ctx) and ctx.live == "cancelled" and _not_free_preview(ctx)
    if expr == "failure() && steps.live.outcome == 'failure'":
        return ctx.failed and ctx.live == "failure"
    if expr == f"failure() && steps.live.outcome == 'failure' && {NOT_FREE}":
        return ctx.failed and ctx.live == "failure" and _not_free_preview(ctx)
    if expr == FREE_PREVIEW:
        return _free_preview(ctx)
    if expr == f"always() && {FREE_PREVIEW}":
        return _free_preview(ctx)
    partial = (
        "always() && (" + WORK_GATE + ") && steps.live.outcome != 'success' "
        "&& steps.live.outcome != 'skipped' && (steps.live.outcome == 'failure' "
        "|| steps.live.outcome == 'cancelled')"
    )
    if expr == partial:
        return (
            _work(ctx)
            and ctx.live not in {"success", "skipped"}
            and ctx.live in {"failure", "cancelled"}
        )
    if expr == f"({WORK_GATE}) && steps.live.outcome == 'success' && {NOT_FREE}":
        return _work(ctx) and ctx.live == "success" and _not_free_preview(ctx)
    publish = (
        f"({WORK_GATE}) && steps.live.outcome == 'success' && "
        f"steps.r2upload.outcome == 'success' && {NOT_FREE}"
    )
    if expr == publish:
        return _work(ctx) and ctx.live == "success" and ctx.r2 == "success" and _not_free_preview(ctx)
    raise AssertionError(f"unrecognized workflow if: {expr}")


def free_ingest_value(event: str, enabled: bool) -> str:
    """Mirror the live-step env expression. Only boolean true on a dispatch yields 1."""
    chosen = event == "workflow_dispatch" and enabled is True and "1"
    return chosen or ""


def hold_topups_value(event: str) -> str:
    """Mirror the live-step hold-topups env. Only schedule events set 1."""
    return "1" if event == "schedule" else ""


def _running_names(ctx: Ctx) -> list[str]:
    names = []
    for step in _steps():
        name = step["name"]
        if step_runs(step.get("if"), ctx):
            names.append(name)
    return names


def test_push_does_not_start_the_pipeline_and_tests_still_cover_main():
    triggers = _on_block(_document(WORKFLOW))
    assert "push" not in triggers
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    header = WORKFLOW.read_text(encoding="utf-8").split("concurrency:", 1)[0]
    assert "\n  push:" not in header

    tests = _on_block(_document(Path(".github/workflows/pytest.yml")))
    assert "main" in tests["push"]["branches"]
    frontend = _on_block(_document(Path(".github/workflows/frontend.yml")))
    assert "main" in frontend["push"]["branches"]
    audit = _on_block(_document(Path(".github/workflows/security-audit.yml")))
    assert "push" in audit
    pages = _on_block(_document(Path(".github/workflows/pages.yml")))
    assert "main" in pages["push"]["branches"]


def test_free_ingest_defaults_off_and_only_a_dispatch_sets_it():
    inputs = _on_block(_document(WORKFLOW))["workflow_dispatch"]["inputs"]
    free = inputs["free_ingest"]
    assert free["type"] == "boolean"
    assert free["default"] is False
    assert free["required"] is False
    assert inputs["fill_budget_usd"]["default"] == ""

    live = next(step for step in _steps() if step.get("id") == "live")
    assert live["env"]["PERSPECTIVERSE_FREE_INGEST"] == FREE_INGEST_ENV
    assert live["env"]["PERSPECTIVERSE_FILL_RUN"] == FILL_RUN_ENV
    assert live["env"]["PERSPECTIVERSE_HOLD_TOPUPS"] == HOLD_TOPUPS_ENV
    assert "PERSPECTIVERSE_FREE_INGEST" not in live["run"]
    assert "python -m pipeline.run_pipeline --live --db pipeline/data/live_corpus.db" in live["run"]

    assert free_ingest_value("schedule", False) == ""
    assert free_ingest_value("schedule", True) == ""
    assert free_ingest_value("push", True) == ""
    assert free_ingest_value("workflow_dispatch", False) == ""
    assert free_ingest_value("workflow_dispatch", True) == "1"

    assert hold_topups_value("schedule") == "1"
    assert hold_topups_value("workflow_dispatch") == ""
    assert hold_topups_value("push") == ""


def test_schedule_step_conditions_and_crons_are_unchanged():
    triggers = _on_block(_document(WORKFLOW))
    assert tuple(item["cron"] for item in triggers["schedule"]) == EXPECTED_CRONS
    steps = _steps()
    assert [step["name"] for step in steps] == list(EXPECTED_IF)
    for step in steps:
        assert step.get("if") == EXPECTED_IF[step["name"]]


def test_push_cannot_reach_paid_steps_and_dispatch_steps_match():
    names = [step["name"] for step in _steps()]
    for paid in PAID_OR_PUBLISHING:
        assert paid in names
    # The live step would run on a push if the trigger still existed.
    push_like = Ctx(event="push", skip="false", live="success", r2="success", fill="", failed=False)
    assert step_runs(EXPECTED_IF["Run live pipeline"], push_like) is True
    assert "push" not in _on_block(_document(WORKFLOW))

    worked = Ctx(event="schedule", skip="false", live="success", r2="success", fill="", failed=False)
    skipped = Ctx(event="schedule", skip="true", live="skipped", r2="skipped", fill="", failed=False)
    dispatch = Ctx(
        event="workflow_dispatch", skip="false", live="success", r2="success", fill="", failed=False
    )
    guard = "Skip scheduled run when pipeline already succeeded today (UTC)"
    schedule_runs = _running_names(worked)
    dispatch_runs = _running_names(dispatch)
    assert guard in schedule_runs
    assert guard not in dispatch_runs
    assert [name for name in schedule_runs if name != guard] == dispatch_runs
    assert "Run live pipeline" in schedule_runs
    assert "Publish data-snapshot branch" in schedule_runs
    assert "Refuse fill dispatch when the fill campaign is complete" not in schedule_runs
    assert "Scheduled run skipped (already succeeded today)" not in schedule_runs

    skipped_runs = _running_names(skipped)
    assert skipped_runs == [
        "Record job start for the fill time margin",
        "Checkout repository",
        "Skip scheduled run when pipeline already succeeded today (UTC)",
        "Scheduled run skipped (already succeeded today)",
    ]
    assert not any(name in skipped_runs for name in PAID_OR_PUBLISHING)

    assert "Upload free-ingest preview" not in schedule_runs
    assert "Record free-ingest spend" not in schedule_runs
    assert "Upload free-ingest preview" not in dispatch_runs
    preview = next(step for step in _steps() if step["name"] == "Upload free-ingest preview")
    assert preview["with"]["name"] == "free-ingest-preview"
    spend = next(step for step in _steps() if step["name"] == "Record free-ingest spend")
    assert "record-preview-ledger" in spend["run"]
    assert "--push" in spend["run"]
    assert "data.json" not in spend["run"]
    assert "pipeline.r2" not in spend["run"]


def test_free_ingest_dispatch_cannot_upload_or_publish():
    """A preview must not put unscored posts on R2 or replace the live edition."""
    preview = Ctx(
        event="workflow_dispatch",
        skip="false",
        live="success",
        r2="success",
        fill="",
        failed=False,
        free_ingest=True,
    )
    running = _running_names(preview)
    for blocked in FREE_INGEST_BLOCKED:
        assert blocked not in running
    assert "Run live pipeline" in running
    assert "Write free-ingest preview" in running
    assert "Upload free-ingest preview" in running
    assert "Record free-ingest spend" in running
    order = [step["name"] for step in _steps()]
    assert order.index("Write free-ingest preview") < order.index("Upload free-ingest preview")
    assert order.index("Upload free-ingest preview") < order.index("Record free-ingest spend")
    assert order.index("Record free-ingest spend") < order.index("Publish data-snapshot branch")
    assert "Record partial spend when the run ends early" not in running

    cancelled = Ctx(
        event="workflow_dispatch",
        skip="false",
        live="cancelled",
        r2="skipped",
        fill="",
        failed=False,
        free_ingest=True,
    )
    cancelled_runs = _running_names(cancelled)
    assert "Upload corpus to R2 after cancelled live" not in cancelled_runs
    assert "Publish data-snapshot branch" not in cancelled_runs
    assert "Upload free-ingest preview" not in cancelled_runs
    assert "Record partial spend when the run ends early" in cancelled_runs

    failed = Ctx(
        event="workflow_dispatch",
        skip="false",
        live="failure",
        r2="skipped",
        fill="",
        failed=True,
        free_ingest=True,
    )
    failed_runs = _running_names(failed)
    assert "Upload halted corpus to R2" not in failed_runs
    assert "Publish data-snapshot branch" not in failed_runs
    assert "Record partial spend when the run ends early" in failed_runs
    assert "Keep yesterday's edition when the daily spend cap stops the run" in failed_runs
