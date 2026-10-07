<!-- Copy to .github/pull_request_template.md -->
<!-- Factory workers + Cursor agents: fill every section. This is how humans audit adherence. -->

## Summary

<!-- One or two sentences. -->

Closes #

## Factory loop

<!-- Required on every factory PR. Check what’s done; for N/A add a short note on the same line. -->

- [ ] **1. Intake** — Linked issue; one-sentence outcome stated on issue or below:
- [ ] **2. Triage** — easy / hard / high-risk → risk class: **trivial** | **normal** | **high**
- [ ] **3. Spec gate** — human approved specs / skipped (easy or trivial only)
- [ ] **4. Build** — synced latest default branch; branch + PR linked to issue; scope matches
- [ ] **5. Review** — agent self-review vs issue outcome + `.factory/skills/liability-gates.md`
- [ ] **6. Verify** — required CI green (or N/A + reason); evidence below; **UI → screenshots attached**
- [ ] **7. Product gate** — human approved (**required** for normal/high) / N/A trivial only
- [ ] **8. Ship + monitor** — merge only per risk class; after merge watch deploy/pages and fix if red

## Risk class

- [ ] trivial (typo/docs/comment/playbook-only — no product/behavior change; worker may merge after green CI)
- [ ] normal (feature/bugfix/behavior/**UI** — **human product gate before merge**)
- [ ] **high** (license, secrets, auth, crypto, safety, workflows, supply chain — human required)

## AI disclosure

- Tools used (factory worker / Cursor agent / both):
- Approx. share AI-authored: [ ] little [ ] mixed [ ] mostly
- Human reviewed before merge: [ ] yes [ ] no — who:

## Safety checklist

- [ ] No secrets, credentials, or `.env` content
- [ ] No `LICENSE` / `NOTICE` / SPDX change (or human approved + logged in `.factory/DECISIONS.md`)
- [ ] New deps: licenses checked / allowlisted (or N/A)
- [ ] Did not over-claim safety, security, or compliance in docs
- [ ] Did not auto-merge normal/high work

## Evidence

<!-- CI links, test output, screenshots (required for UI/frontend/pages) -->

## Notes for reviewers

<!-- Risks, follow-ups, what you want them to focus on -->

## Post-merge (worker)

- [ ] Deploy / pages / CD on default branch checked; fix opened if red; status on issue
