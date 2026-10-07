# Skill: liability-gates

Hard stops for factory agents on **public** repos. Reduces common failure modes (secrets, license contamination, false safety claims, merging without evidence). **Not legal advice** — does not eliminate liability.

Read this with `factory-loop.md` on every change.

## Never (stop and escalate to a human)

1. Commit secrets, `.env`, key material, tokens, or paste them into issues/PRs/logs.
2. Change `LICENSE`, `NOTICE`, copyright headers, or SPDX identifiers without a human decision logged in `.factory/DECISIONS.md`.
3. Disable, bypass, or weaken required CI, branch protection, CODEOWNERS, or secret scanning.
4. Merge (or ask to auto-merge) when required checks are red, pending, or skipped.
5. Add dependencies with unknown or disallowed licenses (especially strong copyleft like GPL/AGPL) without human approval.
6. Invent or “fix” license/attribution metadata the agent cannot verify from the source.
7. Over-claim safety, medical, security, or compliance outcomes in README/docs/marketing copy.
8. Relicense the project or strip third-party notices because “AI rewrote it.”

## Always

1. Sync to the latest default branch (`git fetch` + update from `main`/default) before branching or continuing a stale agent checkout.
2. Open a PR linked to the issue; put evidence on the PR (CI, tests, screenshots).
3. Fill the PR template: risk class, AI disclosure, secrets/license checklist.
4. Request **human** review when touching: auth, crypto, payments, PII, safety-related behavior, `.github/workflows`, CODEOWNERS, Dependabot, LICENSE/NOTICE, security docs.
5. Prefer deps from an allowlisted set when the repo defines one (e.g. MIT, Apache-2.0, BSD-2/3).
6. Document limitations and non-goals instead of adding compliance theater.
7. Leave work pick-uppable: issue + PR explain what changed and what still needs a human.

## Risk classes (for PR template)

| Class | Examples | Gate |
|---|---|---|
| **trivial** | Typos, docs-only, comment fixes | Agent self-review + green CI |
| **normal** | Feature/bugfix with tests | Agent review + green CI; human product gate if user-facing |
| **high** | License, secrets, auth, crypto, safety claims, workflows, supply chain | **Human required** before merge |

## If unsure

Stop. Comment on the issue/PR with the question. Do not guess on license, safety claims, or secrets.
