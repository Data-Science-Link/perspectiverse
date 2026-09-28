# Perspectiverse

Live mapping the universe of human attention and perspectives.

Perspectiverse turns a week of public conversation into a 3D solar system so you do not live in an echo chamber. Tilt the solar system to see **every** perspective, then check where yours stacks up. The largest topic sits at the origin as the sun. The next nine topics orbit by volume. Planet size is share of public attention — whether the general public was talking about that topic. Planets wear solar-system skins. Open one and the sphere dissolves into a **crystal of two to six faces** — one per real perspective, never more than a cube. Face length is that view's share of the conversation. Gold is the majority (loudest) view; shorter faces are minority opinions. Colors always run gold → ember → sky → violet → jade → rose, loudest first.

The analytical sidebar reacts to the solar system. Filter by category with the **Solar System** dropdown, select a planet to turn its cube, then select a face to read the representative posts. A first-visit welcome explains the metaphor; the menu can reopen it.

This is not social listening, brand monitoring, or a poll. Those tools start from a query, a named entity, or a survey instrument. Perspectiverse starts from a week of public posts and keeps the ten largest topics, each cut into two to six perspectives. [Similar Products and Differentiation](project_documentation/Similar%20Products%20and%20Differentiation.md) maps the neighboring categories — monitoring, listening, civic deliberation, news-literacy, researcher topic maps — and says what this observatory adds.

On a phone the solar system stays up front: tagline, a short prompt, and a rail of planets. Opening a planet jumps to a tight topic page (summary + its perspectives). Opening a perspective turns that face toward you and shows representative posts, always from the top, with a back arrow and the browser back button wired to the same stack. The hamburger opens Vision, About, the author, connect (GitHub and LinkedIn), methodology (with connection diagrams), FAQ, and donate, plus filters and feedback.

Bodies keep solar-system skins in volume order: the largest topic is the Sun, then Mercury through Pluto.

## Current status

The observatory runs on a schema-compatible **demo** `public/data.json` (10 topics × 6 perspectives) until a live snapshot is published. The live path is implemented and can be run locally or on the daily Actions job. It defaults to a **small** Bluesky sample (200 posts) so the plumbing can be proved without a 10k embed. Raise `sample_size` in `pipeline/config/pipeline.example.yaml` toward 10000 for a fuller window.

| Layer | State |
| --- | --- |
| Demo universe (`public/data.json`, `mode: demo`) | Ready, labeled synthetic in the sidebar |
| Live pipeline (`--live`) | Ready, lexical clustering by default |
| React + R3F observatory | Ready, with category filters and inspect mode |
| GitHub Pages | Workflow ready. Pages source is still a repo setting |
| Daily refresh | `.github/workflows/pipeline.yml` |
| Conversational LLM on a planet | Roadmap only (Horizon A) |
| Custom sky from `--query` | Ready for operators; not a public form |
| Historical skies / topic tracking | Roadmap only (Horizon C) |

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 20+ and npm
- [uv](https://github.com/astral-sh/uv) for the Python environment
- Optional: [Ollama](https://ollama.com/) for local face labels

### Frontend

```bash
npm install
npm run dev
```

Open the printed local URL. Filter the solar system, click a planet, drag to turn the locked cube, then click a spike or a sidebar bar. The first visit opens a short welcome that explains size, tilt, and the crystal. The opening camera is pulled back so all ten planets fit in view.

```bash
npm run test
```

That lints, runs the Node helpers, builds, then Playwright against **desktop and mobile** viewports. CI does the same in `.github/workflows/frontend.yml`.

```bash
npm run build
npm run preview
```

### Pipeline

```bash
uv venv
uv sync
source .venv/bin/activate
python -m pipeline.run_pipeline --demo
python -m pipeline.run_pipeline --live
```

`--demo` rewrites the synthetic universe. `--live` extracts a 7-day English Bluesky sample, cleans it into `pipeline/data/posts.db`, clusters 10 planets and 6 faces, labels the faces, and overwrites `public/data.json`. With no flag, the command defaults to `--demo`.

Copy `.env.example` to `.env` for secrets. The public Bluesky search works with `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` left blank. Set both to use an app password from Bluesky settings. Do not commit `.env`.

To rehearse the live path without the network, point `--output` somewhere other than `public/data.json` unless you mean to replace the demo sky:

```bash
python -m pipeline.run_pipeline --live --fixture tests/fixtures/tiny_posts.json --output /tmp/perspectiverse-data.json
```

The example config uses `label_backend: auto` (Ollama, then an API key, then the fallback title). Set `label_backend: heuristic` in a local `pipeline.yaml` to name faces from top terms instead.

To pull a **brand-shaped or claim-shaped sample** instead of the default common-English queries (still a 7-day search, still the same 10-planet job):

```bash
python -m pipeline.run_pipeline --live --query "acme" --query "acme shoes" --output /tmp/acme.json
```

That is the free operator path toward custom universes. It does not retain history and it is not the public homepage. The civic sky stays unsupervised; see [ROADMAP.md](ROADMAP.md).

## Who can approve a PR to main

The **Main Branch Protections** ruleset requires one approving review from a code owner, plus the `security-audit` check on the latest commit. `.github/CODEOWNERS` names `@Data-Science-Link` for the whole repo. That account approves merges to `main`. This repository's ruleset is not something a pull request can turn off.

`security-audit` is a required status, not an optional lint. If GitHub shows "Waiting for status to be reported," the workflow never started — the merge box will sit there forever. That is not caused by docs-only diffs: the workflow has no path filter. The usual cause is a missed `pull_request` event (common on bot-opened or draft PRs). The workflow therefore also runs on every branch push, so the check lands on the SHA even when the PR event is dropped. If a run is still missing, push another commit or use Actions → **Security Audit Pipeline** → **Run workflow**. Close/reopen the PR also re-fires `pull_request`. Marking a draft ready does not, unless the workflow lists `ready_for_review`.

## GitHub Pages

The site is not live until Pages is switched on. The merge deploy failed because the source was never set (`Ensure GitHub Pages has been enabled`).

1. Open https://github.com/Data-Science-Link/perspectiverse/settings/pages
2. Set **Source** to **GitHub Actions**
3. Re-run **Deploy GitHub Pages**

The workflow builds with `base: /perspectiverse/`. After a green deploy the site is:

`https://data-science-link.github.io/perspectiverse/`

Setting the repository homepage to that URL is optional and done in the same settings screen. The daily job does not push to `main` (the ruleset would block it). It uploads `data.json` and commits it on the unprotected `data-snapshot` branch. The Pages build uses that file when the branch exists.

## Security

Automated scanning still runs on every push and pull request, weekly on Mondays, and on demand (`workflow_dispatch`):

- **Bandit** for Python
- **pip-audit** for Python dependencies

```bash
./scripts/security_check.sh
```

Pytest runs in `.github/workflows/pytest.yml` without downloading the embedding model. The lexical clusterer is what CI executes.

## Project structure

- `src/` — React Three Fiber observatory and sidebar
- `public/data.json` — snapshot the frontend loads
- `pipeline/` — demo writer and live ingestion
- `project_documentation/` — architecture, UI canvases, engagement/archive/history designs, and how this differs from neighboring products
- `ROADMAP.md` — what ships, what would change the architecture, and what it costs to keep (Horizons A–C)
- `.github/workflows/` — security audit, tests, frontend CI, daily pipeline, GitHub Pages

See [FILES.md](FILES.md), [pipeline/README.md](pipeline/README.md), and [ROADMAP.md](ROADMAP.md).
