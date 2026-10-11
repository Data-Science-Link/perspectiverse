"""Run the publish step's checkout, then the guard, without pushing.

#115's unit tests imported publish_guard from a main checkout. The paid
comparison never executed this step. data-snapshot has no publish_guard.py,
so `python -m pipeline.publish_guard` after that checkout cannot run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SNAP = Path("/tmp/perspectiverse-snapshot")


def _snapshot(section_count: int) -> dict:
    return {
        "topics": [{"id": 1}] * 10,
        "sections": {"Politics": [{"id": index + 1} for index in range(section_count)]},
    }


def _label_run(*, calls: int, final: int, incomplete: int) -> dict:
    return {
        "deepinfra_errors": {
            "calls": calls,
            "retried_calls": 0,
            "final_failures": final,
            "retried": {"429": 0, "5xx": 0, "timeout": 0, "other": 0},
            "final_failures_by_type": {"429": 0, "5xx": 0, "timeout": final, "other": 0},
        },
        "face_relabel": {
            "sections_queued": 10,
            "sections_incomplete": incomplete,
            "calls_queued": 160,
            "calls_completed": (10 - incomplete) * 16,
            "budget_exhausted": incomplete > 0,
        },
        "section_planets": 0,
    }


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path, live: dict) -> Path:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Publish Guard Test")
    pipeline = repo / "pipeline"
    pipeline.mkdir()
    (pipeline / "__init__.py").write_text("", encoding="utf-8")
    (pipeline / "publish_guard.py").write_text(
        Path("pipeline/publish_guard.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main")
    _git(repo, "checkout", "-b", "data-snapshot")
    (pipeline / "publish_guard.py").unlink()
    (pipeline / "live.py").write_text("# snapshot tree, no publish guard\n", encoding="utf-8")
    public = repo / "public"
    public.mkdir()
    (public / "data.json").write_text(json.dumps(live) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "snapshot")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "origin", "main")
    _git(repo, "push", "origin", "data-snapshot")
    _git(repo, "checkout", "main")
    return repo


def _workflow_slice(start: str, end: str) -> str:
    """Dedent a `run: |` block (10 spaces) from the daily workflow."""
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    body = workflow[workflow.index(start) : workflow.index(end)]
    lines = []
    for line in body.splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def _guard_script() -> str:
    return _workflow_slice("# BEGIN publish-guard\n", "# END publish-guard\n")


def _checkout_script() -> str:
    """Literal reset/fetch/checkout from the publish step, before the guard."""
    return _workflow_slice("git reset --hard HEAD\n", "# BEGIN publish-guard\n")


def _stage_inputs(new: dict, label_run: dict) -> None:
    """Write this run's snapshot inputs. Leave any other files in the dir alone."""
    SNAP.mkdir(parents=True, exist_ok=True)
    (SNAP / "data.json").write_text(json.dumps(new) + "\n", encoding="utf-8")
    (SNAP / "label_run.json").write_text(json.dumps(label_run) + "\n", encoding="utf-8")


def _install_python_shim(repo: Path) -> None:
    """The step calls `python` after sourcing `.venv`. That dir is gitignored."""
    bin_dir = repo / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    link = bin_dir / "python"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(sys.executable)
    (bin_dir / "activate").write_text(
        'export PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd):${PATH}"\n',
        encoding="utf-8",
    )


def _checkout_data_snapshot(repo: Path, *, copy_guard: bool) -> subprocess.CompletedProcess[str]:
    """Copy main's module, then switch. Both happen before the guard runs.

    The copy is the workflow line, executed while HEAD is still main.
    Skipping it is the missing-module case (the staged file is absent).
    """
    staged = SNAP / "publish_guard.py"
    if staged.exists():
        staged.unlink()
    copy = ""
    if copy_guard:
        copy = "cp pipeline/publish_guard.py /tmp/perspectiverse-snapshot/publish_guard.py\n"
    script = "set -eu\n" + copy + _checkout_script()
    return subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_guard_step(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-eo", "pipefail", "-c", _guard_script()],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_workflow_copies_the_guard_before_the_data_snapshot_checkout():
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    assert "python -m pipeline.publish_guard" not in workflow
    copy_at = workflow.index("cp pipeline/publish_guard.py /tmp/perspectiverse-snapshot/publish_guard.py")
    checkout_at = workflow.index("git checkout --force -B data-snapshot")
    begin = workflow.index("# BEGIN publish-guard")
    assert copy_at < checkout_at < begin
    assert "::warning::Publish guard could not run" in workflow
    assert '"$guard_status" -eq 10' in workflow


def test_checkout_sequence_passes_and_blocks_without_publishing(tmp_path):
    """Switch to data-snapshot, then run the step. No commit and no push."""
    live = _snapshot(98)
    repo = _init_repo(tmp_path, live)
    _install_python_shim(repo)
    origin_before = _git(repo, "rev-parse", "origin/data-snapshot")
    transcript: list[str] = [
        "sequence: cp pipeline/publish_guard.py (while HEAD is main) -> "
        "git reset --hard HEAD -> git fetch origin data-snapshot -> "
        "git checkout --force -B data-snapshot origin/data-snapshot -> "
        'python "$GUARD" (workflow publish-guard block)',
    ]

    cases = [
        (
            "healthy",
            _snapshot(97),
            _label_run(calls=1172, final=3, incomplete=0),
            True,
            "PASS",
        ),
        (
            "degraded",
            _snapshot(90),
            _label_run(calls=947, final=86, incomplete=10),
            True,
            "BLOCKED",
        ),
        (
            "missing-module",
            _snapshot(90),
            _label_run(calls=947, final=86, incomplete=10),
            False,
            "COULD_NOT_RUN",
        ),
    ]
    for name, new, label_run, copy_guard, expect in cases:
        _git(repo, "checkout", "--force", "main")
        assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
        assert (repo / "pipeline" / "publish_guard.py").is_file()
        _stage_inputs(new, label_run)
        checkout = _checkout_data_snapshot(repo, copy_guard=copy_guard)
        assert checkout.returncode == 0, checkout.stderr
        assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "data-snapshot"
        assert not (repo / "pipeline" / "publish_guard.py").exists()
        if copy_guard:
            staged = (SNAP / "publish_guard.py").read_text(encoding="utf-8")
            assert staged == Path("pipeline/publish_guard.py").read_text(encoding="utf-8")
        else:
            assert not (SNAP / "publish_guard.py").exists()
        old = subprocess.run(
            [sys.executable, "-m", "pipeline.publish_guard", "--help"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert old.returncode != 0
        assert "No module named" in old.stderr
        before = (repo / "public" / "data.json").read_text(encoding="utf-8")
        result = _run_guard_step(repo)
        output = result.stdout + result.stderr
        after = (repo / "public" / "data.json").read_text(encoding="utf-8")
        transcript.append(f"=== {name} ({expect}) ===")
        transcript.append(f"copied publish_guard.py from main before checkout: {copy_guard}")
        transcript.append(f"cwd branch: {_git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')}")
        transcript.append(f"python -m pipeline.publish_guard exit: {old.returncode} ({old.stderr.strip()})")
        transcript.append(output.strip())
        transcript.append(f"step exit: {result.returncode}")
        transcript.append(f"origin/data-snapshot unchanged: {_git(repo, 'rev-parse', 'origin/data-snapshot') == origin_before}")
        if expect == "PASS":
            assert result.returncode == 0, output
            assert "Publish guard:" in result.stdout
            assert "publishing" in result.stdout
            assert "not replacing" not in result.stdout
            assert after == json.dumps(new) + "\n"
            transcript.append("verdict: PASS (local file replaced, nothing pushed)")
        elif expect == "BLOCKED":
            assert result.returncode == 0, output
            assert "::error::" in result.stdout
            assert "not replacing public/data.json" in result.stdout
            assert after == before
            transcript.append("verdict: BLOCKED (live public/data.json unchanged, nothing pushed)")
        else:
            assert result.returncode == 0, output
            assert "::warning::Publish guard could not run" in result.stdout
            assert "not replacing" not in result.stdout
            assert after == json.dumps(new) + "\n"
            transcript.append("verdict: COULD_NOT_RUN warning, fail open, nothing pushed")
        assert _git(repo, "rev-parse", "HEAD") == origin_before

    transcript_path = tmp_path / "checkout-guard.txt"
    transcript_path.write_text("\n".join(transcript) + "\n", encoding="utf-8")
    print("\n".join(transcript))
