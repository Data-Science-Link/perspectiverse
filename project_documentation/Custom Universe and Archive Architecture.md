# Custom Universe and Archive Architecture

How to keep more than twelve posts, how to build a sky from a brand or a block of text, and how a Google plugin could sell that without wrecking the public observatory.

## The tension

The public product is **week-shaped**. The pipeline does not start from a noun. It samples English Bluesky, clusters, and keeps the ten largest neighborhoods. That is the civic trick: you find out what the week was about.

A custom universe is **query-shaped**. Someone types `Nike`, or pastes a paragraph they wrote, or highlights a sentence in Chrome. They want *their* solar system. That is social listening with our gravity and our cube. It is a real product. It is a different product.

[Similar Products and Differentiation](Similar%20Products%20and%20Differentiation.md) exists so we do not accidentally turn the home page into Brandwatch. This note is the architecture for the second surface — and for the storage the second surface requires.

## What "retain all Bluesky posts" would actually mean

Today we retain almost nothing:

- The daily job asks public search for a handful of common tokens (`the`, `people`, `today`, …).
- It keeps up to `sample_size` posts (200 default) inside the last 168 hours.
- Those rows sit in `pipeline/data/posts.db` on the runner and vanish when the job ends.
- `data.json` keeps ≤12 representatives per face.

People hear "7-day window" and picture a firehose on disk. We do not have that. We have a **windowed search + subsample**. Storage cost of Bluesky posts is currently ~0 because we throw them away.

"Retain all posts" has four grades. Only the first two belong near v1.

### Grade 1 — keep what we already fetched

After clustering, write the cleaned sample (and face membership) to object storage before the runner dies. 200–10,000 posts × ~1–2 KB is nothing.

**Unlocks:** reruns, better extractive debate, debugging a bad planet, a 30-day trail of *samples* (not of Bluesky), and **URI-overlap matching** so Horizon C can tell whether yesterday's planet and today's are the same neighborhood instead of guessing from names.

**Steady cost:** $0–$2 / month.

### Grade 2 — drain for named queries

A persistent consumer (or a frequent search poll) keeps every post that matches a **watch list**: paying brands, a research term, a journalist's beat. The public unsupervised job stays separate.

**Unlocks:** custom skies that feel current for the nouns someone will pay for.

**Steady cost:** $5–$25 / month for the consumer, plus storage of those streams only.

### Grade 3 — windowed firehose

A Jetstream (or equivalent) consumer writes every post — or every English post — to cheap object storage with a lifecycle: 7, 30, or 90 days, then delete.

Rough physics (order-of-magnitude, not a invoice):

| Assumption | 7-day keep | 30-day keep | 90-day keep |
| --- | --- | --- | --- |
| 1M posts/day × 2 KB | 14 GB / ~$0.20 | 60 GB / ~$1 | 180 GB / ~$3 |
| 4M posts/day × 2 KB | 56 GB / ~$1 | 240 GB / ~$4 | 720 GB / ~$11 |

Object storage is not the scary line. The scary lines are:

- **Always-on ingest.** Jetstream is a socket, not a cron. A $5–$12 box, or a platform worker that does not sleep.
- **Index.** Grep over 50 GB of JSONL is not a product. You need partitions (day + lang) and FTS or a column store. That is another few dollars to a few tens, plus care.
- **Embeddings of the firehose.** This is how bills jump two orders of magnitude. Do not. Embed after a filter, or not at all (lexical cluster is how CI already works).
- **ToS, deletion, and "public" vs "publicly archived."** A post that was public at ingest may be deleted later. Lifecycle plus a honor-delete path is part of the architecture, not a later ethics slide.

**Unlocks:** "type any brand, get this week's sky" without a pre-registered watch list.

**Steady cost:** **$15–$60 / month** at current Bluesky-scale guesses if you stay lexical and delete aggressively. Recheck volume before you promise a price; firehose rates move.

### Grade 4 — forever

A year of 4M posts/day is ~3 TB raw (~$40–$50 / month storage alone) plus index growth. This is a research corpus, not a feature. Do not start here.

## Target architecture for custom skies

The public daily job stays as it is. Custom skies are an **on-demand pipeline** in front of a **retained index**.

```
                 ┌─ public cron ──► data.json ──► Pages observatory
                 │
Jetstream/search ┤
                 │
                 └─ writer ──► object store (lifecycle)
                                    │
                                    ▼
                              hot index (FTS / parquet by day)
                                    │
                     POST /universes { text | brand | url }
                                    │
                         authorize + quota (premium)
                                    │
                    retrieve matching posts in window
                                    │
                    same clusterer as pipeline.topics
                    + 2–6 faces + labels
                                    │
                         store sky JSON at /u/:id
                                    │
                    plugin iframe or /u/:id observatory
```

### Why not run this in the browser today

It looks tempting: the clusterer is numpy TF-IDF; we could port it. Three hard no's:

1. **The corpus is not in the bundle.** Filtering the public snapshot for "Nike" tells you whether Nike appeared in a 200-post general sample. That is Path 0 on the home page (useful!). It is not a Nike universe.
2. **Bluesky search is not a browser API.** `api.bsky.app` is not a CORS-open, keyless, quota-free engine for a GitHub Pages origin. Putting an app password in an extension is how you lose the account.
3. **A 10k embed in someone's tab** is a worse product than a 4-second server job.

So: extractive "where does this brand land *in this week's public sky*" can be free and client-side. **Generating** a universe cannot.

### What we can do for $0 today (operator path)

The live extractor already takes a list of search queries. The CLI now lets you override them without editing YAML:

```bash
python -m pipeline.run_pipeline --live \
  --query "acme" \
  --query "acme shoes" \
  --output /tmp/acme.json
```

That is a custom universe for a person who can run Python. It is the correct prototype of the premium API: same clusterer, same schema, same observatory. Point the frontend at another `data.json` and you are done. No archive, no plugin, no invoice.

If those skies look like product, *then* wrap the same function in HTTP.

## On-demand job design

Reuse `pipeline.live.run_live` with injected posts. Do not fork a second NLP stack.

| Step | Public cron | Custom universe |
| --- | --- | --- |
| Source | config `queries` (common English tokens) | request text / brand / plugin highlight |
| Window | 168 hours | 168 hours (or 24h for "live") |
| Sample | 200–10,000 | 2,000–10,000 matches, then cap |
| Cluster | lexical default | lexical default (same code) |
| Labels | heuristic / Ollama / mini | same; prefer heuristic if the quota is thin |
| Output | `public/data.json` | `universes/{id}.json` + metadata (query, owner, expiry) |
| Cache | one sky / day | cache key = `(normalized query, window, snapshot date)` |

Cache hard. "Nike" will be typed a thousand times before lunch. One sky per brand per day is the same semantic-stability argument as the public job.

**Empty result is a product.** If the filter returns 40 posts, do not invent 10 planets. Return a small-sky contract (or a refusal) and say so. A fake cube is worse than a sparse one.

## Google / Chrome plugin (premium)

The plugin is distribution, not a new model of discourse.

**Motion.**

1. User highlights text on a page, or types a brand into the extension.
2. Extension sends `{ text, url, window }` to `POST /universes` with their account.
3. Worker returns `{ id, status }`. First hit may take 5–30 seconds (cold search + cluster + 60 labels). Cached hits return the JSON.
4. Extension opens a side panel: mini solar system + "Test your take" against *that* sky.
5. Deep link to the full observatory at `/u/:id` for the cube.

**Why this is premium.** Each miss is compute and, if labeled, tokens. Each miss also risks a ToS problem if we scrape the host page. Send *user-highlighted text*, not the whole DOM.

**Why Google.** Chrome Web Store reaches the people who are already arguing in a tab (docs, news, Twitter/Bluesky, Slack-in-browser). A Workspace add-on is a later cousin (Docs comment → universe). Same API.

**What the plugin must not do.**

- Replace the public sky's homepage.
- Store the user's highlight forever without saying so.
- Run the visitor's Bluesky password.
- Claim the generated sky is "public opinion about the brand."

**Steady cost beyond the API:** store review, OAuth client, a privacy policy that matches Grade 2/3 retention, and refunding the days the firehose moved. Cash is near $0. Attention is not.

## Application split (keep the civic URL clean)

| Surface | URL | Auth | Cost model |
| --- | --- | --- | --- |
| Public observatory | `/` | none | $0, daily snapshot |
| Test your take | `/` sidebar | none | $0, extractive |
| Custom sky | `/u/:id` | signed link or account | per sky / subscription |
| Plugin | Store listing → API | account | same as custom sky |
| Clerk chat | `/` or `/u/:id` | cap or paid | see [Planet Engagement](Planet%20Engagement%20Architecture.md) |

Two JSON contracts can stay identical (`schema.py`). The difference is **how the posts were chosen**, and that difference must be labeled in the sidebar (`source`, `mode`, and a new `query` field when the sky was requested). Optional fields do not break today's validator.

## Cost to maintain (lean premium, honest)

Assumptions: Grade 2 or a small Grade 3 window, lexical clustering, mini labels, a few hundred custom skies a month, no public ungated LLM.

| Line | Monthly |
| --- | --- |
| Ingest / API box | $5–$12 |
| Object store + FTS | $2–$15 |
| Labels on custom skies | $5–$30 |
| Domain, Store, OAuth | ~$0 cash |
| **Subtotal** | **~$20–$80** |

Add Horizon A chat on every custom sky and tokens dominate. Add Grade 4 retention and storage plus legal review dominate.

This is still cheap next to Brandwatch. It is not the $0 public observatory. Price the plugin so a quiet month does not require a sponsor, and so a busy month does not surprise you.

## Sequence

1. Use `--query` on real brands. Keep the JSON. Read it in the existing UI (swap `public/data.json` locally). Decide if the metaphor still holds when the sample is query-shaped.
2. Persist Grade 1 samples from the public job. Almost free, immediately useful to engagement.
3. If (1) is product, wrap `run_live` in a queued HTTP job with cache and a `query` field.
4. Ship the extension against that job. Do not build the extension first.
5. Only then consider Jetstream. Search-API drains will carry a surprising number of brands without a firehose.

See [ROADMAP.md](../ROADMAP.md) for how this sits next to the civic sky. Dated public skies and topic tracking (a different job from retaining a firehose) are [Historical Skies and Topic Continuity](Historical%20Skies%20and%20Topic%20Continuity.md).
