# Natural groups, then the top ten

How a week of posts becomes planets without a formula that decides the count in advance. This note is the spec for issue #85 and for the clustering change on issue #32. The corpus is the `data-json` artifact from Daily Discourse Pipeline run [37789244791](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37789244791): 10,000 claims.

## What “natural” means

A topic is a crowd of posts that sit near one center in the embedding, and sit farther from every other crowd. Readers already know that shape. A conversation has a middle. Remarks that are not near any middle are not a topic.

The old production path did not look for that shape. It chose the number of cells first: `k = n / floor`, with the floor itself raised as `max(8, n // 200)`. At 10,000 claims that is a floor of 50 and about 200 cells. The week was sliced into that many cells, nearby cells were merged, and anything under the floor was thrown away. On this corpus that left **12 candidate planets and 85.8% of posts as noise** (8,584 posts). The count came from the formula.

Lowering the floor, and only that, still lets the formula pick the count. `k = n / 8` asks for 1,250 cells. What we measured is that the count of *surviving* balls does not follow that number. At floor 8, a grid of 800 seeds leaves 252 groups, 1,250 seeds leaves 269, and 1,600 seeds leaves 261, all with about 44–48% of posts inside a group. A grid of 200 seeds, which is the old formula’s neighborhood, leaves only 63. The grid has to be fine enough that two crowds are not glued together first. Past that, adding seeds does not mint new topics. The topics are the balls that stay dense.

## Why this is not a chain of nearest neighbors

HDBSCAN’s distance is mutual reachability, then single linkage: join the closest pair, then the next, and call a jump a boundary. That is the right picture when a crowd is much tighter than the space around it. It is the wrong picture in this MiniLM space.

On this 10K week the nearest neighbor of a post is at cosine distance about 0.46 (median). The fifth neighbor is about 0.53. Those distances look almost the same inside a topic and between topics. Cut the nearest-neighbor graph at distance 0.40 and almost nobody connects (43 groups, 12% of posts). Cut it at 0.50 and the graph percolates: one chain of 6,088 posts and four specks. There is no threshold that is both tight enough to keep topics apart and wide enough to hold a topic together, because a topic here is not a chain. It is a ball. Posts can all sit near a center even when each post’s nearest neighbor is only moderately close, and a chain of moderately close neighbors can wander across the whole week without any center.

So production grouping grows balls, not chains:

1. Lay down a fine grid of seeds, about one per `min_cluster_size` posts, and assign every post to a seed. This step exists so two neighboring crowds are not forced into one cell. The seed count is not published and is not the topic count.
2. Peel any post farther than cosine 0.50 from its cell’s center.
3. Merge cells whose centers are at cosine 0.72 or above. Those are one subject the grid split apart.
4. Drop a ball whose posts are not near the center on average (mean cosine below 0.60). That is a mood, not a subject.
5. Drop a ball smaller than `min_cluster_size`. Those posts stay noise. Isolated posts never become a planet.

`min_cluster_size` is 5. On this corpus, 5 puts 58% of posts into a ball and leaves 533 balls. A floor of 8 leaves the familiar ~264 balls and 47.5% of posts, just under half. Five is the smaller floor that still clears half the week, and the published top ten are the same large balls either way. The floor is not raised with the claim count.

## What the site shows

Every ball is ranked by the reach measure already in the pipeline: distinct authors, then size. The global solar system publishes the top 10. Each newspaper section publishes its own top 10. Drafting walks that ranking until 10 planets survive. A candidate that is dropped or split still pays for its draft, and the next candidate is drafted. Candidates after the catalog fills are not labeled.

A planet is still split into faces in its own space, trying 2 through 6. When that split finds real, separated views, they are published. When it does not, the planet is one perspective and carries `opposing_note`: “No clear opposing view found in this sample.” A second face is not invented to pad the count. A face that does not share a claim, judged on a spread of up to 40 posts rather than the five closest to the centroid, is not published. One remaining real face is kept. The decision to allow a single clear perspective is a product call from 2026-10-08. It is implemented here. Its log entry already sits in `.factory/DECISIONS.md` (one clear perspective, #85). This change adds only the clustering-method entry.

`section_grouping: cluster_once` lists planets from this one density pass. The default listing is the section with the most of a planet's posts, and both sections when the top two are each at least 35%. The planet is labeled once and that label is reused in All topics and in every section that lists it. A section that still has fewer than 10 planets is clustered on its own to fill the rest. `per_section` remains available and is what main did before this change. One Jev section call per planet is implemented (`section_assignment: jev`) and is not the default: on this October corpus it matched the post majority on 78 of 107 planets (72.9%), and Culture on 4 of 11 (36.4%). The planet-level question tells Jev that arts, entertainment, media, and celebrity commentary are Culture, not Other. The paid before/after is in the #90 PR.

Non-English posts and posts that are only a link are dropped before clustering, with a local word and script check. No model call.

## Scale

At 10,000 posts the grid is fit on every post. That clustering step took **10.1 seconds** for the whole week and **2.8 seconds** for Politics (5,148 posts). All ten sections together are a few more seconds. That is comfortable inside CI.

At 100,000 posts an assignment of every post to `n / 5` centers would be an n×k matrix of about 10 GB, and it would do work the topic count does not need. Above 12,000 posts, centers are fit on a sample of 12,000 (the same ball rules), then every other post joins a center only when it sits inside that ball (cosine at least 0.50). A post outside the sample does not create a new group. A synthetic 100K run in 384 dimensions — 30 tight crowds of 400 posts plus 88,000 noise posts — finished in **18.9 seconds**, found **30 groups**, and left the noise unlabeled (12,000 posts in a group, the crowds only). The #32 bar is a finish within 10 minutes and at least 20 candidates. This is a synthetic corpus, not a second week of Bluesky, so it checks the path and the timing, not the topic count of a real 100K window.

## Labeling cost

Labeling walks ranked candidates until `catalog_size` (10) planets survive, for the global system and for each section. Only the wide relabel is limited to planets that made the catalog. On this 10,000-claim artifact the heuristic labeler, walked the same way as the daily job, published 100 section planets (178 faces) and 10 global planets (14 faces). Six of the global ten are a single view.

Face-draft calls were 361 in the sections and 389 including the global list. Ranked candidates drafted were 133 in the sections and 144 including global. Counting the extra `_draft_planet` call inside a story split, those are 150 and 161. Wide relabels, one per published face, are 178 and 192. Names recorded on that walk were 102 and 112. Briefs, one for each published planet and each published face, add 278 and 302. The sum is 919 paid calls for the sections and 995 including global. About 796 is only the floor from one draft per published face (`3 × 192 + 2 × 110`). It leaves out candidates that were drafted and then dropped or split.

Issue #86 measured about 1,025–1,080 DeepInfra calls. This walk is about 995, in that same band. It does not spend a second pass to invent a second view. A paid labeler can drop different candidates, so a real run can draft further than this count. The section budget stays 20 minutes (1,200 seconds). Parallel relabel from #95 is in this branch (pool 12). With that pool the section phase projects to about 767–893 seconds. A 1.5× case is about 1,257 seconds, or about 1,346 if the face-draft calls also grow 1.5×.

The census uses the heuristic labeler, so it does not measure a paid run. Published “Mixed remarks” faces in that heuristic pass are **zero** in every section, because a face that does not share a claim is dropped instead of published. A paid labeler can still say the words; the same drop applies, so the published rate should stay at the floor rather than the old 46% of faces (101 of 220).

## Measurement

Harness: `python -m pipeline.eval.grouping_eval --census-only --min-cluster-size 5`. It embeds with the same MiniLM the daily job uses (cached for the cluster timings below), clusters with `density_labels`, and heuristic-labels only the published top 10 of each solar system.

Before, on this same 10K artifact, the old production floor (`max(8, n // 200)` = 50, `k` = 200): **12 global candidates, 8,584 noise posts (85.8%)**. Those figures are from the comment on issue #32.

After, floor 5, dense balls. “Seconds” is the cluster step only.

| Slice | Posts | Candidates | Posts in a group | Share | Seconds |
|---|---:|---:|---:|---:|---:|
| All topics | 10000 | 533 | 5842 | 58.4% | 10.1 |
| Politics | 5148 | 312 | 3122 | 60.6% | 2.8 |
| World | 1279 | 49 | 836 | 65.4% | 0.2 |
| Business | 653 | 40 | 338 | 51.8% | 0.1 |
| Other | 639 | 41 | 340 | 53.2% | 0.1 |
| Technology | 629 | 30 | 390 | 62.0% | 0.1 |
| Culture | 548 | 29 | 242 | 44.2% | 0.1 |
| Health | 300 | 19 | 193 | 64.3% | 0.0 |
| Environment | 297 | 23 | 193 | 65.0% | 0.0 |
| Sports | 270 | 20 | 168 | 62.2% | 0.0 |
| Education | 237 | 17 | 159 | 67.1% | 0.0 |

Sections with at least 1,000 claims are Politics and World. Both clear the #32 bar of 15 candidates (312 and 49). The global bar of 30 candidates is 533. The bar of at least half the posts in a group is 58.4% globally, and it holds in both large sections. The largest global balls are 274, 184, 167, and 103 posts, not one chain of thousands.

At floor 8 the same week is 264 global candidates, 4,755 posts in a group (47.5%), in 6.5 seconds. That is the ~268-group figure from the #32 comment. Floor 5 is what ships because it clears half the posts.

Published top 10, heuristic labels (not a paid model). Mixed-remarks columns are titles that still say “Mixed remarks” after the wide-sample check. Those faces are dropped, so the counts are zero.

| Solar system | Published | One view | Two or more | Mixed-remarks faces | All-mixed planets | Mixed-remarks names |
|---|---:|---:|---:|---:|---:|---:|
| All topics | 10 | 6 | 4 | 0 | 0 | 0 |
| Politics | 10 | 3 | 7 | 0 | 0 | 0 |
| World | 10 | 4 | 6 | 0 | 0 | 0 |
| Business | 10 | 2 | 8 | 0 | 0 | 0 |
| Other | 10 | 5 | 5 | 0 | 0 | 0 |
| Technology | 10 | 4 | 6 | 0 | 0 | 0 |
| Culture | 10 | 3 | 7 | 0 | 0 | 0 |
| Health | 10 | 3 | 7 | 0 | 0 | 0 |
| Environment | 10 | 3 | 7 | 0 | 0 | 0 |
| Sports | 10 | 3 | 7 | 0 | 0 | 0 |
| Education | 10 | 4 | 6 | 0 | 0 | 0 |

Every section published at least 6 planets. The #85 bar of 6 applies to sections with at least 1,000 claims; Politics and World are those sections, and the smaller sections cleared it too on this week.

### Sources

- The cohesion lines (member cosine 0.50, merge 0.72, mean cosine 0.60) are the ones already used to reject a loose cell. They are now the definition of a ball, not a cleanup after `k = n / floor`.
- Ricardo J. G. B. Campello, Davoud Moulavi, and Jörg Sander, “Density-Based Clustering Based on Hierarchical Density Estimates,” PAKDD 2013. https://doi.org/10.1007/978-3-642-37456-2_14 — mutual reachability and single linkage. Measured here and not used for production planets, because this embedding percolates.
- The face-split comparison that still uses a quantile of that tree, inside one planet, is `docs/research/perspective-grouping.md`.
