# Data Engineering Pipeline

Daily job: keep a rolling 7-day window of ~1,000 non-spam English Bluesky posts, cluster 10 planets and 2–6 faces, generate names and a short steelman per face, and write `public/data.json`.

The 2026-09-28 audit of the synthetic era is in [Pipeline Audit 2026-09-28](../project_documentation/Pipeline%20Audit%202026-09-28.md).

## Commands

```bash
python -m pipeline.run_pipeline --live
python -m pipeline.run_pipeline --live --relabel
python -m pipeline.run_pipeline --demo
python -m pipeline.run_pipeline --live --fixture tests/fixtures/tiny_posts.json
python -m pipeline.run_pipeline --live --query "acme" --query "acme shoes" --output /tmp/acme.json
```

`--live` is the default. It hits Bluesky unless `--fixture` or `--relabel` is set (`source: "fixture"` or `"bluesky"`, `mode: "live"`).
`--relabel` rebuilds planet names, face titles, and steelmans from `live_corpus.db` without calling Bluesky.
`--demo` writes the synthetic universe (`mode: "demo"`, `source: "synthetic"`).
`--query` (repeatable) overrides the neutral search terms so an operator can pull a brand- or claim-shaped sample and still run the same 10-planet job. It is ignored when `--fixture` is set. It does not mark that UTC day as already fetched.

## Auth

Copy the repo-root `.env.example` to `.env`. The CLI loads it on start without overriding a non-empty process environment (Actions secrets win).

- Leave `BLUESKY_*` empty to use public AppView search. The extractor tries `api.bsky.app` then `public.api.bsky.app` with retries. GitHub-hosted runners 403 on anonymous GET. Set `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` (an **app password** from https://bsky.app/settings/app-passwords, never the account password) as Actions secrets so the job logs in via `atproto`.
- `OLLAMA_HOST` and `OLLAMA_MODEL` label planets and faces locally when Ollama is running.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` are the paid OpenAI-compatible path. DeepInfra is the intended host:

  ```
  OPENAI_API_KEY=<deepinfra token>
  OPENAI_BASE_URL=https://api.deepinfra.com/v1/openai
  OPENAI_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
  ```

  Create the token at https://deepinfra.com/dash. Reuse the `OPENAI_*` names; the client is OpenAI-compatible. Llama 3.3 70B Turbo is about **$0.01 per snapshot** (~$0.30/month daily). Alternatives: `deepseek-ai/DeepSeek-V4-Flash`, `Qwen/Qwen3.5-9B`. `pipeline/http_json.py` allow-lists `api.deepinfra.com` and `api.openai.com`. The daily workflow forwards all three `OPENAI_*` secrets.
- `TYPESAFE_API_KEY` turns on Jev for per-post spam and newspaper section. `JEV_MODEL` is optional and defaults to `jev-latest`. The workflow forwards both. With no key, the regex and keyword section map run and the job still publishes.

`.env` is gitignored. Scratch extracts in `pipeline/data/*` stay gitignored. The retained window `pipeline/data/live_corpus.db` is tracked. Copy `pipeline/config/pipeline.example.yaml` to `pipeline/config/pipeline.yaml` for local overrides (also gitignored).

## What lands in `pipeline/data/`

| Path | Kind | Contents |
| --- | --- | --- |
| `live_corpus.db` → `posts` | retained window | ~1,000 cleaned posts, plus section and spam score when Jev ran |
| `live_corpus.db` → `fetched_days` | ledger | UTC dates already searched, so those days are not pulled again |
| `live_corpus.db` → `topic_membership` | derived | planet id per kept post |
| `live_corpus.db` → `perspectives` | derived | face index and centroid distance |
| `posts.db` | scratch | local override if you pass `--db` |

The public sample searches content-neutral tokens (`the`, `and`, `to`, `of`, `in`, `for`), newest English posts, then keeps a random subset. Bluesky search cannot draw a truly random post; this only stops steering the week toward sports, wars, or AI. The first run with an empty `fetched_days` table replaces the retained file with a 7-day sample, because the previous file was a seeded mix. Later runs drop posts older than 168 hours and search only the newest 24 hours. A UTC day already in `fetched_days` that still has posts is not searched again. If Bluesky 403s, the job **does not drop** — it rebuilds the snapshot from whatever is already retained.

Re-running BERTopic reads this SQLite file. It does not fetch days that are already stored. `--relabel` skips Bluesky and rebuilds names from the same rows.

## Clustering

`cluster_backend: lexical` (default) uses numpy TF-IDF and k-means. CI and the daily Actions job use this path.

`cluster_backend: bertopic` uses BERTopic with `all-MiniLM-L6-v2` when that extra stack is installed (`uv sync` locally).

The lexical pass asks for 11 clusters. Anything smaller than `min_cluster_size` is Topic -1. A planet also needs at least 6 posts so it can grow two to six faces. If a messy sample leaves fewer than 10 planets, large groups are split and leftover posts are reassigned. **Topic -1 is excluded from the volume denominator.**

`min_cluster_size` is **8** on the 1,000-post window. Planet ids are 1–10 in descending volume for that snapshot. Names are generated each run and are not a durable key.

## Faces and labels

Each kept planet is split into **2–6 faces**. Representative posts: highest likes first, then nearer the face centroid. Cap is `representative_posts` (12).

`label_backend: auto` tries, in order:

1. Ollama at `OLLAMA_HOST`
2. An OpenAI-compatible API when `OPENAI_API_KEY` is set (`OPENAI_BASE_URL` defaults to OpenAI, or DeepInfra when pointed at `https://api.deepinfra.com/v1/openai`)
3. Heuristic names from top terms, plus extractive steelmans from the strongest posts

There is one topic-name call per planet and one face call per perspective (title, summary, 2–4 arguments). Invalid model output is tried once more, then the heuristic is stored. Relabel the retained 1,000 without a Bluesky fetch:

```bash
python -m pipeline.run_pipeline --live --relabel --db pipeline/data/live_corpus.db
```

The public dropdown is a newspaper: **World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, Other**. With `TYPESAFE_API_KEY` set, Jev assigns a section to each new post (one `choice` plus a spam `noul` per post). A planet's category is the majority section of its members. Without a key, or when a call fails, the keyword map is the fallback. All topics is still one unsupervised clustering of the whole window. A section filter can show fewer than 10 planets at 1,000 posts. Jev does not name planets and does not replace BERTopic.

## Publish

The daily workflow (06:00 UTC, plus `workflow_dispatch`) runs `--live`. It does not commit to `main`. It uploads `data.json` and `live_corpus.db` as artifacts and pushes both to `data-snapshot`. Pages overlays `data.json` at build time when the branch exists.

## When the corpus approaches 100,000 posts

Do not add object storage for the 1,000-post file. It is about 1 MB and fits on `data-snapshot`. At 100,000 posts the same SQLite file is about 100–200 MB, and GitHub rejects blobs over 100 MB. Move that file, not the schema, to Cloudflare R2 before it nears 50 MB. BERTopic still reads a local database. The job would download it at the start and upload it at the end. That uploader is not in this repo yet.

1. Create a [Cloudflare](https://dash.cloudflare.com/) account and open **R2**.
2. Create a bucket named `perspectiverse-corpus`. Default region is fine. Leave public access off.
3. Under **Manage R2 API tokens**, create a token that can read and write objects in that bucket. Copy the access key id, the secret, and the account endpoint (`https://<accountid>.r2.cloudflarestorage.com`).
4. Add GitHub Actions secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET` (`perspectiverse-corpus`).
5. Point the daily job at the file with the S3-compatible API, for example `aws s3 cp` using that endpoint, `--db` on the downloaded path, then upload the same path after a successful run. Keep `public/data.json` in git. Do not put Postgres in front of BERTopic.

R2's free tier includes 10 GB. This file stays under a gigabyte.

## Layout

- `config/pipeline.example.yaml` — window, 1,000-post target, neutral search tokens
- `settings.py` — loads the example, then `pipeline.yaml` if you created one
- `data_sources/extract_bluesky.py` — Bluesky extract with host fallback
- `cleaning.py`, `jev.py`, `corpus.py`, `store.py` — regex, Jev decisions, 7-day window, SQLite
- `topics.py`, `perspectives.py`, `label.py`, `assemble.py` — planets, faces, names, `data.json`
- `live.py` — live orchestration
- `generate_demo_data.py` — synthetic universe (still available)
- `run_pipeline.py` — `--live` / `--relabel` / `--demo`
- `schema.py` — the contract `src/App.jsx` loads
