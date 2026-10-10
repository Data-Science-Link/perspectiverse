# Decision log

Append-only. Newest at the bottom.

## Template

```
### YYYY-MM-DD — Short title
- **Decision:** what we chose
- **Why:** one or two sentences
- **Decided by:** who made the call (optional; use when attributing credit matters)
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

### 2026-10-07 — Section labels share one pool; ceiling is 20 minutes (#71)
- **Decision:** Section solar systems are ordered by post volume and labeled through one shared pool. The default `label_workers` of 8 stays the global cap and is widened to 12 in-flight calls for sections; any other `label_workers` is the section cap. `section_budget_minutes` defaults to 20. `0` still skips sections and `None` still means the default. Labeling still stops at `catalog_size` survivors per section, and one bad planet or section is logged and skipped.
- **Why:** Run 37696485020 built 4 of 10 sections in 1,052s and skipped the rest with "the section time budget is spent." Sections ran one after another, so partial waves left workers idle. Sharing the pool keeps the biggest sections first if the ceiling hits, and 12 in flight fits the live planet counts inside 20 minutes.
- **Alternatives:** Raise the ceiling to ~35 minutes and keep serial sections; cap each section at 6 planets.
- **Revisit when:** Live logs show HTTP 429s under 12 in-flight calls, or a day still drops sections inside 20 minutes.

### 2026-10-07 — 20-minute section ceiling supersedes the 15-minute default (#71)
- **Decision:** The 15-minute `section_budget_minutes` default in "Label planets lazily and concurrently; section time budget (#53)" is superseded. Section solar systems are ordered by post volume and labeled through one shared pool: 12 calls in flight when `label_workers` is the default 8, and that configured value otherwise (`label_workers` 0 is one at a time). The ceiling default is 20 minutes. `0` still skips sections and `None` still means the default.
- **Why:** The earlier bullet still says 15 minutes. Run 37696485020 published 4 of 10 sections under that serial ceiling. The shared pool and the 20-minute ceiling are the current default.
- **Alternatives:** Editing the older bullet in place.
- **Revisit when:** A live run under the 20-minute ceiling still drops sections, or HTTP 429s show up at 12 in flight.

### 2026-10-07 — Shared pool and 20-minute ceiling supersede the 15-minute section budget (#71)
- **Decision:** This supersedes the earlier entry dated 2026-10-07 headed "Label planets lazily and concurrently; section time budget (#53)" (that entry's `section_budget_minutes` default of 15). Section solar systems are ordered by post volume and labeled through one shared pool: 12 calls in flight when `label_workers` is the default 8, and that configured value otherwise (`label_workers` 0 is one at a time). The ceiling default is 20 minutes. `0` still skips sections and `None` still means the default. Pointer: [2026-10-07 — Label planets lazily and concurrently; section time budget (#53)](#2026-10-07-label-planets-lazily-and-concurrently-section-time-budget-53).
- **Why:** The named entry still records a 15-minute default. Run 37696485020 published 4 of 10 sections under that serial ceiling. The shared pool and the 20-minute ceiling are the current default.
- **Alternatives:** Editing that older entry in place.
- **Revisit when:** A live run under the 20-minute ceiling still drops sections, or HTTP 429s show up at 12 in flight.

### 2026-10-08 — Keep planets that collapse below two faces; record distinctness (#76)
- **Decision:** This supersedes the drop-the-planet rule in [2026-10-07 — Faces chosen by fit in 2..6; drop, never pad (#53)](#2026-10-07-faces-chosen-by-fit-in-26-drop-never-pad-53). `choose_n_faces` still returns `None` when no k in 2..6 passes the silhouette gates, but `split_perspectives` then forces a 2-way cut (residual axis, embedding 2-means, Ward, or TF-IDF 2-means — whichever has the tightest cosine silhouette, then the higher distinctness, then the lower term overlap). Both faces are labeled. If labeling or a same-stance merge would leave fewer than two faces, the pre-collapse faces are kept and alike titles gain a distinguishing term; a last forced cut is labeled with merging turned off. The planet is not dropped for having fewer than two faces. Each published planet carries optional `face_distinctness` in `data.json` (`1 - max centroid cosine`, clipped to 0..1). The schema allows it to be missing. The frontend copies the topic through and does not require the field.
- **Why:** Run 37706379226 published 0 Health planets and 1 Culture and 1 Sports planet because faces collapsed. Michael: that is a weak grouping algorithm, not a topic with one view. Similar faces stay, with a low score, instead of deleting the planet. The offline comparison is in `docs/research/perspective-grouping.md`.
- **Alternatives:** Keep dropping (the #53 rule). Pad a duplicate of the same face with no score. Switch the happy path off silhouette k-means onto Ward, spectral, or an LLM stance pass. Those were measured; silhouette k-means stays when it already passes, because it keeps small tight minorities. LLM opposing-position prompts are a better label, not the daily split: one call per planet would spend the label budget on a step the local cut already does.
- **Revisit when:** A live week shows forced faces that readers cannot tell apart even with the score, or a local cut beats silhouette k-means on distinctness without losing the minority-face cases.

### 2026-10-08 — Split glued different-stories planets instead of dropping them (#78)
- **Decision:** This supersedes the different-stories drop that [2026-10-08 — Keep planets that collapse below two faces; record distinctness (#76)](#2026-10-08-keep-planets-that-collapse-below-two-faces-record-distinctness-76) left in place. That entry stopped dropping a planet for having fewer than two faces. It left the other removal: when `specific_shared_words` is empty, `pipeline/live.py` discarded the candidate ("its faces are different stories"), and a spare group took the slot. A glued candidate is now split into one planet per story. Faces stay in the same story only while they still share a specific subject word; a face with no such word is its own story. Each story then goes through the normal face split (the forced 2-way cut and `face_distinctness` from the entry above). A story of a single post is folded into a neighbour that shares a subject word, or skipped with a log line. The catalog ceiling still applies. The shared section label pool and the 20-minute ceiling are unchanged. `_drop_unshared_planets` does not apply this rule; it still drops a planet that arrives outside 2–6 faces or whose remaining faces have no posts.
- **Why:** Two real topics that clustering glued together were both vanishing. Keeping them as one planet would publish unrelated stories under one name. Dropping them removed both.
- **Alternatives:** Keep dropping the candidate. Publish the glued planet with a low distinctness score. Leave the stories as the glued planet's faces instead of giving each story its own face split.
- **Revisit when:** A live run shows the extra face-label and name calls pushing section labeling past 20 minutes, or a split that readers still experience as one conversation cut in two.

### 2026-10-08 — Do not publish a planet with fewer than five posts (#78)
- **Decision:** This supersedes the single-post fold in [2026-10-08 — Split glued different-stories planets instead of dropping them (#78)](#2026-10-08-split-glued-different-stories-planets-instead-of-dropping-them-78). A published planet needs at least five posts. Approved by Michael on 2026-10-08. Floors of 8 and 10 were measured on the Oct 7 corpus and were not shipped; the comparison is in `docs/research/perspective-grouping.md`. `MIN_PLANET_POSTS` is 5, next to the other grouping floors. `min_planet_posts` in the pipeline config overrides it, and `PERSPECTIVERSE_MIN_PLANET_POSTS` overrides the file. The floor applies to every planet that would be published: a split story, an unsplit planet, and a global topic. A piece under the floor is not published, not glued onto a sibling, and not used to fill a catalog slot. When the post count is already known, the check runs before any face label, name, or brief. If labeling then leaves fewer posts than the floor, the name and the briefs are skipped and the planet is still left out. One INFO line records the section, a label hint, and the post count, and the piece is added to the skip counter the eval harness reports. The catalog ceiling still fills from the remaining candidates in rank order. The shared section label pool and the 20-minute ceiling are unchanged.
- **Why:** Splitting glued stories was going to publish planets a reader would not treat as a topic, including stories of two, three, or four posts.
- **Alternatives:** Keep publishing those small stories, including folding a one-post story into a neighbour. Ship 8 or 10 instead of 5.
- **Revisit when:** A live week shows the floor cutting a conversation readers still wanted, or section labeling goes past 20 minutes.

### 2026-10-08 — Production call costs live on data-snapshot (#80)
- **Decision:** Paid production calls are metered in process and, after a successful run, appended to `costs/ledger.csv` on the `data-snapshot` branch (one row per service and model). `costs/README.md` on that branch is regenerated as an ISO-week table. The pipeline does not commit these files to `main`. `costs/` is not under `public/`, so Pages does not deploy it. DeepInfra dollars are `usage.estimated_cost`. Jev dollars are computed as input tokens × `JEV_USD_PER_MILLION_INPUT_TOKENS` / 1,000,000. That constant is `Decimal("0.042")`, dated 2026-10-08, in `pipeline/costs.py`. Output tokens are free. Posts are the run's `data.json` `total_posts`. Planets are every planet in that file, including section solar systems, counted once per run. The meter is thread-safe. A metering or ledger error is a warning and the snapshot still publishes.
- **Why:** Michael asked for production costs that cost money to stay in the repo as a simple week-over-week table. The snapshot branch already receives one commit per successful run, so the ledger can append there without CI churn on `main` or a fight with the ruleset.
- **Alternatives:** Commit the ledger to `main`. Leave the figures only in Actions logs. Price Jev from a live rate API (the response has token counts, not a dollar amount).
- **Revisit when:** TypeSafe changes the $0.042 per 1M input-token price, or a monthly console bill disagrees with the computed Jev column.

### 2026-10-08 — R2 Standard price, free tier, and the 14-day chart (#80)
- **Decision:** Cloudflare R2 is a third ledger service (`cloudflare-r2`, model `r2-standard`, `cost_source` `computed`). The dated constants in `pipeline/costs.py` are `R2_PRICE_AS_OF = "2026-10-08"`, taken from [Cloudflare's R2 pricing](https://developers.cloudflare.com/r2/pricing/) (page updated 2026-10-01). Standard storage is $0.015 per GB-month, prorated per day as that price ÷ 30. Class A is $4.50 per million requests. Class B is $0.36 per million. Egress is free. One GB is 1e9 bytes, matching the page's 100,000 × 100 KB example. The Standard free tier is 10 GB-month, 1 million Class A, and 10 million Class B per month (egress free). It does not apply to Infrequent Access; the corpus uses Standard. `list_price_usd` is this run's own storage day plus its Class A and Class B counts at those rates. `cost_usd` is the increase in that calendar month's bill above the free tier. Days since the previous R2 row are included at the last known object size, because those days were not in the earlier bill. A later run on the same UTC day replaces that day's size and adds its operations. The weekly table and `costs/daily_spend_14d.svg` use `cost_usd`. When the month's bill is zero, `costs/README.md` says R2 is inside the free tier. Storage bytes are the `Content-Length` from a HEAD of the corpus object after a successful PUT, or the uploaded byte length if that HEAD does not return a length. The bucket is not listed. PUT is Class A. HEAD and GET are Class B, including a 404. HTTP 401 and a request that never returned a response are not counted. A ledger that still has the pre-R2 header is rewritten once: every old row is kept, the new columns are filled, and `list_price_usd` is copied from `cost_usd`. A matching new header is still appended without rewriting earlier bytes. A foreign header is still left untouched. The SVG is regenerated on `data-snapshot` each run. `main` only embeds an absolute raw URL. The pricing page also rounds usage up to the next whole billing unit. These constants follow the Standard worked example, which subtracts the free tier from the exact quantity (990 GB-month × $0.015 = $14.85) and does not apply that rounding.
- **Why:** Michael asked for actual R2 spend in the log and the graph, and for a 14-day chart that does not commit to `main` every day.
- **Alternatives:** List every object in the bucket. Record only the list price and ignore the free tier. Apply the whole-unit rounding. Commit the SVG to `main` on each run.
- **Revisit when:** Cloudflare changes the Standard price or the free tier, a monthly invoice disagrees because of whole-unit rounding, or the bucket holds objects other than the corpus.

### 2026-10-08 — A smaller R2 object is not a credit (#80)
- **Decision:** This adds to [2026-10-08 — R2 Standard price, free tier, and the 14-day chart (#80)](#2026-10-08-r2-standard-price-free-tier-and-the-14-day-chart-80). The month bill is still computed from storage and operations above the free tier. The signed increment can be negative when a later measurement is smaller. The ledger row stores `cost_usd` as `max(0, increment)`. `list_price_usd` stays this run's list price. The weekly table and the chart sum those non-negative amounts, so neither total can go below zero. A same-day rerun that shrinks storage records $0 rather than a credit. If only the SVG fails, the ledger and the table are still published.
- **Why:** Michael wants the table and the chart to show actual spend. A negative row reads as a refund.
- **Alternatives:** Record the negative so the month's rows sum to the month bill. Hold the ledger and the table until the SVG exists.
- **Revisit when:** A monthly invoice needs that credit in order to reconcile.

### 2026-10-08 — Daily pipeline cron at an odd minute (06:17 UTC)
- **Decision:** The Daily Discourse Pipeline schedule is `cron: "17 6 * * *"` (06:17 UTC, 1:17 AM CT during daylight time). The daily health check treats a scheduled run that has not started within about 2 hours of that time as a finding.
- **Why:** GitHub delays or drops scheduled runs when many jobs start at once, and this is worst at :00. The 2026-10-08 06:00 UTC run did not start until 12:25 UTC, about 6.5 hours late.
- **Alternatives:** Stay on `0 6 * * *`. Move the job to a different hour.
- **Revisit when:** A 06:17 UTC run is still delayed by hours, or the about-2-hour start window stops matching how late GitHub actually is.

### 2026-10-08 — A planet may show one clear perspective (#85)
- **Decision:** This supersedes the at-least-two-views requirement in [2026-10-08 — Keep planets that collapse below two faces; record distinctness (#76)](#2026-10-08-keep-planets-that-collapse-below-two-faces-record-distinctness-76). Approved by Michael on 2026-10-08. A planet with only one real perspective publishes that one perspective, with a short note that no clear opposing view was found in this sample, instead of being padded to two with a "Mixed remarks" leftover pile. A second perspective is shown only when it is a genuinely distinct view. Popular topics are still never dropped for having one view. The implementation lands in the #85 PR.
- **Why:** On 2026-10-08, 101 of 220 perspectives (46%) were "Mixed remarks", mostly tiny (median 4 posts), and 29 planets were nothing but Mixed remarks. The padding hid the planet's real view behind filler.
- **Alternatives:** Keep forcing two views. Drop one-view planets.
- **Revisit when:** Readers miss the contrast on one-view planets, or a better stance split finds a real opposing view where we now show one.

### 2026-10-08 — Quality bars for cheaper Jev scoring (#87)
- **Decision:** Michael left the bars to the factory worker on 2026-10-08. A cheaper scoring path (a local claim or section classifier, batching posts per request, or a free pre-filter) replaces a Jev decision only if, on a shadow test against Jev's own answers, it reaches at least 95% agreement on claim versus not-claim, at least 90% agreement on section, and loses no more than 3% of the posts Jev would keep as claims. Below any bar, Jev keeps that decision. A shadow test may spend about $0.03 of Jev (approved by Michael on 2026-10-08).
- **Why:** The 100K-post window must cost about $0.25/day without lowering the quality of the claims and sections Jev decides today.
- **Alternatives:** Require exact parity. Judge by eye on sample planets.
- **Revisit when:** A bar turns out to let visibly worse planets through, or Jev's price or model changes.

### 2026-10-08 — Pushes to main reuse cached labels (#87)
- **Decision:** Approved by Michael on 2026-10-08 (option a). A pipeline run started by a push to `main` still publishes a fresh snapshot right away, but reuses saved LLM labels (planet names, perspective titles and arguments, briefs) for any planet or perspective whose inputs and prompt version have not changed. A change to labeling itself (prompt, sample, or model) bumps the prompt version and pays for a full relabel. The scheduled daily run labels only what is new or changed.
- **Why:** Every push relabeled everything for about $0.10. On 2026-10-08 three runs cost $0.30 on an unchanged corpus.
- **Alternatives:** (b) Only the scheduled run publishes, and pushes do not run the paid pipeline.
- **Revisit when:** Cached labels go stale in a way readers notice, or the cache costs more to keep than it saves.

### 2026-10-08 — Daily spend target $0.25, fallback $0.30 (#87, #27)
- **Decision:** Approved by Michael on 2026-10-08. The target for total production spend (Jev, LLM labeling, and R2) at a 100,000-post window is about $0.25 per day. About $0.30 per day is the accepted fallback if $0.25 cannot be met at the quality bars above.
- **Why:** A 100K corpus should give larger, more natural planets, but not at the roughly $1.70/day the current design would cost.
- **Alternatives:** A 50K-post window at the lower budget.
- **Revisit when:** The cost ledger shows a sustained daily total above $0.30, or prices change.

### 2026-10-08 — Group once; Jev picks the section per planet, not per post (#90, #87)
- **Decision:** Michael approved this as the official plan on 2026-10-08. Each post goes through Jev once, for spam and claim only. The section question and section definitions come out of the per-post call. All claim posts are grouped in one natural (density-based) pass. Each planet then gets one Jev call on its summary and arguments, and Jev picks its section; a planet split between two sections may be listed in both. Planets are ranked by reach within each section, and each section shows its top 10. Each planet is labeled once, and that label is reused in the global and section lists. A section that can't fill 10 slots may be re-grouped on its own as a fallback. Switching over requires a shadow test, inside the approved ~$0.03 Jev budget, showing the planet-level section matches the majority of today's per-post sections for at least 90% of planets.
- **Why:** Per-section re-grouping labels the same stories twice and classifies up to 100K posts by section. Judging a planet by what it actually argues handles mixed-section planets honestly, keeps the same story consistent across views, and cuts Jev section calls from one per post to one per planet (a few hundred a day). This also supports the $0.25/day target.
- **Alternatives:** Re-group each section's posts separately (today's approach). Group once and assign a planet's section by majority vote of its posts' per-post Jev sections.
- **Revisit when:** The shadow test misses the 90% bar, sections can't fill their top 10, or readers find planets in the wrong section.

### 2026-10-08 — A named approval in the factory room is a merge instruction

- **Decision:** When the human approver posts an approval naming a PR (e.g. "approve #88") in the project's factory room or a 1:1 chat with the worker, that message is a direct instruction for the worker to merge that PR on their behalf. The worker records the approval in the PR body, makes sure the branch is 0 behind the default branch with required checks green on the head commit, and merges, without asking for a second confirmation in another chat. Scope is the named PR only; it does not cover follow-ups, other PRs, or approvals relayed by another bot. If a catch-up changes the PR's behavior, the gate is re-asked.
- **Why:** On Perspectiverse #88 the worker asked the approver to repeat an approval from the factory room in a 1:1 chat before it would merge. That duplicate step added friction and no safety: the PR body is the audit trail either way.
- **Alternatives:** Require 1:1 confirmation for every merge (rejected: duplicate step); allow any room member or bot to approve (rejected: only the human approver holds the product gate).
- **Revisit:** If a room ever includes humans who are not approvers, name the approvers explicitly.

### 2026-10-08 — Planets are dense balls, not a formula for k (#85, #32)
- **Decision:** Production embedding clustering keeps dense balls and drops everything else. A fine grid of seeds (about one per `min_cluster_size` posts) only stops two crowds from being glued together before they can be separated. A post farther than cosine 0.50 from its center is peeled. Centers at cosine 0.72 or above are merged as one subject. A ball whose mean cosine is below 0.60 is dropped. A ball smaller than `min_cluster_size` (5, tuned on the 10K corpus) is noise. The grid size is not the group count. Every surviving group is ranked by distinct authors, then by size. The labeler publishes the top `catalog_size` (10) in the global system and in each section. Through 12,000 posts the grid is fit on every post. Above that, centers are fit on a sample of 12,000 and other posts join a center only when they sit inside its ball. The comparison is in `docs/research/natural-grouping.md`.
- **Why:** A formula for the cell count was deciding how many topics existed before the posts were read. About 200 cells at 10K, then a floor of `n // 200`, left 12 candidates and 85.8% of posts as noise. On this embedding a topic is a ball of posts near one center. Single-linkage on mutual reachability, the HDBSCAN distance, was measured and does not separate the week: nearest-neighbor distances inside a topic and between topics are almost the same, so the graph becomes one chain (one group of about 2,800 posts and a handful of specks). The ball count stays near 250–270 at floor 8 when the grid moves from 800 to 1,600 seeds, so the grid is not the answer.
- **Alternatives:** Lower the k-means floor and publish `k = n / floor` cells. Keep single-linkage anyway. Build an n×k distance matrix at 100K.
- **Revisit when:** A 10K week produces only a handful of candidates, the share of posts in a group falls back near 14%, or a 100K run cannot finish the sample-and-assign path in about 10 minutes.

### 2026-10-08 — PRs state what changes in production on merge

- **Decision:** The PR template gains a "What changes in production on merge" section, required for normal and high-risk PRs: what users, live data, or scheduled jobs see differently as soon as the PR merges, which parts stay off, and what would turn them on.
- **Why:** On Perspectiverse #92 the summary said nothing in the daily run would change until a test passed, but a filter and cache with no switch went live on merge and dropped real data. The human gate only means something if the approver knows what goes live.
- **Alternatives:** Rely on the summary (rejected: it was wrong once already); require feature flags for everything (rejected: too heavy for small changes).
- **Revisit:** If the section is routinely boilerplate, fold it into Verify.

### 2026-10-08 — Jev verdict cache and free pre-filter (#87)
- **Decision:** Phases 1 and 2 of #87 are on. Phase 3 is implemented and left off. Every Jev answer (spam, non-claim, and claim) is stored in table `jev_verdicts` inside `live_corpus.db`, the same R2 object the corpus already uses. The key is the post URI. The columns are `spam_score`, `claim_score`, `section`, `model`, `scored_on` (UTC date), and `text_fp` (a 16-hex simhash). Rows older than 14 days are deleted (`scored_on` earlier than today minus 14 days). A post in that window is not sent to Jev again. Pre-filter skips and failed calls are not stored. Claims already in the corpus are backfilled as model `retained` with `claim_score` 1.0, which is not a Jev noul, so a claim that leaves the 7-day window and comes back within 14 days is not scored again. A real Jev row is not overwritten by that backfill. The free pre-filter runs only when Jev itself is on. It drops link-only posts (a URL, and fewer than 3 alphabetic words after the URL is removed), posts under 6 whitespace words, non-English posts (declared `langs` without English, or a local function-word / non-Latin check), and near-exact duplicates of an already-scored post (64-bit simhash; Hamming distance at most 3 when both sides have at least 8 tokens, otherwise only an identical hash). Phase 3 (`jev_batch`, default false; env `PERSPECTIVERSE_JEV_BATCH`) packs about 25 posts into one TypeSafe `systemone` request: section definitions once in `state`, spam folded into the claim's false criteria, and the section question asked only for claims. `scripts/jev_shadow_test.py` compares the two shapes and stops at $0.03. It was not run in this change.
- **Why:** Non-claims were discarded, so a later top-up scored them again. On the 10,000 Jev-approved claims in the 2026-10-08 corpus (Actions run 37789244791), the shipped pre-filter drops 269 claims (2.69%): 185 under 6 words, 75 non-English, 1 link-only, and 8 near-duplicates. That is inside the 3% bar. The same checks at a floor of 8 words dropped 465 (4.65%), and at 7 words dropped 357 (3.57%). A 1,000-row insert of corpus-length URIs (70 characters) grew the SQLite file by about 229 bytes per row. At the phase-2 scoring rate (new claims divided by a 35% yield) that is about 13 MB over 14 days at a 10K window and about 130 MB at a 100K window, inside the 10 GB R2 free tier, on the same PUT.
- **Alternatives:** A second R2 object. An 8-word floor. Token-set or 12-token-prefix duplicates. Switching phase 3 on before a shadow test clears the bars.
- **Revisit when:** A shadow test clears claim agreement ≥ 95%, section agreement ≥ 90%, and claims lost ≤ 3%, or a later corpus loses more than 3% of claims to this pre-filter.

### 2026-10-08 — Batched Jev is spam and claim only; section moves to the planet (#90, #87)
- **Decision:** This supersedes the phase-3 request shape in [2026-10-08 — Jev verdict cache and free pre-filter (#87)](#2026-10-08-jev-verdict-cache-and-free-pre-filter-87). The per-post call that ships today still asks spam, section, and claim. The batched request (`jev_batch`, default false) asks spam and claim only. It does not send the section question or `SECTION_CRITERIA`. A cached `section` may be null when the call did not ask. The planet-level section call is not in the live pipeline. `scripts/jev_shadow_test.py --planets` can score it later, inside the same $0.03 cap, against the majority of the member posts' existing per-post sections (bar ≥ 90%). The post shadow test reports claim agreement (≥ 95%) and claims lost (≤ 3%). The projection for batched spam+claim plus one section call per planet uses 103 tokens per scored post (the #87 77-token batch with a second short question: 280/25 + 40 + 26×2) and 490 tokens per planet (280 overhead + 170 of `SECTION_CRITERIA` + 40 of summary) for 300 planets a day, at both the 10K and 100K windows.
- **Why:** #90, approved by Michael on 2026-10-08, takes the section question off the per-post prompt and asks it once per planet after grouping. That live call lands in #90, after #85. This change only updates the switched-off batch, the shadow test, and the projection.
- **Alternatives:** Leave the batch asking a section for each claim. Build the planet call in this PR.
- **Revisit when:** #90 lands the planet call, or a shadow test misses the 95% claim bar, the 3% claims-lost bar, or the 90% planet-section bar.

### 2026-10-09 — Daily run freshness: GitHub-only scheduling, deadline flag

- **Decision:** Michael decided scheduling stays inside GitHub Actions because it is free, with no outside scheduler (it adds a dependency on another system). The primary cron stays at `17 6 * * *` UTC (about 1:17 AM CT). #97 adds a guarded backup cron at `17 8` UTC that no-ops if today's scheduled or manual run already succeeded on `main`; both share the `discourse-pipeline` concurrency group. GitHub started scheduled runs 4.5–7 hours late all week, so late starts are expected and not flagged. The daily check flags only when no successful run on `main` has finished by 10 AM CT. This replaces the earlier "not started within 2 hours" rule.
- **Why:** Free, no extra dependency, and data fresh by late morning is good enough.
- **Alternatives:** Outside scheduler calling the manual trigger (rejected: extra dependency); keep the 2-hour late-start flag (rejected: noise after a week of multi-hour delays).
- **Revisit when:** A job truly needs on-time runs, reconsider an outside trigger for that job only.

### 2026-10-09 — Cloud agent evidence before approving high-risk labeling or grouping
- **Decision:** Michael (2026-10-09): PRs that change labeling or grouping in ways that could alter the public snapshot must include real before-and-after output from a cloud agent run (not mocked fixtures alone) before Michael approves merge. That evidence run must not publish: no R2 upload, no push to `data-snapshot`, and no GitHub Pages deploy. Secret names available to cloud agents are listed in `.factory/DOCS.md` (names only).
- **Why:** Grouping and label changes are hard to review from diffs alone; a paid or corpus-backed run catches regressions before they hit readers.
- **Alternatives:** Review-only on unit tests; mandatory full daily pipeline on every PR.
- **Revisit when:** Automated eval gates reliably match live quality bars without a human spot-check run.

### 2026-10-09 — Batched Jev stays off; the shadow test failed claims (#87, #92)
- **Decision:** `jev_batch` stays false. The shadow test of the batched spam-and-claim request failed the claim bar, so the live path remains one post per request (spam, section, and claim). The verdict cache and the free pre-filter stay on. The planet-level section call is still #90 and is not in this pipeline.
- **Why:** A cheaper request replaces a Jev decision only when the shadow test clears the bars. This one did not, on claims.
- **Alternatives:** Turn `jev_batch` on anyway. Remove the batched request.
- **Revisit when:** A later shadow test clears claim agreement ≥ 95% and claims lost ≤ 3%.

### 2026-10-09 — Acceptance includes the original ask's metric
- **Decision:** Normal and high PRs state the success metric from the original request (baseline, target, measured or projected value) and the post-merge check reports it. Proxy checks alone don't make a PR done.
- **Why:** On Perspectiverse, a grouping PR passed its own checks (fewer filler faces, labeling time) and shipped, but the owner's actual complaint (top planets too small) got worse: 297 to 165 posts.
- **Alternatives:** Trust proxy metrics (rejected: this miss).
- **Revisit:** If the metric can't be measured pre-merge, say so and make the post-merge check mandatory.

### 2026-10-09 — Roles: Factory Manager (renamed from factory worker) and an optional Giver
- **Decision:** The repo's coordinating bot is the **factory manager** (previously "factory worker"); child cloud agents are the **workers**. Add a recommended **giver** role per repo (`skills/giver.md`): asks ledger as a pinned issue, decision drafts for the manager to commit, healthy challenge, daily digest; never builds, merges, approves, or spends. Earlier entries that say "factory worker" mean the factory manager.
- **Why:** On Perspectiverse the coordinating bot spent most of its effort facilitating, and the owner wanted dedicated memory of asks and decisions plus a challenger; a grouping PR shipped that passed its checks but missed the owner's actual ask.
- **Alternatives:** Keep one bot for everything (rejected: overloaded memory); have the cross-repo methodology bot do it (rejected: its memory spans repos and should stay generic).
- **Revisit:** If the giver adds noise without catching misses after two weeks, drop it to digest-only.

### 2026-10-09 — #104 done bar: Michael confirmed size bars
- **Decision:** Michael confirmed size bars (top planet ≥500, top-10 coverage ≥30%, noise ≤25%, World/Politics lead ≥100, Politics coverage ≥25%, no duplicate faces, labeling <1,000s, coherence check). Diagnosis showed no coherent 500-post story exists at 10K posts; the bar is under review with Michael.
- **Why:** #104 needs explicit acceptance numbers before grouping changes ship; the diagnosis prevents chasing an impossible bar on the current corpus size.
- **Alternatives:** Ship grouping changes without the bar; lower the top-planet floor without owner sign-off.
- **Revisit when:** Michael confirms revised bars or the corpus window grows enough to support a 500-post top planet.

### 2026-10-09 — Daily production cost cap at 100K posts (#87, #27)
- **Decision:** Approved by Michael on 2026-10-09. Total production spend (Jev, LLM labeling, and R2) at a 100,000-post window must stay under $0.50 per day; lower is better. This supersedes the $0.30-per-day accepted fallback as a hard ceiling in [2026-10-08 — Daily spend target $0.25, fallback $0.30 (#87, #27)](#2026-10-08-daily-spend-target-025-fallback-030-87-27). About $0.25 per day remains the target and about $0.30 remains an aspiration, not a cap.
- **Why:** A 100K corpus should scale without the roughly $1.70/day the pre-#87 design implied, while leaving headroom above the earlier $0.25–$0.30 figures when quality bars require it.
- **Alternatives:** Keep $0.30 as the hard ceiling; shrink the corpus window instead of raising the cap.
- **Revisit when:** The cost ledger shows a sustained daily total above $0.50 at 100K, or prices change.

### 2026-10-09 — #104: fix missing posts (approved)
- **Decision:** Michael on 2026-10-09: "Fix missing posts - yes." The factory builds the fix: restore dropped posts, attach strays, fold split-offs, and address duplicate faces (#103). Each change on the #104 PR shows before-and-after evidence.
- **Why:** Popular stories today land incomplete on their planets (for example Ukraine at roughly 108 of ~380 posts on the live site).
- **Alternatives:** Accept smaller planets as correct grouping; change only labeling.
- **Revisit when:** The attachment-recall bar below is met on the fixed keyword/labeled story sample.

### 2026-10-09 — #104 done bar: attachment recall replaces the 500-post floor
- **Decision:** This supersedes the absolute top-planet ≥500 bar in [2026-10-09 — #104 done bar: Michael confirmed size bars](#2026-10-09-104-done-bar-michael-confirmed-size-bars). Michael on 2026-10-09 (revised 10:38 AM): for truly popular stuff with a lot of posts, posts must properly attach to the right planet and the planet must have all the right ones attached. The done bar is **attachment recall**: for each story with ≥100 posts (story size counted on a fixed keyword/labeled sample, set before the change, independent of grouping code), ≥80% of that story's posts land on its planet, with the coherence check and without gluing separate stories ([2026-10-08 — Split glued different-stories planets instead of dropping them (#78)](#2026-10-08-split-glued-different-stories-planets-instead-of-dropping-them-78); [2026-10-08 — Do not publish a planet with fewer than five posts (#78)](#2026-10-08-do-not-publish-a-planet-with-fewer-than-five-posts-78) / #77/#79). Still in force unless Michael says otherwise: top-10 coverage ≥30%, noise ≤25%, Politics coverage ≥25%, World/Politics lead ≥100, no duplicate faces (#103), no Mixed remarks, labeling <1,000s.
- **Why:** At a 10K window no coherent 500-post story exists; the owner cares that high-volume stories are whole and on the right planet, not a single arbitrary size floor.
- **Alternatives:** Keep the ≥500 top-planet bar; judge only by top-10 coverage and noise.
- **Revisit when:** Michael changes the recall threshold or story sample, or the corpus window makes a size floor meaningful again.

### 2026-10-09 — #90 cluster-once (PR #102) parked
- **Decision:** #90 and PR #102 stay parked. Cluster-once does not ship until Jetstream speed headroom is reclaimed from the label cache path in #87 first.
- **Why:** Paid testing put section labeling at 1,287s (above the 1,200s ceiling), with 80 failed calls and 72.9% section agreement — below the quality bars for replacing today's per-post section path.
- **Alternatives:** Merge #102 and accept slower or weaker section labeling; drop section solar systems.
- **Revisit when:** Label-cache savings show up in live runs and a retest clears section agreement and the labeling-time bar.

### 2026-10-09 — Room voice: Factory Manager speaks for Michael
- **Decision:** In the project's factory room, the Factory Manager is Michael's one voice. The Giver tracks quietly on pinned issue #106 (Asks ledger) and challenges the Manager when plans, status, or done claims drift from the ledger or agreed bars. This narrows [2026-10-09 — Roles: Factory Manager (renamed from factory worker) and an optional Giver](#2026-10-09-roles-factory-manager-renamed-from-factory-worker-and-an-optional-giver) to room behavior; the Manager still commits `DECISIONS.md`.
- **Why:** Michael asked for a single coordinating voice in the room while keeping durable memory and challenge off the main thread.
- **Alternatives:** Owner speaks directly in the room for every update; Giver speaks in the room by default.
- **Revisit when:** The Giver's challenge catches misses without adding room noise, or Michael wants a different split.

### 2026-10-09 — Correction: "#90 / PR #102 parked" attribution
- **Decision:** Correction to the 2026-10-09 entry "#90 / PR #102 parked": that was the Factory Manager's own sequencing call, not Michael's decision.
- **Decided by:** Factory Manager
- **Basis:** Michael set the order (grouping quality first, then Jetstream), and the paid test on #102 showed 1,287s section labeling (over the 1,200s ceiling), 80 failed calls, and 72.9% section agreement.
- **Revisit when:** Michael wants #90 prioritized.

### 2026-10-09 — Same-story attach, fold, restore, and post-relabel title merge (#104, #103)
- **Decision:** Implement the approved missing-post fix without a transitive merge. A noise post joins the nearest planet of at least 20 posts only when its cosine to that planet's original center is at least 0.42 and the post contains that planet's top subject stem. A smaller planet folds into one larger planet only when the cosine is at least 0.55 and at least 60% of its posts contain that same top stem. A secondary stem such as "russia" on a Ukraine planet is not enough by itself. A much longer token (a place name or hashtag) does not cancel the top stem; a stem only a character or two longer ("zionism" against "israel") is a different subject and stays off. Centers and stems are fixed before either step, and a planet that is folding is not a parent, so nothing chains. A face the claim gate drops gives a post back when the post matches that face's story stems, including a stem that travels with the top stem, so a Ukraine post is not lost just because the surviving face says "Russia" more often. After the wide relabel, faces on one planet whose titles `titles_alike` already treats as the same are merged. `titles_alike` is unchanged, so "Iran War" and "Iran Conflict" stay distinct. The author cap is not undone. The 0.72 center merge, 0.50 peel, and 0.60 mean gate are unchanged.
- **Why:** The face gate cut same-war posts off Ukraine (159 to 108) and Epstein (47 to 21), and the same story was split across neighboring planets. A transitive merge at 0.62 glued separate stories.
- **Alternatives:** Transitive merge at cosine 0.62 (rejected: it glues distinct stories). Loosening `titles_alike` (rejected: an existing test keeps "Iran War" and "Iran Conflict" apart).
- **Revisit when:** A fold sample fails the one-story check, or the fixed story reference shows recall can rise without lowering the cosine gates.

### 2026-10-09 — Do not publish a labeling-failure regression (#107)
- **Decision:** A daily run keeps the live `data.json` when the new snapshot is degraded by DeepInfra distress. Distress means final failures are over 5% of labeling calls, or retried attempts plus final failures are over 5% of calls (`calls` is every HTTP attempt). Exactly 5% does not count. Hold if either: (1) section planets fell by more than the larger of 3 and 5% of the live section-planet count, rounded up (live 98 → margin 5, so 92 or fewer holds); or (2) the wide face relabel was left unfinished in a strict majority of sections that queued one (at least two sections). A planet drop or a relabel skip without distress still publishes, including a real day that simply has fewer planets. A missing live snapshot, a missing label report, or a guard error publishes (fail open). The workflow still records the cost ledger, then fails the publish step so Pages does not deploy the degraded file. Each run logs 429, 5xx, timeout, and other separately for retried attempts and for final failures. Final failures over 5% also print a warning. HTTP 429, 5xx, and timeouts retry twice (2s, then 6s); a retry that would pass the section ceiling is skipped, and a timeout retry needs another 60s inside that ceiling. `failed_calls` stays the mixed count; `retried_calls` and `final_failures` are the split. Older ledger rows store 0 in the new columns.
- **Why:** Run 37946621071 published 90 section planets and skipped every section's face relabel after 86 failed DeepInfra calls, over the 1,200s ceiling. A clean re-run (37954827855) on the same corpus took 823s, had 8 failures, and published 97 section planets. The ledger mixed retries with final failures, and the log had no error type.
- **Alternatives:** Always publish. Hold on any drop in section planets (rejected: a quiet news day must still publish). Fail closed when the live file or the label report is missing (rejected: that sticks the site on a guard bug).
- **Revisit when:** A real quiet day is held, or a failure-driven drop still replaces the live snapshot.

### 2026-10-09 — Paid labeling tests must not overlap the daily pipeline (#107)
- **Decision:** Cloud-agent paid labeling tests must not run while a Daily Discourse Pipeline run is queued or in progress. They share `OPENAI_API_KEY`. Before spending, run `python scripts/check_pipeline_overlap.py` (exit 0 clear, exit 2 wait, exit 3 do not start). The check uses the GitHub API only.
- **Why:** The 86 failures on run 37946621071 are consistent with a concurrent paid test (#90 / PR #102) hitting the same key. A clean re-run with nothing else on the key dropped to 8 failures. The workflow concurrency group does not see a cloud agent.
- **Alternatives:** A second DeepInfra key. Rely on the Actions concurrency group alone.
- **Revisit when:** Labeling uses a key the daily pipeline does not use.

### 2026-10-10 One face only when no real second stance exists
- **Decision:** A planet shows a single face only when a real search finds no second stance of meaningful size. One face is never the default just because it is easiest or lowest-error. The hand-checked stance sample includes the planets that currently show one face (Gaza, Abolish ICE, MAGA Fails, Labour) and measures how often the pipeline misses a real second side.
- **Open:** the size threshold (proposed: about 10% of the planet's posts). It is confirmed by Michael once the stance numbers are in, before anything is built.
- **Supersedes:** the 10/9 reading that the 48 one-face planets after #94 were genuinely one-view. That count is to be re-checked against the stance sample.
- **Decided by:** Michael, 10/10 11:15 AM: "I am ok with one face if that's the reality, but my gut tells me we are not doing a good job of finding the multiple distinct perspectives so we shouldn't just opt for 1 face cause it's the easiest and lowest error."

### 2026-10-10 Improve PR over PR
- **Decision:** A partial improvement may merge when it beats main on numbers measured the same way, the same day. Its PR still reports every bar on the parent issue as pass or fail, and the parent issue stays open until its own done bar is met. First applied to #114 (top-10 coverage 5.9% to 8.1%, Politics coverage 4.5% to 9.2%, noise 38.6% to 35.7%; 5 of 9 #104 bars still fail).
- **Decided by:** Michael, 10/10 11:19 AM: "Feel free to merge 114. Just steadily improve the project PR over PR."

### 2026-10-10 #118 tracked under #104
- **Decision:** #118 ("Separatism" puts Canadian separatism and US–Canada threats on one planet) is a coherence failure and is tracked under #104 next to the Gaza and Zionism-motion mix, not under the face fix.
- **Decided by:** Giver flagged it; the Factory Manager made the sequencing call, 10/10 11:12 AM.
