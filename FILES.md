# Complete File Listing

This document provides a complete listing of all files in the Perspectiverse repository.

## Root Level Files

| File | Description |
| --- | --- |
| `README.md` | Project overview, current status, and local run instructions |
| `ROADMAP.md` | Product roadmap, architecture forks, and maintain-cost tables |
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
| `pipeline/run_pipeline.py` | `--demo` or `--live` entry point |
| `pipeline/generate_demo_data.py` | Synthetic 10×6 universe |
| `pipeline/live.py` | Extract, cluster, label, write `data.json` |
| `pipeline/schema.py` | Shared `data.json` contract |
| `pipeline/settings.py` | YAML config loader |
| `pipeline/cleaning.py` | URL, handle, and spam cleaning |
| `pipeline/store.py` | SQLite posts and derived membership |
| `pipeline/topics.py` | 10 planets (lexical or BERTopic) |
| `pipeline/perspectives.py` | 2–6 faces and representative posts |
| `pipeline/label.py` | Ollama, API, or fallback titles |
| `pipeline/assemble.py` | Writes `public/data.json` |
| `pipeline/cluster_math.py` | TF-IDF and k-means |
| `pipeline/http_json.py` | Allow-listed JSON HTTP |
| `pipeline/config/pipeline.example.yaml` | Sample size, models, `min_cluster_size` |
| `pipeline/data/` | Gitignored SQLite store (`posts.db`) |
| `pipeline/data_sources/extract_bluesky.py` | Bluesky 7-day sample |
| `tests/` | Contract tests and the tiny live fixture |

## Frontend (`src/` & `public/`)

| File/Directory | Description |
| --- | --- |
| `src/App.jsx` | Loads `data.json`, category filter, URL-backed selection |
| `src/components/Observatory.jsx` | Canvas, camera, bloom (desktop), lighter mobile sky |
| `src/components/Planet.jsx` | Orbits, inspect drag, hover stats |
| `src/components/SpikyCube.jsx` | Planet-skinned cores, spikes, Saturn rings |
| `src/components/MiniCube.jsx` | Sidebar preview |
| `src/components/Sidebar.jsx` | Welcome, topic, and face panels |
| `src/components/WelcomeModal.jsx` | First-visit tour with don't-show-again |
| `src/components/TwinklingStars.jsx` | Shader-based star twinkle |
| `src/components/SkySelect.jsx` | Compact sky/category dropdown |
| `src/components/SiteChrome.jsx` | Sticky header, tagline, back arrow, hamburger |
| `src/components/SiteMenu.jsx` | About, how to read, filters, feedback |
| `src/lib/copy.js` | Title, tagline, welcome storage |
| `src/lib/skySettings.js` | Desktop vs mobile render budget |
| `src/lib/categories.js` | Category list and filter helper |
| `src/lib/colors.js` | Planet and spike palette |
| `src/lib/faces.js` | 2–6 spike layouts and shape names |
| `src/lib/polyhedra.js` | Cube, tetrahedron, pyramid, prism, diamond solids |
| `src/lib/planets.js` | Solar-system order and body metadata |
| `src/lib/planetTextures.js` | Cached canvas skins for Sun through Pluto |
| `src/lib/navigation.js` | Query-string selection and scroll reset |
| `src/lib/useMediaQuery.js` | Mobile breakpoint hook |
| `src/lib/layout.js` | Orbit radii, planet scale, formatting |
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
| `Custom Universe and Archive Architecture.md` | Retain posts, on-demand skies, Google plugin |

## Scripts & CI/CD

| File | Description |
| --- | --- |
| `scripts/security_check.sh` | Local Bandit and pip-audit |
| `scripts/check_categories.mjs` | Category filter helper check |
| `scripts/check_planets.mjs` | Solar-system order and selection URLs |
| `scripts/check_sky.mjs` | Mobile/desktop render budget and tagline |
| `scripts/check_data_contract.mjs` | Asserts the built `dist/data.json` contract |
| `.github/workflows/security-audit.yml` | Bandit + pip-audit on every push/PR, plus `workflow_dispatch` |
| `.github/workflows/pytest.yml` | Pytest without a model download |
| `.github/workflows/frontend.yml` | Lint, category check, build, data contract |
| `.github/workflows/pipeline.yml` | Daily live run, artifact, `data-snapshot` branch |
| `.github/workflows/pages.yml` | GitHub Pages, overlaying `data-snapshot` when present |
