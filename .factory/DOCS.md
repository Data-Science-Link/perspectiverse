# Repo documentation map — Perspectiverse

Pointers only — do not duplicate long docs here. Open the linked files; do not paste them.

## Core orientation

| Topic | Path | Notes |
|---|---|---|
| Project overview & local setup | `README.md` | Start here. Covers env vars, demo vs live mode, and the data contract. |
| Complete file listing | `FILES.md` | Every file in the repo with one-line descriptions. Use to orient quickly. |
| Product roadmap (Horizons A–C) | `ROADMAP.md` | Audience, cost constraints, roadmap forks. Read before proposing big changes. |

## Architecture & product design

| Topic | Path | Notes |
|---|---|---|
| Project architecture overview | `project_documentation/Project Architecture_ Discourse Universe.md` | System design, layers, data flow. |
| UI & 3D implementation | `project_documentation/UI & 3D Implementation Canvas_ Perspectiverse.md` | React + R3F canvas, planet/spike rendering. |
| Technical implementation | `project_documentation/Technical Implementation Canvas.md` | Backend/pipeline technical decisions. |
| Planet engagement architecture | `project_documentation/Planet Engagement Architecture.md` | Debate, follow-ups, LLM backend considerations. |
| Custom universe & archive | `project_documentation/Custom Universe and Archive Architecture.md` | Operator / paid surface design. |
| Historical solar systems | `project_documentation/Historical Solar Systems and Topic Continuity.md` | Rewind, trending, BERTopic naming. |
| Similar products & differentiation | `project_documentation/Similar Products and Differentiation.md` | Competitive landscape; why the public solar system stays week-shaped. |
| Pipeline audit (2026-09-28) | `project_documentation/Pipeline Audit 2026-09-28.md` | Point-in-time audit; useful for understanding known gaps. |
| Handoff — DeepInfra & Bluesky auth | `project_documentation/Handoff DeepInfra and Bluesky Auth.md` | Credential and API handoff notes. |
| Improvement requests backlog | `project_documentation/Improvement Requests.md` | Queued ideas; check before filing a duplicate issue. |
| Formal architecture file | `docs/architecture.md` | Short data-flow entry. Longer notes stay in `project_documentation/`. |

## Pipeline (Python backend)

| Topic | Path | Notes |
|---|---|---|
| Pipeline overview | `pipeline/README.md` | Entry point for the data pipeline. |
| Data sources | `pipeline/data_sources/README.md` | Bluesky extraction and source conventions. |
| Pipeline config example | `pipeline/config/pipeline.example.yaml` | Config reference for operators. |
| Main pipeline runner | `pipeline/run_pipeline.py` | `--live` flag runs the daily job; demo mode generates static data. |
| Perspective grouping research | `docs/research/perspective-grouping.md` | Stance splits inside one planet, offline comparison, and the keep-and-score rule (#76). |
| Settings | `pipeline/settings.py` | All env-var-driven settings; cross-reference `.env.example`. |
| Schema | `pipeline/schema.py` | Canonical data contract between pipeline and frontend. |
| Production call costs | `pipeline/costs.py` | Meter for DeepInfra and Jev. Ledger on `data-snapshot` (`costs/`), not `main`. `retried_calls` and `final_failures` split `failed_calls` (#115). Each row has `trigger` for production vs merge/test spend (#101). |
| Jev pre-filter & cache | `pipeline/jev_prefilter.py`, `pipeline/jev.py`, `pipeline/store.py` | Free pre-filter before paid Jev; 14-day `jev_verdicts` cache (#92). |
| Same-story attach | `pipeline/story_attach.py` | Attach strays, fold planets, merge alike face titles after relabel (#114). |
| Schedule guard | `pipeline/schedule_guard.py` | Scheduled workflow no-op when today's pipeline already succeeded (#97). |
| Publish guard | `pipeline/publish_guard.py` | Keeps the live `data.json` when labeling failures degrade the new snapshot. A quiet day with fewer planets still publishes (#115). The daily job copies this file off main before it checks out `data-snapshot`, then runs that copy. `data-snapshot` does not carry the module. |
| Pipeline overlap check | `pipeline/pipeline_overlap.py`, `scripts/check_pipeline_overlap.py` | GitHub API check for an in-progress Daily Discourse Pipeline run. No DeepInfra calls (#115). |
| Natural grouping research | `docs/research/natural-grouping.md` | Dense-ball clustering comparison; one-view planets carry `opposing_note` (#94). |

## Frontend (React + R3F)

| Topic | Path | Notes |
|---|---|---|
| Frontend entry | `src/main.jsx` | Vite/React entry. |
| App root | `src/App.jsx` | Top-level routing and layout. |
| Components | `src/components/` | All React components (Observatory, Planet, Sidebar, etc.). |
| Lib / utilities | `src/lib/` | Pure JS helpers: colors, layout, navigation, planet textures, polyhedra. |
| Vite config | `vite.config.js` | Build config including GitHub Pages base path. |
| Env vars | `.env.example` | All supported environment variables with comments. |

## Tests & CI

| Topic | Path | Notes |
|---|---|---|
| Python tests | `tests/` | pytest suite. Run with `uv run pytest` (lexical backend; no BERTopic/torch needed). |
| E2E tests | `tests/e2e/views.spec.js` | Playwright end-to-end spec. Config: `playwright.config.js`. |
| Python CI | `.github/workflows/pytest.yml` | Runs on push/PR to main. Installs lightweight deps via `uv`. |
| Frontend CI | `.github/workflows/frontend.yml` | Lint (`npm run lint`) + category helper on push/PR to main. |
| Daily pipeline | `.github/workflows/pipeline.yml` | Staggered UTC crons (`06:17`, `07:47`, `09:17`, `10:47`, `12:17`; #97) + `schedule_guard` + `workflow_dispatch`. Publishes `public/data.json`. |
| Pages deploy | `.github/workflows/pages.yml` | Deploys on push to main, `workflow_dispatch`, and a successful Daily Discourse Pipeline (`workflow_run`). Build checks out main and overlays `public/data.json` from `data-snapshot`. |
| Security audit | `.github/workflows/security-audit.yml` | Required check on all pushes; runs `bandit` + `pip-audit`. Do not add path filters. |
| CODEOWNERS | `.github/CODEOWNERS` | `@Data-Science-Link` must approve PRs to `main`. |

## Domain glossary

| Term | Where defined |
|---|---|
| Solar system metaphor (sun, planets, spikes, faces) | `README.md` introduction |
| "Public claim" / cleaning / spam filter | `README.md` current-status table; `pipeline/cleaning.py`, `pipeline/jev.py` |
| Discourse universe, perspectives, steelmans | `project_documentation/Project Architecture_ Discourse Universe.md` |
| Formal domain glossary file | `docs/glossary.md` | Terms from the README, pipeline, and frontend. |

## Secrets available to cloud agents

Names only — never log or commit values. Listed from `.github/workflows/pipeline.yml` and names present in this cloud agent environment (2026-10-10). **Unverified** = forwarded by the workflow but not observed in this run's environment.

| Name | Use | Verified here |
|---|---|---|
| `BLUESKY_HANDLE` | Bluesky ingest (Actions daily job) | yes |
| `BLUESKY_APP_PASSWORD` | Bluesky app password (not account password) | yes |
| `OPENAI_API_KEY` | DeepInfra labeling | yes |
| `OPENAI_BASE_URL` | OpenAI-compatible API host (DeepInfra) | yes |
| `OPENAI_MODEL` | Model id for planet/face labels | yes |
| `TYPESAFE_API_KEY` | Jev (spam, claim, section) | yes |
| `JEV_MODEL` | Optional Jev model override (`jev-latest` default) | unverified |
| `OLLAMA_HOST` | Local Ollama labels (optional) | unverified |
| `OLLAMA_MODEL` | Ollama model name | unverified |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 corpus download/upload | yes |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 corpus download/upload | yes |
| `R2_ENDPOINT` | R2 S3 API endpoint | yes |
| `R2_BUCKET` | Private corpus bucket | yes |
| `R2_OBJECT_KEY` | Optional corpus object key (env var, not an Actions secret) | unverified |
| `GITHUB_TOKEN` | `pipeline/schedule_guard.py` in Actions only (default `github.token`) | unverified (not needed for local paid tests) |

**Approval rule (Michael, 2026-10-09):** High-risk labeling or grouping PRs must show real before-and-after output from a cloud agent run before Michael approves. No publishing on that run: no R2 upload, no `data-snapshot` push, and no Pages deploy.

## Paid labeling tests must not overlap the daily pipeline

Cloud-agent paid labeling tests and the Daily Discourse Pipeline share one DeepInfra key (`OPENAI_API_KEY`). A test that runs while a pipeline run is in progress can exhaust the key, blow the section time budget, and publish a thinner snapshot (issue #107, run 37946621071).

**Rule:** do not start a paid labeling test while a Daily Discourse Pipeline run is queued or in progress. Before the test:

```bash
python scripts/check_pipeline_overlap.py
```

Exit 0 means clear. Exit 2 means wait until that run finishes. Exit 3 means the GitHub API check failed: do not start the paid test. The same check is `python -m pipeline.pipeline_overlap`. It does not call DeepInfra. The workflow `concurrency` group only serialises pipeline runs with each other; it does not see a cloud agent.

Agents: read this map, then open the linked files. Prefer linking over pasting.
