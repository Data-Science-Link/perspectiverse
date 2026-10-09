"""Decide whether a pipeline run may replace the live ``data.json``.

Run 37946621071 published 90 section planets and skipped the wide face
relabel in every section after a burst of DeepInfra failures. A later clean
run on the same corpus published 97. This guard holds the previous snapshot
only when the new one is worse *and* labeling was in distress. A real day
with fewer planets and a healthy labeler still publishes.

Distress means DeepInfra final failures are over 5% of calls, or retried
attempts plus final failures are over 5% of calls. ``calls`` counts every
DeepInfra (and other OpenAI-compatible) HTTP attempt, the same way the cost
ledger counts ``calls``. Exactly 5% is not over the line.

Two hold rules, either one is enough:

1. Section planets fell by more than a small margin, and labeling is in
   distress. The margin is the larger of 3 planets and 5% of the live
   section-planet count, rounded up. The drop must be strictly greater.
   Live 98 → margin 5, so 92 or fewer holds and 93 or more publishes.
2. The wide face relabel was left unfinished in most section solar systems
   (a strict majority of sections that queued one), and labeling is in
   distress. That is the "skipped because of failures" case. A majority
   skip with a clean error log publishes: the skip is not blamed on
   failures. Fewer than two sections queued cannot be "most."

Fail open: a missing or unreadable live snapshot, a missing label report,
or any error inside the check publishes. The ordinary case must not stick
on yesterday's sky.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ERROR_CLASSES = ("429", "5xx", "timeout", "other")
FAILURE_RATE_PERCENT = 5
SECTION_PLANET_MARGIN_FLOOR = 3
# Exit status the workflow treats as "keep the live snapshot."
# Any other non-zero status fail-opens and publishes.
HOLD_EXIT = 10
LABEL_RUN_PATH = Path(__file__).resolve().parent / "data" / "label_run.json"


@dataclass(frozen=True)
class PublishDecision:
    publish: bool
    reason: str
    code: str


def empty_error_summary() -> dict:
    return {
        "calls": 0,
        "retried": {name: 0 for name in ERROR_CLASSES},
        "final_failures_by_type": {name: 0 for name in ERROR_CLASSES},
        "retried_calls": 0,
        "final_failures": 0,
    }


def empty_face_relabel() -> dict:
    return {
        "sections_queued": 0,
        "sections_incomplete": 0,
        "calls_queued": 0,
        "calls_completed": 0,
        "budget_exhausted": False,
    }


def rate_over_line(numerator: int, denominator: int, *, percent: int = FAILURE_RATE_PERCENT) -> bool:
    """True when ``numerator / denominator`` is strictly greater than ``percent`` percent."""
    if denominator <= 0 or numerator <= 0:
        return False
    return int(numerator) * 100 > int(denominator) * int(percent)


def section_planet_margin(live_count: int) -> int:
    """How many section planets may disappear before the drop is no longer small.

    Five percent of the live count, rounded up, and at least three planets.
    """
    count = max(0, int(live_count))
    percent = (count * FAILURE_RATE_PERCENT + 99) // 100
    return max(SECTION_PLANET_MARGIN_FLOOR, percent)


def count_section_planets(payload: dict | None) -> int:
    """Planets in section solar systems. The global catalog is not included."""
    if not isinstance(payload, dict):
        return 0
    sections = payload.get("sections") or {}
    if not isinstance(sections, dict):
        return 0
    total = 0
    for planets in sections.values():
        if isinstance(planets, list):
            total += len(planets)
    return total


def labeling_in_distress(errors: dict | None) -> bool:
    """Final failures or the retry-plus-final share are over 5% of calls."""
    if not isinstance(errors, dict):
        return False
    calls = int(errors.get("calls") or 0)
    retried = int(errors.get("retried_calls") or 0)
    final = int(errors.get("final_failures") or 0)
    if rate_over_line(final, calls):
        return True
    return rate_over_line(retried + final, calls)


def relabel_skipped_in_most_sections(face: dict | None) -> bool:
    """Strict majority of sections that queued a wide relabel did not finish."""
    if not isinstance(face, dict):
        return False
    queued = int(face.get("sections_queued") or 0)
    incomplete = int(face.get("sections_incomplete") or 0)
    if queued < 2:
        return False
    return incomplete * 2 > queued


def decide_publish(
    live: dict | None,
    new: dict | None,
    label_run: dict | None,
) -> PublishDecision:
    """Compare a new snapshot with the live one. See the module docstring."""
    if not isinstance(new, dict):
        return PublishDecision(True, "new snapshot is missing; publishing (fail open)", "fail-open")
    if not isinstance(live, dict):
        return PublishDecision(True, "no live snapshot to compare; publishing (fail open)", "fail-open")

    errors = None
    face = None
    if isinstance(label_run, dict):
        raw_errors = label_run.get("deepinfra_errors")
        raw_face = label_run.get("face_relabel")
        errors = raw_errors if isinstance(raw_errors, dict) else None
        face = raw_face if isinstance(raw_face, dict) else None

    distress = labeling_in_distress(errors)
    holds: list[str] = []
    if relabel_skipped_in_most_sections(face) and distress:
        queued = int(face["sections_queued"]) if isinstance(face, dict) else 0
        incomplete = int(face["sections_incomplete"]) if isinstance(face, dict) else 0
        holds.append(
            "wide face relabel skipped in most sections because of DeepInfra failures "
            f"({incomplete} of {queued} sections unfinished)"
        )

    live_planets = count_section_planets(live)
    new_planets = count_section_planets(new)
    margin = section_planet_margin(live_planets)
    drop = live_planets - new_planets
    if live_planets > 0 and drop > margin and distress:
        holds.append(
            f"section planets fell from {live_planets} to {new_planets}, "
            f"more than the {margin}-planet margin, and DeepInfra failures are over 5% of calls"
        )
    if holds:
        return PublishDecision(False, "; ".join(holds) + "; keeping the live snapshot", "hold")

    if live_planets > 0 and drop > margin:
        return PublishDecision(
            True,
            f"section planets fell from {live_planets} to {new_planets}, "
            "but labeling was not in distress; publishing",
            "publish",
        )
    return PublishDecision(
        True,
        f"section planets {new_planets} vs live {live_planets}; publishing",
        "publish",
    )


def _count_phrase(bucket: dict | None) -> str:
    source = bucket if isinstance(bucket, dict) else {}
    parts = [f"{name}={int(source.get(name) or 0)}" for name in ERROR_CLASSES]
    total = sum(int(source.get(name) or 0) for name in ERROR_CLASSES)
    return ", ".join(parts) + f" ({total})"


def format_deepinfra_error_log(summary: dict | None) -> str:
    """One line: retried attempts and final failures, each split by error type."""
    data = summary if isinstance(summary, dict) else empty_error_summary()
    calls = int(data.get("calls") or 0)
    return (
        f"DeepInfra errors: {calls} call(s). "
        f"Retried attempts: {_count_phrase(data.get('retried'))}. "
        f"Final failures: {_count_phrase(data.get('final_failures_by_type'))}."
    )


def final_failure_warning(summary: dict | None) -> str | None:
    """Warning when final failures are over 5% of calls. Retries alone do not warn."""
    if not isinstance(summary, dict):
        return None
    calls = int(summary.get("calls") or 0)
    final = int(summary.get("final_failures") or 0)
    if not rate_over_line(final, calls):
        return None
    percent = 100.0 * final / calls
    return (
        f"DeepInfra final failures are {final} of {calls} calls "
        f"({percent:.1f}%), over the 5% line. Labeling output may be degraded."
    )


def append_github_step_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def report_label_health(summary: dict | None) -> str | None:
    """Print the per-run error line and, over 5% final failures, a warning.

    Returns the warning text when one was emitted.
    """
    line = format_deepinfra_error_log(summary)
    print(line)
    warning = final_failure_warning(summary)
    body = "## DeepInfra labeling errors\n\n" + line + "\n"
    if warning:
        print(f"WARNING: {warning}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning::{warning}")
        body += f"\n**WARNING:** {warning}\n"
    append_github_step_summary(body + "\n")
    return warning


def write_label_run(
    *,
    deepinfra_errors: dict,
    face_relabel: dict,
    section_planets: int,
    path: Path | None = None,
) -> Path:
    """Write the gitignored label report the publish guard reads. Never raises."""
    destination = Path(path) if path is not None else LABEL_RUN_PATH
    payload = {
        "deepinfra_errors": deepinfra_errors,
        "face_relabel": face_relabel,
        "section_planets": int(section_planets),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    print(f"Label run file: {destination}")
    return destination


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "not a JSON object"
    return payload, None


def _hold_summary(decision: PublishDecision) -> str:
    return (
        "## Publish guard: live snapshot kept\n\n"
        "This run did **not** replace `public/data.json`. "
        "The previous snapshot stays on the live site.\n\n"
        f"{decision.reason}\n"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Keep the live data.json when this run's labeling output is degraded"
    )
    parser.add_argument("--live", type=Path, required=True, help="data.json currently on data-snapshot")
    parser.add_argument("--new", type=Path, required=True, help="data.json this run just wrote")
    parser.add_argument("--label-run", type=Path, default=None, help="label_run.json from this run")
    args = parser.parse_args(argv)

    if not args.live.exists():
        decision = PublishDecision(True, "no live snapshot to compare; publishing (fail open)", "fail-open")
        print(f"Publish guard: {decision.reason}")
        return 0

    live, live_error = _load_json(args.live)
    if live_error is not None:
        print(
            f"WARNING: Publish guard could not read the live snapshot ({live_error}); publishing (fail open).",
            file=sys.stderr,
        )
        return 0

    if not args.new.exists():
        print("WARNING: Publish guard could not read the new snapshot; publishing (fail open).", file=sys.stderr)
        return 0
    new, new_error = _load_json(args.new)
    if new_error is not None:
        print(
            f"WARNING: Publish guard could not read the new snapshot ({new_error}); publishing (fail open).",
            file=sys.stderr,
        )
        return 0

    label_run = None
    if args.label_run is not None:
        if args.label_run.exists():
            label_run, label_error = _load_json(args.label_run)
            if label_error is not None:
                print(
                    f"WARNING: Publish guard could not read the label report ({label_error}); "
                    "publishing unless another check holds (fail open).",
                    file=sys.stderr,
                )
                label_run = None
        else:
            print(
                "WARNING: Publish guard has no label report; a planet drop cannot be blamed on failures.",
                file=sys.stderr,
            )

    decision = decide_publish(live, new, label_run)
    print(f"Publish guard: {decision.reason}")
    if decision.publish:
        return 0
    print(f"::error::{decision.reason}")
    append_github_step_summary(_hold_summary(decision))
    return HOLD_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
