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

## Build

- Branch from default; open a PR that references the issue.
- Stay inside issue scope. Lasting choices → `.factory/DECISIONS.md`.
- Follow repo conventions via `.factory/DOCS.md` and any repo-specific skills here.
- Fill the PR template (AI disclosure, risk class, checklist).
- **UI / frontend / website / pages:** attach screenshots on the PR (before/after when practical). No screenshots → do not treat the PR as ready.

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

## Ship & feed back

- Merge only when the table above allows.
- **After merge — monitor deploy:** watch pages / deploy / CD workflows on the default branch. If deploy CI is red or stuck, open a fix promptly (same issue or new); comment status on the issue. Do not walk away after PR CI alone was green.
- Close or update the issue when ship + deploy are good (or note follow-ups).
- Failures, monitor hits, process lessons → new GitHub issues and/or skill updates. Not chat-only.
