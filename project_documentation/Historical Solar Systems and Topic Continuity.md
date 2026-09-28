# Historical Solar Systems and Topic Continuity

How the public observatory could show **what changed over time** — a date you can rewind to, a topic that grew, a majority face that flipped — without pretending that yesterday's "Housing Rent Crisis" and today's "Cost Of Living" are automatically the same planet.

This is investigation, not a build plan. Nothing in the pipeline or frontend has to change for this note to be true. The living sequence and cost table is [ROADMAP.md](../ROADMAP.md) (Horizon C). Storage of *posts* (so a clerk or a custom solar system can retrieve them) is a different job: [Custom Universe and Archive Architecture](Custom%20Universe%20and%20Archive%20Architecture.md). Talking to a planet is [Planet Engagement Architecture](Planet%20Engagement%20Architecture.md).

## The jobs that look like "history"

Four product questions get bundled as "trending" and they do not share an architecture.

| Job | Visitor question | What you must keep | What you must solve |
| --- | --- | --- | --- |
| **A. Time-travel the solar system** | "Show me last Tuesday." | One `data.json` per day | Almost nothing. Fetch the file. Planet *ids* will not mean the same thing as today. |
| **B. Topic trajectory** | "Has Housing grown since August?" | A **stable identity** across days, plus a volume per day | Matching (or incremental clustering). Names will not do it. |
| **C. Birth / death / rank change** | "What became a planet this week?" | Identity plus the top-10 cutoff | Matching, plus an honest rule for "fell out of the solar system" vs "the conversation ended." |
| **D. Face drift** | "Did the gold face on AI flip from optimism to safety?" | Identity at **planet and face** grain | Harder matching. LLM titles drift more than cluster geometry. |

"Trending" in the Google Trends sense is closest to **B + C with a velocity**, not A. A date picker on the solar system is A, and A is the cheap one.

Do not build B by stuffing solar systems into Postgres and hoping `WHERE name = 'Housing'` works. That is the failure mode this note exists to name.

## What the system actually does today

Ground this in the code that ships, not the canvas.

- The daily job writes **one** `public/data.json` and **overwrites** it. `.github/workflows/pipeline.yml` commits that file onto `data-snapshot`. Pages overlays it at build time. Git history of that branch is a crude archive of whole files, not a product.
- Actions **artifacts** keep `data.json` for **14 days**. After that the runner copy is gone.
- Runner SQLite (`pipeline/data/posts.db`) is ephemeral. Membership dies with the job. See [Planet Engagement](Planet%20Engagement%20Architecture.md) for the table of what survives.
- `topics.id` is **1–10 in descending volume for that snapshot**. Pipeline README: *stable inside the file and recomputed on the next run.* Today's Sun is "largest cluster today," not "the same neighborhood as yesterday's Sun."
- Live planet **names** are not BERTopic's pretty labels and not an LLM title. `assemble.topic_name` joins the top three salient terms (`Housing Rent Crisis`). BERTopic, when used, only supplies those terms via `get_topic`. Faces get the LLM (or heuristic) titles.
- Clustering is **independent every day**. Default is lexical TF-IDF + k-means (`cluster_backend: lexical`). BERTopic is optional and is not what CI or the scheduled job installs. Either way, `fit_transform` starts from scratch. Topic numbers from the model are remapped to 0…9 by size, then `+ 1` for the JSON.
- The window is **168 hours, overlapping**. Consecutive days share six calendar days of *search window*, then independently subsample (`sample_size` default 200). Post-URI overlap between Tuesday's sample and Wednesday's sample can be tiny even when the weeks look similar.
- Representative posts in the snapshot have `author`, `text`, `likes`. **URIs are not in `data.json`.** Matching on "the same posts" is impossible from the published file alone.

So: we already throw away the two things a serious time series wants — the sample, and a stable key.

## Why names will not line up

This is the usual topic-model tracking problem. It is not a BERTopic bug.

Independent clustering produces a **new partition** of a **new sample** every morning. The human-readable string is a compression of that partition.

| Churn | Example | What a naive name-join does |
| --- | --- | --- |
| Paraphrase | `Ai Jobs Model` vs `Layoff Copilot` | Treats one conversation as two series. |
| Granularity | `Housing` splits into `Rent` and `Mortgage Rates` | Orphaned series; a "death" that is really a split. |
| Merge | `Wildfire` + `Heat Dome` become `Climate Extreme` | Fake birth; two lines vanish. |
| Rank churn | Same neighborhood, 11th → 9th | Appears as a birth because only the top 10 are published. |
| Label noise | Heuristic terms shuffle `Crisis Rent Housing` | String equality fails; even fuzzy match is brittle. |
| Face titles | `Job Displacement` vs `Payroll Automation` on the same planet | Sidebar looks like a new argument when the posts did not move. |

BERTopic's default representation (`0_ai_jobs_model`) is a bag of words with a run-local index. `fit_transform` on tomorrow's posts will not reuse `0`. Incremental / merged BERTopic can keep *model* indices more stable; it still will not make the **published** `topics[].name` a primary key, and it is not the path the daily Actions job runs.

**Rule:** treat `name`, `title`, and `id` as display. Identity is a separate object, computed after the solar system exists (or imposed *before* clustering, which is a different product).

## High-level approaches

Three families. They can be mixed. They should not be confused.

### 1. Archive solar systems, cluster independently (time-travel first)

Keep each day's `data.json`. The observatory grows a date control. Selecting a day fetches that snapshot and renders it with today's frontend. No identity. Planet 3 on Monday is unrelated to planet 3 on Tuesday except by coincidence of volume rank.

**This is the correct v1 of "history"** if the question is "what did the observatory *say* that morning?" It is also the only approach that stays on static hosting for free.

**It is not trending.** You cannot draw a line called Housing.

### 2. Independent cluster, then align (tracking)

Keep doing today's job. After two (or N) solar systems exist, run a **matcher** that decides which planets continue, split, merge, appear, or drop. Write a lineage file:

```text
canonical_id  ←──  2026-09-27 / topic 4  "Housing Rent Crisis"
              ←──  2026-09-28 / topic 2  "Cost Of Living"
              ──X  2026-09-29            (dropped out of top 10)
```

The solar system still publishes 1–10 per day. The matcher adds `canonical_id` (and maybe `parent_ids`, `relation`) onto each topic. Charts and "this planet last week" read the canonical key. The date picker still loads a snapshot file.

This fits the current pipeline. It does not require BERTopic. It does not require Postgres. It *does* require a representation of each planet that is richer than its name.

### 3. Impose identity at cluster time (incremental / seeded / taxonomy)

Do not throw away yesterday's model.

| Variant | Idea | Cost to the civic thesis |
| --- | --- | --- |
| **Seeded k-means** | Initialize today's centroids with yesterday's. New posts snap to old neighborhoods; leftover density can birth a topic. | The solar system is less "what is this week unsupervised" and more "how did last week's neighborhoods move." |
| **Incremental / merged BERTopic** | `partial_fit` or `merge_models` so topic numbers persist. | Ties the daily job to the embedding stack CI currently skips. Still need a match step for splits. |
| **One model over a long corpus** | Dynamic topic model, or BERTopic with timestamps, over 30–90 days. Topics have a time series *inside* one fit. | You no longer have ten independent daily solar systems. You have a river. Different visualization. Different product. |
| **Canonical taxonomy** | Standing list (Housing, AI, Elections, …). Assign each day's clusters to the list; overflow is `Other`. | This is social listening. It is honest as a *premium* query-shaped solar system. It is how you accidentally erase the public homepage's unsupervised claim. |

Use family 3 when family 2's match quality is measured and still bad, or when a paid surface *wants* a stable codebook. Do not start here on `/`.

---

## Would we just store the data in PostgreSQL and load the day they select?

You *can*. For job A it is usually the wrong first database.

A date picker that loads Tuesday's solar system is:

```text
GET /snapshots/2026-09-23.json
```

or

```sql
SELECT payload FROM solar systems WHERE day = '2026-09-23';
```

Those are the same product. The SQL version adds an always-on API in front of GitHub Pages. Today's observatory has no application server. The moment you need `SELECT` you have left the $0 static constraint, which is fine — Horizon A and B already propose that — but **do not buy Postgres to replace a folder of JSON files**.

Postgres (or SQLite on a small box, or DuckDB over parquet) starts to win when you want queries the files do not answer:

- "Volume of canonical topic X for the last 90 days" without opening 90 JSON documents in the browser.
- Join lineage → faces → representative posts → (if retained) member URIs.
- Research SQL, clerk retrieval, custom-universe metadata, billing — the same box Horizon B already argued for.

A reasonable split:

| Data | Put it | Why |
| --- | --- | --- |
| Daily snapshot JSON (`data.json` contract) | Object store or `public/snapshots/YYYY-MM-DD.json` | The frontend already knows this shape. Time-travel is a fetch. |
| Manifest of available days | Tiny `solar systems/index.json` | Date picker, no directory listing. |
| Lineage / canonical topics / daily volumes | JSON first (`lineage.jsonl`); Postgres when charts are a product | Small. Can live next to the solar systems. |
| Cleaned posts + membership (Grade 1 archive) | Object store, then a real DB if you query them | See Horizon B. Needed for URI-overlap matching, not for rendering a past solar system. |
| Firehose | Not for this feature | Unbounded history is Grade 4. Trending the public solar system does not require it. |

**SQLite is already in the pipeline.** A persistent `history.db` on object storage, downloaded by the daily job, updated, uploaded, is a middle path that still has no live API. The site would either (a) still publish static JSON derived from that DB, or (b) need a server to query it. Prefer (a) until someone is issuing ad-hoc SQL.

### Store the output files?

**Yes, as the default.** The published snapshot *is* the product artifact. It is tens to a few hundred KB. A year of daily files is well under 100 MB even with thicker snapshots. That is git-tolerable on a dedicated branch, trivial in R2/S3, and cheap as Actions artifacts if you raise retention.

Three file layouts, in increasing honesty:

**Layout 0 — git history of one path.** `data-snapshot` already overwrites `public/data.json`. `git log -p` is not a date picker. Recovering day N means a checkout. Do not ship this as UX. Do use it as an accidental backup of whatever has been published so far.

**Layout 1 — dated files, static hosting.**

```text
public/snapshots/index.json          # { "days": ["2026-09-01", ...], "latest": "2026-09-28" }
public/snapshots/2026-09-28.json     # full data.json contract
public/data.json                 # copy of latest (today's observatory unchanged)
public/lineage.json              # optional; canonical ids + match edges
```

The daily job writes the new dated file, updates the manifest, copies to `data.json`. The frontend: `?day=2026-09-23` fetches that file. Cache forever (content-addressed by date). GitHub Pages can host this until the tree is ugly; then move `solar systems/` to object storage and keep Pages as the app.

**Layout 2 — object store + optional DB.** Same JSON objects, `s3://…/snapshots/2026-09-28.json`. Pages or a worker fetches them. Postgres holds `solar systems(day primary key, payload jsonb, canonical built_at)` only if you need indexes or you are already running Horizon B's box.

**Do not store only metrics and throw away the solar system.** A sparkline without a cube you can open is a dashboard, and we already decided not to be Brandwatch on `/`. Keep the renderable JSON. Derive series from it.

**Do not commit 10k-post membership into git.** That is the Grade 1 archive (object store, lifecycle). The snapshot file should stay the contract `schema.py` already validates.

---

## Continuity: matching similar-but-different topics across days

This is the actual design problem. Storage is easy.

### What to match *on* (representations)

Ranked by how much they need from today's pipeline vs Horizon B.

1. **Top terms (already in the solar system).** Jaccard or overlap of the 3–15 salient terms. Cheap, language-native, fails on paraphrase (`ai` vs `copilot`). Use as one signal, never the only one.
2. **Category.** Already precomputed. A weak prior (two Politics planets should still compete with each other, not with Sports).
3. **Representative-post text.** Embed the 12 posts per face (or concatenate and embed the planet). Cosine similarity of planet centroids. Works from `data.json` alone. Quality tracks how representative those posts are. The demo solar system has 3 posts/face; live cap is 12.
4. **Member-set overlap (gold when you have it).** Jaccard of post URIs (or of `clean_text` hashes) between yesterday's cluster and today's. Requires Grade 1 retention of membership, which `data.json` does not have. The 7-day window helps *if the same posts are resampled*; the independent 200-post subsample works against it. Raise `sample_size` and persist URIs before betting on this.
5. **Centroid of the full cluster.** TF-IDF or MiniLM mean of all members, not just reps. Best geometry, needs the sample that currently dies on the runner. Persist a 384-d vector per planet (tiny) even if you delete the posts.
6. **LLM judge.** "Are these the same conversation?" Last resort, 10×10 = 100 cheap calls/day if you score every pair; or ~10 calls if you only judge Hungarian leftovers. Drift, cost, and non-determinism. Use to *label* a match (`continues` vs `related`), not to invent the graph.

A practical scoring function for v1 matching, still $0:

```text
score(a, b) =
    0.45 * cosine(embed(reps(a)), embed(reps(b)))   # or TF-IDF cosine if no model
  + 0.35 * jaccard(terms(a), terms(b))
  + 0.10 * 1[category_a == category_b]
  + 0.10 * jaccard(uris(a), uris(b))                # 0 until Grade 1 exists
```

Threshold τ (start around 0.55–0.65 and **measure**). Embeddings: the same `all-MiniLM-L6-v2` BERTopic would use, run *once per planet-day* (10 vectors), not once per post.

### Assignment, not greedy name equality

Ten planets yesterday × ten today is a 10×10 cost matrix. Use the **Hungarian algorithm** (or greedy if you must) to get a 1–1 matching, then **drop** edges below τ.

What the leftovers mean:

| Leftover | Honest label | Often actually |
| --- | --- | --- |
| Yesterday unmatched | Left the published snapshot | Dropped from top 10, split, or the sample missed it |
| Today unmatched | Entered the published snapshot | Rose into top 10, merged residue, or a new event |

**Splits and merges are not 1–1.** After the primary assignment, look at unmatched today-planets whose second-best yesterday neighbor is still above a lower threshold τ_split — that is a split. Two yesterday-planets both close to one today-planet is a merge. Store relations explicitly:

```text
continues | splits_into | merges_from | appears | disappears | rank_only
```

`rank_only` is the case where the neighborhood still exists in the *sample* (you would see it if `catalog_size` were 20) but it is not a planet today. You cannot know this unless you persist more than 10 clusters. Cheap improvement: keep a **shadow catalog** of the next 10 clusters in the archive (not rendered). Then "disappeared" vs "fell to #14" is visible.

### Canonical ids

- Mint a `canonical_id` (UUID or `t_<short>`) the first time a planet has no parent.
- On `continues`, inherit it.
- On `splits_into`, mint children and record `parent`.
- On `merges_from`, mint a new id *or* inherit the heavier parent's id and record the absorbed one as an alias. Pick one rule and keep it. Inheriting the heavier parent is less surprising on a chart.
- Published `topics[].id` stays 1–10 for the renderer. Add optional `canonical_id` later; `schema.py` can ignore unknown fields today, or we extend the contract when we build this.
- Display name of a canonical topic is **not** frozen. Show today's terms. Optionally keep a "also known as" list for the sidebar. Freezing the first name (`Ai Jobs Model` forever) is how you get a stale museum.

### Face-level continuity

Match **planets first**, then run the same algorithm *inside* a matched pair (2–6 × 2–6). Face titles from the LLM will thrash; use representative-post embeddings. Gold (majority) can move from face A to face C — that is a product moment, not a bug. If the planet match is wrong, face matches are fiction, so never face-match across unmatched planets.

A majority-flip detector: same `canonical_id`, argmax(face volume) changed, and the new gold matches yesterday's non-gold face above τ. Worth a sidebar sentence. Not worth a new database.

### What not to do for identity

- **Do not key on `topics[].id`.** Rank is not identity.
- **Do not key on BERTopic's integer label** unless you have moved to incremental models *and* still record a match score. A fresh `fit_transform` resets it.
- **Do not key on exact name.**
- **Do not ask an LLM to emit a stable slug as the only id.** It will invent `housing-policy` one day and `rent-affordability` the next.
- **Do not freeze k-means with yesterday's k and no birth process.** The civic observatory's job is to let a new neighborhood become the Sun.

### Incremental clustering, in more detail

If match quality on independent solar systems is poor (you will know after a month of dated files), seed today's clusterer:

1. Persist yesterday's 10 (or 20) TF-IDF / MiniLM centroids.
2. Assign today's posts to nearest centroid if distance < δ.
3. Cluster the unassigned residue; allow new planets.
4. Drop empty seeds (yesterday's topic got no mass — candidate disappearance).
5. Recompute names from *today's* members so the sidebar stays current.
6. Still run the matcher as a check: seeded assignment can trap a new event inside an old blob.

This preserves identity by construction for the posts that stayed near a centroid. It biases against "the week changed shape." Put it behind a config flag. Compare both methods on the same dated archive before picking one for `/`.

BERTopic-specific tools (`merge_models`, `reduce_topics`, online HDBSCAN) are the same idea on the embedding path. They are unavailable on the GitHub Actions lexical job unless we change the runner. Measure lexical matching first; the default clusterer is lexical.

---

## Trending without lying about the 7-day window

Even with perfect identity, **day-over-day volume on a 168-hour rolling window is autocorrelated**. Six of seven days are shared (in the search window, not necessarily in the subsample). A topic that truly doubled today moves the 7-day share only modestly. A "hot" chart will look like a sleepy one.

Ways to say "trending" honestly:

| Measure | How | Honest as |
| --- | --- | --- |
| **Stock** | 7-day cluster share (what we already publish) | Size of the planet. Not velocity. |
| **Week vs prior week** | Compare `day` to `day-7` (non-overlapping windows) | Change. Slow. Good for "this month." |
| **Flow / novelty** | Count posts in the cluster with `created_at` in the last 24h (needs timestamps in the sample, which SQLite already has) | Actual "what heated up today." Requires keeping membership or at least per-planet new-post counts in the snapshot file. |
| **Rank delta** | Canonical topic's position 1–10 vs yesterday | Cheap, noisy, good as annotation ("entered the solar system"). |
| **Share of window vs share of sample** | If we ever retain more than the subsample | Research. Not v1. |

Do not label a sparkline "trending" if it is 7-day stock. Call it **attention this week**. Put velocity on a second number, or on week-over-week, and say which.

Platform "trending" (boosted, engaging, query-shaped) is a different ranking. [Similar Products](Similar%20Products%20and%20Differentiation.md) already distinguishes that. A Perspectiverse trend should stay **cluster mass in this extract**, plus optionally **flow**. It should not become a list of hashtags.

---

## Frontend shapes (when someone builds this)

All of these consume either dated snapshot files (A) or snapshot files + lineage (B). None of them require Postgres in the request path if the daily job precomputes JSON.

1. **Date control** on the existing observatory. `?day=` fetches `solar systems/{day}.json`. Latest remains `/`. No morph. Cheapest UX. Planet skins will jump: yesterday's Sun might be today's Mars because rank changed. That jump is confusing unless you also have identity (or you drop solar skins in history mode and use a neutral encoding).
2. **Pinned canonical planet.** Open Housing, then scrub days. The camera stays on `canonical_id`; missing days show "not in the top 10" rather than a different topic wearing the same orbit.
3. **Sparklines** in the sidebar: 14–30 days of stock for the canonical id. Precompute into `lineage.json` so the browser does not fetch 30 solar systems.
4. **Entered / left today.** A short list derived from unmatched nodes. This is the one that feels like "trending" without a chart library.
5. **Morphing orbits.** Interpolate radii and sizes between day t and t+1 for matched ids. Unmatched fade in/out. Beautiful, expensive in engineering, easy to fake if matching is wrong. Do not lead with this.

History mode should label the window (`7-day sample ending {date}`, `source`, `sample_size`) so a visitor does not think they are seeing a live firehose.

---

## Technical implementation (when we build, not now)

No code in this investigation. The seams already in the repo:

| Step | Where it would hang | Notes |
| --- | --- | --- |
| Stop overwriting | `.github/workflows/pipeline.yml` | After `write_payload`, copy to `public/snapshots/{last_updated}.json` and append `index.json`. `last_updated` is already an ISO date. |
| Persist a planet vector | `pipeline/assemble.py` / live orchestration | Optional `topics[].centroid` or a sidecar `solar systems/{day}.meta.json` so the public contract stays lean. |
| Persist URIs of members | Grade 1 object archive, not `data.json` | Enables Jaccard matching. Privacy / ToS: URIs are posts; lifecycle them. |
| Matcher job | New `pipeline/lineage.py` (name TBD) | Reads two solar systems + optional meta, writes edges. Can run in the same daily workflow after assemble. |
| Schema | `pipeline/schema.py` | Additive: `canonical_id`, `day`, `flow_24h` can wait until a consumer exists. Validator today rejects unknown *mode/source* but extra topic fields would need a decision (strict vs open). |
| Frontend | `src/App.jsx` fetch path | Today: `data.json`. History: `solar systems/${day}.json` with fallback. |
| API | Only if Pages cannot host the files or SQL shows up | Same worker as Horizon A/B. |

Worked matcher sketch (independent solar systems, lexical):

```text
for each planet in solar system[t-1], solar system[t]:
    terms = set(name.split + persisted terms)
    vec = mean(TF-IDF or MiniLM of representative_posts[].text)
    uris = membership archive or []

cost[i,j] = 1 - score(planet_i, planet_j)     # see formula above
assignment = hungarian(cost)
for each pair:
    if score < τ: mark unmatched
    else: relation = continues; inherit canonical_id
then: detect splits/merges on near-misses
mint ids for appears
write lineage.jsonl append-only (day, from, to, relation, score)
rebuild lineage.json summary for the UI (canonical_id → [{day, local_id, volume, name}])
```

Cold start: the first dated snapshot mints 10 canonical ids. There is no yesterday. That is fine.

Backfill: if we later scrape `data-snapshot` git history, we can run the matcher over recovered files. Representative posts are enough for a v0 alignment. Quality will be worse than with centroids/URIs.

---

## Trade-offs (summary)

| Approach | Implements jobs | Stay on Pages? | Identity? | Maintain cost | Main risk |
| --- | --- | --- | --- | --- | --- |
| Git history of one `data.json` | Accident | yes | no | $0 | Not a product |
| Dated snapshot files + date picker | A | yes | no | **$0** | Visitors think planet 1 is "the same" |
| Dated files + matcher + `lineage.json` | A, B, C, weak D | yes | yes, post-hoc | **$0–$1** (embed 10 planets) | Bad matches look like insight |
| Files + Grade 1 membership archive | Better B, C, D | files still static | URI Jaccard | **$0–$2** | ToS, deletion, sample still tiny |
| Seeded / incremental cluster | B, C by construction | yes (output still a file) | stronger | $0, but **changes the solar system** | Less unsupervised; new events get absorbed |
| Long-corpus DTM / one 90-day model | B as a river | maybe | yes, inside one model | compute on the job | Not ten daily civic solar systems |
| Postgres of JSON payloads | A with an API | **no** | no unless matcher too | **$5–$20** box | Paying for `GET by date` |
| Postgres normalized (runs, topics, faces, posts, edges) | All, plus research SQL | no | yes | **$5–$20** + care | Right when Horizon B already needs a box; overkill before that |
| Canonical taxonomy | B as listening | either | by fiat | labeling time | Replaces the public product |

**Recommendation, in this project's cost language:**

1. **Keep dated output files.** That is the whole of job A and the substrate for everything else. Postgres is not required to pick a day.
2. **Do not treat names or BERTopic labels as keys.** Run a matcher on terms + representative-post vectors; persist a 10×N lineage sidecar.
3. **Add Grade 1 membership (URIs + optional centroids) when we want match quality**, which is the same persist step Horizon B already wants for debate reruns.
4. **Buy a database when we already have a server** (clerk, custom universes) or when the browser would otherwise download 90 solar systems to draw a sparkline — and even then, precompute the sparkline in the daily job first.
5. **Do not incremental-cluster the public solar system until** independent matching has a month of files to lose to.

---

## Cost to maintain (steady state)

| Layer | Lean path | If it gets popular |
| --- | --- | --- |
| Dated `data.json` (≈50–300 KB/day) | git branch or Pages tree, **$0** | object store, **~$0** |
| 14–90 days of Actions artifacts | already 14 days, **$0** | still $0; not a UI |
| Matcher (TF-IDF cosine, 10×10) | seconds on the existing job, **$0** | — |
| Matcher (MiniLM on ~120 posts) | laptop/Actions extra minute; model download **breaks the current lean runner** | run only if we already pay for BERTopic |
| Grade 1 sample archive | **$0–$2 / month** | same |
| History API + Postgres | — | **$5–$20 / month** for a small box; storage negligible |
| LLM match judge | skip | a few cents/day |

History is cheap next to Horizon A tokens and Horizon B ingest. The expensive mistake is **identity theater**: shipping a time slider that implies continuity the matcher has not earned.

## What we will not do (on the free public solar system)

- Promise Google-Trends-style "what's hot" from a 200-post overlapping week without a flow measure.
- Key time series on planet names, face titles, or rank ids.
- Put the civic homepage on a standing taxonomy so the lines look clean.
- Stand up Postgres only to serve files we could have written to `public/snapshots/`.
- Retain an unbounded firehose "so we can trend later." Lifecycle or do not ingest.
- Morph orbits until matching has a documented precision on real dated solar systems.

## Suggested sequence

1. **Stop deleting yesterday.** Dated JSON + manifest. Recover whatever `data-snapshot` git still has. No UI required; operators can already point the app at another file.
2. **Date picker** (job A). Label the day. Accept that skins and ids jump. Learn whether anyone rewinds.
3. **Offline matcher** on those files (terms + reps). Publish `lineage.json` and read it yourself. Tune τ. Add shadow catalog (clusters 11–20) if "deaths" are mostly rank churn.
4. **Sparklines / entered-the-solar-system** for canonical ids that survive τ. Still static.
5. **Grade 1 URIs + centroids** (shared with Horizon B). Re-run matching. Only then consider seeded clustering as an A/B against independent+match.
6. **Postgres** if and when a box exists for another reason, or the precomputed JSON is not enough.

If step 2 sees no use, stop. A trend line nobody opens is a dashboard we said we were not building.

See [ROADMAP.md](../ROADMAP.md) Horizon C for how this sits next to the clerk and custom universes.
