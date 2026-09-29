# Pipeline audit — 2026-09-28

Honest assessment of what shipped versus what is still synthetic, written so a later pass does not have to rediscover it. The living sequence is [ROADMAP.md](../ROADMAP.md). This note is the snapshot of the codebase *before* the live-corpus conversion; the conversion itself is the next commit on this branch.

## Verdict

**What you see in the observatory was a designed demo.** That was the right move for the visual product. It was not only a cardboard facade: the UI, the `data.json` contract, and the live extract → clean → cluster → label path were real. The live path had never successfully published. Daily Actions was failing. There was no `data-snapshot` branch.

| Layer | State on 2026-09-28 |
| --- | --- |
| 3D observatory + static hosting | Production-shaped |
| Shared `data.json` contract | Real, validated in Python and Node |
| Committed `public/data.json` | 100% synthetic (`mode: demo`, `source: synthetic`, `total_posts: 100000`) |
| Live ingest / cluster / label | Written and fixture-tested; **not publishing** |
| BERTopic | Implemented, skipped on CI (no torch) |
| LLM labels / synthesis | Implemented; environment-dependent; no keys on Actions |
| Firehose, chat clerk, topic identity | Documentation only (Horizons A–C) |

## What the live path actually did

1. Public Bluesky **search** (not Jetstream). Default queries were common English tokens (`the`, `people`, `today`, …).
2. Client-side 168-hour window, then a **subsample** (default **200** posts).
3. Conservative spam regexes (short text, repeated characters, many hashtags, “buy followers”).
4. Ephemeral runner SQLite, discarded when the job ended.
5. Lexical TF-IDF + k-means on CI. BERTopic only if installed.
6. 2–6 faces via a second k-means.
7. Face titles from Ollama → OpenAI → `Untitled cluster`. Planet names were the top three terms (`Housing Rent Crisis`).
8. Published file kept ≤12 representative posts per face. No core arguments on the live path.

The “7 days” in the product was a **search window**, not a retained firehose.

## Why the daily job was not operational

Observed Actions runs:

- **2026-09-28:** `api.bsky.app` returned **HTTP 403** from the GitHub-hosted runner. `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` were empty.
- **2026-09-27:** extract succeeded, clustering raised `Need 10 clusters of at least 6 posts, found 9`. A 200-post sample is too thin for a guaranteed 10-planet snapshot.

No `data-snapshot` branch existed, so Pages kept overlaying the committed demo file.

## Demo vs live (why the demo looked “logical”)

The demo is an **editorial argument map**: branded planet names, orthogonal steelmanned faces, curated posts, 100 topics (10 per category) so the dropdown never emptied.

Live clustering finds **neighborhoods in short, noisy posts**. BERTopic helps paraphrase grouping; it does not write Perspectiverse. Face titles from 12 posts will invent a debate on a garbage cluster. Categories were a fixed keyword vote (unmatched → Media).

**Conclusion:** the UI socket can take live data without a 3D rewrite. The *experience* will look thinner than the demo unless sampling, spam, naming, and synthesis are first-class. That is product work, not “turn on BERTopic.”

## Storage feasibility (unchanged)

Disk is not the blocker. Rough physics from the archive note:

| Grade | What we keep | Steady cost |
| --- | --- | --- |
| Sample of 1k–10k posts | Grade 1 archive | ~$0–$2 / month |
| 7-day English firehose | ~56 GB at 4M posts/day × 2 KB | ~$1 storage; ingest box costs more |
| Forever firehose | ~3 TB / year raw | Do not start here |

Do not embed the firehose. Embed, at most, posts that survive a filter.

## Spam and “recent” labels

The 2026-09-28 spam filter was four heuristics. Bluesky junk (bots, gm-only, follow-for-follow, crypto, link dumps) would become planets.

Unsupervised daily clustering *can* surface new topics. It cannot keep a stable “housing planet” whose label stays current. Rank ids and term-bag names remint every run. Identity across days is Horizon C.

## API keys

This environment could reach public Bluesky search without auth. GitHub Actions could not (403). There was no `OPENAI_API_KEY` and no Ollama on the runner.

For **higher-quality** planet names, face titles, and perspective synthesis, set `OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.deepinfra.com/v1/openai`, and `OPENAI_MODEL` (DeepInfra via the OpenAI-compatible client) as GitHub Actions secrets and in `.env`. Then `python -m pipeline.run_pipeline --live --relabel`.

For a **reliable daily fetch from Actions IPs**, set `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD`. The conversion also tries `public.api.bsky.app`, retries, and will **rebuild from the retained corpus** if the day’s fetch fails so the job still publishes.

## What this conversion is aiming at

Documented here so the roadmap and the code stay aligned:

1. Stronger spam filter; first rendition is **1,000 non-spam Bluesky posts** in a retained SQLite corpus.
2. Daily job **rotates ~1/7** of that corpus (drop oldest, add yesterday’s quality posts).
3. Ten unsupervised planets from that corpus.
4. Three public groupings for the dropdown: **Sports, Geopolitics, AI** (other demo categories stay in the synthetic writer only).
5. Autogenerated planet names, face titles, and perspective synthesis (LLM when a key exists; heuristic/extractive otherwise).
6. Daily job must succeed even when Bluesky 403s, by clustering the retained 1,000.
