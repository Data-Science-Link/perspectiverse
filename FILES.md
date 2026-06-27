# Complete File Listing

This document provides a complete listing of all files in the Perspectiverse repository.

## Root Level Files

| File | Description |
|------|-------------|
| `README.md` | Main project documentation with overview, quick start, and usage instructions |
| `FILES.md` | This file - complete file listing and organization guide |
| `LICENSE` | Project license |
| `pyproject.toml` | Python project configuration, dependencies, and build system |
| `.gitignore` | Git ignore rules for Python, data files, logs, and IDE files |
| `uv.lock` | Lock file for uv package manager (generated) |

## Scripts

| File | Description |
|------|-------------|
| `scripts/security_check.sh` | Security scanning script for local development (Bandit + pip-audit) |

## GitHub Configuration (`.github/`)
| File | Description |
|------|-------------|
| `workflows/security-audit.yml` | Automated security scanning workflow (Bandit + pip-audit) |

## Data Engineering Files (`data_engineering/`)

| Directory | Description |
|-----------|-------------|
| `config/` | Central configuration files |
| `scripts/` | Main pipeline orchestrators and scripts |
| `data_sources/` | Extraction and processing scripts for various data sources |

## Final Output (`data_final/`)

| Directory | Description |
|-----------|-------------|
| `data_final/` | Final processed Markdown files ready for use |
