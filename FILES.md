# Complete File Listing

This document provides a complete listing of all files in the Perspectiverse repository.

## Root Level Files

| File | Description |
|------|-------------|
| `README.md` | Main project documentation with overview, quick start, and usage instructions |
| `FILES.md` | This file - complete file listing and organization guide |
| `LICENSE` | Project license |
| `pyproject.toml` | Python project configuration, dependencies, and build system |
| `package.json` | Frontend dependencies and scripts |
| `.gitignore` | Git ignore rules |
| `uv.lock` | Lock file for uv package manager (generated) |

## Pipeline (`pipeline/`)

| File/Directory | Description |
|----------------|-------------|
| `pipeline/run_pipeline.py` | Main orchestrator script for data ingestion and processing |
| `pipeline/data/` | Local storage for SQLite databases and raw JSONs |
| `pipeline/config/` | Pipeline configuration files |
| `pipeline/data_sources/` | Source-specific extraction scripts (e.g., Bluesky) |

## Frontend (`src/` & `public/`)

| File/Directory | Description |
|----------------|-------------|
| `src/` | React components and Three.js visualization code |
| `public/` | Static assets |
| `public/data.json` | The bridge: Output of pipeline, input for frontend |
| `index.html` | Entry point for the web application |
| `tailwind.config.js` | Tailwind CSS configuration |
| `postcss.config.js` | PostCSS configuration |

## Documentation (`project_documentation/`)

| File | Description |
|------|-------------|
| `Project Architecture_ Discourse Universe.md` | Conceptual overview and high-level architecture |
| `Technical Implementation Canvas.md` | Technical details and implementation stages |
| `UI & 3D Implementation Canvas_ Perspectiverse.md` | Frontend design and 3D visualization details |

## Scripts & CI/CD

| File | Description |
|------|-------------|
| `scripts/security_check.sh` | Security scanning script for local development |
| `.github/workflows/security-audit.yml` | Automated security scanning workflow |
