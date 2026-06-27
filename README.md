# perspectiverse
Live mapping the universe of human attention and perspectives

## 🎯 Project Overview
Perspectiverse aims to map the universe of human attention and perspectives through a reproducible data engineering pipeline and an immersive 3D visualization.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js & npm
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- [Ollama](https://ollama.ai/) (for local LLM processing)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd perspectiverse
   ```

2. **Set up the Python environment:**
   ```bash
   uv venv
   uv sync
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Set up the Frontend:**
   ```bash
   npm install
   ```

## 📁 Project Structure
- `pipeline/`: Python backend code for data ingestion and NLP processing.
  - `data/`: Local storage for raw and intermediate data.
  - `run_pipeline.py`: Main orchestrator script.
- `public/`: Static web assets, including the generated `data.json`.
- `src/`: React and React Three Fiber frontend source code.
- `project_documentation/`: High-level design and implementation documents.
- `scripts/`: Utility scripts for security and maintenance.

For a detailed file listing, see [FILES.md](FILES.md).

## 🔒 Security
Automated security scanning is performed on every push and pull request:
- **Bandit**: Scans Python code for security vulnerabilities.
- **pip-audit**: Checks dependencies for known vulnerabilities.

To run security scans locally:
```bash
./scripts/security_check.sh
```
