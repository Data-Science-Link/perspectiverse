# Face stance, step 0 (no product change)

Hand labels for issues #116, #117, and #103. The reference is `stance_reference.json` in this folder. Nothing here changes the pipeline, the site, or `data.json`.

Michael on 2026-10-10, 11:16 AM CT: one face is acceptable only when that is actually the case. He suspects real second perspectives are being missed, and he does not want one face as the easy, low-error default. This note measures that, and proposes a done bar. It does not adopt the bar.

## Where the posts came from

Live planets are the global top 10 in `public/data.json` on `data-snapshot` commit `acd7872` (2026-10-10 13:09 UTC, `last_updated` 2026-10-10, 9,874 posts). That file is what Daily Discourse Pipeline run [38052773565](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38052773565) published.

Post text and face membership are the `perspectives` table in that run's `data-json` artifact, joined to `posts`. Published face sizes match that table exactly (Diesel Deal 73/68/56/53, Gaza 167, and so on).

Run [37942713535](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37942713535), the #104 corpus, is a different day (`last_updated` 2026-10-09). Its top 10 does not contain Trump Putin Diesel Deal, Rise of Fascism, or ICE Abuse, so these labels do not use it.

The sample draws evenly across each face by distance to that face, including both ends. A planet under 40 posts is labeled in full. 227 posts, read and labeled by hand. No paid API.

`supports` and `opposes` are the two answers to that planet's question. `other-angle` is about the subject and is not a yes or no. Those posts do not share one claim, so they are not counted as a second stance. `off-topic` is a different subject.

A second coherent stance is the largest pole that is not the sample's plurality. If the plurality is `other-angle`, the largest pole itself is the second stance. The line used below is **at least 10% of the hand sample**.

## What the current split does

| Planet | Posts | Faces now | Sample | Majority of each face | Faces on that same majority | Purity (sample) | Second coherent stance |
|---|---:|---:|---:|---|---:|---|---|
| Trump Putin Diesel Deal | 250 | 4 | 40 | supports on all four | 4 | 70%, 100%, 60%, 90% | 0/40 |
| Gaza Genocide | 167 | 1 | 40 | supports | 1 | 72.5% (29/40) | 4/40 = 10% opposes |
| Livestreamed Execution Plan | 83 | 2 | 40 | supports on both | 2 | 58% (14/24), 81% (13/16) | 1/40 = 2.5% |
| Rise of Fascism | 40 | 2 | 40 (all) | supports on both | 2 | 100%, 100% | 0/40 |
| ICE Abuse | 14 | 1 | 14 (all) | supports | 1 | 79% (11/14) | 1/14 = 7% |
| MAGA Fails | 19 | 1 | 19 (all) | supports | 1 | 100% | 0/19 |
| Labour Party | 34 | 1 | 34 (all) | plurality is other-angle, 56% (19/34) | 1 | 56%, and it is not one claim | 10/34 = 29% say Labour has lost them; 4/34 = 12% say stick with Labour |

ICE Abuse is the global top-10 planet for the "Abolish ICE" ask. The posts are about agent misconduct, not a large abolish-versus-enforce argument. The section planet ICE Enforcement Surge (25 posts) is not in this global set.

### Same-stance faces (#116, #117, #103)

Diesel Deal's four faces are one stance. All 32 posts that take a side condemn the deal or side with Ukraine. The other 8 are war headlines, analogies, or a price-cause aside, not a defense of the deal. A one-line skim of the other 210 posts found 3 that do take the other side ("NATO's war," "oil matters more than Ukraine," "Russia is defending herself"). That is about 1% of the planet. The four faces are wording (helps Russia, Trump-Putin ties, the invasion, the diesel contract), not four perspectives.

Rise of Fascism is the same finding on the whole planet. All 40 posts treat fascism as real and bad. Face 4A is mostly the US. Face 4B is mostly global. That is geography, not a second stance.

Livestreamed Execution Plan is the same pattern on a planet nobody filed. Both faces say the livestream is wrong. One post in the sample says it is not a big deal. One more, outside the sample, prefers to see the shooter executed. Still one stance.

#103 was identical titles on US Iran War, which is not in today's top 10. The failure mode that is in today's top 10 is the near-duplicate: different titles, one majority stance. Distinctness does not catch it (Diesel Deal 0.174, Fascism 0.146, both already under a cosine gap of 0.90).

### Missed second stance on one-face planets

Four global top-10 planets have one face. On **2 of 4**, the hand sample has a second coherent stance at or above 10%.

- **Gaza Genocide.** 29/40 say Israel is committing genocide or the equivalent. 4/40 reject that or treat the war as the consequence of Oct 7 or Palestinian choices, including an explicit "specious genocide accusation" and "crimes are not the same as genocide." That is the line, at 10%. A one-line skim of all 167, then a full read of the pushbacks, found 7 more explicit opposing posts outside the sample. Those 7 plus the sample's 4 are 11/167, about 6.6%. The distance sample over-weights the far tail, so it can sit on the 10% line while the planet sits under it. If the softest of the four ("was Oct 7 worth it?") is recoded as other-angle, the sample falls to 3/40 = 7.5% and Gaza drops off the missed list. The explicit denials are still real.
- **Labour Party.** There is no majority stance. 10/34 say Labour has lost its voters. 4/34 say stick with Labour, defend a Labour candidate, or say Labour is taking it seriously. 19/34 are Greens, Tories, Lib Dems, or Australian parties. One face hides two Labour stances and a pile of other parties. Both Labour poles are at or above 10%.
- **ICE Abuse.** One opposing post (the detention force was proper). 1/14 = 7%, under the line. One face matches this planet.
- **MAGA Fails.** 19/19 oppose MAGA. One face matches this planet. This is the case Michael said is allowed.

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
