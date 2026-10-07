# Decision log

Append-only. Newest at the bottom.

## Template

```
### YYYY-MM-DD — Short title
- **Decision:** what we chose
- **Why:** one or two sentences
- **Alternatives:** what we rejected (optional)
- **Revisit when:** trigger to reconsider (optional)
```

## Log

### 2026-10-06 — Factory layout
- **Decision:** Ship a copy-paste `.factory/` template: `FACTORY.md`, `DECISIONS.md`, `DOCS.md`, `skills/`
- **Why:** Portable across repos and models; process separate from product docs
- **Alternatives:** Root-level files only; heavyweight monorepo factory infra
- **Revisit when:** A target repo already uses `.factory` for something else

### 2026-10-06 — GitHub issues as sole intake
- **Decision:** Factory work = GitHub issues only. CoS chat files issues; open issues start the loop when a watcher/agent picks them up.
- **Why:** Durable, multiplayer, pick-uppable; history out of chat
- **Alternatives:** Chat-as-queue; external tracker as primary
- **Revisit when:** Need a label/filter so not every issue enters the factory

### 2026-10-06 — Coordinator message kicks the production line
- **Decision:** A message to the project coordinator (CoS or similar) is a factory trigger: file/refine a GitHub issue, then hand off to the factory worker (`intake-from-coordinator.md`). Renamed skill from intake-from-cos.
- **Why:** Stakeholder chat should start the line, not only create a dormant issue; still issue-first and multiplayer.
- **Alternatives:** CoS files issue and always stops; chat-as-queue with no GitHub issue.
- **Revisit when:** A project uses labels so only some coordinator asks enter the factory.

### 2026-10-06 — Adopt software factory on Perspectiverse
- **Decision:** Add `.factory/` playbook to the Perspectiverse repo.
- **Why:** Provides a durable, agent-readable process layer without touching product/app code. Agents can orient from `.factory/DOCS.md` → real repo files rather than rediscovering paths each session.
- **Alternatives:** Keep process in chat only; use a separate process repo.
- **Revisit when:** The repo gains a second sub-package or a dedicated docs site that changes the path map in `DOCS.md`.

### 2026-10-06 — Liability gates + contributor sketches
- **Decision:** Add `skills/liability-gates.md` and portable sketches (`CONTRIBUTING.md`, PR template, CODEOWNERS example) under `.factory/sketches/`. Factory-loop must follow liability-gates. Not legal advice; does not eliminate liability.
- **Why:** Light-review public factories need machine-readable hard stops (secrets, license, CI, over-claims) and copy-paste diligence artifacts.
- **Alternatives:** Repo-only ad hoc docs; no agent-enforced gates.
- **Revisit when:** Counsel provides project-specific terms, or CLA is chosen over DCO.

### 2026-10-06 — Always sync latest main before factory work
- **Decision:** Factory skills require fetching/updating onto the current default branch before branching or continuing work; cloud agents may have a slightly stale main.
- **Why:** Avoid PRs based on outdated tips and painful rebase conflicts.
- **Alternatives:** Hope the agent environment is fresh; only sync when conflicts appear.
- **Revisit when:** Agent harnesses guarantee up-to-date default branch at start.

### 2026-10-07 — Hard minimum of 2 perspectives per published planet (#41)
- **Decision:** Set `MIN_FACES = 2` in `pipeline/schema.py`; lower `MIN_FACE_SHARE` to 0.05 in `perspectives.py`; remove inertia-gain as a veto in `choose_n_faces` (tiebreaker only); every face needs at least one post. Frontend mirrors in `src/lib/faces.js` and `src/lib/polyhedra.js` already carried `MIN_FACES = 2`.
- **Why:** A skewed planet collapsed to a single 100% bar hid real minority viewpoints. Michael explicitly prioritised issue #41 (hard floor of 2) over the earlier #32 proposal that allowed one face.
- **Alternatives:** #32 proposal 4 (allow one face); raising inertia-gain threshold to prevent trivial splits.
- **Revisit when:** Evidence that forcing k ≥ 2 on a near-uniform corpus introduces misleading splits in production.

### 2026-10-07 — Merge authority: trivial may auto-merge; normal/high need human
- **Decision:** Only **trivial** PRs (typo/docs/comment/playbook-only, no product/behavior change) may be merged by the factory worker after green required CI. **Normal** (features, bugfixes, behavior, any UI) and **high** require a human before merge. Unsure → normal.
- **Why:** Auto-merges on green CI for user-facing work surprised stakeholders; design allows simple stuff to ship without blocking, but product judgment stays human.
- **Alternatives:** Never auto-merge; always auto-merge on green CI.
- **Revisit when:** Branch protection / CODEOWNERS enforce the same split mechanically.

### 2026-10-07 — UI PRs require screenshots
- **Decision:** Any factory PR that changes websites, pages, or UI must attach screenshots on the PR before it is treated as ready / mergeable.
- **Why:** Text diffs under-communicate visual regressions; humans need a fast visual gate.
- **Alternatives:** Optional screenshots; video-only; rely on live preview links alone.
- **Revisit when:** Automated visual regression is wired into CI.

### 2026-10-07 — Post-merge deploy monitoring
- **Decision:** After merge, the factory worker watches deploy/pages/CD on the default branch and opens a fix if it fails; status is commented on the issue.
- **Why:** Green PR CI is not the same as a healthy deployment; walking away after merge leaves broken sites.
- **Alternatives:** Rely only on humans noticing Pages failures; separate deploy-only bot.
- **Revisit when:** Deploy notifications are automatic and always routed to the worker.
