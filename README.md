# perspectiverse
Live mapping the universe of human attention and perspectives

## 🎯 Project Overview
Perspectiverse aims to map the universe of human attention and perspectives through a reproducible data engineering pipeline.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd perspectiverse
   ```

2. **Set up the virtual environment:**
   ```bash
   uv venv
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Activate the environment:**
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

## 📁 Project Structure
The project follows an intuitive structure inspired by [the_depositum](https://github.com/Data-Science-Link/the_depositum):

- `data_engineering/`: Contains all technical components for data extraction and transformation.
- `data_final/`: Contains the final output files (optimized for AI tools).
- `scripts/`: Useful utility scripts, including security checks.
- `.github/workflows/`: Automated CI/CD pipelines, including security audits.

For a detailed file listing, see [FILES.md](FILES.md).

## 🔒 Security
Automated security scanning is performed on every push and pull request:
- **Bandit**: Scans Python code for security vulnerabilities.
- **pip-audit**: Checks dependencies for known vulnerabilities.

To run security scans locally:
```bash
./scripts/security_check.sh
```
