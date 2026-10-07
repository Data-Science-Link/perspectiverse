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
5. **Review** — agent first; human on risk (see `skills/liability-gates.md`).
6. **Verify** — CI + evidence on the PR; never merge on red/skipped required checks.
7. **Product gate (human)** — is this useful?
8. **Ship → monitor → feed back** — merge/close; new lessons → new issues or skill updates.

## Folder map

```
.factory/
  FACTORY.md                      ← this playbook (keep thin)
  DECISIONS.md                    ← append-only decisions for this repo
  DOCS.md                         ← map to repo docs (pointers only, no copies)
  skills/
    factory-loop.md               ← run the loop on an issue
    intake-from-coordinator.md    ← coordinator: chat → issue → hand off to worker
    liability-gates.md            ← hard stops (secrets, license, CI, over-claims)
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

- Humans own “is this useful?” and all **high-risk** merges
- History in GitHub + this folder — not only chat
- Leave work pick-uppable from issue/PR alone
- Agents see their own CI/evidence before asking for review
- Follow `skills/liability-gates.md` on every change
- Drop process that stopped helping
