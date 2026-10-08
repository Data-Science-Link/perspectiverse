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
| Daily pipeline | `.github/workflows/pipeline.yml` | Scheduled (06:17 UTC daily) + `workflow_dispatch`. Publishes `public/data.json`. |
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

Agents: read this map, then open the linked files. Prefer linking over pasting.
