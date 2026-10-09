# Software Factory

Copy this whole folder into a repo as `.factory/`. Works with any model or chat product. System of record: **GitHub**.

## 20-second pitch

Work enters as a GitHub issue. Agents triage → (specs if hard) → build → review → verify → ship. Humans only at judgment gates. Skills and decisions live here so the next agent can continue without the chat.

## Triggers

| Trigger | What happens |
|---|---|
| **New / open GitHub issue** | Valid factory work item. The repo’s **factory manager** (or any agent with repo access) runs `skills/factory-loop.md`. |
| **Message to project coordinator** | Valid start of the **production line**. Coordinator = chief of staff, project lead bot, or any designated intake agent — not chat-as-queue. They run `skills/intake-from-coordinator.md`: file/refine a GitHub issue, then **hand off to the factory manager** to start the loop. |

Chat alone is never the work item. The issue is. Messaging the coordinator is how a human (or another agent) **kicks the line**: issue + explicit handoff to the manager.

If there is no separate manager yet, the coordinator may run `factory-loop` themselves after filing — still issue-first.

## Roles

| Role | Who | Does | Never |
|---|---|---|---|
| **Human owner** | The person | Product judgment, spec and product gates, approvals | — |
| **Coordinator** (optional) | Chief of staff / intake bot | Turns chat asks into issues, hands off | Builds |
| **Factory manager** | One bot per repo | Runs the loop, sequences work, launches and reviews worker agents, merges per gates | Decides product questions |
| **Workers** | Child cloud agents | Build, review, test on a branch/PR | Merge without the manager |
| **Giver** (recommended) | One bot per repo | Keeps the asks ledger, drafts decisions, challenges claims against the owner's asks — see `skills/giver.md` | Builds, merges, approves, spends |

## Loop

1. **Intake** — GitHub issue with a clear outcome (from coordinator handoff or native issue).
2. **Triage** — easy → build; hard → product + tech specs on the issue. Pick the model per `MODEL_ROUTING.md`.
3. **Spec gate (human)** — approve, or skip if trivial.
4. **Build** — sync latest default branch first (agents often have a stale tip), then branch + PR linked to the issue.
5. **Review** — agent first; human on risk and product (see merge authority below + `skills/liability-gates.md`).
6. **Verify** — CI + evidence on the PR (screenshots required for UI); fill the **Factory loop** section of the PR template so adherence is auditable; never merge on red/skipped required checks. Acceptance numbers must include the metric from the original ask (what the human actually complained about), not only proxies; the post-merge check reports that metric against its baseline. For high-risk changes to model or data output, show real before/after output from a cloud agent before the product gate (capped spend, publishes nothing), using the secrets listed in `DOCS.md`; don't defer the evidence to after merge.
7. **Product gate (human)** — required for **normal** and **high** work; skipped only for **trivial**. When approval arrives in chat (or elsewhere), the manager **edits the PR description first** (step 7 checked + Human reviewed before merge: yes + who), then merges — chat alone is not the audit trail. A human approver's approval that names the PR (e.g. "approve #88"), posted by them in the project's factory room or in a 1:1 chat with the manager, **is a direct merge instruction for that PR**: the manager merges it itself, with no second confirmation in another chat, once the PR body is updated, the branch is 0 behind the default branch, and required checks are green on the head commit. It covers only the named PR; a relay from another bot is not approval.
8. **Ship → monitor deploy → feed back** — merge only when authority allows; **right before merge, update the PR branch onto latest default branch and wait for required CI green on that new head commit** (see Rules); watch post-merge deploy CI; fix if red; lessons → issues/skills.

## Merge authority (by design)

| Risk class | Examples | Who may merge |
|---|---|---|
| **trivial** | Typos, docs-only, comment-only, pure playbook sync with **no** product/behavior change | Factory manager **may** merge after green required CI (no human wait) |
| **normal** | Features, bugfixes, behavior changes, **any UI / frontend / website / pages** | **Human product gate first** — do **not** auto-merge |
| **high** | License, secrets, auth, crypto, safety claims, workflows, CODEOWNERS, supply chain | **Human required** before merge |

If unsure whether something is trivial vs normal, treat it as **normal** and wait for a human.

## UI / frontend evidence

Any PR that changes a website, page, or UI **must** put screenshots in the PR **Evidence** section (embed or link; before/after when practical, or current state + what changed). Thread-only comments do **not** count. No Evidence screenshots → incomplete; do not ask for merge.

## Post-merge deploy

After merge: watch the repo’s deploy / pages / CD workflows on the default branch. If deploy CI fails, open a fix PR (or continue on the same issue) promptly — do not walk away after a green PR CI. Comment deploy status on the issue.

## Scheduled jobs (cron) watch

Scheduled workflows (daily data jobs, nightly builds) can fail with no PR in flight. At the start of each work session, and after any merge that touches a scheduled job, check the latest scheduled runs on the default branch. If one failed, open (or reopen) a bug issue with the failing step and log excerpt, tell the human, and treat it as top priority. Also note run duration trends; a big jump is worth an issue. A green run is not enough: confirm the job's output actually reached its destination (for example, the published site shows today's data). Pushes made with the default workflow token do not trigger other workflows, so a job that commits data can silently skip the deploy. Also check that scheduled runs actually start: GitHub delays or drops scheduled runs under load, worst at the top of the hour, so schedule cron jobs at an odd minute (for example `17 6 * * *`, not `0 6 * * *`) and schedule early enough that a delay of several hours is harmless. Keep scheduling inside GitHub Actions (no outside scheduler). For a daily job that matters, schedule several guarded crons spread over a few hours (each exits immediately if today's run already succeeded, all in one concurrency group, and no-op runs must not redeploy or publish), because GitHub can create scheduled runs many hours late. Also note GitHub disables schedules on public repos after 60 days without repository activity; confirm the project's activity keeps them alive. Flag a finding only when no run has *finished* by the project's freshness deadline (e.g. late morning), not merely when a start is late. If a job has a time or cost limit that degrades quietly when hit (skips work instead of failing), the daily check flags any run above about 80% of that limit, and any PR that adds work to that job must show a projection of the whole job, with every step scaled to the expected growth, under the limit before merge.

## Folder map

```
.factory/
  FACTORY.md                      ← this playbook (keep thin)
  DECISIONS.md                    ← append-only decisions for this repo
  DOCS.md                         ← map to repo docs (pointers only, no copies)
  MODEL_ROUTING.md                ← which model per task; what to do when spend limits hit
  skills/
    factory-loop.md               ← run the loop on an issue
    intake-from-coordinator.md    ← coordinator: chat → issue → hand off to manager
    giver.md                      ← giver: asks ledger, decision drafts, healthy challenge
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

- Pin a model on every agent launch per `MODEL_ROUTING.md`; cheapest capable model first; never enable on-demand spend yourself

- Humans own “is this useful?” for all **normal** and **high** work; only **trivial** may auto-merge
- Chat (or issue) product-gate approval must be **written onto the PR description** before merge
- **Update the branch right before every merge** (trivial, or after the human gate): if behind the default branch, update it, wait for required CI green on the new head, then merge — never a behind branch or stale-commit CI. Clean catch-up keeps approval; conflicts or changes to the PR’s own diff/behavior → re-verify and tell the human (re-ask the gate for normal/high). Update before human review, too
- **Bypass merges:** If you merge with an admin/ruleset bypass, the bypass skips every rule including the up-to-date check, so first verify by hand that the branch is 0 commits behind the default branch and that all required checks are green on the current head SHA; use a merge method the ruleset allows.
- History in GitHub + this folder — not only chat
- Leave work pick-uppable from issue/PR alone
- Agents see their own CI/evidence (incl. UI screenshots) before asking for review
- Follow `skills/liability-gates.md` on every change
- After merge, monitor deploy CI and correct failures
- Check scheduled (cron) workflow runs each session; a failure becomes a top-priority bug issue
- Drop process that stopped helping

## Daily newcomer review (optional, recommended for live products)

Once a day, after the scheduled job finishes, the manager launches a short cloud-agent review (pinned to the trivial/normal model, a few minutes' cap) that looks at the live product as a newcomer would, against `DOCS.md` and the project goals. It logs only obvious problems (misaligned with goals, unhelpful, clearly bad data or output) as issues: at most ~3 per day, de-duplicated against open issues, each with evidence (screenshot or live data) and the goal it misses, plus the review's run ID. Fixes go through the normal loop and risk gates; only true trivial fixes auto-merge.

