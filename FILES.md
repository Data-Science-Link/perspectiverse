# Complete File Listing

This document provides a complete listing of all files in the Perspectiverse repository.

## Root Level Files

| File | Description |
| --- | --- |
| `README.md` | Project overview, current status, and local run instructions |
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
| `pipeline/perspectives.py` | 6 faces and representative posts |
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
| `src/components/Observatory.jsx` | Canvas, camera, bloom, WebGL remount |
| `src/components/Planet.jsx` | Orbits, inspect drag, hover stats |
| `src/components/SpikyCube.jsx` | Planet-skinned cores, spikes, Saturn rings |
| `src/components/MiniCube.jsx` | Sidebar preview |
| `src/components/Sidebar.jsx` | Welcome, topic, and face panels |
| `src/components/SiteChrome.jsx` | Sticky header, back arrow, hamburger |
| `src/components/SiteMenu.jsx` | About, graphic, filters, feedback |
| `src/components/PerspectiverseGraphic.jsx` | SVG explainer of the solar-system metaphor |
| `src/lib/categories.js` | Category list and filter helper |
| `src/lib/colors.js` | Planet and spike palette |
| `src/lib/planets.js` | Solar-system order and body metadata |
| `src/lib/planetTextures.js` | Canvas skins for Sun through Pluto |
| `src/lib/navigation.js` | Query-string selection and scroll reset |
| `src/lib/useMediaQuery.js` | Mobile breakpoint hook |
| `src/lib/layout.js` | Orbit radii, planet scale, formatting |
| `public/data.json` | Snapshot the observatory loads |
| `public/vite.svg` | Favicon |

## Documentation (`project_documentation/`)

| File | Description |
| --- | --- |
| `Project Architecture_ Discourse Universe.md` | Conceptual overview and high-level architecture |
| `Technical Implementation Canvas.md` | Technical details and implementation stages |
| `UI & 3D Implementation Canvas_ Perspectiverse.md` | Frontend design and 3D visualization details |

## Scripts & CI/CD

| File | Description |
| --- | --- |
| `scripts/security_check.sh` | Local Bandit and pip-audit |
| `scripts/check_categories.mjs` | Category filter helper check |
| `scripts/check_planets.mjs` | Solar-system order and selection URLs |
| `scripts/check_data_contract.mjs` | Asserts the built `dist/data.json` contract |
| `.github/workflows/security-audit.yml` | Bandit + pip-audit, including `workflow_dispatch` |
| `.github/workflows/pytest.yml` | Pytest without a model download |
| `.github/workflows/frontend.yml` | Lint, category check, build, data contract |
| `.github/workflows/pipeline.yml` | Daily live run, artifact, `data-snapshot` branch |
| `.github/workflows/pages.yml` | GitHub Pages, overlaying `data-snapshot` when present |
