# Grouping perspectives inside one planet

How to give every planet at least two faces without pretending a weak cut is a strong disagreement. This note is the technical spec for issue #76. The numbers are from the corpus published by Daily Discourse Pipeline run [37706379226](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37706379226) (2026-10-07). That run's Health section published **zero** planets ("no planet with two distinct faces"). Culture and Sports published one each.

## Recommendation, in plain language

A planet is a topic people are already talking about. The old rule deleted the planet when the posts would not separate into two tidy camps. That threw away popular topics, including every Health topic in that run.

The change we ship: **keep the planet.** Use the current embedding split when it already finds two or more solid faces. When it does not, cut the posts in two anyway, label both sides, and store a **distinctness score**. A high score means the two sides sit far apart. A low score means they are similar and a reader should treat the split as tentative, not as two settled camps.

We tried several other ways of cutting the same posts. None was clearly better as the everyday method. Asking a language model to name the positions produces nicer sentences on some topics and muddled ones on others, and it costs a model call per planet. Clustering itself is a few seconds. The time limit that matters is still the labeling budget, so the daily job does not add that extra call.

## What went wrong on 2026-10-07

Two different steps can leave a planet with one face:

1. **The geometric gate.** Inside a planet, k-means tries 2, 3, 4, 5, and 6 faces on MiniLM embeddings and keeps the count with the best cosine silhouette, but only if every face has at least 2 posts and 5% of the planet, centroids are not closer than cosine 0.90, and each face is at least as tight as the planet. If nothing passes, the planet used to be dropped before any label was written. See `choose_n_faces` in `pipeline/perspectives.py` and the #53 entry in `.factory/DECISIONS.md`.
2. **The labeler.** A face titled "Mixed remarks", or two faces whose titles are the same stance, used to be merged or removed. If fewer than two faces remained, the planet was dropped after the model had already been called.

On this corpus the second step is the one that emptied Health. Of 7 Health candidate planets, **6 already passed the geometric gate**. Only "plague russia" (22 posts) failed it, because every k left a face of one post. The other six would have reached the labeler and then been discarded when titles collapsed. Keeping the pre-collapse faces, and forcing a cut only when the gate fails, is what puts those planets back.

## Survey

The job is stance and viewpoint grouping **inside one topic**, on short social posts (here, about 180 characters). The posts in a planet are already about the same subject, so a general sentence embedding mostly says "these match," not "these disagree."

| Approach | What it does | Expected quality on one topic | LLM calls | Runtime | Deterministic? |
|---|---|---|---|---|---|
| Baseline: silhouette k-means on MiniLM, k = 2..6 | Lloyd k-means, 3 farthest-first restarts, pick k by mean cosine silhouette (Rousseeuw) if the hard gates pass | Good when two stances really sit apart. Drops the planet when they do not. Known to glue "yes" and "no" on the same subject. | 0 | Milliseconds to a couple of seconds per planet. The daily embed of the week is separate (~1 minute here). | Yes, given the seed |
| Agglomerative / Ward | Merge closest clusters by minimum variance until k remains. Squared Euclidean on normalized vectors is a monotone function of cosine. | Similar to k-means, slightly more stable sizes. No natural "drop" — you always get k faces. Ward prefers Euclidean distance; average linkage is the usual cosine alternative. | 0 | Well under a second per planet at these sizes (largest candidates are a few hundred posts). | Yes |
| HDBSCAN, then a forced 2-split | Mutual-reachability single linkage (the HDBSCAN tree). Keep components above a minimum size. If fewer than two survive, force a 2-cut. | Right tool when a topic has dense pockets and junk around them. On a tight topic it often returns one cluster, so the fallback does the real work. Our cut is a quantile of that tree, not the full excess-of-mass extractor. | 0 | About a second for all 125 planets. | Yes |
| Spectral clustering | Cosine affinity, normalized Laplacian, top eigenvectors, then k-means (Ng, Jordan, Weiss). Best silhouette for k = 2..6. | Can find non-round groups. Inside one already-tight topic the affinity is almost flat, so it rarely beats k-means. More balanced faces in this run. | 0 | Sub-second here. An eigenvector step gets heavy only for thousands of posts in one planet, which we do not have. | Yes, given the seed |
| BERTopic-style c-TF-IDF | k-means on TF-IDF (the split). c-TF-IDF then names each face by terms that are common inside it and rare in the other faces. | Best at separating vocabulary ("vaccine" vs "outbreak"). Worst at embedding separation: the faces are about the same subject, so MiniLM still puts them close. Useful as a naming step and as one candidate for the forced cut, not as the only split. | 0 | Sub-second. | Yes, given the seed |
| Stance-aware / contrastive embeddings | Fine-tune a sentence encoder so opposing claims move apart (triplet or contrastive loss). A cheap stand-in, used here, subtracts the planet mean and splits on the strongest leftover direction. | A trained stance encoder is the high-quality version and needs a corpus of pro/con pairs plus a new model in the daily image. The residual-axis stand-in needs neither. It is balanced and a bit less distinct than k-means. | 0 for the stand-in. Training is offline and large. | The stand-in is the fastest cut in the table. | Yes for the stand-in. A fine-tune is deterministic only if the training seed is pinned. |
| LLM proposes 2–6 positions, then posts are assigned by embedding | One prompt sees a sample of posts and returns short position sentences. Each post goes to the nearest position in MiniLM space (GoalEx / "text clustering as classification", without the second classify call). | The sentences are often readable. The assignment is only as good as the embedding, which is the original problem. On this Health slice the embedding gap was **worse** than the local cut. | **1 per planet** (propose). Assigning every post with the model would be 1 per post and is not worth it. | A few seconds per call, plus network. 7 Health planets were 7 calls. | No. Temperature 0 reduces drift; it does not remove it. |
| LLM "opposing positions" prompt | The same call, worded as "name 2 to 4 positions that disagree." This is zero-shot stance discovery, not a new algorithm. | Same as the row above. Strong on measles, plague, and raw milk. Weak on a mixed Health grab-bag, where the model wrote "some people say / others say" sentences that are not positions. | 1 per planet if it replaces the propose step. A second call that labels every post doubles it. | Same. | No |

### Sources

- Peter J. Rousseeuw, "Silhouettes: a graphical aid to the interpretation and validation of cluster analysis," *Journal of Computational and Applied Mathematics* 20 (1987). https://doi.org/10.1016/0377-0427(87)90125-7
- Joe H. Ward Jr., "Hierarchical grouping to optimize an objective function," *Journal of the American Statistical Association* 58 (1963). https://doi.org/10.1080/01621459.1963.10500845
- scikit-learn user guide, hierarchical clustering and silhouette. Ward minimizes variance and is the Euclidean cousin of k-means; cosine is the documented reason to prefer average linkage instead. https://scikit-learn.org/stable/modules/clustering.html#hierarchical-clustering
- Ricardo J. G. B. Campello, Davoud Moulavi, and Jörg Sander, "Density-Based Clustering Based on Hierarchical Density Estimates," PAKDD 2013. https://doi.org/10.1007/978-3-642-37456-2_14
- How the popular HDBSCAN implementation turns that hierarchy into clusters. https://hdbscan.readthedocs.io/en/latest/how_hdbscan_works.html
- Andrew Y. Ng, Michael I. Jordan, and Yair Weiss, "On Spectral Clustering: Analysis and an Algorithm," NeurIPS 2001. https://proceedings.neurips.cc/paper/2001/hash/801272ee79cfde7fa5960571fee36b9b-Abstract.html
- Maarten Grootendorst, "BERTopic: Neural topic modeling with a class-based TF-IDF procedure," arXiv:2203.05794. https://arxiv.org/abs/2203.05794 and the c-TF-IDF write-up https://maartengr.github.io/BERTopic/algorithm/algorithm.html
- Nils Reimers and Iryna Gurevych, "Sentence-BERT," EMNLP 2019. The daily embedder is `sentence-transformers/all-MiniLM-L6-v2`. https://arxiv.org/abs/1908.10084 and https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- Arman Irani and colleagues, "≠ pizza: Stance-Aware Sentence Transformers for Opinion Mining," EMNLP 2024. Default sentence embeddings group pro- and anti- posts together because they share a topic. https://aclanthology.org/2024.emnlp-main.1171/
- Contrastive stance training: WASSA 2023, https://aclanthology.org/2023.wassa-1.37/ and Liang et al., "Zero-Shot Stance Detection via Contrastive Learning," WWW 2022, https://doi.org/10.1145/3485447.3511994
- Negation and antonyms are a known hole in semantic similarity: Vahtola et al., SemAntoNeg, BlackboxNLP 2022. https://aclanthology.org/2022.blackboxnlp-1.20/
- Yuwei Zhang, Zihan Wang, and Jingbo Shang, "ClusterLLM: Large Language Models as a Guide for Text Clustering," EMNLP 2023. The model judges hard pairs; it does not embed the corpus. https://arxiv.org/abs/2305.14871
- Zihan Wang, Jingbo Shang, and Ruiqi Zhong, "Goal-Driven Explainable Clustering via Language Descriptions," EMNLP 2023. Propose explanations, then assign texts. https://arxiv.org/abs/2305.13749
- "Text Clustering as Classification with LLMs," arXiv:2410.00927. The model proposes labels, then classifies each text. We tested the propose step plus a local embedding assign, which is the cheap half. https://arxiv.org/abs/2410.00927
- Stance Reasoner, zero-shot stance on social posts with an explicit prompt. https://arxiv.org/abs/2403.14895

## Experiment

Harness: `python -m pipeline.eval.grouping_eval`. It reads a SQLite corpus, embeds with the same MiniLM the daily job uses, builds candidate planets with the same section clustering as `pipeline/live.py`, and runs every local approach on those planets. The database is not committed.

Corpus: artifact `data-json` from run 37706379226. 10,000 public claims. Section sizes: Politics 5,148, World 1,279, Business 653, Other 639, Technology 629, Culture 548, Health 300, Environment 297, Sports 270, Education 237. That produced **125 candidate planets**. Embedding the week took 46 seconds and is cached outside the repo. Grouping all seven local approaches took about 7 seconds.

Distinctness is `1 - (highest cosine between two face centroids)`, clipped to 0..1. Higher means the faces sit farther apart in MiniLM space. Term overlap is the average Jaccard of the salient terms. Lower means the faces use different words. Balance is the smallest face divided by the largest. LLM calls and seconds are for the grouping step only.

| Approach | Kept | Dropped | Faces | Distinctness | Distinctness on the 9 the baseline drops | Silhouette | Term overlap | c-TF-IDF overlap | Balance | LLM calls | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline (silhouette k-means, drop if none pass) | 116 | 9 | 2.66 | 0.371 | — | 0.120 | 0.096 | 0.034 | 0.474 | 0 | 1.98 |
| Ward | 125 | 0 | 3.27 | 0.385 | 0.389 | 0.137 | 0.068 | 0.028 | 0.473 | 0 | 0.53 |
| Spectral | 125 | 0 | 3.01 | 0.368 | 0.364 | 0.130 | 0.091 | 0.041 | 0.642 | 0 | 0.45 |
| HDBSCAN-style + forced 2-split | 125 | 0 | 2.03 | 0.377 | 0.406 | 0.125 | 0.095 | 0.040 | 0.525 | 0 | 0.95 |
| c-TF-IDF k-means | 125 | 0 | 3.04 | 0.307 | 0.331 | 0.032 | 0.041 | 0.014 | 0.400 | 0 | 0.70 |
| Residual axis (always 2) | 125 | 0 | 2.00 | 0.338 | 0.359 | 0.111 | 0.125 | 0.053 | 0.756 | 0 | 0.25 |
| **Keep-floor (shipped)** | **125** | **0** | **2.62** | **0.374** | **0.406** | **0.120** | **0.091** | **0.032** | **0.467** | **0** | **2.06** |

Keep-floor is the baseline split when the gates pass, and otherwise the best forced 2-cut among the residual axis, embedding 2-means, Ward, and TF-IDF 2-means. The tightest silhouette wins that fallback; distinctness, then term separation, breaks ties.

Reading the table:

- Every method except the baseline keeps all 125 planets. That was the requirement.
- Ward is the strongest pure alternative: a little more distinct (0.385 vs 0.374), a little less term overlap, and it never drops a planet. It also changes faces the baseline already accepted (3.27 faces instead of 2.62). That is a bigger product change than the gain.
- c-TF-IDF wins on vocabulary and loses on geometry (silhouette 0.032). The words differ; the embeddings do not. That matches the stance papers: topic embeddings do not encode disagreement.
- Spectral is the most balanced of the multi-face methods and does not improve distinctness.
- The residual axis is the most even 2-way cut and the least term-distinct.
- On the 9 planets the baseline would delete, keep-floor ties the HDBSCAN fallback at distinctness 0.406, ahead of Ward (0.389).

### Health, the hard cases

Seven candidate planets from 300 Health posts. Six already had a legal geometric split. One did not. In the live run they were all dropped later, or not labeled, and the section published nothing.

| Planet | Posts | Baseline | Shipped faces | Distinctness | Terms |
|---|---:|---|---|---:|---|
| measles cases | 24 | kept, 2 faces | 7 and 17 | 0.365 | vaccines / parents / children vs measles / cases / outbreak |
| covid flu | 21 | kept, 2 faces | 16 and 5 | 0.366 | covid / flu / vaccination vs africa / ebola |
| plague russia | 22 | **dropped** (every k had a 1-post face) | 20 and 2, forced | 0.407 | plague / russia vs a 2-post leftover |
| while | 11 | kept, 3 faces | 3, 4, 4 | 0.461 | weak terms (while / kind / around) |
| milk raw children | 11 | kept, 3 faces | 7, 2, 2 | 0.515 | raw milk / children vs two tiny faces |
| care health | 10 | kept, 4 faces | 2, 2, 4, 2 | 0.473 | care / health vs smaller slices |
| claims gov let | 8 | kept, 2 faces | 6 and 2 | 0.551 | claims / gov vs communities |

"plague russia" is the geometric failure. The forced cut isolated two odd posts (a Wikipedia link and a GB News aside) because they sit far from the outbreak reports. Ward's 15-vs-7 cut on the same planet read more like "reports of a Russian outbreak" versus "this panic is overblown," at a lower distinctness (0.252). The score is a distance, not a promise that the faces are the argument a person would name. That is why a low or a strangely high score should stay visible instead of deleting the planet.

### Qualitative sample

Labels below are salient terms, not model titles. Two posts per face, shortened.

**Health / plague russia** (baseline drops it; shipped forces 2).

- Face A, 20 posts, terms plague / russia. "Russia is investigating a lab worker’s death after unconfirmed reports of pneumonic plague. Experts say it requires close contact, is treatable with antibiotics and poses little risk." And: "Researcher at Russian plague laboratory dies of ‘unknown’ infection."
- Face B, 2 posts, term ben. A Wikipedia pneumonic-plague link, and a GB News aside about the word "vaccinated." This face is thin. Ward's alternative face (7 posts) was people calling the coverage hysteria, including "a disease whose last person-to-person infection occurred in 1924 has already killed 10 million imaginary Americans."

**Health / measles cases** (baseline already keeps it).

- 7 posts, vaccines / parents / children. Consent and school vaccination, and children harmed when they are not vaccinated.
- 17 posts, measles / cases / outbreak. Case counts and the Pennsylvania outbreak.

**Health / covid flu** (baseline already keeps it).

- 16 posts, covid / flu / vaccination. Seasonal jabs, NHS eligibility, rising cases.
- 5 posts, africa / ebola. A different disease story that landed in the same planet. Distinctness 0.366 says the geometry is only moderate.

**Technology / use** (baseline drops it: faces looser than the planet, or paraphrases). 147 posts, shipped 113 and 34, distinctness 0.123. Both sides are "what is AI actually good for / who is using it." The score correctly says the two faces are close. The planet stays.

**Politics / fascism** (baseline keeps it, and keep-floor does not touch it). 55 posts on fascism / fascist, 27 on nazi / nazis, distinctness 0.256, no shared top term. This is the kind of split the old gate was built to keep.

### LLM opposing-positions, Health only

Seven calls, temperature 0, the same OpenAI-compatible client the labeler already uses. The model named 2–6 positions from a 24-post sample. Posts were assigned locally. Mean distinctness on these seven planets was **0.315**, against **0.448** for keep-floor on the same seven. The model was better at sentences than at geometry.

- Measles: it named "vaccines work and refusal puts others at risk," government handling, Mennonite and Amish reluctance, and RFK Jr. disinformation. Those are real stances. Several posts still fell into the disinformation bin because the embedding could not tell a case-count headline from an argument.
- Plague: "the government is covering this up" (17 posts) versus "it is treatable and contained" (3). That is the split a person would hope for, and it is cleaner than the 20-vs-2 geometric fallback.
- Raw milk: risk to children versus "banning it is overreach," which matches the posts.
- "while" and "care health": the model wrote balanced "some say / others say" sentences and the assignment scattered. Not worth a daily call.

Doing this for every planet would add one model call per planet on top of the face labels and the planet name. A full day is on the order of a hundred planets. The section ceiling is 20 minutes of labeling (#71). Clustering is not what spends that time. An extra call per planet would.

## What the code does

`split_perspectives` still runs the silhouette gate. When a count passes, that split is the one that is labeled, including a small tight minority. When none passes, `force_two_labels` cuts the planet in two and sets `forced`. The planet is labeled either way.

If the labeler then merges titles or drops a "Mixed remarks" face and fewer than two would remain, the pre-collapse faces are kept and alike titles gain a distinguishing term. That path does **not** call the model again. A second k is tried only when the first labeling never produced two faces at all. The old code always paid for that retry and then deleted the planet.

`face_distinctness` on the planet in `data.json` is optional. Missing is valid, so older snapshots and the demo catalog still load. A present value must be a number from 0 to 1. The observatory copies the topic through and does not require the field.

### Label-call change

- Planets the gate already accepts: same face labels as before. If titles collapse, we keep them instead of labeling a second k. That is fewer calls, not more.
- Planets the gate used to drop with no labels (9 of 125 candidates here, including one Health planet): two face labels and one planet name, and the planet counts toward the catalog so a later spare is not labeled.
- No new call was added to the daily path for the LLM propose step.

## What we did not ship

- Replacing silhouette k-means with Ward on every planet. The average gain is about 0.01 distinctness, and it rewrites faces that already passed the gate.
- A stance-encoder fine-tune. The papers say it is the real fix for "yes" versus "no." It needs a paired corpus and a model change in the daily image. The residual axis is the stand-in, and it lost on distinctness.
- An LLM position list in the daily job. Better sentences on three Health topics, worse embedding separation, and a call we do not have spare budget for.
