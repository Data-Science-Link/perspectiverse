# 275 — Root cause of duplicate planets and faces

Diagnosis and spec only. This document does not change pipeline behavior.

Oct 19 is the baseline edition: `data-snapshot` `44a537b`, `last_updated` 2026-10-19, 100,000 posts, 107 published planets. The producing run was GitHub Actions `39285647768` (head `cbec72e`). Paid Jev and section labeling stayed off for every replay here. No workflow was dispatched.

The Oct 20 examples are the live edition on `data-snapshot` `b049731` (`last_updated` 2026-10-20, 100,000 posts). `origin/main`'s committed `public/data.json` is still the 2026-10-04 file. The site serves the snapshot.

Planet-level duplicates on Oct 19 are the #272 trace ([comment on #275](https://github.com/Data-Science-Link/perspectiverse/issues/275#issuecomment-6293892230)). This spec adopts that trace. The new measurement is faces, posts that stayed off a published face, and `_attach_noise`.

## Headline (guards off)

The yardstick sheet is `docs/evidence/275/oct19-pairs.csv`: 60 planet pairs and 60 face pairs, seed 275, `is_duplicate` empty. A different model labels that column. Those labels, reweighted by the band shares below, become the before/after rate. The similarity figures in this section are the secondary stand-in until that column is filled. They use the full pair census. They are not a count of the 60-row sample.

A near-duplicate, for this secondary rule only, is a representative-post MiniLM centroid cosine ≥ 0.70. Global is one solar system, so there are 11 scopes. There are 107 planets.

**2.4545 near-duplicate planet pairs per section. 0.1495 near-duplicate face pairs per planet.**

The pair rates those counts come from, reweighted to each band's share of its population:

| | Population | Reweighted pair rate | Per unit |
| --- | ---: | ---: | ---: |
| Planets | 480 same-section planet pairs | 0.05625 | 2.4545 pairs / 11 sections |
| Faces | 27 within-planet face pairs | 0.592593 | 0.1495 pairs / 107 planets |

Planets that sit in at least one of those planet pairs: 1.9091 per section. Same-section face pairs that cross planets (774 pairs, reweighted rate 0.054264) are a different population. They are in the blind face sample. They are not the faces-per-planet headline.

`headline = Σ (rate inside band b) × (band b's share of that population)`. With a hard cosine cut the band rate is 0 or 1, so the pair rate equals the share of pairs at or above 0.70. The sample draw is stratified (planet allocation after the trace exclusion: B0 17, B1 17, B2 16, B3 9, B4 1). An average of those 60 rows is a different number and is not reported here.

### Planet bands (480 pairs)

| Band | Cosine | Pairs | Share | Rate ≥ 0.70 | Contribution |
| --- | --- | ---: | ---: | ---: | ---: |
| B0 | −1.01 – 0.40 | 353 | 0.735417 | 0 | 0 |
| B1 | 0.40 – 0.55 | 54 | 0.112500 | 0 | 0 |
| B2 | 0.55 – 0.70 | 46 | 0.095833 | 0 | 0 |
| B3 | 0.70 – 0.85 | 26 | 0.054167 | 1 | 0.054167 |
| B4 | 0.85 – 1.01 | 1 | 0.002083 | 1 | 0.002083 |

Contributions sum to 0.05625. Times 480 pairs / 11 sections = 2.4545.

Per section, pairs at cosine ≥ 0.70: Other 14 (7 planets), Technology 7 (6 planets), Sports 4 (4 planets), Culture 1 (2 planets), Education 1 (2 planets). Business, Environment, Health, Politics, World, and global have none. Health's ADHD pair sits at 0.541, so this cosine rule does not see it. World has 5 pairs and Business 6 pairs in the 0.55–0.70 band; those are near in embedding and are different stories (#272).

### Within-planet face bands (27 pairs)

| Band | Pairs | Share | Rate ≥ 0.70 | Contribution |
| --- | ---: | ---: | ---: | ---: |
| B0 | 0 | 0 | 0 | 0 |
| B1 | 3 | 0.111111 | 0 | 0 |
| B2 | 8 | 0.296296 | 0 | 0 |
| B3 | 14 | 0.518519 | 1 | 0.518519 |
| B4 | 2 | 0.074074 | 1 | 0.074074 |

Contributions sum to 0.592593. Times 27 pairs / 107 planets = 0.1495. Sixteen within-planet face pairs clear 0.70. Two of them clear 0.85 (Culture Twitch Streamers, Stream Plans 223 / Burnout 10, cosine 0.895; global Good Morning, Good Wishes 376 / Night Time 7, cosine 0.856).

### Guards on (secondary)

Applying the 30-post floor (#266) or `planet_chitchat_reason` on representative posts (#264) drops 54 of 107 planets. The reweighted planet headline falls to **0 pairs per section**. The face headline rises to **0.2407 pairs per planet** (within-planet reweighted rate 0.764706). The floor deletes the small duplicate planets instead of joining them, and the large-planet face duplicates (The Show, Twitch, Account Security, Cold Weather) stay in a smaller denominator.

On this file the floor alone drops 53 planets and 548 published posts (sum of `post_count`; a post in global and a section counts twice). #264 on representative posts drops 6 planets: global Good Morning 383, and Other Good Morning 22, Great Day 16, Hope For The Day 14, wonderful day 8, Happy Sunday 6. #235 exact-title fold finds 0 duplicate face titles on Oct 19. #268's stance replay, on representative posts, folds 11 multi-face planets and leaves 14, including The Show at cosine 0.849.

#266 is on `main` now (`MIN_PLANET_POSTS = 30`, merge `ce1564a`). Oct 19 was produced with the floor at 5. The numbers above are the published edition with that floor held off.

## Where the duplicates are made

Clustering is `density_labels` → `_cohesive_balls` (`pipeline/grouping.py`). Above 12,000 posts the centers come from a 12,000-post sample, seed 0 (`_density_from_sample`). The grid is about one seed per `min_cluster_size` posts (5 on the Oct 19 run). `_BALL_MEMBER` 0.50 peels outliers, `_BALL_MERGE` 0.72 folds centers, `_BALL_MEAN` 0.60 drops a loose ball, then groups under the floor become noise. The author cap is 3 (`_cap_author_posts`). Sections are clustered again on their own posts (`live.py` `_cluster_sections`), same seed and same floor. Section labels are one Jev category call per candidate (`stamp_candidate_sections`); that call was not repeated here.

Attach is `attach_same_story` (`pipeline/story_attach.py`). A sibling folds only into a strictly larger parent of at least `BIG_PLANET` 20 posts, centroid cosine ≥ `FOLD_COSINE` 0.55, and ≥ `SIBLING_MAJORITY` 0.60 of its posts passing `post_matches` on the parent's top stem. Noise joins a parent of at least 20 posts at cosine ≥ `ATTACH_COSINE` 0.42 when `post_matches` passes and a second parent is not within `AMBIGUITY` 0.03. `specific_stems` drops tokens under 4 characters, so "ai", "ps5", and "ps6" never become stems.

Faces are `split_perspectives` (`pipeline/perspectives.py`). k-means for k = 2..6, seed 0, three restarts. A cut is invalid when any face is under `MIN_FACE_POSTS` 2 or `MIN_FACE_SHARE` 0.05, when two face centroids are closer than `_FACE_COSINE` 0.90, or when a face is looser than the planet. If no k passes, the planet is one face (`single_view`). The module docstring still mentions a forced second face; `split_perspectives` does not force one. `_draft_planet` (`live.py`) applies the post floor before any name exists, then `_label_faces` drops a face that fails the shared-claim check. `return_same_story_posts` puts a dropped face's posts back only when `post_matches` says they belong to the kept face.

`post_matches` requires the parent's top stem. It then rejects the post when the longest stem in the post is a similar length and is not part of the story (`len(longest) > len(longest_match) + 1` is the only way a longer extra word is ignored).

### Planets (#272, adopted)

Same story, more than one planet, all inside one section:

- Technology. Six planets of 5 posts: AI Generated Articles, AI bots, AI Adoption, AI Creative Effort, Crazy, AI Art. Representative cosine 0.706–0.781. Joined they are 30 posts. Stage: `_merge_same_subject` only merges at 0.72, so the full centers stayed apart, then `_fold_targets` refuses them. None has 20 posts, a parent must be strictly larger, and `specific_stems` drops "ai". `story_of` names them "okay" or "actively". AI Control (5 posts, cosine 0.652) does not join.
- Culture. Tax Movie Titles (177) and Tax Purposes (25), cosine 0.701. Same joke. The representative sample passes today's fold (parent reps ≥ 20, cosine > 0.55). The published edition still has two planets, so the full membership failed a gate this sample passes.
- Health. ADHD Struggles (29) and ADHD Struggles 2 (15). `titles_alike` treats the names as one title. The second planet's posts say hyperfocus and executive function and do not say "adhd". Representative cosine 0.541, under 0.55. The title does not exist until after the floor in `_draft_planet`. Mental Health Struggles is only 0.027 farther from ADHD Struggles than the duplicate is. Lowering the cosine cut to catch ADHD also catches a different condition.
- Education. School Surgeries (33) and School Medical Care (8), cosine 0.701, shared stem "school". `post_matches` hits 3 of 6 representative posts, under the 0.60 majority. Two of those posts are a Media Literacy face, a different story on the same planet.

Sports console planets (PS6 Pricing 7, PS5 Compatibility 6, Sony PS5 5, Playstation Games Sony 5, cosine 0.739–0.820) fail the same attach gates and are not one story. "ps5" / "ps6" are three characters, so they are not stems.

Near in embedding, different stories, do not fold: Business Trump Gas Prices / Brent Oil Prices 0.623, Millionaire Definition / Ultra Rich 0.695; World US Ukraine War / Russia Sanctions 0.601; Sports College Football Playoff / BYU vs Notre Dame 0.648; Environment Fires / Coffee Building Fire 0.628; Education Bar Exam / Bits Limited Neighborhood 0.489 (both say "bar"). `_merge_same_subject` has no stem check. Lowering `_BALL_MERGE` or `FOLD_COSINE` on cosine alone is the wrong change.

Other greeting planets (Good Day, Good Morning, Great Day, Hope For The Day, wonderful day, Great Time, Glad Returns, Happy Sunday) are one pleasantry family, pairwise cosine about 0.61–0.85, and 14 of the 27 planet pairs at cosine ≥ 0.70. They stayed separate, so their full centers were under 0.72. Joining them would publish one pleasantry planet large enough to clear a 30-post floor.

### Faces

`_FACE_COSINE` 0.90 treats 0.80–0.89 as two views. On Oct 19 the published within-planet pairs at cosine ≥ 0.80 are:

| Section | Planet | Faces | Posts | Cosine |
| --- | --- | --- | ---: | ---: |
| Culture | Twitch Streamers | Stream Plans / Burnout | 223 / 10 | 0.895 |
| global | Good Morning | Good Wishes / Night Time | 376 / 7 | 0.856 |
| Culture | The Show | Show Quality / Show Enjoyment | 111 / 89 | 0.849 |
| Technology | Account Security | Account Suspensions / Account Deletions | 60 / 33 | 0.824 |
| Environment | Cold Weather | Weather Changes / Weather Reports | 72 / 61 | 0.818 |

The Show's posts are generic television chatter ("dropped the show", "enjoy the new series"), not two takes on one named show. A #268 replay on representative posts folds Good Morning, Twitch, Account Security, and Cold Weather, and does not fold The Show. It also folds Twitter Exodus (0.732), AEW WrestleDream (0.734), Hair Preferences (0.773), Voice Training (0.782 and 0.760; three faces become one), ADHD Struggles (0.798), and School Surgeries (0.757). It keeps US Iran War (0.756), Brewers Dodgers, French Protests (0.732), and the other disagreed planets listed in the replay. Adopting #268 as a finalize gate leaves The Show in place. The cut is made earlier, in `split_perspectives`, before a title exists.

Two global planets show a collapsed title with a leftover cut. Video Game Enjoyment is one published face (353 posts) with `face_distinctness` 0.135; the corpus stored faces of 253 and 100 at centroid cosine 0.865. No Kings is one published face (345) with distinctness 0.344; the corpus stored 260 and 85 at cosine 0.656. Distinctness is `1 − max face-centroid cosine` (`live.py` `_face_distinctness`), including a cut that labeling then collapsed to one title.

### Posts that stayed off the published face

The Oct 19 log has 53 "stayed off" lines: 1,856 of 7,619 posts in those planets (24.4%). The global share is the 748 membership rows that have no perspective row:

| Planet | Off the published face | Kept | Kept stem | Mean cosine to the kept face | `post_matches` hits |
| --- | ---: | ---: | --- | ---: | ---: |
| Trump Ukraine Sanctions | 257 of 1,116 | 859 | ukrain | 0.559 | 0 |
| Early Voting | 375 of 710 | 335 | early | 0.532 | 0 |
| Good Morning | 62 of 445 | 383 | good | 0.581 | 0 |
| Musk | 16 of 395 | 379 | musk | — | 0 |
| Halloween | 38 of 333 | 295 | halloween | — | 0 |

All 257 Ukraine posts and 373 of 375 Early Voting posts are still within cosine 0.42 of the kept face. Seven of the 257 Ukraine posts contain the substring "ukrain". A post that says "Ukraine" can still fail the longest-stem veto. Early Voting's off-face posts say "vote" and do not say "early". Stage: `split_perspectives` can open a second face under the 0.90 gate, `_label_faces` drops the face that fails the shared-claim check, and `return_same_story_posts` / `post_matches` does not put the posts back. Those posts were already inside the planet ball.

The same veto is why a large ball can shrink under the 30-post floor after the face step. The log's largest section leftovers include Cat Cats 209 of 226 (published 17), Day 154 of 502, Weather 90 of 223, School Gun 86 of 306.

### Unassigned and `_attach_noise`

A global replay of `density_labels` (min cluster 5, seed 0) plus the author cap plus `attach_same_story` on the stored 100,000 posts, ordered by `created_at`, with no Jev call:

| | Replay | Oct 19 run log |
| --- | ---: | ---: |
| Candidate planets before attach | 818 | 795 |
| Folded planets | 22 | 22 |
| Folded posts | 706 | 706 |
| Posts attached from noise | 8,952 | 8,568 |
| Noise after attach | 59,162 | 59,553 excluded |

The fold counts match the run. The candidate and attached-post gaps are the difference between this offline call and the live path; the gate counters below are from the replay.

Noise gate, against parents of at least 20 posts that have a stem (338 such parents):

| Gate | Posts |
| --- | ---: |
| Would attach | 8,983 |
| Ambiguous between two parents | 439 |
| Cosine ≥ 0.42 and stem fail | 28,047 |
| of which cosine ≥ 0.55 | 2,026 |
| Stem matches, cosine 0.35–0.42 | 2,551 |
| Cosine under 0.42 | 30,645 |

Sibling gate, among candidate balls: 204 pairs at cosine ≥ 0.55 with both sides under 20 posts, 16 pairs blocked because the parent is not strictly larger, 2,227 pairs under the sibling majority. The majority examples are dominated by one 158-post ball whose top stem is empty, sitting near balls about cold, weather, soup, and drinks. That is not a missed duplicate. The 204 pairs with both sides under 20 are the fragment shape the AI planets have: neither side is allowed to be the parent.

### Oct 20 trace

These rows are on `handpicked-pairs.csv` only. They are not in the baseline rate. Cosines are representative centroids.

Duplicate planets:

| Section | Pair | Posts | Cosine | Stage |
| --- | --- | ---: | ---: | --- |
| Technology | AI Use / AI Use 2 | 5 / 5 | 0.754 | Same attach failure as the Oct 19 AI fragments. `unique_label` appends " 2" when the names collide. Faces: AI Use, and AI Not Welcome. |
| Technology | Data Centers / AI Data Centres | 120 / 5 | 0.709 | Parent is already over 20, so `BIG_PLANET` is not the block. Spelling (center / centre) and the stem or majority gate are what is left. Data Centers also has two faces, Data Centers Harm 108 and Data Collection 12, cosine 0.740. |
| Business | Tesla Flying Roadster / Elon Flying Cars | 112 / 9 | 0.616 | Representative cosine 0.616 is above `FOLD_COSINE` 0.55, and the parent (112) is larger than the child (9), so size is not the block. The stem (`tesla` / `elon` / `flying`) or the 0.60 majority is the gate that held. Tesla's own faces, Tesla Fails 90 and Tesla Overhyped 22, sit at 0.846. |
| Other | Cat Behavior / Kitten Behavior | 37 / 12 | 0.753 | Parent clears 20. Child has faces Kitten Behavior 9 and Kitten Lessons 3 (cosine 0.693). Stem (cat / kitten) or majority held them apart. |

Duplicate faces, both on the global planet. The section planet of the same story is a different, single-face planet:

- #278. Global Bad Jobs, category Business, 344 posts. Faces Bad Jobs 258 (75%) and Short Lived Jobs 86 (25%), cosine 0.752. Both are quit-after-one-day anecdotes. The Business-section planet is Bad First Jobs, 329 posts, one face titled Bad Jobs.
- #279. Global Trump Putin Ukraine, category World, 1,038 posts. Faces Trump Helps Russia 1,019 (98.2%) and Trump Supports Putin 19 (1.8%), representative cosine 0.939. Both are the anti-Trump, helping-Russia claim. The World-section planet of the same name is 835 posts and one face, Trump Helps Russia. Representative centroids sit past `_FACE_COSINE` 0.90. The cube still shipped two faces, so the vectors the split actually scored were not these representative centroids (the Oct 19 Video Game case is the same split: the corpus kept two face indices, the published title collapsed, and distinctness preserved the cut). Full-membership centroids for this Oct 20 planet were not replayed.

#277 Good Sunday. Global, category Other, 349 posts, one face Good Wishes, about 8.4% of that solar system. It is a greeting planet, not a face duplicate. Twelve representative posts are in the edition ("Good morning Kelly…", "Good morning, Seima… relaxing Sunday", "Have a good rest of your evening"). `pleasantry_reason` returns None on all 12, so `planet_content_share` and the gesture share are 0. The greeting matcher (`_greeting` / `_greeting_wish_body`) keeps a "good morning" whose tail is a name, weather, or a weekend plan; those tokens are not on the allowlist. Stage, in order: ingest kept the posts because they were not classified as chit-chat; `density_labels` formed one ball of 349; the post floor cannot drop 349; `catalog_size` keeps the largest global planets and this is the second largest. The Oct 20 pipeline run (Actions `39417351709`, 11:51 UTC) finished before #264 merged at 14:43 UTC, so that run did not have this guard. Today's guard, applied to the 12 representatives, still does not drop the planet. The 349 member texts are not in the snapshot, so this does not say what the guard would do on the full ball. None of the three method changes below removes Good Sunday. The pleasantry decision has to recognize a day-wish that carries a name or a weather aside.

## What each root fix retires

| Guard | Attach / stem (#272) | Face cut inside `split_perspectives` | Keep dropped-face posts on the surviving face |
| --- | --- | --- | --- |
| #266 30-post floor | Retires it for the AI fragments only. They become one 30-post planet before the floor. Bar Exam (23), BYU (17), and the other genuine small stories still need a floor or they publish as specks. | No | Shrinks the set of stories the floor drops because a face was discarded. Does not retire the floor. |
| #264 junk / pleasantry | No. Joining the greeting family by cosine would publish the pleasantry. | No | No |
| #268 stance gate | No. Attach does not merge faces. | Yes, for the pairs the gate folds, including The Show, which #268 misses. | No |
| #235 exact-title face fold | No | Yes. The second face is not published, so a duplicate title is not minted. Oct 19 had 0 exact duplicate face titles. Oct 20 Business Stock Market has two faces both titled Market Volatility; that run did not have #235. | No |
| #265 label guard | No | No | No |

#264 stays. Fourteen of the 27 planet pairs at cosine ≥ 0.70 are the Other greeting family. Good Sunday is the same failure at planet size 349, and the current matcher misses its representatives.

## Method changes

Ranked by the expected drop in the two headlines. All three are local. None adds a model call. The Oct 19 producing run spent $0.118 on DeepInfra (1,046 calls) and $0.032 on Jev (795 calls). The Oct 20 scheduled run spent $0.129 and $0.031. The daily budget is about $0.25–$0.30. These changes add $0.

Blind `is_duplicate` labels do not exist yet. The drops below are estimated from the cosine census and the #272 / #268 replays. After the sheet is labeled, replace them with the reweighted label rate. Do not score the change with `titles_alike` or with the grouping code that produced the pairs.

### 1. Refuse a paraphrase face in the split

In `split_perspectives` / `score_face_counts`, a second face is a paraphrase when the face centroids are at or above about 0.80, unless the posts actually disagree. Use the existing free lexicon check from #268 for the disagreement test. Do not add a paid stance pass. `_FACE_COSINE` 0.90 is what let 0.80–0.89 through, including Trump Supports Putin at 0.939 on Oct 20 if that cut was scored on a different vector than the published representatives.

Estimated Oct 19 effect: 16 within-planet pairs sit at cosine ≥ 0.70 (headline 0.1495 pairs per planet, reweighted pair rate 0.592593). The #268 replay folds 11 of the 25 multi-face planets, covering the pairs at Twitch, Good Morning, Account Security, Cold Weather, Twitter Exodus, AEW, Hair, Voice Training, ADHD Struggles, and School Surgeries. It misses The Show at 0.849. A bar at 0.80 inside the split removes The Show as well. The pairs it should keep are the ones the lexicon marks as disagreement (Iran War at 0.756, Brewers, French Protests). That leaves on the order of 4 pairs and a headline around 0.04–0.06 face pairs per planet. The planet-pair headline does not move.

Risk: a real minority pressed against the majority collapses. Night Time is 7 posts at full-member cosine 0.883 against Good Wishes. The disagreement check is what keeps Iran War. If the lexicon cannot see a disagreement, the geometric bar will fold the minority.

### 2. Let same-subject fragments join before the floor

This is #272's change. #275 does not carry a second attach implementation.

`_fold_targets` currently requires a strictly larger parent of at least 20 posts, and `specific_stems` drops any token under 4 characters. Change the fold so two sub-20 balls of one subject can join, and so a real subject token shorter than 4 characters can be a stem through an allowlist. Do not drop the 4-character floor for every token: "bar" would glue Bar Exam to Bits Limited Neighborhood, and "ps5" / "ps6" would glue the console history into one story. Do not lower `_BALL_MERGE` or `FOLD_COSINE`. The 0.55–0.70 band is full of different stories (46 planet pairs, share 0.095833, rate 0 under the 0.70 rule, and #272's reading is that they are not duplicates).

Estimated Oct 19 effect on the planet headline: the six Technology planets are 7 of the 27 pairs. Joining them removes 0.636 pairs per section (2.4545 → 1.818) and clears the 30-post floor with 30 posts. Tax Purposes is uncertain: the representative sample already passes the fold and the full ball did not. ADHD is not in the cosine headline (0.541) and is not fixed by an attach threshold, because the shared signal is the published title and the title is written after the floor. School Medical Care fails the majority, and part of that planet is a different story. The 14 greeting pairs stay separate. The 204 sibling pairs with both sides under 20 are the pool this change can fold; a stem allowlist, not the cosine, decides which of them are one subject. The face headline does not move.

Risk: a loose allowlist over-merges. The stem list is the control, not the cosine. Console fragments and the greeting family are the cases the allowlist must refuse.

### 3. Keep a dropped face's posts on the surviving face

When `_label_faces` drops a face, posts already inside the planet ball should remain on the surviving face unless they are a different story. `return_same_story_posts` currently requires the kept face's top stem as a password, and the longest-stem veto then rejects a post that contains the subject and also contains another word of similar length. On the global membership that veto hit 0 of 257 Ukraine posts and 0 of 375 Early Voting posts, all of them already inside cosine 0.42 of the kept face.

Estimated Oct 19 effect on the two headlines: about zero directly. These posts are unpublished; they are not a second planet or a second face. The indirect effect is the floor. Restoring them stops a face drop from pushing a real story under 30 (Cat Cats 226 → 17 in the log; Early Voting 710 → 335). The same `post_matches` path blocks `_attach_noise` (28,047 posts at cosine ≥ 0.42 fail the stem, 2,026 of them at cosine ≥ 0.55). Loosening it inside the planet and loosening it for noise are the same function. The noise change is larger and riskier; do it only for posts that were members of the planet and lost their face.

Risk: the veto exists so a second story inside the ball does not attach. Zionism posts in a Gaza planet are the case `story_of` already documents. A restore rule that only puts back posts whose longest stem matches, or posts with no competing stem, keeps that case out. A restore rule that ignores stems will pull the second story in.

## Overlap with #272

#272 (builder `bc-ac9dba54`) is the grouping fix so real stories clear the 30-post floor. Its planet trace is the planet section above. No grouping code from that builder was available to replay here.

Proposal 2 is #272's work. #275 should not land a parallel attach change. What #275 adds, and #272 did not measure, is the face cut, the stayed-off posts, and the noise-gate counts. The face change and the attach change do not touch the same function. They do interact at the floor: joining the AI fragments makes #266 unnecessary for those planets, and restoring stayed-off posts makes #266 drop fewer stories that the face step had shrunk. The greeting family is in both traces and is not a fold candidate in either.

The before/after yardstick for both is `docs/evidence/275/oct19-pairs.csv`, labeled by a different model, reweighted with the band shares in `oct19-sample-design.json`. `handpicked-pairs.csv` is scored on its own.

## Out of scope

No pipeline edit in this change. No Jev call, no section labeling, no workflow dispatch. `is_duplicate` stays empty. The hand-picked pairs are not mixed into the baseline rate.
