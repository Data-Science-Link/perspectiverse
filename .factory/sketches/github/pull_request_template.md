<!-- Copy to .github/pull_request_template.md -->

## Summary

<!-- One or two sentences. Link the issue. -->

Closes #

## Risk class

- [ ] trivial (typo/docs)
- [ ] normal
- [ ] **high** (license, secrets, auth, crypto, safety, workflows, supply chain)

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
- [ ] High-risk paths: requested human / CODEOWNERS review

## Evidence

<!-- CI link, test output, screenshots -->

## Notes for reviewers

<!-- Risks, follow-ups, what you want them to focus on -->
