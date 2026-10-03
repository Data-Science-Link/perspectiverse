# Complete File Listing

This document provides a complete listing of all files in the Perspectiverse repository.

## Root Level Files

| File | Description |
| --- | --- |
| `README.md` | Project overview, current status, and local run instructions |
| `ROADMAP.md` | Product roadmap, architecture forks (Horizons A–C), and maintain-cost tables |
| `FILES.md` | This file — complete file listing and organization guide |
| `LICENSE` | Project license |
| `pyproject.toml` | Python project configuration, dependencies, and build system |
| `package.json` | Frontend dependencies and scripts |
| `package-lock.json` | Locked frontend dependencies |
| `vite.config.js` | Vite + React config, including the GitHub Pages base path |
| `.eslintrc.cjs` | Frontend lint rules (React Three Fiber friendly) |
| `.env.example` | Bluesky and optional LLM environment variables |
| `.github/CODEOWNERS` | `@Data-Science-Link` approves pull requests to `main` |
| `index.html` | Vite HTML entry |
| `.gitignore` | Git ignore rules |
| `uv.lock` | Lock file for uv package manager |

## Pipeline (`pipeline/`)

| File/Directory | Description |
| --- | --- |
| `pipeline/run_pipeline.py` | `--live` (default), `--relabel`, or `--demo` entry point |
| `pipeline/r2.py` | Download and upload `live_corpus.db` to private Cloudflare R2 |
| `pipeline/generate_demo_data.py` | Synthetic 10×6 universe (not what the site ships) |
| `pipeline/live.py` | Rotate corpus, cluster, label, write `data.json` |
| `pipeline/schema.py` | Shared `data.json` contract |
| `pipeline/settings.py` | YAML config loader |
| `pipeline/cleaning.py` | URL, handle, and spam cleaning |
| `pipeline/jev.py` | Jev spam (drop at 0.8), public-claim (keep at 0.5), newspaper section |
| `pipeline/corpus.py` | Rolling 7-day window of up to 10,000 filtered claims |
| `pipeline/store.py` | SQLite posts, fetched days, and derived membership |
| `pipeline/topics.py` | Up to 10 planets (MiniLM, lexical, or BERTopic), author cap, cohesion gate |
| `pipeline/perspectives.py` | 1–6 faces and representative posts |
| `pipeline/label.py` | Ollama, OpenAI-compatible (DeepInfra), or heuristic titles |
| `pipeline/assemble.py` | Writes `public/data.json` |
| `pipeline/cluster_math.py` | TF-IDF and k-means |
| `pipeline/http_json.py` | Allow-listed JSON HTTP (`api.bsky.app`, `api.openai.com`, `api.deepinfra.com`, `api.typesafe.ai`) |
| `pipeline/config/pipeline.example.yaml` | Sample size, models, `min_cluster_size` |
| `pipeline/data/live_corpus.db` | Retained-window seed (tracked). Daily rotation uses R2 when configured |
| `pipeline/data_sources/extract_bluesky.py` | Bluesky 7-day sample |
| `tests/` | Contract tests and the tiny live fixture |

## Frontend (`src/` & `public/`)

| File/Directory | Description |
| --- | --- |
| `src/App.jsx` | Loads `data.json`, category filter, URL-backed selection and site pages |
| `src/components/Observatory.jsx` | Canvas, camera, bloom (desktop), lighter mobile solar system |
| `src/components/Planet.jsx` | Orbits, inspect drag, hover stats |
| `src/components/SpikyCube.jsx` | Planet-skinned cores, spikes, Saturn rings |
| `src/components/MiniCube.jsx` | Sidebar preview |
| `src/components/Sidebar.jsx` | Welcome, topic, and face panels |
| `src/components/WelcomeModal.jsx` | First-visit tour with don't-show-again |
| `src/components/TwinklingStars.jsx` | Shader-based star twinkle |
| `src/components/TopicFilter.jsx` | Compact Solar System category dropdown |
| `src/components/SiteChrome.jsx` | Sticky header, tagline, back arrow, hamburger |
| `src/components/SiteMenu.jsx` | Pages, how to read, filters, feedback |
| `src/components/SitePage.jsx` | Vision, about, author, connect, methodology, FAQ, and donate views |
| `src/components/MethodologyGraphics.jsx` | High-level connection graphic and technical systems map |
| `src/lib/copy.js` | Title, tagline, Solar System label, welcome storage |
| `src/lib/pages.js` | Site page ids, labels, and neighbor links |
| `src/lib/solarSettings.js` | Desktop vs mobile render budget |
| `src/lib/categories.js` | Category list and filter helper |
| `src/lib/colors.js` | Planet color and opaque face shades (darker means more common) |
| `src/lib/faces.js` | Cube spike layout for 1–6 occupied faces |
| `src/lib/polyhedra.js` | Cube used by the crystal; older solids remain for the clamp helper |
| `src/lib/planets.js` | Solar-system order and body metadata |
| `src/lib/planetTextures.js` | Cached canvas skins for Sun through Pluto |
| `src/lib/navigation.js` | Query-string selection, site pages, and scroll reset |
| `src/lib/useMediaQuery.js` | Mobile breakpoint hook |
| `src/lib/layout.js` | Orbit radii, planet scale, home camera framing |
| `public/data.json` | Snapshot the observatory loads |
| `public/vite.svg` | Favicon |
| `tests/e2e/views.spec.js` | Playwright desktop and mobile view checks |

## Documentation (`project_documentation/`)

| File | Description |
| --- | --- |
| `Project Architecture_ Discourse Universe.md` | Conceptual overview and high-level architecture |
| `Technical Implementation Canvas.md` | Technical details and implementation stages |
| `UI & 3D Implementation Canvas_ Perspectiverse.md` | Frontend design and 3D visualization details |
| `Similar Products and Differentiation.md` | Neighboring product categories and how this observatory differs |
| `Planet Engagement Architecture.md` | Debate / LLM clerk design on the daily-static split |
| `Custom Universe and Archive Architecture.md` | Retain posts, on-demand solar systems, Google plugin |
| `Historical Solar Systems and Topic Continuity.md` | Dated solar systems, trending vs stock, matching topic names across days |
| `Pipeline Audit 2026-09-28.md` | What was synthetic vs live, and why the daily job was failing |
| `Handoff DeepInfra and Bluesky Auth.md` | Prompt for a follow-up agent: DeepInfra labels + Bluesky app password |
| `Improvement Requests.md` | Living log of requested changes. Not implemented until the list is closed |

## Scripts & CI/CD

| File | Description |
| --- | --- |
| `scripts/security_check.sh` | Local Bandit and pip-audit |
| `scripts/check_categories.mjs` | Category filter helper check |
| `scripts/check_planets.mjs` | Solar-system order, selection URLs, and face shades |
| `scripts/check_spikes.mjs` | Pencil spikes, opaque shades, and dashed empty faces |
| `scripts/check_solar.mjs` | Mobile/desktop render budget and tagline |
| `scripts/check_pages.mjs` | Site page ids and `?page=` URLs |
| `scripts/check_data_contract.mjs` | Asserts the built `dist/data.json` contract |
| `.github/workflows/security-audit.yml` | Bandit + pip-audit on every push/PR, plus `workflow_dispatch` |
| `.github/workflows/pytest.yml` | Pytest without a model download |
| `.github/workflows/frontend.yml` | Lint, category check, build, data contract |
| `.github/workflows/pipeline.yml` | Daily live run, R2 corpus sync, artifact, `data-snapshot` `data.json` |
| `.github/workflows/pages.yml` | GitHub Pages, overlaying `data-snapshot` when present |
