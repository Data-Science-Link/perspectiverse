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

### 2026-10-07 — Factory-loop section required on every factory PR
- **Decision:** The GitHub PR template includes a succinct **Factory loop** checklist (intake → triage → spec gate → build → review → verify → product gate → ship/monitor). Factory workers and Cursor agents must fill it on every factory PR so humans can audit process adherence from the PR alone.
- **Why:** Hard to tell from chat whether workers followed the playbook; PR is the durable, multiplayer surface.
- **Alternatives:** Chat-only status updates; separate process ticket per change.
- **Revisit when:** Checklist becomes noise or steps change.

### 2026-10-07 — UI screenshots must be in PR Evidence section
- **Decision:** UI/frontend screenshots must live in the PR **Evidence** section of the description (not only a conversation comment). Factory skills and PR template updated to enforce this.
- **Why:** Thread-only comments are easy to miss, not durable in the PR body, and harder to audit at a glance. The Evidence section is the canonical place for CI links, test output, and screenshots.
- **Alternatives:** Allow screenshots anywhere on the PR (comment, review, description); rely on convention.
- **Revisit when:** PR review tooling makes comment-based screenshots equally prominent and durable.

### 2026-10-07 — Chat product-gate approval must update the PR description
- **Decision:** When a human product gate (or similar review) is given in chat or another channel, the factory worker must **edit the PR description** before merging: check **Factory loop step 7 (Product gate)**, set **Human reviewed before merge: yes** (and who), and any other matching review fields. Chat approval alone is not enough — the PR body is the durable audit trail.
- **Why:** Workers were merging after chat "Approved" without reflecting that on the PR; humans auditing the PR later could not see that a product gate happened.
- **Alternatives:** Rely on chat history only; require a GitHub review click instead of chat.
- **Revisit when:** Branch protection requires an approving GitHub review for all normal/high PRs.

### 2026-10-07 — Faces chosen by fit in 2..6; drop, never pad (#53)
- **Decision:** `choose_n_faces` tries k = 2..6 in the planet's own embedding space and keeps the best mean cosine silhouette among counts that pass hard gates: every face ≥ `MIN_FACE_POSTS` (2) posts and ≥ `MIN_FACE_SHARE` (0.05), face centroids below cosine 0.90, and every face at least as tight as its planet. No passing count → `None`, and the planet is not published. If labeling collapses a split below 2 faces (Mixed remarks or alike titles), the next passing count is tried once, then the planet is dropped. A final guard drops any planet outside 2–6 faces before `validate_payload`, which stays strict.
- **Why:** The 2026-10-07 daily run failed validation on a 1-face planet. #43 set the floor to 2 but `choose_n_faces` could still return 1 and post-label merging could collapse faces. Picking the highest k that passed (inertia "gain" always grows with k) also over-split planets into near-duplicate faces. Michael (#53): small minorities are fine, groupings must be tight, and more than one perspective must exist.
- **Alternatives:** Relax the schema to allow 1 face (#32 proposal 4; rejected in #41); pad a second face; keep 1-post faces (a lone remark is not a group).
- **Revisit when:** Production logs show many popular planets dropped for lack of a second face, or LLM labels routinely merge silhouette-chosen faces.

### 2026-10-07 — Label planets lazily and concurrently; section time budget (#53)
- **Decision:** Labeling stops once `catalog_size` planets survive (global and per section); the planet name and briefs are generated only for survivors. With a network label backend, `label_workers` (default 8) planets are labeled concurrently and results are used in rank order. Section solar systems run largest first under `section_budget_minutes` (default 15). One planet or section that raises is logged and skipped.
- **Why:** The 2026-10-07 run took ~2.5 h: ~140 candidate planets × ~8 sequential LLM calls (~1,170 calls at ~7–11 s each). Clustering itself was ~1 min but allocated an n×k×d tensor (8.8 GB peak at 7,447 claims); it now uses an n×k distance form.
- **Alternatives:** Drop LLM briefs for section planets; cache labels across global and section planets; a total LLM-call budget.
- **Revisit when:** DeepInfra rate limits (429) show up in logs, or the job still exceeds ~30 minutes.

### 2026-10-07 — Watch scheduled (cron) workflow runs, not just post-merge deploys
- **Decision:** Factory workers check the latest scheduled workflow runs on the default branch at the start of each session and after merges touching scheduled jobs. A failed run becomes a top-priority bug issue (failing step + log excerpt) and is reported to the human; large duration jumps are flagged.
- **Why:** A daily data job failed and the site silently served stale data; it surfaced only when a human asked about something else. Post-merge deploy watching doesn't cover cron jobs with no PR in flight.
- **Alternatives:** GitHub email notifications only; a separate monitoring bot.
- **Revisit when:** The repo has real alerting on scheduled job failures.

### 2026-10-07 — Model routing table; pin models, cheapest capable first
- **Decision:** Add `MODEL_ROUTING.md`. Workers pick a model at triage from risk class + type of work, pin it on every cloud-agent launch (never Auto), escalate one step at a time, and record the model in the PR body. Cursor Models pool (Composer 2.5, Grok 4.7) first; third-party models only when stuck or for a high-risk second opinion. Other Models exhausted → stay on Cursor Models; Cursor Models exhausted → stop new work and ask the human. Workers never enable on-demand spend.
- **Why:** The Other Models pool hit 100% while Cursor Models sat at 1%, blocking agent launches; model choice was implicit and cost-blind.
- **Alternatives:** Leave everything on Auto; one model for all work.
- **Revisit when:** Plan, pool rules, or model lineup changes.

### 2026-10-07 — Update PR branch onto latest main right before merge; repo setting requires up-to-date branches
- **Decision:** Immediately before any merge (trivial auto-merge, or after the human gate), the worker updates the PR branch onto the latest default branch if it is behind and merges only after required CI is green on that new head commit. PRs are also updated before handing them to the human for review. A clean catch-up keeps prior approval; conflicts or changes to the PR’s own diff/behavior are re-verified and reported to the human (gate re-asked for normal/high). As a second layer, repos enable "Always suggest updating pull request branches" and require branches to be up to date (strict status checks) on the default branch.
- **Why:** PRs were reaching human review, and could be merged, while out of date with main, so CI results no longer described what would actually land.
- **Alternatives:** Rely on the start-of-work sync only; merge queue.
- **Revisit when:** The repo adopts a merge queue or the platform auto-updates branches before merge.

### 2026-10-07 — Section labels share one pool; ceiling is 20 minutes (#71)
- **Decision:** Section solar systems are ordered by post volume and labeled through one shared pool. The default `label_workers` of 8 stays the global cap and is widened to 12 in-flight calls for sections; any other `label_workers` is the section cap. `section_budget_minutes` defaults to 20. `0` still skips sections and `None` still means the default. Labeling still stops at `catalog_size` survivors per section, and one bad planet or section is logged and skipped.
- **Why:** Run 37696485020 built 4 of 10 sections in 1,052s and skipped the rest with "the section time budget is spent." Sections ran one after another, so partial waves left workers idle. Sharing the pool keeps the biggest sections first if the ceiling hits, and 12 in flight fits the live planet counts inside 20 minutes.
- **Alternatives:** Raise the ceiling to ~35 minutes and keep serial sections; cap each section at 6 planets.
- **Revisit when:** Live logs show HTTP 429s under 12 in-flight calls, or a day still drops sections inside 20 minutes.

### 2026-10-07 — Bypass merges: verify up-to-date + green by hand
- **Decision:** Factory PRs authored by the owner's account can't get the ruleset's required approval, so workers merge chat-approved and trivial PRs with the admin bypass. Because a bypass skips every rule, including the up-to-date check, the worker first verifies by hand that the branch is 0 commits behind the default branch and all required checks are green on the current head SHA, and uses a merge method the ruleset allows. The review rule and bypass actors stay unchanged.
- **Why:** Keeps the "update onto latest main right before merge" guarantee when the ruleset itself is bypassed.
- **Alternatives:** Remove the review requirement; a separate bot account to approve.
- **Revisit when:** PRs come from an account that can be approved, or a merge queue is adopted.

### 2026-10-07 — Pages follows a successful daily pipeline via workflow_run (#70)
- **Decision:** `pages.yml` triggers on `workflow_run` completion of `Daily Discourse Pipeline`, and the build job runs only when that conclusion is `success` (deploy `needs: build`, so a skip skips the deploy). Checkout stays unset, so a `workflow_run` deploy builds the default branch (`main`), then overlays `public/data.json` from `data-snapshot`. Existing `push`, `workflow_dispatch`, and the `pages` concurrency group stay.
- **Why:** The pipeline pushes `data-snapshot` with `GITHUB_TOKEN`, which does not start `push` workflows, so new snapshots never auto-deployed. `workflow_run` does run after that, and its `GITHUB_REF` is `main`, which is the only branch the `github-pages` environment allows.
- **Alternatives:** A final `gh workflow run` step in `pipeline.yml` (touches the pipeline and needs `actions: write`). A PAT push so the `data-snapshot` push trigger fires (that ref is not allowed to deploy to `github-pages`).
- **Revisit when:** The Pages environment branch policy changes, or the pipeline stops publishing `data-snapshot`.
