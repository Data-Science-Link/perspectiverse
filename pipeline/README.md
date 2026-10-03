# Data Engineering Pipeline

Daily job: keep a rolling 7-day window of up to 10,000 English Bluesky posts that passed cleaning, dedup, spam, and the public-claim check. Non-claims stay in the SQLite file and do not count toward that 10,000. Cluster up to 10 planets and 1–6 faces, generate names and a short steelman per face, and write `public/data.json`. If search cannot fill 10,000 claims, the run keeps the shortfall and logs it.

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
- `TYPESAFE_API_KEY` turns on Jev for per-post spam, newspaper section, and the public-claim check. `JEV_MODEL` is optional and defaults to `jev-latest`. The workflow forwards both. With no key, sections fall back to the keyword map, and a live Bluesky run stops instead of clustering unlabeled posts. `--fixture` and `--relabel` of an unlabeled file still run.

`.env` is gitignored. Scratch extracts in `pipeline/data/*` stay gitignored. The retained window `pipeline/data/live_corpus.db` is tracked as the seed. When the `R2_*` secrets are set, the daily job uses the private R2 object instead. Copy `pipeline/config/pipeline.example.yaml` to `pipeline/config/pipeline.yaml` for local overrides (also gitignored).

## What lands in `pipeline/data/`

| Path | Kind | Contents |
| --- | --- | --- |
| `live_corpus.db` → `posts` | retained window | Up to 10,000 filtered claims, plus non-claims that were fetched with them |
| `live_corpus.db` → `fetched_days` | ledger | UTC dates already searched, so those days are not pulled again |
| `live_corpus.db` → `topic_membership` | derived | planet id per kept post |
| `live_corpus.db` → `perspectives` | derived | face index and centroid distance |
| `posts.db` | scratch | local override if you pass `--db` |

The public sample searches content-neutral tokens (`the`, `and`, `to`, `of`, `in`, `for`), newest English posts, then keeps a random subset. Bluesky search cannot draw a truly random post; this only stops steering the week toward sports, wars, or AI. The first run with an empty `fetched_days` table replaces the retained file with a 7-day sample, because the previous file was a seeded mix. Later runs drop posts older than 168 hours and search only the newest 24 hours. A UTC day already in `fetched_days` that still has posts is not searched again. If Bluesky 403s, the job **does not drop** — it rebuilds the snapshot from whatever is already retained.

Re-running BERTopic reads this SQLite file. It does not fetch days that are already stored. `--relabel` skips Bluesky and rebuilds names from the same rows.

## Clustering

`cluster_backend: embedding` (default) uses a local MiniLM model through fastembed (ONNX, no torch). It looks for many tight groups — a long week can have 100 or more — and leaves posts that are not close to a group unlabeled. The embedding path asks for a few spare groups past `catalog_size` (10 by default) so a mixed planet can be dropped and the next specific group takes its place. It does not assign every post to a planet, and it does not split a week until ten orbits are full. The daily job installs fastembed.

`cluster_backend: lexical` uses numpy TF-IDF and k-means. Pytest uses this path and does not download a model.

`cluster_backend: bertopic` uses BERTopic with `all-MiniLM-L6-v2` when that extra stack is installed (`uv sync` locally).

Anything smaller than `min_cluster_size` is Topic -1. The live floor is `max(8, claims // 200)`. A planet needs at least 6 posts. Further faces are cut only when the second stance is large. One face is allowed when the posts actually agree. **Topic -1 is excluded from the volume denominator.**

Inside a candidate group, at most 3 posts per author count. Planets are ranked by distinct authors, then by posts. A group whose mean cosine to its centroid is below 0.60 is dropped, so a political mood does not crowd out a specific conversation. Groups closer than cosine 0.72 are merged as one subject. `catalog_size` (10) is a ceiling. Planet ids are 1–N in that rank order for the snapshot. Names are generated each run and are not a durable key.

## Faces and labels

Each kept planet is split into **1–6 faces**. A second face needs at least a fifth of the planet and a centroid cosine below 0.90. That line is higher than the planet-merge line on purpose: two stances of one subject sit above 0.72 on MiniLM, and the old face gate treated them as one view. Representative posts: highest likes first, then nearer the face centroid. Cap is `representative_posts` (12). Two faces with the same or near-same title are merged. Face titles name the claim in a grammatical phrase, not a camp ("Anti Republican"), not an insult, and not two leftover words ("Evangelists Unequipped"). A title or summary that is still a camp, a fragment, a "but" joining a second claim, or an ellipsis is rewritten once. If it is still not one claim, that face is dropped. A face whose title and summary share no subject word is dropped, as is a face that cannot show three posts of its claim. Two faces that share only a one-off word are different stories. A planet name that never appears on its faces is replaced with the face's claim. Two faces that are different stories, or whose posts share no subject word, are dropped as a planet, and a spare group fills the slot. Face titles are not numbered to look distinct.

`label_backend: auto` tries, in order:

1. Ollama at `OLLAMA_HOST`
2. An OpenAI-compatible API when `OPENAI_API_KEY` is set (`OPENAI_BASE_URL` defaults to OpenAI, or DeepInfra when pointed at `https://api.deepinfra.com/v1/openai`)
3. Heuristic names from top terms, plus extractive steelmans from the strongest posts

There is one topic-name call per planet, one face call per perspective (title, summary, 2–4 arguments), a repair call when that label is not publishable, and a same-subject check when a planet has two faces. Invalid model output is tried once more, then the heuristic is stored. The heuristic summary is a complete sentence from a shown post. Relabel the retained corpus without a Bluesky fetch:

```bash
python -m pipeline.run_pipeline --live --relabel --db pipeline/data/live_corpus.db
```

The public dropdown is a newspaper: **World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, Other**. With `TYPESAFE_API_KEY` set, Jev assigns a section to each new post (one `choice` plus a spam `noul` per post). A planet's category is the majority section of its members. Without a key, or when a call fails, the keyword map is the fallback. All topics is still one unsupervised clustering of the whole window. A section filter can show fewer planets than All topics. Jev does not name planets and does not replace the embedder. Spam drops at 0.8. A public claim is kept at 0.5. Non-claims stay in the window and out of the planets.

## Publish

The daily workflow (06:00 UTC, plus `workflow_dispatch`) runs `--live`. It does not commit to `main`. It uploads `data.json` and `live_corpus.db` as artifacts. `data.json` is pushed to `data-snapshot`, which Pages overlays at build time. When the R2 secrets are set, `live_corpus.db` is uploaded to the private bucket and removed from that branch. Until the secrets exist, the SQLite file is still committed to `data-snapshot`.

## Retained corpus in Cloudflare R2

`public/data.json` stays in git. The SQLite window is a different file. A few thousand posts are a few megabytes. At 100,000 posts the same file is about 100–200 MB, and GitHub rejects blobs over 100 MB. `pipeline/r2.py` is the uploader. It talks to R2 with the S3 API (SigV4, region `auto`). The clusterer still reads a local database. Do not put Postgres in front of it.

Until `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_ENDPOINT` are set, the job keeps the git behavior: restore `pipeline/data/live_corpus.db` from `data-snapshot` (or the committed seed) and push it back after a successful run.

`R2_OBJECT_KEY` defaults to `live_corpus.db`. That is the object the daily job downloads and uploads. A preview run can set `R2_OBJECT_KEY=live_corpus_preview.db` and write a second object in the same bucket. Leave the variable unset on the scheduled job.

1. Create a [Cloudflare](https://dash.cloudflare.com/) account and open **R2**.
2. Create a bucket named `perspectiverse-corpus`. Default region is fine. Leave public access off.
3. Under **Manage R2 API tokens**, create a token that can read and write objects in that bucket. Copy the access key id, the secret, and the account endpoint (`https://<accountid>.r2.cloudflarestorage.com`).
4. Add GitHub Actions secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET` (`perspectiverse-corpus`).

On each run the workflow downloads `live_corpus.db` and passes that path to `--db`. The upload runs only after the pipeline step succeeds, and only if `PRAGMA integrity_check` returns `ok` and `posts`, `fetched_days`, `topic_membership`, and `perspectives` are present. A failed step skips the upload. The PUT replaces the object only when R2 accepts the full body, so a dropped connection leaves the previous object in place. A missing object (the first run) keeps the git seed and uploads it after success. Any other R2 error stops the job, so that seed is not written over a newer object.

The schema stays as it is. `--relabel` and a BERTopic rerun read the downloaded file and do not search a UTC day already in `fetched_days`.

```bash
python -m pipeline.r2 restore pipeline/data/live_corpus.db
python -m pipeline.run_pipeline --live --relabel --db pipeline/data/live_corpus.db
python -m pipeline.r2 upload pipeline/data/live_corpus.db
```

R2's free tier includes 10 GB. This file stays under a gigabyte.

## Layout

- `config/pipeline.example.yaml` — window, 10,000-claim target, neutral search tokens
- `settings.py` — loads the example, then `pipeline.yaml` if you created one
- `data_sources/extract_bluesky.py` — Bluesky extract with host fallback
- `cleaning.py`, `jev.py`, `corpus.py`, `store.py` — regex, Jev decisions, 7-day window, SQLite
- `topics.py`, `perspectives.py`, `label.py`, `assemble.py` — planets, faces, names, `data.json`
- `r2.py` — download and upload `live_corpus.db` to private Cloudflare R2
- `live.py` — live orchestration
- `generate_demo_data.py` — synthetic universe (still available)
- `run_pipeline.py` — `--live` / `--relabel` / `--demo`
- `schema.py` — the contract `src/App.jsx` loads
