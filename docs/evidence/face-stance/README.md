# Face stance, step 0 (no product change)

Hand labels for issues #116, #117, and #103. The reference is `stance_reference.json` in this folder. The `stance` field is the adjudicated final. Nothing here changes the pipeline, the site, or `data.json`. The build that reads this file is pull request #129.

Michael on 2026-10-10, 11:16 AM CT: one face is acceptable only when that is actually the case. He suspects real second perspectives are being missed, and he does not want one face as the easy, low-error default. This note measures that, and proposes a done bar. It does not adopt the bar.

## Who labeled

| Role | Model | What it saw |
|---|---|---|
| Original labels | grok-4.7 high | The post text. No paid labeling API. |
| Blind second labeler | deepseek-ai/DeepSeek-V4-Flash | The stance question, what supports and opposes mean, and the post text. Not the grok label. |
| Adjudicator | grok-4.7 high | The 64 posts where those two disagreed, re-read in full. |

227 posts. Agreement 163/227 = 0.718. Cohen's kappa 0.427, computed on grok versus DeepSeek before any adjudication. 64 disagreements were adjudicated. 17 labels changed. The other 47 kept the grok label. Each adjudicated post in the JSON has `grok`, `deepseek`, `final`, and `adjudication_reason`.

The adjudicator is the same model family as the original labeler. It is not a third family. Michael can spot-check the 17 changes and the 47 kept labels.

The blind pass is part of the paid measurement on pull request #129 (DeepInfra, shared spend under $0.25, nothing published). The original 227 labels were not a paid call.

## Where the posts came from

Live planets are the global top 10 in `public/data.json` on `data-snapshot` commit `acd7872` (2026-10-10 13:09 UTC, `last_updated` 2026-10-10, 9,874 posts). That file is what Daily Discourse Pipeline run [38052773565](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38052773565) published.

Post text and face membership are the `perspectives` table in that run's `data-json` artifact, joined to `posts`. Published face sizes match that table exactly (Diesel Deal 73/68/56/53, Gaza 167, and so on).

Run [37942713535](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37942713535), the #104 corpus, is a different day (`last_updated` 2026-10-09). Its top 10 does not contain Trump Putin Diesel Deal, Rise of Fascism, or ICE Abuse, so these labels do not use it.

The sample draws evenly across each face by distance to that face, including both ends. A planet under 40 posts is labeled in full. 227 posts.

`supports` and `opposes` are the two answers to that planet's question. `other-angle` is about the subject and is not a yes or no. Those posts do not share one claim, so they are not counted as a second stance. `off-topic` is a different subject.

A second coherent stance is the largest pole that is not the sample's plurality. If the plurality is `other-angle`, the largest pole itself is the second stance. The line used below is **at least 10% of the hand sample**.

## What the current split does

Counts below are the adjudicated finals. The pipeline face counts are unchanged: this table is the reference, not the fix.

| Planet | Posts | Faces now | Sample | Majority of each face | Faces on that same majority | Purity (sample) | Second coherent stance |
|---|---:|---:|---:|---|---:|---|---|
| Trump Putin Diesel Deal | 250 | 4 | 40 | supports on all four | 4 | 60%, 100%, 60%, 80% | 1/40 opposes, under 2 posts |
| Gaza Genocide | 167 | 1 | 40 | supports | 1 | 55% (22/40) | 4/40 = 10% opposes |
| Livestreamed Execution Plan | 83 | 2 | 40 | supports on both | 2 | 62.5% (15/24), 87.5% (14/16) | 2/40 = 5% opposes |
| Rise of Fascism | 40 | 2 | 40 (all) | supports on both | 2 | 100%, 100% | 0/40 |
| ICE Abuse | 14 | 1 | 14 (all) | supports | 1 | 64% (9/14) | 1/14 = 7% opposes |
| MAGA Fails | 19 | 1 | 19 (all) | supports | 1 | 100% | 0/19 |
| Labour Party | 34 | 1 | 34 (all) | plurality is other-angle, 53% (18/34) | 1 | 53%, and it is not one claim | 11/34 = 32% say Labour has lost them; 4/34 = 12% say stick with Labour |

ICE Abuse is the global top-10 planet for the "Abolish ICE" ask. The posts are about agent misconduct, not a large abolish-versus-enforce argument. The section planet ICE Enforcement Surge (25 posts) is not in this global set.

### Same-stance faces (#116, #117, #103)

Diesel Deal's four faces are one stance. 30 of the 40 sample posts condemn the deal or side with Ukraine. One post calls Ukraine's backers traitors (the only `opposes`). Nine are war headlines, analogies, or a price-cause aside, not a defense of the deal. A one-line skim of the other 210 posts, not adjudicated, found 3 that do take the other side ("NATO's war," "oil matters more than Ukraine," "Russia is defending herself"). That is about 1% of the planet. The four faces are wording (helps Russia, Trump-Putin ties, the invasion, the diesel contract), not four perspectives.

Rise of Fascism is the same finding on the whole planet. All 40 posts treat fascism as real and bad. Face 4A is mostly the US. Face 4B is mostly global. That is geography, not a second stance.

Livestreamed Execution Plan is the same pattern on a planet nobody filed. Both faces say the livestream is wrong. Two posts in the sample take the other side (2/40 = 5%), including one that says citizens should hang mass murderers. One more, outside the sample and not adjudicated, prefers to see the shooter executed. Still under a 10% second stance.

#103 was identical titles on US Iran War, which is not in today's top 10. The failure mode that is in today's top 10 is the near-duplicate: different titles, one majority stance. Distinctness does not catch it (Diesel Deal 0.174, Fascism 0.146, both already under a cosine gap of 0.90).

### Missed second stance on one-face planets

Four global top-10 planets have one face. On **2 of 4**, the adjudicated sample has a second coherent stance at or above 10% and at least 2 posts.

- **Gaza Genocide.** 22/40 say Israel is committing genocide or the equivalent. 4/40 reject that charge, including an explicit "crimes are not the same as genocide." 14/40 are other-angle (West Bank, elections, a request that the UK help, whatabouts) and are not a second stance. The opposing pole is the line, at 4/40 = 10%. A one-line skim of all 167, then a full read of the pushbacks, found 7 more explicit opposing posts outside the sample. Those 7 plus the sample's 4 are 11/167, about 6.6%. That skim was not adjudicated. DeepSeek's labels on all 167 posts put opposes at 15/167 = 9.0%, still under 10%. The distance sample can sit on the 10% line while the planet sits under it.
- **Labour Party.** There is no majority stance. 11/34 say Labour has lost its voters. 4/34 say stick with Labour, defend a Labour candidate, or say the media is unfair to Labour. 18/34 are Greens, Tories, Lib Dems, or other parties. One is off-topic. One face hides two Labour stances and a pile of other parties. Because the plurality is other-angle, the second stance is the larger pole: supports, 11/34 = 32%. The stick-with-Labour pole is 4/34 = 12%, also at or above 10%.
- **ICE Abuse.** One opposing post (the detention force was proper). Two posts that the original labels called supports were recoded as other-angle (no news of an attack; an off-duty incompetence joke). 1/14 = 7%, and one post cannot be a face. One face matches this planet.
- **MAGA Fails.** 19/19 oppose MAGA. DeepSeek agreed on all 19. One face matches this planet. This is the case Michael said is allowed.

So the suspicion holds on some one-face planets and not others. One face is sometimes the truth (MAGA Fails, and Fascism once the duplicate face is merged). It is the wrong default on Gaza and Labour.

## Proposed done bar

Not a decision, and not built.

A planet may show one face only when a checked sample finds no second coherent stance at or above 10% of that sample. The check is this kind of hand label, or one model call on a fixed spread of about 40 posts (the whole planet when it is smaller). Faces that share a majority stance merge, including when the titles differ. `other-angle` does not count as a stance unless those posts actually share a claim. Off-topic does not count.

Gaza is the awkward case for the denominator. The sample is at 10% and the planet skim is at about 6.6%. A build should say which one it uses. This proposal uses the checked sample, because that is what a daily model call can see, and it should keep a second face when the sample is at the line. It should not invent a second face from a single post (ICE).

## Two ways to split by stance, not built

Both keep the extra calls on the number of planets. The catalog is the top 10 globally and per section (110 published planets on the 2026-10-10 run). They do not label every post.

DeepInfra prices below are the rates that reproduce the cost ledger exactly: **$0.10 per million input tokens and $0.32 per million output tokens**. Jev stays **$0.042 per million input tokens**, output free (`pipeline/costs.py`, dated 2026-10-08). A stance prompt of about 40 posts is about 2,200 input tokens and 400 output tokens at the length of this sample (mean post about 180 characters).

### A. One sample call per planet, then merge

One DeepInfra call sees the fixed spread and returns the question plus a stance for each shown post. Faces with the same majority stance merge. A second face is kept only when the other pole is at least 10% of that sample. Posts outside the sample stay with their current face when that face survives. They are not re-clustered with MiniLM. MiniLM is what split these planets by wording. The research note in `docs/research/perspective-grouping.md` already found that assigning posts to model-written positions in MiniLM space made the gap worse, not better.

Cost at 110 planets: 110 × (2,200 × $0.10 + 400 × $0.32) / 1,000,000 = **$0.038 per day**. At 300 planets, the upper count used in the #87 projection, **$0.10 per day**.

### B. A short same-stance check, plus a sample call only if the planet would otherwise have one face

One short call per planet sees the face titles and summaries the labeler already wrote and says whether they are the same side. That merges Diesel Deal and Fascism. It cannot see a minority buried inside one face, which is the Gaza and Labour failure. So a planet that would publish a single face pays the longer sample call from A, and keeps a second face only when that sample clears 10%.

On today's global top 10, 4 of 10 planets have one face. At that rate, about 44 of 110 planets pay the long call. Short call about 350 input and 80 output tokens. Long calls 44 × $0.000348, short calls 110 × $0.000061, together **$0.022 per day**. This is the smaller bill that still refuses one face as the default.

A is simpler. B is cheaper and spends the careful call where Michael's suspicion applies. Either is a labeler call, not a Jev call. Using Jev for the same 2,200-token prompt would be about $0.01 per day at 110 planets, and it would need a quality bar before it replaced the labeler. That test was not run.

## Daily cost at 100K posts

The 2026-10-10 scheduled run, 9,874 posts, 110 planets:

| Service | Calls | Cost |
|---|---:|---:|
| Jev | 7,232 | $0.201 |
| DeepInfra labeling | 1,205 | $0.106 |
| R2 | 3 | $0.00 |
| **Total** | | **$0.307** |

The cap is under **$0.50 per day** at a 100,000-post window. Stance labeling does not grow with the post count. The rest of Jev does, if it stays one call per newly scored post.

Worked bound, not a measured 100K bill. A 7-day window of 100K posts, with the 14-day verdict cache already warm, scores about 100,000 / 7 ≈ 14,300 new posts a day. Today's Jev calls average 663 input tokens. 14,300 × 663 × $0.042 / 1,000,000 = **$0.40 of Jev**. Hold DeepInfra labeling at today's $0.106, because the published planet count stays at the catalog cap. R2 was $0 on this day and is not re-priced here.

| | Jev | Other labeling | Stance add-on | Day |
|---|---:|---:|---:|---:|
| Approach A, 110 planets | $0.40 | $0.106 | $0.038 | **$0.54** |
| Approach B, 110 planets | $0.40 | $0.106 | $0.022 | **$0.53** |
| Approach A, 300 planets | $0.40 | $0.106 | $0.10 | **$0.61** |

The add-on itself is inside the cap. The day goes over $0.50 because per-post Jev on a 100K window is already about $0.40 before any stance call. A stance design that labeled every post would make that worse. These two do not.

Today's Jev ratio (7,232 calls on a 9,874-post file) is a cache-filling day, not the steady state used above. Scaling that ratio by ten would be about $2 of Jev and is the wrong comparison once the cache is warm.

## UI evidence for #129

`screenshots/` is the reader view of the three planet states on this branch. Desktop is 1280×800. Mobile is 390×844. No new labeling call was made.

| File | What it shows |
|---|---|
| `gaza-two-face-desktop.png`, `gaza-two-face-mobile.png` | Gaza War, two faces (Israel War Crimes, Zionism Condemned). No opposing-view note. This is the layout a split publishes. |
| `one-face-opposing-note-desktop.png`, `one-face-opposing-note-mobile.png` | US Election Vote, one face, with `No clear opposing view found in this sample`. |
| `stance-check-failed-desktop.png`, `stance-check-failed-mobile.png` | Pension Triple Lock, one face. The data field is `stance check failed`. The reader line is `Perspectives still being analyzed`, not the opposing-view note. This planet was patched for the screenshot; it was not a pipeline failure. |
