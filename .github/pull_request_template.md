<!-- Copy to .github/pull_request_template.md -->

## Summary

<!-- One or two sentences. Link the issue. -->

Closes #

## Risk class

- [ ] trivial (typo/docs/comment/playbook-only — no product/behavior change; worker may merge after green CI)
- [ ] normal (feature/bugfix/behavior/**UI** — **human product gate before merge**)
- [ ] **high** (license, secrets, auth, crypto, safety, workflows, supply chain — human required)

## AI disclosure

- Tools used:
- Approx. share AI-authored: [ ] little [ ] mixed [ ] mostly
- Human reviewed before merge request: [ ] yes [ ] no — who:

## Checklist

- [ ] Linked GitHub issue; scope matches the issue
- [ ] Tests / lint / required CI green (or N/A with reason)
- [ ] No secrets, credentials, or `.env` content
- [ ] No `LICENSE` / `NOTICE` / SPDX change (or human approved + logged in `.factory/DECISIONS.md`)
- [ ] New deps: licenses checked / allowlisted
- [ ] Did not over-claim safety, security, or compliance in docs
- [ ] High-risk / normal paths: requested human / CODEOWNERS review (not auto-merged)
- [ ] **UI / frontend / pages:** screenshots attached (before/after or current + note)

## Evidence

<!-- CI link, test output, screenshots (required for UI) -->

## Notes for reviewers

<!-- Risks, follow-ups, what you want them to focus on -->

## Post-merge (worker)

- [ ] Watch deploy / pages / CD on default branch after merge; fix if red; comment status on issue
