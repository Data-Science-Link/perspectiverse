# Perspectiverse

Live mapping the universe of human attention and perspectives.

Perspectiverse turns a week of public conversation into a 3D solar system so you do not live in an echo chamber. Tilt the solar system to see **every** perspective, then check where yours stacks up. The largest topic sits at the origin as the sun. The next nine topics orbit by volume. Planet size is share of public attention — whether the general public was talking about that topic. Planets wear solar-system skins. Open one and the sphere dissolves into a **crystal of two to six faces** — one per real perspective, never more than a cube. Face length is that view's share of the conversation. Gold is the majority (loudest) view; shorter faces are minority opinions. Colors always run gold → ember → azure → violet → jade → rose, loudest first.

The analytical sidebar reacts to the solar system. Filter by category with the **Solar System** dropdown, select a planet to turn its cube, then select a face to read the representative posts. A first-visit welcome explains the metaphor; the menu can reopen it.

This is not social listening, brand monitoring, or a poll. Those tools start from a query, a named entity, or a survey instrument. Perspectiverse starts from a week of public posts and keeps the ten largest topics, each cut into two to six perspectives. [Similar Products and Differentiation](project_documentation/Similar%20Products%20and%20Differentiation.md) maps the neighboring categories — monitoring, listening, civic deliberation, news-literacy, researcher topic maps — and says what this observatory adds.

On a phone the solar system stays up front: tagline, a short prompt, and a rail of planets. Opening a planet jumps to a tight topic page (summary + its perspectives). Opening a perspective turns that face toward you and shows representative posts, always from the top, with a back arrow and the browser back button wired to the same stack. The hamburger opens Vision, About, the author, connect (GitHub and LinkedIn), methodology (with connection diagrams), FAQ, and donate, plus filters and feedback.

Bodies keep solar-system skins in volume order: the largest topic is the Sun, then Mercury through Pluto.

## Current status

The observatory now ships a **live** `public/data.json` built from a retained window of **1,000 non-spam English Bluesky posts**. The public fetch is a neutral 7-day sample, not a sports or AI keyword quota. Each later day drops posts older than seven days and searches only today. Planet names, face titles, and perspective steelmans are generated (LLM when a key is present, heuristic otherwise). The dropdown is a newspaper: World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, and Other.

| Layer | State |
| --- | --- |
| Live universe (`public/data.json`, `mode: live`) | First 1,000-post corpus |
| Retained SQLite (`pipeline/data/live_corpus.db`) | Rolling 7 days; a fetched UTC day is not searched again. Daily job uses private R2 when the `R2_*` secrets are set |
| Spam filter | Regex, then Jev when `TYPESAFE_API_KEY` is set |
| Live pipeline (`--live`) | Default command; lexical clustering on CI |
| React + R3F observatory | Newspaper-section filters; All topics stays unsupervised |
| GitHub Pages | Workflow ready. Pages source is still a repo setting |
| Daily refresh | `.github/workflows/pipeline.yml` — publishes even if Bluesky 403s |
| DeepInfra / OpenAI-compatible labels | Wired (`OPENAI_API_KEY` + `OPENAI_BASE_URL`); heuristic until a token is set |
| Conversational LLM on a planet | Roadmap only (Horizon A) |
| Custom solar system from `--query` | Ready for operators; not a public form |
| Historical solar systems / topic tracking | Roadmap only (Horizon C) |

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
python -m pipeline.run_pipeline --live
python -m pipeline.run_pipeline --demo
```

`--live` is the default. It refreshes `pipeline/data/live_corpus.db` (about 1,000 quality posts), clusters 10 planets, labels planets and faces, synthesizes core arguments, and overwrites `public/data.json`. `--demo` still writes the old synthetic 10-category universe.

Copy `.env.example` to `.env` for secrets. Do not commit `.env`.

**Bluesky (ingest).** Anonymous public search 403s from GitHub Actions. Create an [app password](https://bsky.app/settings/app-passwords) named `perspectiverse-pipeline`, then set `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` as [Actions secrets](https://github.com/Data-Science-Link/perspectiverse/settings/secrets/actions) and in `.env`. Use the app password, never the account password.

**Labels (DeepInfra).** Heuristic names are term-bags (`Chatgpt Intelligence Artificial`). For planet names, face titles, and steelmans, reuse the OpenAI-compatible client with a [DeepInfra](https://deepinfra.com/dash) token:

```
OPENAI_API_KEY=<deepinfra token>
OPENAI_BASE_URL=https://api.deepinfra.com/v1/openai
OPENAI_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
```

Same three names as GitHub Actions secrets. About 50 short JSON calls per snapshot (~$0.01, cents/month on the daily job).

**Sections and spam (Jev).** Jev is a decision model, not a writer. When `TYPESAFE_API_KEY` is set, each new post gets a spam probability and one newspaper section. High-confidence spam is dropped. Planet names still come from DeepInfra. With no key, the regex and the keyword section map run and the job still publishes. Add the key as an Actions secret too. `JEV_MODEL` is optional (`jev-latest` if unset).

Relabel the saved 1,000 without refetching Bluesky:

```bash
python -m pipeline.run_pipeline --live --relabel --db pipeline/data/live_corpus.db
```

To rehearse the live path without the network:

```bash
python -m pipeline.run_pipeline --live --fixture tests/fixtures/tiny_posts.json --output /tmp/perspectiverse-data.json
```

The example config uses `label_backend: auto` (Ollama, then `OPENAI_API_KEY`, then heuristic names from terms and posts).

To pull a **brand-shaped or claim-shaped sample** instead of the neutral public sample (still the same 10-planet job):

```bash
python -m pipeline.run_pipeline --live --query "acme" --query "acme shoes" --output /tmp/acme.json
```

That is the free operator path toward custom universes. It does not retain history and it is not the public homepage. The civic observatory stays unsupervised; see [ROADMAP.md](ROADMAP.md).

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

Setting the repository homepage to that URL is optional and done in the same settings screen. The daily job does not push to `main` (the ruleset would block it). It commits `data.json` on the unprotected `data-snapshot` branch. The Pages build uses that file when the branch exists. The SQLite corpus is uploaded to a private R2 bucket when those secrets exist, and stays on `data-snapshot` until they do.

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
