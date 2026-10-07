# Software Factory

Copy this whole folder into a repo as `.factory/`. Works with any model or chat product. System of record: **GitHub**.

## 20-second pitch

Work enters as a GitHub issue. Agents triage → (specs if hard) → build → review → verify → ship. Humans only at judgment gates. Skills and decisions live here so the next agent can continue without the chat.

## Triggers

| Trigger | What happens |
|---|---|
| **New / open GitHub issue** | Valid factory work item. The repo’s **factory worker** (or any agent with repo access) runs `skills/factory-loop.md`. |
| **Message to project coordinator** | Valid start of the **production line**. Coordinator = chief of staff, project lead bot, or any designated intake agent — not chat-as-queue. They run `skills/intake-from-coordinator.md`: file/refine a GitHub issue, then **hand off to the factory worker** to start the loop. |

Chat alone is never the work item. The issue is. Messaging the coordinator is how a human (or another agent) **kicks the line**: issue + explicit handoff to the worker.

If there is no separate worker yet, the coordinator may run `factory-loop` themselves after filing — still issue-first.

## Loop

1. **Intake** — GitHub issue with a clear outcome (from coordinator handoff or native issue).
2. **Triage** — easy → build; hard → product + tech specs on the issue.
3. **Spec gate (human)** — approve, or skip if trivial.
4. **Build** — sync latest default branch first (agents often have a stale tip), then branch + PR linked to the issue.
5. **Review** — agent first; human on risk and product (see merge authority below + `skills/liability-gates.md`).
6. **Verify** — CI + evidence on the PR (screenshots required for UI); fill the **Factory loop** section of the PR template so adherence is auditable; never merge on red/skipped required checks.
7. **Product gate (human)** — required for **normal** and **high** work; skipped only for **trivial**.
8. **Ship → monitor deploy → feed back** — merge only when authority allows; watch post-merge deploy CI; fix if red; lessons → issues/skills.

## Merge authority (by design)

| Risk class | Examples | Who may merge |
|---|---|---|
| **trivial** | Typos, docs-only, comment-only, pure playbook sync with **no** product/behavior change | Factory worker **may** merge after green required CI (no human wait) |
| **normal** | Features, bugfixes, behavior changes, **any UI / frontend / website / pages** | **Human product gate first** — do **not** auto-merge |
| **high** | License, secrets, auth, crypto, safety claims, workflows, CODEOWNERS, supply chain | **Human required** before merge |

If unsure whether something is trivial vs normal, treat it as **normal** and wait for a human.

## UI / frontend evidence

Any PR that changes a website, page, or UI **must** put screenshots in the PR **Evidence** section (embed or link; before/after when practical, or current state + what changed). Thread-only comments do **not** count. No Evidence screenshots → incomplete; do not ask for merge.

## Post-merge deploy

After merge: watch the repo’s deploy / pages / CD workflows on the default branch. If deploy CI fails, open a fix PR (or continue on the same issue) promptly — do not walk away after a green PR CI. Comment deploy status on the issue.

## Folder map

```
.factory/
  FACTORY.md                      ← this playbook (keep thin)
  DECISIONS.md                    ← append-only decisions for this repo
  DOCS.md                         ← map to repo docs (pointers only, no copies)
  skills/
    factory-loop.md               ← run the loop on an issue
    intake-from-coordinator.md    ← coordinator: chat → issue → hand off to worker
    liability-gates.md            ← hard stops (secrets, license, CI, over-claims, merge authority)
  sketches/                       ← copy these into the repo root / .github/
    CONTRIBUTING.md
    github/pull_request_template.md
    github/CODEOWNERS.example
    (add repo-specific skills under skills/, not sketches/)
```

- **Factory skills** → `.factory/skills/`
- **Repo documentation** → stays in the repo (`README`, `docs/`, …); list paths in `DOCS.md`
- **Contributor / PR / owners sketches** → copy from `.factory/sketches/` into the repo, then point `DOCS.md` at them

## Rules

- Humans own “is this useful?” for all **normal** and **high** work; only **trivial** may auto-merge
- History in GitHub + this folder — not only chat
- Leave work pick-uppable from issue/PR alone
- Agents see their own CI/evidence (incl. UI screenshots) before asking for review
- Follow `skills/liability-gates.md` on every change
- After merge, monitor deploy CI and correct failures
- Drop process that stopped helping
