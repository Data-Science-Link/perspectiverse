# Perspectiverse

Live mapping the universe of human attention and perspectives.

Perspectiverse turns a week of public conversation into a 3D solar system. The largest topic sits at the origin as the sun. The next nine topics orbit by volume. Each planet is a **spiky cube**: six pyramid faces, one per dominant perspective, with spike length driven by that face's share of the conversation.

The analytical sidebar reacts to the sky. Select a planet to inspect its six faces. Select a face to read the representative posts that formed the cluster.

## Current status

The look and feel of the daily observatory is in place and driven by a schema-compatible **demo** `public/data.json` (10 topics × 6 perspectives). The live Bluesky → BERTopic → LLM pipeline is intentionally deferred so the visualization can be judged on its own.

| Layer | State |
| --- | --- |
| Demo universe (`public/data.json`) | Ready |
| React + R3F observatory | Ready |
| Analytical sidebar | Ready |
| GitHub Pages deploy workflow | Ready (enable Pages → GitHub Actions) |
| Live social ingestion + NLP | Not started |

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 20+ and npm
- Optional: [uv](https://github.com/astral-sh/uv) for the later Python pipeline

### Frontend

```bash
npm install
npm run dev
```

Open the printed local URL. You should see the Discourse Universe on the left and the briefing sidebar on the right.

```bash
npm run build
npm run preview
```

### Demo data

`public/data.json` is the bridge file: output of the pipeline, input for the frontend.

```bash
python -m pipeline.run_pipeline
```

Until the real sorter and explainer land, that command rewrites the demo universe. Edit `pipeline/generate_demo_data.py` if you want a different day's sky.

## Project structure

- `src/` — React Three Fiber observatory and sidebar
- `public/data.json` — daily snapshot consumed on load
- `pipeline/` — data generation now; ingestion and NLP later
- `project_documentation/` — architecture and UI canvases
- `.github/workflows/` — security audit, frontend CI, GitHub Pages

See [FILES.md](FILES.md) for a complete listing.

## GitHub Pages

The `Deploy GitHub Pages` workflow builds the Vite app with `base: /perspectiverse/` and publishes `dist/`. In the repository settings, set Pages to **GitHub Actions**, then merge to `main` (or run the workflow manually). The live site will be:

`https://data-science-link.github.io/perspectiverse/`

## Security

Automated scanning still runs on every push and pull request:

- **Bandit** for Python
- **pip-audit** for Python dependencies

```bash
./scripts/security_check.sh
```
