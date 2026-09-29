# Data Engineering Pipeline

Daily job: rotate a retained window of ~1,000 non-spam English Bluesky posts, cluster 10 planets and 2–6 faces, generate names and a short steelman per face, and write `public/data.json`.

The 2026-09-28 audit of the synthetic era is in [Pipeline Audit 2026-09-28](../project_documentation/Pipeline%20Audit%202026-09-28.md).

## Commands

```bash
python -m pipeline.run_pipeline --live
python -m pipeline.run_pipeline --demo
python -m pipeline.run_pipeline --live --fixture tests/fixtures/tiny_posts.json
python -m pipeline.run_pipeline --live --query "acme" --query "acme shoes" --output /tmp/acme.json
```

`--live` is the default. It hits Bluesky unless `--fixture` is set (`source: "fixture"` or `"bluesky"`, `mode: "live"`).
`--demo` writes the synthetic universe (`mode: "demo"`, `source: "synthetic"`).
`--query` (repeatable) overrides the config search terms so an operator can pull a brand- or claim-shaped sample and still run the same 10-planet job. It is ignored when `--fixture` is set.

## Auth

Copy the repo-root `.env.example` to `.env`.

- Leave `BLUESKY_*` empty to use public AppView search. The extractor tries `public.api.bsky.app` then `api.bsky.app` with retries. GitHub-hosted runners have been 403'd; set `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` as Actions secrets if that keeps happening.
- `OLLAMA_HOST` and `OLLAMA_MODEL` label planets and faces locally when Ollama is running.
- `OPENAI_API_KEY` is the paid path for better names and steelmans.

`.env` is gitignored. Scratch extracts in `pipeline/data/*` stay gitignored. The retained window `pipeline/data/live_corpus.db` is tracked. Copy `pipeline/config/pipeline.example.yaml` to `pipeline/config/pipeline.yaml` for local overrides (also gitignored).

## What lands in `pipeline/data/`

| Path | Kind | Contents |
| --- | --- | --- |
| `live_corpus.db` → `posts` | retained window | ~1,000 cleaned posts (URI, author, text, likes, time) |
| `live_corpus.db` → `topic_membership` | derived | planet id per kept post |
| `live_corpus.db` → `perspectives` | derived | face index and centroid distance |
| `posts.db` | scratch | local override if you pass `--db` |

The daily job restores `live_corpus.db` from `data-snapshot` (or the copy on the branch), drops the oldest seventh, adds yesterday’s quality posts, and writes the db back with `data.json`. If Bluesky 403s, the job **does not drop** — it rebuilds the snapshot from the retained 1,000.

## Clustering

`cluster_backend: lexical` (default) uses numpy TF-IDF and k-means. CI and the daily Actions job use this path.

`cluster_backend: bertopic` uses BERTopic with `all-MiniLM-L6-v2` when that extra stack is installed (`uv sync` locally).

The lexical pass asks for 11 clusters. Anything smaller than `min_cluster_size` is Topic -1. A planet also needs at least 6 posts so it can grow two to six faces. If a messy sample leaves fewer than 10 planets, large groups are split and leftover posts are reassigned. **Topic -1 is excluded from the volume denominator.**

`min_cluster_size` is **8** on the 1,000-post window. Planet ids are 1–10 in descending volume for that snapshot. Names are generated each run and are not a durable key.

## Faces and labels

Each kept planet is split into **2–6 faces**. Representative posts: highest likes first, then nearer the face centroid. Cap is `representative_posts` (12).

`label_backend: auto` tries, in order:

1. Ollama at `OLLAMA_HOST`
2. An OpenAI-compatible API when `OPENAI_API_KEY` is set
3. Heuristic names from top terms, plus extractive steelmans from the strongest posts

There is one topic-name call per planet and one face call per perspective (title, summary, 2–4 arguments). Invalid model output is tried once more, then the heuristic is stored.

The public dropdown is **Sports, Geopolitics, AI**. Unmatched planets are `Other` and only appear in All topics. Category is a keyword map over the topic name and terms.

## Publish

The daily workflow (06:00 UTC, plus `workflow_dispatch`) runs `--live`. It does not commit to `main`. It uploads `data.json` and `live_corpus.db` as artifacts and pushes both to `data-snapshot`. Pages overlays `data.json` at build time when the branch exists.

## Layout

- `config/pipeline.example.yaml` — window, 1,000-post target, query groups
- `settings.py` — loads the example, then `pipeline.yaml` if you created one
- `data_sources/extract_bluesky.py` — Bluesky extract with host fallback
- `cleaning.py`, `corpus.py`, `store.py` — spam, rotate 1/7, SQLite
- `topics.py`, `perspectives.py`, `label.py`, `assemble.py` — planets, faces, names, `data.json`
- `live.py` — live orchestration
- `generate_demo_data.py` — synthetic universe (still available)
- `run_pipeline.py` — `--live` / `--demo`
- `schema.py` — the contract `src/App.jsx` loads
