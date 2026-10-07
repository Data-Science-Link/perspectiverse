# Skill: factory-loop

Run when an **open GitHub issue** should move through the factory — including after a coordinator handoff (`intake-from-coordinator.md`).

Also follow `liability-gates.md` on every change.

## Before you start

1. **Sync to latest default branch** before you branch or push. Cursor cloud agents (and local checkouts) can be slightly stale — fetch and rebase/merge onto current `main` (or the repo’s default branch) first; do not build on an outdated tip.
2. Read `.factory/FACTORY.md`, `.factory/DOCS.md`, `.factory/skills/liability-gates.md`, and recent `.factory/DECISIONS.md`.
3. Open the issue. Ensure a one-sentence outcome is visible (comment if needed). If still unclear, ask once on the issue — then stop guessing.

## Triage

- **Easy** — clear, low risk: skip specs; branch and implement.
- **Hard** — write short product + technical specs on the issue (or linked files); wait for human approval before coding.
- **High-risk** (license, secrets, auth, crypto, safety, workflows): treat as hard; human review required before merge.
- Assign a **risk class** on the PR: `trivial` | `normal` | `high` (see merge authority).
- **Pick the model** from `.factory/MODEL_ROUTING.md` using risk class + type of work; note it on the issue. Pin it on every cloud-agent launch (never Auto). Escalate only per the table.

## Build

- Branch from default; open a PR that references the issue.
- Stay inside issue scope. Lasting choices → `.factory/DECISIONS.md`.
- Follow repo conventions via `.factory/DOCS.md` and any repo-specific skills here.
- **Fill the whole PR template**, especially the **Factory loop** section (steps 1–8). That checklist is how humans audit process adherence — leave it blank only if a step is truly N/A, with a one-line note.
- Fill risk class, AI disclosure, safety checklist, and evidence.
- **UI / frontend / website / pages:** put screenshots in the PR **Evidence** section of the description (embed or link; before/after when practical). Thread-only comments do **not** count. No Evidence screenshots → do not treat the PR as ready.

## Review & verify

- Self-review against the issue outcome / specs and `liability-gates.md`.
- Run tests/CI; put evidence on the PR (CI links, tests, **screenshots for UI**).
- Do not merge if required CI is red, pending, or skipped.

### Merge authority (do not invent exceptions)

| Class | Merge rule |
|---|---|
| **trivial** | Typos, docs-only, comment-only, pure `.factory/` playbook with **no** product/behavior change. Worker **may** merge after green required CI. |
| **normal** | Features, bugfixes, behavior changes, **any UI**. **Wait for human product gate** — never auto-merge. |
| **high** | License/secrets/auth/crypto/safety/workflows/CODEOWNERS/supply chain. **Human required** before merge. |

If unsure → **normal** (wait for human). Behavior changes (e.g. clustering thresholds, defaults users feel) are **normal**, not trivial.

### Record the human gate on the PR (required)

When a human gives product-gate (or similar) approval in **chat**, on the issue, or elsewhere:

1. **Edit the PR description before you merge** — do not merge on chat approval alone.
2. Check **Factory loop step 7 (Product gate)** as done.
3. Set **AI disclosure → Human reviewed before merge: yes** and name who (e.g. Michael / @User).
4. Update any other matching fields (spec gate, safety “did not auto-merge”, Notes) so the PR body matches reality.
5. Then merge per risk class.

The PR body is the durable audit trail. Chat is ephemeral relative to GitHub.

## Ship & feed back

- Merge only when the table above allows.
- **Before handing a PR to the human for review:** update the branch onto latest default branch so it is current at review time.
- **Immediately before any merge** (trivial auto-merge, or after the human gate):
  1. Check whether the PR branch is behind the default branch.
  2. If behind, update it (GitHub “Update branch” / `update_pull_request_branch`, or merge/rebase main in).
  3. Wait for required CI to pass on the **new head commit**; only then merge.
  4. A human approval given while the branch was behind still stands for a clean catch-up update. If the update hits conflicts or changes the PR’s own diff or behavior: resolve, re-verify, and tell the human what changed before merging (re-ask the gate for normal/high).
  5. Never merge a branch that is behind, and never merge on CI results from a stale commit.
- **After merge — monitor deploy:** watch pages / deploy / CD workflows on the default branch. If deploy CI is red or stuck, open a fix promptly (same issue or new); comment status on the issue. Do not walk away after PR CI alone was green.
- Close or update the issue when ship + deploy are good (or note follow-ups).
- **Scheduled jobs:** at the start of each session, check the latest scheduled (cron) workflow runs on the default branch. A failed run becomes a bug issue (failing step + log excerpt), is reported to the human, and goes to the top of the queue. Flag big jumps in run duration too.
- Failures, monitor hits, process lessons → new GitHub issues and/or skill updates. Not chat-only.
