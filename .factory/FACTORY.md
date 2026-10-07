# Software Factory

Copy this whole folder into a repo as `.factory/`. Works with any model or chat product. System of record: **GitHub**.

## 20-second pitch

Work enters as a GitHub issue. Agents triage → (specs if hard) → build → review → verify → ship. Humans only at judgment gates. Skills and decisions live here so the next agent can continue without the chat.

## Triggers

| Trigger | What happens |
|---|---|
| **New / open GitHub issue** | Valid factory work item. An agent with repo access should pick it up using `skills/factory-loop.md`. |
| **Chat with project chief of staff** | Valid *request*. CoS uses `skills/intake-from-cos.md` to file or refine a GitHub issue, then stops. The **issue** is what the factory runs on — not the chat thread. |

Chat alone is not a queue. If it isn't an issue yet, it isn't in the factory yet.

**"Automatic" means:** once an issue exists (and your agent/routines watch that repo), the loop applies. Filing from CoS chat is deliberate; pickup depends on whoever is assigned to watch issues (you, a routine, or a coding agent) — not silent magic with no watcher.

## Loop

1. **Intake** — GitHub issue with a clear outcome.
2. **Triage** — easy → build; hard → product + tech specs on the issue.
3. **Spec gate (human)** — approve, or skip if trivial.
4. **Build** — branch + PR linked to the issue.
5. **Review** — agent first; human on risk.
6. **Verify** — CI + evidence on the PR.
7. **Product gate (human)** — is this useful?
8. **Ship → monitor → feed back** — merge/close; new lessons → new issues or skill updates.

## Folder map

```
.factory/
  FACTORY.md           ← this playbook (keep thin)
  DECISIONS.md         ← append-only decisions for this repo
  DOCS.md              ← map to repo docs (pointers only, no copies)
  skills/
    factory-loop.md    ← run the loop on an issue
    intake-from-cos.md ← CoS: chat → GitHub issue
    (add repo-specific skills here)
```

- **Factory skills** → `.factory/skills/`
- **Repo documentation** → stays in the repo (`README`, `docs/`, …); list paths in `DOCS.md`
- **Product/code conventions** → repo-specific skills under `.factory/skills/` *or* linked from `DOCS.md`

## Rules

- Humans own "is this useful?"
- History in GitHub + this folder — not only chat
- Leave work pick-uppable from issue/PR alone
- Agents see their own CI/evidence before asking for review
- Drop process that stopped helping
