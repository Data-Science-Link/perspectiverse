# Data Engineering Pipeline

Daily job: ingest a 7-day window of English posts, cluster 10 planets and 2–6 faces, label the faces, and write `public/data.json`.

## Commands

```bash
python -m pipeline.run_pipeline --demo
python -m pipeline.run_pipeline --live
python -m pipeline.run_pipeline --live --fixture tests/fixtures/tiny_posts.json
```

`--demo` writes the synthetic universe (`mode: "demo"`, `source: "synthetic"`).
`--live` hits Bluesky unless `--fixture` is set (`source: "fixture"` or `"bluesky"`, `mode: "live"`).
No flag defaults to `--demo`.

## Auth

Copy the repo-root `.env.example` to `.env`.

- Leave `BLUESKY_*` empty to use the public AppView search (`https://api.bsky.app`). No token is required for the small sample. `public.api.bsky.app` is the same API behind a CDN that rejects some datacenter addresses.
- Set `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` (an app password, not the account password) to search as that account via `atproto`.
- `OLLAMA_HOST` and `OLLAMA_MODEL` label faces locally when Ollama is running.
- `OPENAI_API_KEY` is the optional paid path.

`.env` is gitignored. `pipeline/data/*` is gitignored except `.gitkeep`. Copy `pipeline/config/pipeline.example.yaml` to `pipeline/config/pipeline.yaml` for local overrides (also gitignored).

## What lands in `pipeline/data/`

| Path | Kind | Contents |
| --- | --- | --- |
| `posts.db` → `posts` | cleaned extract | URL-stripped text, author, likes, timestamp |
| `posts.db` → `topic_membership` | derived | planet id per kept post |
| `posts.db` → `perspectives` | derived | face index and centroid distance |

Raw network payloads are not stored. Re-run `--live` to rebuild the derived tables.

The default `sample_size` is **200** so a run can finish without a laptop-sized embed. The production target commented in the example config is **10000**.

## Clustering

`cluster_backend: lexical` (default) uses numpy TF-IDF and k-means. It does not download a model. CI and the daily Actions job use this path.

`cluster_backend: bertopic` uses BERTopic with `all-MiniLM-L6-v2`. That import pulls the embedding stack (`uv sync` locally). It is not what the scheduled job installs.

The lexical pass asks for 11 clusters. Anything smaller than `min_cluster_size` is Topic -1. A planet also needs at least 6 posts so it can grow two to six faces, so the effective floor is `max(min_cluster_size, 6)`. If more than 10 clusters remain, the smaller ones are dropped too. If a messy sample leaves fewer than 10 planets above that floor, leftover and surplus posts are reassigned so the snapshot still has 10 bodies. **Topic -1 is excluded from the volume denominator.** Topic percents and face percents are renormalized to 100. `total_posts` still counts the cleaned sample, including noise. The sidebar says those outliers are left out of the percentages.

`min_cluster_size` starts at **2** so a 200-post sample can still publish 10 planets. Use **8** when the posts separate cleanly, and **15–25** once `sample_size` is near 10000 so tiny clumps do not become planets.

Planet ids are 1–10 in descending volume for that snapshot. They are stable inside the file and recomputed on the next run.

## Faces

Each kept planet is split with k-means into **2–6 faces**, chosen from how the posts separate. A cube is the ceiling, not the default. One face may dominate; its volume is still renormalized with the others so a lopsided body stays valid.

Representative posts: **highest likes first**, then nearer the face centroid in TF-IDF space. The cap is `representative_posts` (12). A tiny cluster may have fewer, but never zero, and every post has `likes`.

## Labels

`label_backend: auto` tries, in order:

1. Ollama at `OLLAMA_HOST` (local, no per-call fee)
2. An OpenAI-compatible API when `OPENAI_API_KEY` is set
3. A visible fallback title, `Untitled cluster`, plus the top terms

The prompt asks for JSON only: `{"title": "...", "summary": "..."}`. Invalid output is tried once more, then the fallback is stored. There are 60 calls (10×6), not one per post.

`label_backend: heuristic` skips the network and builds a title from the top terms. Use it for fixtures.

Cost and runtime for one snapshot:

| Path | Calls | Cost | Runtime |
| --- | --- | --- | --- |
| Heuristic | 0 | free | seconds |
| Ollama on a laptop | 60 short prompts | free | a few minutes, depends on the model |
| `gpt-4o-mini` (or similar) | 60 short prompts | a few cents at typical mini prices | about a minute plus rate limits |

Category on each planet is a keyword map over the topic terms (Politics, Sports, Technology, Economy, Environment, Health, Education, Media). It is precomputed into `data.json`. The UI filters that field and does not call the network again.

## Publish

The daily workflow (06:00 UTC, plus `workflow_dispatch`) runs `--live`. It does not commit to `main`. It uploads `public/data.json` as an artifact and pushes that file to `data-snapshot`. Pages overlays that file at build time when the branch exists. A failed job is the v1 alert (Actions failure mail).

## Layout

- `config/pipeline.example.yaml` — window, sample size, backends, `min_cluster_size`
- `settings.py` — loads the example, then `pipeline.yaml` if you created one
- `data_sources/extract_bluesky.py` — Bluesky extract
- `cleaning.py`, `store.py` — clean text and SQLite
- `topics.py`, `perspectives.py`, `label.py`, `assemble.py` — planets, faces, titles, `data.json`
- `live.py` — live orchestration
- `generate_demo_data.py` — synthetic universe
- `run_pipeline.py` — `--demo` / `--live`
- `schema.py` — the contract `src/App.jsx` loads
