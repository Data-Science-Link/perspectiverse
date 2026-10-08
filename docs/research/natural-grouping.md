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

Every ball is ranked by the reach measure already in the pipeline: distinct authors, then size. The global solar system publishes the top 10. Each newspaper section publishes its own top 10. Balls below that line are not labeled. Finding hundreds of candidates does not spend hundreds of model calls.

A planet is still split into faces in its own space, trying 2 through 6. When that split finds real, separated views, they are published. When it does not, the planet is one perspective and carries `opposing_note`: “No clear opposing view found in this sample.” A second face is not invented to pad the count. A face that does not share a claim, judged on a spread of up to 40 posts rather than the five closest to the centroid, is not published. One remaining real face is kept. The decision to allow a single clear perspective is a product call from 2026-10-08. It is implemented here. Its log entry already sits in `.factory/DECISIONS.md` (one clear perspective, #85). This change logs the clustering method and the section-listing default.

Sections do not each get their own clustering. `section_grouping: cluster_once` (the default) uses the one density pass above. A planet is listed in the section that holds the most of its posts. When the top two sections are each at least 35% of the planet, it is listed in both. The same labels are reused in the global list and in every section list. A section that publishes fewer than 10 planets is clustered on its own, and those extra planets fill the empty slots. `section_grouping: per_section` is the old path: cluster each Jev section again, with the same floor of 5, and label those planets separately.

The #90 plan, a later Jev call that picks the section from the planet’s summary, is still waiting on its shadow test. This comparison uses the sections Jev already wrote on the posts. It does not spend a new Jev call.

## One clustering or ten

Both options were run on this same 10,000-claim artifact, with the heuristic labeler (no paid call). Names below are those heuristic titles. A paid run would rewrite the titles and would not add planets.

A call here is one draft face label, one wide relabel of that face, one planet name, and a brief for the planet plus each face: `3 × faces + 2` calls per planet. Calls inside one planet stay serial. Twelve planets are labeled at once. Each call is taken as 9 seconds, the middle of the 7–11 second band measured on run 37696485020. The projected seconds are the resulting wall clock.

| | A. Cluster once | B. Re-cluster each section |
|---|---:|---:|
| Sections that publish 10 planets | 10 of 10 | 10 of 10 |
| Global top 10 that also appear in a section | 10 | 9 |
| Planets labeled (unique) | 100 | 110 |
| Faces labeled | 175 | 192 |
| Labeling calls | 725 | 796 |
| Projected labeling seconds | 567 | 612 |
| Sections that ran the per-section fallback | 1 (Sports) | 0 (every section is clustered on its own) |

A is the default. It fills every section, every global planet also appears in a section, and it labels 10 fewer planets. B’s section lists are a second clustering, so a story in the global ten is labeled again even when the same posts show up. The fallback ran once: Sports had enough shared planets to be a candidate list, and 8 of them published, so a Sports-only pass added the last two.

Global top 10, same for both: Israel, Russia Ukraine, Rape, Iran Trump War, Labour Party, Scotland Scottish, Trump, Fascism Fascist, Men Women, Trans.

Heuristic top 10 by section.

| Section | A. Cluster once | B. Re-cluster each section |
|---|---|---|
| World | Israel; Russia Ukraine; Iran Trump War; Nazis Nazi; Genocide; China Much World; Netanyahu Iran Did; Kyiv Russia Russian; Colonialism History Imperialist; Peace Prize Nobel | Israel Gaza; Russia Ukraine; Iran War Trump; Trump War Day; Genocide Better Maniac; China Russia; Kyiv Bridge Russian; War Never World; Bail Iranian Released; Europe Daily European |
| Politics | Rape; Labour Party; Scotland Scottish; Trump; Fascism Fascist; Men Women; Trans; Death Penalty; Canada; Treason | Labour Party; Fascism Fascist; Germany Country Far; Ads Trump Taxpayer; Trump Great Paying; Medicare Seniors Trump; Brexit Voted Scotland; Ice; Trump; Zionism Party Racism |
| Business | System; America Private Bullshit; Gallon Cost Diesel; Money; Tariffs Tariff Refund; Heating Oil Home; Billionaires World Think; Never Wealth; Crypto News; Barrels Million Crude | Market; Gas Oil Prices; Housing Building Government; Oil Iran Trump; Economy Off Trying; Money New; Russia Putin Budget; Diesel Battery Crisis; Amazon Anyone Buying; Tourism Much Trade |
| Technology | Llms Better Same; Point Years; Openai Anthropic Australia; Community Media Monetization; Ground Anti Drone; Local; Software; Books Anthropic Train; Many; Disc Digital Key | Data Centers Every; Llms Actually Machine; Openai Company Quit; Youtube Video Channels; Apps App Android; Science Baked; Current Let Off; Compromised Data Addressed; Robots Makes Sense; Technology Able Everyone |
| Sports | City Man; Athletes America Did; Football Politics Sports; Uae City Investments; Tennis Upsets Women; Croatia England Night; Mercedes Ass Die; Chance Win; Most Real Rule; Mercedes Ass Die 2 | League Football; City Liverpool Clubs; City Down Football; Men Sports Women; Most Real Rule; Mercedes Ass Die; Step Wwe; Bad Calls Conference; Only Season; Game Players |
| Culture | Lesbian Women Gay; Art Artist Artists; Women Industry Make; Humiliation Victim; Redemption Done Feel; Harry Potter; Feel Violence; Artists Make Much; Skydance Bros Discovery; Getting Gen | Rape Women Culture; Trans Anti Cares; Scotland; Book Books Banned; Media Newspapers Big; Harry Potter Other; Ahistorical; Content Fucking Advertisers; Music Rock; Masculine See |
| Health | Covid; Medical Profit Healthcare; Measles Cases Pennsylvania; Plague Russia Pneumonic; Covid Flu Nhs; Medicaid; Masks Coverings Face; Milk Raw Ban; Cancer Research Time; Children | Healthcare Insurance Profit; Plague Russia Russian; Flu Covid Nhs; Measles Cases Pennsylvania; Parents Vaccinated Vaccine; Milk Raw Ban; Cancer; Mind; Masks Prevent; Health Rural Areas |
| Environment | Climate Change; Environment Water; Beef Cattle Less; Heritage; Energy Fossil Fuels; Court Emissions Account; Local Food; Course Diesel Petrol; Beast West; Energy Data Example | Climate Change; Electrification Apparently Electricity; Farmers Energy Look; Energy Fossil Subsidies; Ocean; Climatechange Levels Rise; Hurricane Gulf Tropical; Local; Dirty; Neighbours Those |
| Education | Schools Pay; Schools Education Numbers; School Kids Shootings; School Start; Bike Bus City; Fucking Ivy League; Kids Parents; Humanities Arts Challenges; Cornell Required University; Teachers Education Educators | Cornell Men Rape; Teachers Education Day; School Exam; School Students High; America College Education; School Schools Allows; University Management Only; Kids School Things; Students Going Making; High School College |
| Other | Did Accountability Admitted; Live Someone True; Anything Haven Many; Cruelty Point Regime; Women Alone Always; Bluesky Fact; Article Read; History Future Only; Question Species Apart; Church Assault Boys | Men; Trans Making Anything; Child Minor; Rapists Abusers; Religion Cannot Control; Christians Believe Christianity; White Live Men; Women Bisexuality Lesbians; Substack; Church Assault Children |

Non-English posts and posts that are only a link are dropped before clustering, with a local word and script check. No model call.

## Scale

At 10,000 posts the grid is fit on every post. That clustering step took **10.1 seconds** for the whole week and **2.8 seconds** for Politics (5,148 posts). All ten sections together are a few more seconds. That is comfortable inside CI.

At 100,000 posts an assignment of every post to `n / 5` centers would be an n×k matrix of about 10 GB, and it would do work the topic count does not need. Above 12,000 posts, centers are fit on a sample of 12,000 (the same ball rules), then every other post joins a center only when it sits inside that ball (cosine at least 0.50). A post outside the sample does not create a new group. A synthetic 100K run in 384 dimensions — 30 tight crowds of 400 posts plus 88,000 noise posts — finished in **18.9 seconds**, found **30 groups**, and left the noise unlabeled (12,000 posts in a group, the crowds only). The #32 bar is a finish within 10 minutes and at least 20 candidates. This is a synthetic corpus, not a second week of Bluesky, so it checks the path and the timing, not the topic count of a real 100K window.

## Labeling cost

Labeling still stops once `catalog_size` (10) planets survive. With `cluster_once`, a planet that is in the global ten and in a section is labeled once. On this corpus that is 100 planets and 175 faces, about 725 paid calls and about 567 seconds at the rate above. Re-clustering every section instead is 110 planets, 192 faces, about 796 calls and about 612 seconds. Both sit under the old ~1,025–1,080 DeepInfra calls from issue #86 and under the 20-minute section ceiling. A one-perspective planet makes one face call, not a forced pair. Candidate groups below the top 10 are not labeled.

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

Published top 10 when each section is clustered on its own posts (option B above), heuristic labels, not a paid model. Mixed-remarks columns are titles that still say “Mixed remarks” after the wide-sample check. Those faces are dropped, so the counts are zero.

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
