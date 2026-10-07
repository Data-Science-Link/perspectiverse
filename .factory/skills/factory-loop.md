# Skill: factory-loop

Run when an **open GitHub issue** should move through the factory.

## Before you start

1. Read `.factory/FACTORY.md`, `.factory/DOCS.md`, and recent `.factory/DECISIONS.md`.
2. Open the issue. Ensure a one-sentence outcome is visible (comment if needed). If still unclear, ask once on the issue — then stop guessing.

## Triage

- **Easy** — clear, low risk: skip specs; branch and implement.
- **Hard** — write short product + technical specs on the issue (or linked files); wait for human approval before coding.

## Build

- Branch from default; open a PR that references the issue.
- Stay inside issue scope. Lasting choices → `.factory/DECISIONS.md`.
- Follow repo conventions via `.factory/DOCS.md` and any repo-specific skills here.

## Review & verify

- Self-review against the issue outcome / specs.
- Run tests/CI; put evidence on the PR.
- Human only at: spec gate, risky review, product gate.

## Ship & feed back

- After merge: close or update the issue.
- Failures, monitor hits, process lessons → new GitHub issues and/or skill updates. Not chat-only.
