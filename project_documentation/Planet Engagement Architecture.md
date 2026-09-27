# Planet Engagement Architecture

How a visitor talks to a planet or a face — and what has to change if those answers should come from a model that has actually read the people.

The public observatory today is three cheap moves:

1. **Lightweight storage.** A JSON snapshot. The sample that produced it lives in an ephemeral SQLite file on the machine that ran the job.
2. **Once-per-day computation.** Ingest, clean, cluster 10 topics, cut 2–6 faces, label, write `data.json`.
3. **Cheap rendering.** GitHub Pages fetches that file. The GPU in the visitor's machine draws the sky. There is no application server.

That design is why the bill is ~$0. It is also why "chat with the planet" is not a feature you bolt onto `App.jsx`.

## The job

A self-confident visitor believes they already know the argument. They open a planet (or a face) and want to:

- ask a follow-up ("why are they thinking that?")
- debate ("that is overblown; here is my take")
- hear the other side in **their words**, not in a moderator's paraphrase
- notice, sometimes, that their opinion is the minority spike — or is not on the cube at all

The marketing name writes itself: **the anti-echo chamber**. The feed told them they were the sun. The geometry, and then the quotes, may not.

This is a different job from face *labeling*. Labeling runs 60 times a day on representative posts and produces a title and a sentence. Engagement is open-ended, interactive, and scoped to one planet or one face. It has to stay grounded or it becomes a horoscope.

## What the snapshot actually contains

After a live run:

| Object | Survives in `data.json` | Dies with the runner |
| --- | --- | --- |
| Topic name, category, volume | yes | |
| Face title, summary, volume | yes | |
| Up to 12 representative posts / face (`author`, `clean_text`, `likes`) | yes | |
| The other members of that face | | yes (SQLite `perspectives`) |
| Posts in Topic -1 | counted in `total_posts` only | yes |
| Raw Bluesky payloads, URIs in the UI | no | never stored in the snapshot |
| Embeddings | no | computed in memory, discarded |

A visitor who "talks to the planet" on the static site can only hear the **representatives**. On the demo sky that is 3 posts × 2–6 faces. On a full live cap that is 12 × 2–6. That is enough to *feel* a conversation. It is not the cluster.

## Two architectures

### Path 0 — extractive clerk (ships on the static site)

No new process. The browser already has the snapshot.

```
visitor types a claim or a question
        ↓
tokenize (same [a-z]{3,} + stopwords as pipeline/cluster_math.py)
        ↓
score representative posts by coverage + Jaccard
        ↓
verdict: majority | minority | split | absent
        ↓
quotes from the matching face, and from the loud face they are not on
        ↓
follow-up chips that re-ask or open another face
```

This is what **Test your take** does. It is not an LLM. It cannot invent a reason a post did not write. It can put the visitor's words next to the week's words and say which spike they landed on.

**Why this is good enough to ship.** The value of the anti-echo chamber is the *verdict*, not the prose. "You are 17% of this planet; gold is 28% and does not overlap you" is a gravitational fact. A model that restates it in friendlier English adds tone, not information — and costs money.

**Why this will eventually feel thin.** No memory across days. No posts below the representative cap. No paraphrase when the quotes are messy. No real debate (the user cannot get a counter-argument that was never typed into a representative post).

**Cost to maintain:** $0. It is JavaScript on a static host.

### Path 1 — retrieval clerk with a small model (Horizon A)

This is the first design that deserves the word LLM. It still must not become "the planet has a personality."

```
                    daily job (unchanged render)
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
      data.json      briefing.json     face_quotes.json
      (sky)          (60 cards)        (members + reps)
                           │
                           ▼
                    GET /chat  { scope, history, question }
                           │
                    retrieve k quotes in scope
                           │
                    prompt: answer only from quotes;
                            if missing, say so;
                            cite authors
                           ▼
                    JSON { answer, citations, followups }
```

**What changes.**

| Layer | Today | Path 1 |
| --- | --- | --- |
| Storage | snapshot only | snapshot + per-face quote pack (still small) |
| Compute | once / day | once / day **plus** per-turn inference |
| Render | static | static sky + one authenticated POST |
| Secrets | none in the browser | stay on the clerk |

The application server is a **clerk**, not a second pipeline. It does not re-cluster. It does not see the firehose. It reads the briefing written this morning.

**Prompt contract (normative).**

- Scope is mandatory: one `topic_id` or one `perspective_id`.
- The model receives the face title, the one-sentence summary, the volume percents, and *k* retrieved posts (k ≈ 8–16).
- It may quote. It may contrast two faces. It may say the quotes do not contain the answer.
- It may not claim a poll, a fact-check, or a view that does not appear in the quotes.
- "Why do they think that?" is answered with causal language **from the posts** (`because`, stakes, constraints), not with a theory of the posters.

**Retrieval.** Start with the same lexical overlap as Path 0. Upgrade to MiniLM embeddings *of the quote pack only* if lexical misses paraphrases. Do not embed the firehose for this feature.

**Where the model runs.**

| Option | Quality | Cost | Fits the ethos |
| --- | --- | --- | --- |
| Visitor's Ollama on localhost | depends on their box | $0 | yes — already how we label |
| Hosted mini (GPT-4o-mini class) | consistent | $0.005–$0.05 / turn | yes if gated |
| Hosted large | better debate | 5–20× mini | no, not for v1 |
| In-browser WebLLM | offline, huge download | $0 bandwidth aside | only as an experiment |

**Cost to maintain.** The clerk box is $5–$20 / month if you need one. Tokens are the variable. A public, ungated chat box on a civic URL will be scraped. Cap turns, or require a key, before launch. 10k conversations × 4 turns × $0.02 is $800 / month — three orders of magnitude above today's bill.

**What we refuse to do.** Fine-tune a "planet persona." A persona lies when the cluster is split. Retrieval plus a dry clerk is the product.

## Does the daily / static split survive?

Yes, if you keep the split sacred:

- **Batch** still owns truth: what the planets are, how big, which posts belong.
- **Interactive** only *reads* that truth.
- The 3D scene still fetches one JSON file. Chat is a side channel, not a second sky.

The split dies if chat is allowed to invent faces, re-rank volumes, or pull live posts the snapshot never saw. At that point you have built a listening tool and should call it one.

## Product rules for the anti-echo chamber

These belong in the UI, not in a slide.

1. **Lead with placement, then with quotes.** Majority / minority / split / absent first. Prose second.
2. **Absent is a success state.** "Your thing is not a planet this week" is the sentence query-shaped software cannot say.
3. **Gold is not right.** The loud face is the loud face. Copy already in the sidebar must stay next to the model's answer.
4. **One scope at a time.** Whole sky, one planet, or one face. A model that answers from the whole snapshot will smooth the geometry away.
5. **Show the cap.** "Answered from 12 representative posts on this face" prevents the god's-eye reading the metaphor invites.

## Implementation map

| Path | Code | Notes |
| --- | --- | --- |
| Path 0 | `src/lib/tokenize.js`, `src/lib/engagement.js`, `src/components/EngagementPanel.jsx` | Ships now |
| Quote pack | future field on each perspective, or a sibling `briefing.json` | Optional fields do not break `schema.py` |
| Clerk | not in repo | Add only with a host, a cap, and a prompt test suite |

## What "intelligent enough" means here

Intelligent enough is **not** "wins a debate." It is:

- stays inside the scoped posts
- can follow a thread of questions without changing planet
- will say "they did not write that"
- will hand you the gold face when you asked about a moon

A small model with retrieval does that. A large model without retrieval does not.

See [ROADMAP.md](../ROADMAP.md) for sequence and the cost table.
