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
| `live_corpus.db` → `jev_verdicts` | cache | Jev spam, claim, and section scores keyed by post URI; rows older than 14 days are deleted (#92) |
| `posts.db` | scratch | local override if you pass `--db` |

The public sample searches content-neutral tokens (`the`, `and`, `to`, `of`, `in`, `for`), newest English posts, then keeps a random subset. Bluesky search cannot draw a truly random post; this only stops steering the week toward sports, wars, or AI. The first run with an empty `fetched_days` table replaces the retained file with a 7-day sample, because the previous file was a seeded mix. Later runs drop posts older than 168 hours and search only the newest 24 hours. A UTC day already in `fetched_days` that still has posts is not searched again. If Bluesky 403s, the job **does not drop** — it rebuilds the snapshot from whatever is already retained.

Re-running BERTopic reads this SQLite file. It does not fetch days that are already stored. `--relabel` skips Bluesky and rebuilds names from the same rows.

## Clustering

`cluster_backend: embedding` (default) uses a local MiniLM model through fastembed (ONNX, no torch). A group is a dense ball: posts near one center. A fine grid of seeds keeps neighboring crowds from being glued together first; the grid size is not the topic count. Cells that are not dense are dropped, and cells of one subject are merged. A long week can have hundreds of groups. Posts that never join a ball stay unlabeled. The live job ranks every surviving group and publishes the top `catalog_size` (10 by default), so a mixed planet can be dropped and the next group takes its place. It does not assign every post to a planet, and it does not split a week until ten orbits are full. The daily job installs fastembed. Through 12,000 posts the grid is fit on every post. Above that, centers are fit on a sample of 12,000 and other posts join a center only when they sit inside its ball.

`cluster_backend: lexical` uses numpy TF-IDF and k-means. Pytest uses this path and does not download a model.

`cluster_backend: bertopic` uses BERTopic with `all-MiniLM-L6-v2` when that extra stack is installed (`uv sync` locally).

Anything smaller than `min_cluster_size` (5 by default, and not raised with the claim count) is Topic -1. A published planet needs at least `min_planet_posts` posts (5 by default), and it is published with 1–6 faces (see below). **Topic -1 is excluded from the volume denominator.**

Inside a candidate group, at most 3 posts per author count. Extra posts from that author stay unlabeled. A noise post can then join a planet of at least 20 posts when it is close to that planet's original center and it contains that planet's top subject stem. A smaller planet can fold into one larger planet on that same check. A planet that is itself folding is not a parent, so stories do not chain. A face dropped for having no shared claim gives a post back when the post's subject is that kept face's subject. After the wide relabel, two faces on one planet with the same or near-same title are merged. Planets are ranked by distinct authors, then by posts. `catalog_size` (10) is a ceiling on what is published, not on how many groups the week contains. Planet ids are 1–N in that rank order for the snapshot. Names are generated each run and are not a durable key.

## Faces and labels

Each kept planet is split into **1–6 faces** in its own MiniLM space. Every count from 2 to 6 is tried (k-means with three deterministic restarts), and the count with the best mean cosine silhouette wins; a near tie goes to the smaller count. A count only competes when every face has at least 2 posts and 5% of the planet, no two face centroids are at cosine 0.90 or closer (that line is higher than the planet-merge line on purpose: two stances of one subject sit above 0.72 on MiniLM), and every face is at least as tight as the planet. Faces do not have to be balanced: a small, tight minority is a face. A planet where no count passes is published as one perspective. It carries `opposing_note` (`No clear opposing view found in this sample`) and `face_distinctness` 0. A second face is not forced. A face that does not share a claim, judged on a spread of up to 40 posts rather than the few closest to the centroid, is dropped. If one real face remains, the planet stays. A planet is not removed for having one face. Representative posts: closest to the face embedding first, then higher likes. The cosine is the one already computed for clustering. Cap is `representative_posts` (36). Two faces with the same or near-same title are merged. When the label backend is a model, one more call merges faces that argue the same side even when the titles differ. If one face would remain, one call labels a spread of at most 40 posts (the whole planet when it is smaller). A second face is added only when the other pole is at least `stance_second_face_share` of that sample, at least two posts, and one coherent claim. Otherwise the planet stays one face and keeps `opposing_note`. That sample is the count the split uses. The whole planet is not sent. The heuristic backend makes neither call. A face added this way is not wide-relabeled and is not folded back by a later title match. Face titles name the claim in a grammatical phrase, not a camp ("Anti Republican"), not an insult, and not two leftover words ("Evangelists Unequipped"). A title or summary that is still a camp, a fragment, a "but" joining a second claim, or an ellipsis is rewritten once. If it is still not one claim, that face is dropped. A face whose title and summary share no subject word is dropped, as is a face that cannot show three posts of its claim. Two faces that share only a one-off word, or only an office word such as prosecutor, are different stories. A face title has to appear in most of the posts it shows. An "and" ending the posts never say is cut off the summary. A planet name that never appears on its faces is replaced with the face's claim. Two faces that are different stories, or whose posts share no subject word, are split into separate planets. Each of those planets goes through this same face split, gets its own name, and counts toward the catalog ceiling. A planet needs at least `min_planet_posts` posts (5 by default). A candidate or a split story under that floor is left out before any label, name, or brief call, with one INFO line naming the section, a label hint, and the post count. It is not glued onto a sibling and it does not fill a catalog slot. The next eligible candidate, in the existing rank order, takes the slot. Face titles are not numbered to look distinct.

`label_backend: auto` tries, in order:

1. Ollama at `OLLAMA_HOST`
2. An OpenAI-compatible API when `OPENAI_API_KEY` is set (`OPENAI_BASE_URL` defaults to OpenAI, or DeepInfra when pointed at `https://api.deepinfra.com/v1/openai`)
3. Heuristic names from top terms, plus extractive steelmans from the strongest posts

There is one face call per perspective (title, summary, 2–4 arguments), a repair call when that label is not publishable, then one topic-name call and the brief/detail calls only for a planet that is published. A model backend also makes one same-stance call when a planet still has two or more faces, and one sample call when it would otherwise publish a single face. A one-perspective planet still gets that name and those briefs. Extra candidate groups are not extra model calls: labeling stops once `catalog_size` planets survive. Candidates are labeled in rank order and labeling stops once `catalog_size` planets survive, for the global system and for each section. With a network backend, `label_workers` (8) global planets are labeled at once; results are still taken in rank order. HTTP 429, HTTP 5xx, and timeouts from the OpenAI-compatible API are retried twice with backoff (2s, then 6s). A retry is skipped when it would run past the section time budget; a timeout retry needs another full 60s still inside that ceiling. Other HTTP errors are not retried. Each run logs DeepInfra errors by type (429, 5xx, timeout, other), with retried attempts kept separate from final failures. Final failures over 5% of calls print a warning. Invalid model output is tried once more, then the heuristic is stored. Section solar systems are ordered by post volume and labeled through one shared pool — 12 calls in flight when `label_workers` is 8, otherwise that configured cap — so a small section does not wait out a large one. They share a `section_budget_minutes` (20) ceiling after the global system. `0` skips sections; omitting the setting uses 20. A section past the ceiling, or one that raises, is skipped and logged so the snapshot still publishes. The shared pool does not label extra candidates: a section still stops once `catalog_size` planets survive. The heuristic summary is a complete sentence from a shown post. Relabel the retained corpus without a Bluesky fetch:

```bash
python -m pipeline.run_pipeline --live --relabel --db pipeline/data/live_corpus.db
```

The public dropdown is a newspaper: **World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, Other**. With `TYPESAFE_API_KEY` set, `jev_prefilter.py` drops link-only, very short, non-English, and near-duplicate posts before any paid Jev call (#92). Jev then assigns a section to each new post (one `choice` plus a spam `noul` per post). Answers are stored in `jev_verdicts` for 14 days so the same URI is not rescored (#92). A planet's category is the majority section of its members. Without a key, or when a call fails, the keyword map is the fallback. All topics is still one unsupervised clustering of the whole window. A section filter can show fewer planets than All topics. Jev does not name planets and does not replace the embedder. Spam drops at 0.8. A public claim is kept at 0.5. Non-claims stay in the window and out of the planets.

## Publish

The daily workflow runs `--live` and publishes a new snapshot. It does not commit to `main`. It uploads `data.json` and `live_corpus.db` as artifacts. `data.json` is pushed to `data-snapshot`, which Pages overlays at build time. When the R2 secrets are set, `live_corpus.db` is uploaded to the private bucket and removed from that branch. Until the secrets exist, the SQLite file is still committed to `data-snapshot`.

A run does not replace that live `data.json` when labeling failures degraded it: section planets fell by more than a small margin (the larger of 3 and 5% of the live count), or the wide face relabel was left unfinished in most sections, and DeepInfra final failures or retries-plus-finals are over 5% of calls. A real day with fewer planets and a healthy labeler still publishes. The cost ledger can still be updated. The workflow step then fails so Pages does not treat the run as a successful deploy. See `pipeline/publish_guard.py`.

The same commit appends `costs/ledger.csv` and regenerates `costs/README.md` and `costs/daily_spend_14d.svg` on `data-snapshot` (one row per paid service and model, including Cloudflare R2). Each row includes `trigger` (`schedule`, `push`, `workflow_dispatch`, or backfilled from GitHub Actions) so the chart can stack production spend above merge- and test-triggered spend on the same day (#101). Those files are not under `public/`, so Pages does not deploy them. A cost-log error is a warning and does not stop the snapshot.

### When the pipeline triggers

| Trigger | What happens | LLM spend |
| --- | --- | --- |
| Scheduled UTC (`06:17`, `07:47`, `09:17`, `10:47`, `12:17`; #97) | Full live pipeline — Bluesky fetch, Jev on new posts only, embed, cluster, label, publish. Later scheduled slots no-op when `pipeline/schedule_guard.py` sees today's run already succeeded on `main`. | ~$0.01/snapshot (DeepInfra labels) + Jev per new post |
| Push to `main` — pipeline code changed (`pipeline/**`, `pyproject.toml`, `uv.lock`, `.github/workflows/pipeline.yml`) | Same full live pipeline | Same as cron |
| Push to `main` — site-only files (frontend, `pipeline/README.md`, `pipeline/data/**`, docs) | `pages.yml` redeploy only — no pipeline run, no LLM spend | None |
| `workflow_dispatch` | Full live pipeline | Same as cron |

**Same-UTC-day reruns are idempotent on fetching:** `live.py` records each fetched UTC date in `fetched_days` and returns the retained corpus unchanged if that day is already present. **Jev only scores new posts:** `jev.py` skips any post that already has a `section` field, so existing posts are never re-classified. R2 and `data-snapshot` writes are serialised by a workflow-level `concurrency: discourse-pipeline` group (cancel-in-progress: false) so pipeline runs never overlap each other. That group does not cover a cloud-agent paid test, which uses the same DeepInfra key outside Actions. Those tests must run `python scripts/check_pipeline_overlap.py` first and wait when it exits 2. See `.factory/DOCS.md`.

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
- `cleaning.py`, `jev_prefilter.py`, `jev.py`, `corpus.py`, `store.py` — regex, free pre-filter, Jev decisions, 7-day window, SQLite (`jev_verdicts` cache, #92)
- `story_attach.py` — same-story attach, planet fold, and post-relabel title merge (#114)
- `topics.py`, `perspectives.py`, `label.py`, `assemble.py` — planets, faces, names, `data.json`
- `publish_guard.py`, `pipeline_overlap.py`, `schedule_guard.py` — hold degraded snapshots (#115), overlap check for paid tests (#115), skip redundant scheduled runs (#97)
- `r2.py` — download and upload `live_corpus.db` to private Cloudflare R2
- `live.py` — live orchestration
- `generate_demo_data.py` — synthetic universe (still available)
- `run_pipeline.py` — `--live` / `--relabel` / `--demo`
- `schema.py` — the contract `src/App.jsx` loads
