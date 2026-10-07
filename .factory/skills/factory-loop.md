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

## Build

- Branch from default; open a PR that references the issue.
- Stay inside issue scope. Lasting choices → `.factory/DECISIONS.md`.
- Follow repo conventions via `.factory/DOCS.md` and any repo-specific skills here.
- Fill the PR template (AI disclosure, risk class, checklist).

## Review & verify

- Self-review against the issue outcome / specs and `liability-gates.md`.
- Run tests/CI; put evidence on the PR.
- Human only at: spec gate, high-risk / CODEOWNERS paths, product gate.
- Do not merge if required CI is red, pending, or skipped.

## Ship & feed back

- After merge: close or update the issue.
- Failures, monitor hits, process lessons → new GitHub issues and/or skill updates. Not chat-only.
