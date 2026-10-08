# Architecture

Short map of the path that ships. Longer design notes stay in [`project_documentation/`](../project_documentation/Project%20Architecture_%20Discourse%20Universe.md). Product forks are in [ROADMAP.md](../ROADMAP.md). Terms are in [glossary.md](glossary.md).

## Data flow

The daily job is `.github/workflows/pipeline.yml` (`cron` 06:17 UTC, plus `workflow_dispatch`). It runs `python -m pipeline.run_pipeline --live`. It does not push to `main`.

1. **Bluesky ingest.** [`pipeline/data_sources/extract_bluesky.py`](../pipeline/data_sources/extract_bluesky.py) pulls a neutral English sample. [`pipeline/live.py`](../pipeline/live.py) rotates the retained window. If today's UTC date is already in `fetched_days` and the corpus still has posts from that day, the job does not search again.
2. **Clean and decide.** [`pipeline/cleaning.py`](../pipeline/cleaning.py) normalizes text and drops obvious junk. [`pipeline/jev.py`](../pipeline/jev.py) scores spam (drop at 0.8), a public claim (keep at 0.5), and one newspaper section. Jev does not name planets or write steelmans. On a live Bluesky run, posts that are not claims are dropped before the SQLite replace. With no `TYPESAFE_API_KEY`, that run stops instead of clustering unlabeled posts.
3. **Corpus.** [`pipeline/corpus.py`](../pipeline/corpus.py) and [`pipeline/store.py`](../pipeline/store.py) keep a rolling 168-hour window in `pipeline/data/live_corpus.db`, aimed at 10,000 claims. [`pipeline/r2.py`](../pipeline/r2.py) downloads that file from private Cloudflare R2 before the run and uploads it after a successful run when the `R2_*` secrets are set. `data.json` is not stored in R2. If R2 is unset, the workflow restores and commits the SQLite file on `data-snapshot`.
4. **Embed and cluster.** Default backend is local MiniLM (`all-MiniLM-L6-v2` via fastembed) in [`pipeline/topics.py`](../pipeline/topics.py). Groups are dense balls (`density_labels` in [`pipeline/grouping.py`](../pipeline/grouping.py)): a fine seed grid, then drop cells that are not tight and merge cells of one subject. The group count is not the grid size and it is not `n / min_cluster_size`. Pytest uses the lexical TF-IDF path. The job publishes at most 10 planets (`catalog_size` / `SYSTEM_SIZE`) after ranking every group by distinct authors, then size. Posts that fit no group are Topic -1 and are left out of the volume percentages. When sections are labeled, [`pipeline/live.py`](../pipeline/live.py) also clusters each newspaper section on the same embeddings and stores those planets under `sections`.
5. **Faces and labels.** [`pipeline/perspectives.py`](../pipeline/perspectives.py) splits a planet into faces. [`pipeline/label.py`](../pipeline/label.py) names the planet and each face and writes steelmans (`arguments`). With `label_backend: auto` the order is Ollama, then an OpenAI-compatible API (DeepInfra when `OPENAI_*` is set), then a heuristic. [`pipeline/assemble.py`](../pipeline/assemble.py) writes `public/data.json`. [`pipeline/schema.py`](../pipeline/schema.py) checks the file: each published planet needs 1–6 perspectives. When no 2–6 split passes, the planet is one perspective and may carry `opposing_note`.
6. **`data-snapshot`.** After a successful run the workflow commits `public/data.json` on the `data-snapshot` branch. The SQLite file is committed there only when R2 is unconfigured. The same commit appends `costs/ledger.csv` and regenerates `costs/README.md` and `costs/daily_spend_14d.svg` (LLM labeling, Jev, and R2). Those files are not in `public/` and are not deployed.
7. **Pages frontend.** [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) builds on `main` and, when `data-snapshot` exists, overlays `public/data.json` from that branch. [`src/App.jsx`](../src/App.jsx) fetches `${BASE_URL}data.json`. The solar system is React Three Fiber (`src/components/`). Empty cube sides are dashed (`src/lib/spikes.js`). The category dropdown reads `sections` when that object is present (`src/lib/categories.js`).

`--demo` still writes a synthetic universe (`mode: demo`). That is not the daily job.

## Longer notes

| Topic | File |
| --- | --- |
| Discourse-universe canvas | [`project_documentation/Project Architecture_ Discourse Universe.md`](../project_documentation/Project%20Architecture_%20Discourse%20Universe.md) |
| Pipeline technical canvas | [`project_documentation/Technical Implementation Canvas.md`](../project_documentation/Technical%20Implementation%20Canvas.md) |
| UI and 3D canvas | [`project_documentation/UI & 3D Implementation Canvas_ Perspectiverse.md`](../project_documentation/UI%20%26%203D%20Implementation%20Canvas_%20Perspectiverse.md) |
| Planet engagement | [`project_documentation/Planet Engagement Architecture.md`](../project_documentation/Planet%20Engagement%20Architecture.md) |
| Custom universe and archive | [`project_documentation/Custom Universe and Archive Architecture.md`](../project_documentation/Custom%20Universe%20and%20Archive%20Architecture.md) |
| Historical solar systems | [`project_documentation/Historical Solar Systems and Topic Continuity.md`](../project_documentation/Historical%20Solar%20Systems%20and%20Topic%20Continuity.md) |
| Neighboring products | [`project_documentation/Similar Products and Differentiation.md`](../project_documentation/Similar%20Products%20and%20Differentiation.md) |
| Pipeline audit (2026-09-28) | [`project_documentation/Pipeline Audit 2026-09-28.md`](../project_documentation/Pipeline%20Audit%202026-09-28.md) |
| Operator commands | [`pipeline/README.md`](../pipeline/README.md) |
| Setup and current status | [`README.md`](../README.md) |

Some of those canvases still describe earlier choices (one to six faces, Reddit, a hosted LLM as the labeler). The contract that runs is `pipeline/schema.py` and the modules in the list above.
