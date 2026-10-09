# Issue #104: stronger local embeddings do not clear the story bars

Investigation only. No production change, no pull request. Local open ONNX models only. No DeepInfra and no other hosted embedding call (the DeepInfra key is in use for the paid labeling check on #114 / #107).

- Run: `bc-ca699137-85d6-599c-8696-c21f8995f4b3`
- Model: Grok 4.7
- Branch: `cursor/embedding-model-study-f4b3`
- Grouping replayed: PR #114 (`cursor/attach-same-story-posts-6e9b` @ `af19da9`), vendored under `research/issue-104/vendor/story_attach.py`
- Corpus: Actions run `37942713535`, artifact `data-json` `11622439023`. After `partition_posts`: 9,832 kept, 56 non-English, 112 link-only. Sorted-URI sha256 `6189f0ee54e5091ea20aec162c46eafffde63925259af9a0ea0e6b321a75ba7a`.
- Story reference: `docs/evidence/issue-104/story_reference.json` at `28c93de9cfb7f43ba46fb3ecf94bb588fdde869c`.
- Embedder: fastembed 0.9.0, ONNX, 4 threads, batch 64. Nomic texts are prefixed with `clustering: ` (fastembed does not add it). bge and gte get no prefix.

**Recommendation: stay on `all-MiniLM-L6-v2`.** None of the four stronger ONNX models clears story recall, noise, top-10 coverage, and a coherent Politics lead at the same time. Where Iran recall rises, Ukraine or Gaza falls and noise gets worse. Where a large Israel ball appears, it still mixes the Gaza war with the Zionism motion.

`intfloat/e5-base-v2` and `sentence-transformers/all-mpnet-base-v2` were not run. They are not in the fastembed 0.9 catalog, and the CI path is ONNX without torch.

## Bars, and the control

Bars from #104, applied to stories with at least 100 reference posts: story recall ≥ 80%, noise ≤ 25%, top-10 coverage ≥ 30%, World lead ≥ 100 and Politics lead ≥ 100, Politics coverage ≥ 25%, no duplicate faces, no Mixed remark. Epstein has 72 reference posts, so the 80% bar does not apply to it.

The MiniLM control uses the stock gates (member 0.50, merge 0.72, mean 0.60, attach 0.42, fold 0.55) and matches the PR write-up on the counts that matter: Ukraine 135/198, Gaza 137/208, Iran 88/173, ICE 53/110, Epstein 49/72, Zionism posts on the Gaza planet 79, largest planet 277, voice-rank top 10 = 1,088, Politics section top 10 = 566/5,071, attach 282 noise posts, 5 folds / 57 posts. Noise here is 3,514/9,832 (35.74%) against 3,483 (35.4%) in the PR write-up. The 31-post gap is in small planets. Every model below was scored in this same harness, so the gap is shared.

"World lead" and "Politics lead" below are the largest global planet whose majority section is that section (the PR's lead). Section-page leads, from reclustering that section's own rows, are listed separately.

## How the other models were tuned

Held-out split: 1,200 posts, seed 104, URIs absent from all six reference sets. Zero reference leaks. Eight proper-name stems on that split (congress, senate, british, medicare, labour, covid, constitution, christian) were a diagnostic only. They did not set a gate.

Stock 0.50 and 0.60 sit at the floor of MiniLM's raw k-means cells on the 9,008 non-reference posts (member rank 0.0079, mean rank 0.0056, fold rank 0.038, attach rank 0.0, merge rank 0.9184 of nearest cell centers). Each new model takes those same ranks on its own cell distributions, then only repairs an inversion (`attach ≤ member ≤ fold ≤ mean ≤ merge`, clipped to [0.05, 0.99]).

Three earlier tunings were rejected and are not the numbers below:

- Matching half-centroid and cross-story cosine. On these models the two distributions sit on top of each other, so the gates landed above the stories and noise went to 96–99%.
- Matching the middle of the small tuning stories. Stock gates are the floor of a cell, not the middle of a 10-post name group, so the mean gate sat above real cells and noise stayed near 90%.
- Forcing a 0.02 gap between gates and capping merge at 0.95. That lifted gte-base's mean gate from 0.905 to 0.915, above its cell-mean p10, and that run's noise was 81% with Gaza and Iran recall near zero. The gte row below is the raw-quantile rerun.

## Story recall

Best planet's share of the reference set. Zionism "on Gaza" is how many Zionism-reference posts sit on the planet that holds the most Gaza-reference posts.

| Model | Ukraine (198) | Gaza (208) | Iran (173) | ICE (110) | Epstein (72) | Zionism on Gaza planet |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MiniLM stock | 135 (68.2%) | 137 (65.9%) | 88 (50.9%) | 53 (48.2%) | 49 (68.1%) | 79, on the 277 |
| bge-small | 63 (31.8%) | 7 (3.4%) | 120 (69.4%) | 19 (17.3%) | 13 (18.1%) | 0 |
| bge-base | 71 (35.9%) | 123 (59.1%) | 113 (65.3%) | 13 (11.8%) | 53 (73.6%) | 73, on the 258 |
| gte-base | 57 (28.8%) | 134 (64.4%) | 107 (61.8%) | 58 (52.7%) | 51 (70.8%) | 69, on the 268 |
| nomic | 14 (7.1%) | 7 (3.4%) | 104 (60.1%) | 55 (50.0%) | 41 (56.9%) | 0 |

No row is ≥ 80% on Ukraine, Gaza, and Iran together. The best single figure on any ≥100-post story is bge-small's Iran at 69.4%, and that model's Gaza recall is 3.4% because the scorer's best Gaza planet is the Iran ball (7 Gaza posts). Nomic's global Gaza recall is the same failure: 7 Gaza posts on the Iran ball of 112.

Same-story posts do move closer in absolute cosine. Median cosine to the story's own centroid:

| Model | Ukraine | Gaza | Iran | ICE | Epstein | Zionism |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MiniLM | 0.591 | 0.616 | 0.583 | 0.541 | 0.634 | 0.693 |
| bge-small | 0.793 | 0.800 | 0.806 | 0.790 | 0.798 | 0.844 |
| bge-base | 0.752 | 0.776 | 0.775 | 0.756 | 0.796 | 0.820 |
| gte-base | 0.893 | 0.901 | 0.900 | 0.894 | 0.907 | 0.912 |
| nomic | 0.854 | 0.851 | 0.850 | 0.822 | 0.861 | 0.877 |

The cell distributions move up with them. Retuning to the same rank therefore raises every gate, and the ball does not gain a wider margin over nearby stories.

## Noise, coverage, leads

Top-10 is the voice rank used at publish time (distinct authors, then size). Politics coverage is that section's own top 10 over its 5,071 posts.

| Model | Noise | Largest | Top 10 | World lead (global) | Politics lead (global) | Section World lead | Section Politics lead | Politics coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MiniLM | 35.74% (3,514) | 277 | 1,088 (11.07%) | 277 | 67 | 242 | 92 | 11.16% (566) |
| bge-small | 59.16% (5,817) | 141 | 751 (7.64%) | 141 | 125 | 311 | 83 | 7.30% (370) |
| bge-base | 48.56% (4,774) | 258 | 1,008 (10.25%) | 258 | 98 | 219 | 77 | 8.93% (453) |
| gte-base | 46.02% (4,525) | 268 | 1,120 (11.39%) | 268 | 87 | 246 | 69 | 9.31% (472) |
| nomic | 46.60% (4,582) | 112 | 574 (5.84%) | 112 | 71 | 180 | 60 | 8.07% (409) |

Noise is worse than MiniLM for every stronger model, and none is ≤ 25%. Top-10 coverage stays near 6–11%, against a 30% bar. Politics coverage stays under 12%, against 25%.

World lead clears 100 for every model. Politics lead clears 100 only for bge-small (125), and that planet is a "years" grab-bag, not one story. Section Politics leads are 60–92.

## Coherence of the sampled planets

About 15 posts per planet (center, middle, and edge by cosine to the centroid): the 10 largest global planets, the 3 largest World planets, and the 3 largest Politics planets. Yes means those posts are one news story. A mood, a topic grab-bag, or two named stories is No. Full texts are in `out/<model>.samples.json`.

| Model | Global | World | Politics | What failed the one-story read |
| --- | --- | --- | --- | --- |
| MiniLM | 3/10 | 2/3 | 0/3 | Global Yes: Ukraine, Iran, ICE. The 277 Israel planet mixes the Gaza war and the Zionism motion. World Israel is the same mix. Politics is Labour/Tories plus an Australia aside, MAGA, and fascism. |
| bge-small | 1/10 | 1/3 | 2/3 | Global Yes: Iran only. The Ukraine ball of 140 includes the Hormuz-bypass oil pipeline. World Israel (311) is glue. World Ukraine/Trump includes JCPOA and the Hormuz pipeline. Politics Yes: Brexit and Epstein. Politics MAGA is No. |
| bge-base | 3/10 | 1/3 | 1/3 | Global Yes: Ukraine (78), Brexit, Epstein. Israel 258 still holds 73 Zionism-reference posts. Russia 139 includes the plague-lab posts PR #114 refused to fold. Iran 124 includes a Persepolis ban note and Paxton leak posts. World Yes: Iran. World Ukraine includes a long-covid/pandemic aside. Politics Yes: the Iran/San Diego ball. |
| gte-base | 2/10 | 1/3 | 0/3 | Global Yes: ICE, Brexit. Israel 268 holds 69 Zionism-reference posts and a Kosovo–Israel football aside. Russia 160 includes a Fox News disinformation post. Iran 130 includes a Republican list that names ICE. World Yes: Russia/Ukraine. World Iran includes a photo-of-young-men aside. Politics is country / jail / billionaires. |
| nomic | 2/10 | 3/3 | 1/3 | Global Yes: voting, ICE (two edge posts do not name ICE). Iran 112 includes the Boulder/Big Oil Supreme Court post and a Biden-messaging post. World Israel (180) reads as the Gaza war, World Iran as the war, and World Zionism (72) is a separate planet. That split is real on the World page. It is not a global recall win: global Gaza recall is 3.4%. Politics Yes: Epstein. The court planet and the Labour/Tories planet (Greens/Palestine aside) are No. |

Section-level story recall was not computed. Nomic's World Israel planet looking like Gaza is not a measured Gaza recall.

Duplicate published titles were not regenerated, because the labeler was not called. The local splitter's identical-salient-term count is a proxy, not the #103 title check: MiniLM 4 planets, bge-small 1, bge-base 0, gte-base 0, nomic 3. The title-merge does not depend on the embedder. Mixed remarks were not regenerated either. The Gaza+Zionism mix that produces them is still present for MiniLM (79), bge-base (73), and gte-base (69).

## Thresholds used

| Model | attach | member | fold | mean | merge |
| --- | ---: | ---: | ---: | ---: | ---: |
| MiniLM (stock) | 0.4200 | 0.5000 | 0.5500 | 0.6000 | 0.7200 |
| bge-small | 0.6989 | 0.7527 | 0.7800 | 0.8131 | 0.9178 |
| bge-base | 0.6541 | 0.7271 | 0.7535 | 0.7838 | 0.9049 |
| gte-base | 0.8604 | 0.8869 | 0.8953 | 0.9051 | 0.9621 |
| nomic | 0.7900 | 0.8180 | 0.8380 | 0.8580 | 0.9281 |

## Time, size, RAM

Measured on this 4-vCPU VM, the same class as `ubuntu-latest`. Embed time is the first (uncached) pass over 9,832 posts. RSS is resident set around that pass. Later models started with memory already resident, so the "before" column is not a cold process except for MiniLM. gte-base's process high-water mark was 1,568 MB, carried from earlier in the process; its own resident set after the embed was 1,196 MB.

| Model | Fastembed id | Dim | ONNX on disk | RSS before | RSS after embed | Embed 9,832 | Cluster |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MiniLM | sentence-transformers/all-MiniLM-L6-v2 | 384 | 0.09 GB | 102 MB | 521 MB | 36.2 s | 11.0 s |
| bge-small | BAAI/bge-small-en-v1.5 | 384 | 0.07 GB | 217 MB | 761 MB | 82.5 s | 10.9 s |
| bge-base | BAAI/bge-base-en-v1.5 | 768 | 0.21 GB | 330 MB | 1,569 MB | 246.5 s | 26.8 s |
| gte-base | thenlper/gte-base | 768 | 0.44 GB | 657 MB | 1,196 MB | 200.3 s | 24.7 s |
| nomic | nomic-ai/nomic-embed-text-v1.5 | 768 | 0.52 GB | 673 MB | 3,125 MB | 322.3 s | 24.7 s |

Past 12,000 posts, `density_labels` fits centers on a 12,000-post sample and then assigns, so cluster time stays near the 10k figure. Embed time scales with posts. Projected embed time at 100k, ten times the measured 10k pass:

| Model | Embed 100k | Extra Actions time vs MiniLM |
| --- | ---: | ---: |
| MiniLM | 6.0 min | — |
| bge-small | 13.8 min | +7.7 min |
| bge-base | 41.1 min | +35 min |
| gte-base | 33.4 min | +27 min |
| nomic | 53.7 min | +48 min |

Nomic's 3.1 GB resident set fits a 16 GB runner. It is the heaviest of the five and the slowest, and it does not win the bars.

## Cost at 100k posts, against < $0.50/day

The code target is $0.25/day with a $0.30 fallback (`PRODUCTION_SPEND_TARGET_USD` / `PRODUCTION_SPEND_FALLBACK_USD`). The comparison asked for here is < $0.50/day.

- **GitHub Actions minutes: $0.** The repository is public, so hosted `ubuntu-latest` minutes are not billed. The extra 8–48 minutes at 100k posts does not change that.
- **Hosted embedding: $0.** No hosted embedding was called.
- **Labeling calls do not 10×.** Every model still sends 110 planets into the labeler (top 10 of the global sky plus top 10 of each of the 10 sections). Prompts are capped, so a larger planet does not multiply tokens. At 100k the catalog cap is unchanged.
- **Face prompts move, planet prompts do not.** Local `split_perspectives` (cosine 0.90) on those 110 planets, as a proxy for face-level labeling calls: MiniLM 283 faces (108 multi-face), bge-small 221 (76), bge-base 218 (75), gte-base 123 (8), nomic 218 (68). Scaling the diagnosis labeling bill on this window (~$0.10) by that face ratio gives about $0.08, $0.08, $0.04, and $0.08. gte-base's drop is the 0.90 paraphrase gate refusing a second face under heavy anisotropy, which is fewer perspectives, not a reason to switch. This proxy was not re-measured with a DeepInfra call.
- **Jev does not change with the embedder.** The code price is $0.042 per million input tokens, and Jev scores new posts rather than the embedding model. A larger daily window would raise Jev with the new text. That is still cents next to the $0.50 cap, and it is the same for every row.

All five local options stay under $0.50/day. None of them clears the story bars.

## What would still be true after a switch

Switching the embedder would not by itself fix duplicate face titles (the title-merge is downstream) and would not remove the Gaza/Zionism mix on the models that build one large Israel planet. The failure on this corpus is the margin between one story and the next story, not the absolute same-story cosine.
