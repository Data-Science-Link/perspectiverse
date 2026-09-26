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
| `index.html` | Vite HTML entry |
| `.gitignore` | Git ignore rules |
| `uv.lock` | Lock file for uv package manager (generated) |

## Pipeline (`pipeline/`)

| File/Directory | Description |
| --- | --- |
| `pipeline/run_pipeline.py` | Orchestrator. Currently writes the demo universe. |
| `pipeline/generate_demo_data.py` | Schema-compatible 10×6 demo dataset and validator |
| `pipeline/data/` | Local storage for SQLite databases and raw extracts |
| `pipeline/config/` | Pipeline configuration files |
| `pipeline/data_sources/` | Source-specific extraction scripts (e.g. Bluesky) |
| `tests/test_demo_data.py` | Contract tests for the demo payload |

## Frontend (`src/` & `public/`)

| File/Directory | Description |
| --- | --- |
| `src/App.jsx` | Loads `data.json` and owns selection state |
| `src/components/Observatory.jsx` | React Three Fiber canvas, camera, bloom, stars |
| `src/components/Planet.jsx` | Orbital motion, labels, click handling |
| `src/components/SpikyCube.jsx` | Central cube plus six volume-scaled pyramids |
| `src/components/MiniCube.jsx` | Isolated spinning preview in the sidebar |
| `src/components/Sidebar.jsx` | Welcome, topic, and perspective panels |
| `src/lib/colors.js` | Planet and spike palette |
| `src/lib/layout.js` | Orbit radii, planet scale, and number formatting |
| `public/data.json` | The bridge: output of the pipeline, input for the frontend |
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
| `scripts/security_check.sh` | Security scanning script for local development |
| `.github/workflows/security-audit.yml` | Bandit + pip-audit |
| `.github/workflows/frontend.yml` | Lint and production build |
| `.github/workflows/pages.yml` | Publish the static observatory to GitHub Pages |
