# Perspectiverse roadmap

This is the product and architecture roadmap. It is written against the system that actually ships today: a **once-per-day job**, a **small English Bluesky sample**, a **static `public/data.json`**, and a **cheap 3D render**. Near-zero cost is not an accident. It is the constraint that keeps the public observatory public.

Related design notes:

- [Planet Engagement Architecture](project_documentation/Planet%20Engagement%20Architecture.md) — debate, follow-ups, and why an LLM needs a different backend
- [Custom Universe and Archive Architecture](project_documentation/Custom%20Universe%20and%20Archive%20Architecture.md) — retain posts, generate a solar system from a brand or a claim, Google plugin
- [Historical Solar Systems and Topic Continuity](project_documentation/Historical%20Solar%20Systems%20and%20Topic%20Continuity.md) — rewind a day, trend a topic, and why BERTopic names are not a time-series key
- [Similar Products and Differentiation](project_documentation/Similar%20Products%20and%20Differentiation.md) — why the public solar system stays week-shaped
- [Project Architecture](project_documentation/Project%20Architecture_%20Discourse%20Universe.md)

## Audience

The civic surface is for people who already think they know the argument — self-confident readers, debaters, operators, and anyone who treats their feed as a census. The product motion is **anti-echo chamber**, but the public solar system does that with **geometry**, not a chatbot: tilt to see every perspective, read planet size as public interest, and see whether your view is the gold majority face or a shorter minority one. Sometimes the thing you care about is not a planet at all.

That last case is the feature. Query-shaped tools cannot deliver it, because they only search inside the noun you already named.

A second, paid surface can invert the starting question: *generate a universe from this brand or this text.* That is social listening with our metaphor. It is valuable. It is not the public home page. Shipping it on the same URL without a bright line would erase the differentiation the observatory is built on.

## Cost today

| Item | What we actually pay |
| --- | --- |
| Bluesky public search | $0 |
| GitHub Actions daily job + Pages | $0 inside the free tier |
| Snapshot in git (`public/data.json` or `data-snapshot`) | git storage of a small JSON file |
| Runner SQLite (`pipeline/data/posts.db`) | ephemeral; discarded when the job ends |
| Face labels | $0 with heuristic or local Ollama; a few cents per snapshot if `gpt-4o-mini` is on |
| Frontend render | $0 — static fetch, no server |

We do **not** currently retain a 7-day Bluesky firehose. The "7 days" in the product is a **search window**, then a subsample (default 200 posts; 10k is the commented target). After clustering, the published snapshot keeps **at most 12 representative posts per face**. The rest of the sample dies with the runner.

Honest current burn: **$0–$1 / month**.

Everything below is priced as *steady-state maintain*, not build time. Agents do not estimate calendar weeks.

---

## Now — shipped on the static solar system

These stay inside today's architecture. No new vendor, no GPU, no chat API.

| Item | Status | Cost to maintain |
| --- | --- | --- |
| 10-planet observatory, 2–6 faces, solar skins, mobile drill-down | Shipped | $0 |
| Daily lexical pipeline + optional Ollama/OpenAI labels | Shipped | $0–$1 / month |
| Welcome tour + tagline (how to read size, tilt, and the crystal) | Shipped | $0 |
| **`--query` live extract** — operator can pull a brand-shaped sample and write a solar system | Shipped | $0 (your laptop / Actions minutes) |

The extractive **Test your take** panel was pulled from the public site. Token-overlap verdicts were not intelligent or insightful enough; they made the observatory feel like a toy matcher. Conversational LLM reading of a planet or face stays on **Horizon A** — it needs a briefing store and a clerk, not a static Pages bundle.

**`--query`** is the free operator path toward custom universes:

```bash
python -m pipeline.run_pipeline --live --query "acme" --query "acme shoes"
```

It still uses public Bluesky search and the same 10-planet job. It does not retain history and it is not a plugin.

---

## Next — thicken the snapshot without leaving static hosting

Do these before buying a database.

1. **Raise the live `sample_size` toward 10,000** once Labels and clustering look stable. Cost: Actions minutes, still ~$0 if the job stays under the free budget. Risk: a 10k BERTopic embed on a GitHub runner is the thing that *does* start to cost (time, not dollars). Stay lexical on CI.
2. **Ship more evidence per face** (20–50 posts, plus top terms) so a future LLM clerk has enough words. `data.json` grows from tens of KB to a few hundred KB. Pages will not notice.
3. **Optional local LLM in the sidebar** for people who run [Ollama](https://ollama.com/) — same allow-list the pipeline already uses. The site stays static; the browser talks to `localhost`. Cost: $0. Quality: good on a laptop, useless on a phone. This is the first honest LLM on the public solar system — not a keyword overlap panel.
4. **Keep dated copies of `data.json`** instead of only overwriting `data-snapshot`. Cost: git/Pages, still $0. A date picker can load `solar systems/YYYY-MM-DD.json`. That is time-travel, not trending: planet names and rank ids still churn. Matching, week-over-week, and a database are Horizon C, not this list.

Stop here if the goal is a public civic observatory that stays free.

---

## Horizon A — planet and face intelligence (conversational LLM)

**Job:** A visitor locks a planet or a face and talks to it. "Why are people thinking that, in their words?" "Push back on me." "Is my argument even on this cube?" Follow-ups keep the same retrieval scope.

**Why today's architecture is not enough.** The expensive work happens once. The corpus is thrown away. The site is a file. A capable model needs (1) the actual words of the cluster, (2) a retrieval step, (3) a place to run. Putting an API key in a GitHub Pages bundle is not an architecture.

The design that keeps the daily solar system cheap:

```
daily job
  sample → cluster → data.json          (unchanged public render)
  + persist face membership + quotes    (new: briefing store)
  + write 60 briefing cards             (title, summary, 20–50 quotes, terms)

chat request
  scope = planet | face
  retrieve quotes from that briefing
  LLM answers only from retrieved text
  refuse when the quotes do not contain the thing
```

That is retrieval-augmented *reading*, not a free-form persona. The model is not the planet. The posts are the planet. The model is a disciplined clerk.

**Value.** This is the conversion from observatory to argument. The self-confident user does not bounce after one glance. They stay for the discomfort of being a moon. That is also the marketing: *the anti-echo chamber*.

**Cost to maintain (steady state).**

| Layer | Lean path | If it gets popular |
| --- | --- | --- |
| Briefing store (quotes for 10 planets) | git or object file, $0–$1 / month | same |
| Chat model | user-supplied Ollama, $0 | hosted mini model, **$0.005–$0.05 / turn** |
| 10k conversations / month @ 4 turns | $0 with Ollama | **$200–$2,000 / month** in API tokens |
| Small always-on CPU for the clerk | — | **$5–$20 / month** |
| Abuse / rate limits | — | required once the URL is public |

Do not embed the whole firehose to answer "why this face." Embed, or even just store, the **members of that face**. That is a 100–1,000× cheaper retrieval set than "all of Bluesky."

A hosted LLM is the first line item that can take this project off the near-zero curve. Gate it (daily cap, bring-your-own key, or a paid tier) before putting it on the public solar system.

Details: [Planet Engagement Architecture](project_documentation/Planet%20Engagement%20Architecture.md).

---

## Horizon B — retain posts and generate a universe from text

**Job:** Someone types a brand, a claim, or a paragraph. They get *their* 10-planet solar system, not this week's public one. A Google / Chrome plugin is the distribution: highlight text on a page, or type a brand, and open a generated universe.

**Why today's architecture is not enough.** Custom solar systems are **query-shaped** and **on-demand**. The public job is **week-shaped** and **batch**. You cannot filter a 200-post general sample into a meaningful Nike universe. You also cannot call `api.bsky.app` from the Pages origin (no CORS, no secrets, no quota isolation).

The architecture that does it, without pretending we store "all of Bluesky" for free:

```
always-on ingest (Jetstream or search drain)
        ↓
cheap object store, lifecycle 7 / 30 / 90 days
        ↓
hot index (FTS, maybe embeddings on a subset)
        ↓
POST /universes { query | brand | highlighted text }
        ↓
filter → same 10 × 2–6 clusterer → snapshot JSON
        ↓
plugin or /u/:id observatory
```

**Retain "all posts" in three honest grades.** Grade 3 is the one people say when they mean "I never want to miss a mention." Grade 1 is the one that stays near-zero.

| Grade | What we keep | Steady cost | What it unlocks |
| --- | --- | --- | --- |
| 1. Sample archive | Every post the daily job already fetched, for 30–90 days, not just 12 reps | **$0–$2 / month** (object store) | Better debate on the public solar system; reruns |
| 2. Query drains | Firehose or search, but only for watched brands / user texts | **$5–$25 / month** + storage of those streams | Premium custom solar systems that feel live |
| 3. Windowed firehose | All (or all English) posts for 7–30 days, then delete | **$15–$60 / month** at a few million posts/day | True on-demand "any brand, this week" |
| 4. Forever firehose | Unbounded history | **storage grows ~$20–$50 / month per retained year** plus the ingest box | Research. Not a v1 product. |

Numbers assume ~2 KB / post JSON and cheap object storage (R2-class, ~$0.015 / GB-month, no egress). A 4M-post day is ~8 GB. Seven days is ~56 GB (~$1). Ninety days is the first time storage is a real line. The **ingest process** (a persistent Jetstream consumer) is usually more expensive than the disk.

Do not embed the firehose. Embed, at most, posts that survive a filter for a paid universe.

**Value.** This is the commercial twin of the civic observatory. A brand operator who is sure they are the story types their name and either gets a solar system or gets the more useful answer: *you were not a planet*. The plugin puts that motion next to the page they are already arguing on.

**Cost to maintain a modest premium (hundreds of universes / month, lexical cluster, mini labels).**

| Item | Monthly |
| --- | --- |
| Ingest VM or always-on container | $5–$12 |
| 30-day English-ish window | $5–$15 |
| On-demand lexical cluster (seconds of CPU) | ~$0 |
| 60 mini labels × 300 solar systems | **$5–$30** |
| Plugin store / OAuth / review | $0 cash, recurring compliance time |
| Support + abuse | the real cost if it works |
| **Lean total** | **~$20–$80 / month** |

Add conversational LLM on each custom solar system and token spend takes over, same as Horizon A.

The public site stays the unsupervised week. Custom solar systems are a **second product** with a query box, a quota, and a price. Details: [Custom Universe and Archive Architecture](project_documentation/Custom%20Universe%20and%20Archive%20Architecture.md).

---

## Horizon C — historical solar systems, trending, and topic continuity

**Job:** A visitor rewinds the observatory to last Tuesday, or asks whether a neighborhood grew, entered the top ten, or flipped its majority face. "What changed?" is a different question from "what is this week?"

**Why today's architecture is not enough.** The daily job **overwrites** `public/data.json`. Planet `id` is volume rank 1–10 *inside that file*. Live names are the top salient terms (`Housing Rent Crisis`), reminted every run. Faces get LLM titles that paraphrase. Clustering starts from scratch (lexical on CI; BERTopic is optional and also a fresh `fit_transform`). The 7-day windows overlap, then independently subsample, and member URIs never land in the snapshot. Consecutive solar systems are not a panel dataset. String-joining `"Housing"` across days will invent births and deaths.

**Postgres vs files.** A date picker that loads Tuesday's solar system is `GET /snapshots/2026-09-23.json`. Putting the same blob in Postgres and `SELECT`ing by day is the same product plus an application server. Do not buy a database to replace a folder. Keep dated output files (git branch, Pages tree, or object store). Add a matcher sidecar (`lineage.json`) so charts have a **canonical id** that names and rank ids do not provide. Postgres starts to win when a box already exists for Horizon A/B, or when you need SQL over membership — not for "load whatever day they select."

**Identity.** Independent clustering + **Hungarian matching** on terms + representative-post vectors (and URI Jaccard once Grade 1 archives exist). Record `continues | splits_into | merges_from | appears | disappears`. Seeded or incremental BERTopic can impose identity at cluster time; that changes the civic job (less unsupervised) and is a later A/B, not v1. A standing taxonomy is listening, not `/`.

**Trending.** Day-over-day share on a 168-hour rolling window is autocorrelated. Publish **stock** (this week's planet size) and, separately, **week-over-week** or **24h flow** if membership timestamps are kept. Do not label a 7-day sparkline "trending."

**Cost to maintain (steady state).**

| Layer | Lean path | If it gets popular |
| --- | --- | --- |
| Dated snapshot JSON (tens–hundreds of KB/day) | git or Pages, **$0** | object store, still ~$0 |
| Matcher on 10×10 (TF-IDF cosine) | same daily job, **$0** | — |
| MiniLM on ~120 representative posts | extra minute; **breaks the lean runner** (model download) | only if we already run BERTopic |
| Grade 1 membership (URIs, centroids) | **$0–$2 / month** (shared with Horizon B) | same |
| History API + Postgres | skip | **$5–$20 / month** when we already need a box |

History is cheap next to clerk tokens and firehose ingest. The expensive mistake is a time slider that implies continuity the matcher has not earned.

Details: [Historical Solar Systems and Topic Continuity](project_documentation/Historical%20Solar%20Systems%20and%20Topic%20Continuity.md).

---

## What we will not do on the free public solar system

- Put an OpenAI key in the static bundle.
- Generate a new universe in the visitor's browser by scraping Bluesky (CORS, ToS, quota).
- Pretend extractive overlap is a mind.
- Let a custom-brand solar system replace the unsupervised home page.
- Retain an unbounded firehose "just in case." Lifecycle or do not ingest.
- Key a time series on planet names, face titles, or rank `id`. Those churn by design.
- Stand up Postgres only to serve dated `data.json` files a static host can already fetch.
- Call a 7-day overlapping share "trending" without a flow or week-over-week measure.

## Suggested sequence

1. Use the public solar system: tilt, open a planet, see whether you are the gold face. If the discomfort lands, thicken the snapshot (more posts, terms, briefing cards).
2. Run **`--query`** locally for a few brands. If those solar systems are readable, that is the premium prototype — still $0.
3. **Stop overwriting yesterday's solar system** (Horizon C, step 1): dated JSON + manifest. A date picker can follow with no database. Match names later, not first.
4. Only then add a clerk API (Horizon A) or a retained index (Horizon B). Buy the first billable thing when a human is hitting a wall the snapshot cannot answer, not before. Grade 1 membership, when it lands, also makes topic matching honest.
