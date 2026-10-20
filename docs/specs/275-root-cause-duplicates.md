# 275 — Root cause of duplicate planets and faces

Diagnosis and spec only. This document does not change pipeline behavior.

Oct 19 is the baseline edition: `data-snapshot` `44a537b`, `last_updated` 2026-10-19, 100,000 posts, 107 published planets. The producing run was GitHub Actions `39285647768` (head `cbec72e`). Paid Jev and section labeling stayed off for every replay here. No workflow was dispatched.

The Oct 20 edition is `data-snapshot` `b049731` (`last_updated` 2026-10-20, 100,000 posts, 108 published planets). `origin/main`'s committed `public/data.json` is still the 2026-10-04 file. The site serves the snapshot.

Planet-level duplicates on Oct 19 are the #272 trace ([comment on #275](https://github.com/Data-Science-Link/perspectiverse/issues/275#issuecomment-6293892230)). This spec adopts that trace. The new measurement is faces, posts that stayed off a published face, and `_attach_noise`.

## Headline (guards off)

The labels on `docs/evidence/275/oct19-pairs-labeled.csv` and `docs/evidence/275/oct19-face-census.csv` are **composer-2.5 only**. Michael will not spot-check them. They are a first reading of the Oct 19 sheets. They are not the merge bar below.

The scorer is a blind **grok-4.7** pass, a different model. It re-labels the Oct 19 planet rows and the Oct 19 face census, and it labels the Oct 20 sheets for the first time. Until those labels exist, columns (a) and (b) stay empty.

**Composer-2.5 first reading, planets.** 60 planet rows: 20 yes, 38 no, 2 unsure. Band-weighted yes rate **0.15587**, which is **6.8016 duplicate pairs per section**. Counting unsure with yes: **0.167849**, **7.3243 pairs per section**. Unsure alone contributes 0.011979, all of it in B2. The population is 480 same-section pairs and 11 sections. `pairs per section = rate × 480 / 11`.

**Composer-2.5 first reading, faces.** The original face sample leaked. 51 of the 60 face rows in `oct19-pairs.csv` are not within-planet pairs. They compare single-face planets, which copies planet rows (`f008`=`p023`, `f018`=`p001`, `f019`=`p016`, `f025`=`p004`, `f038`=`p017`, `f042`=`p010`). Those rows are `planet_leak` in the labeled file and are not scored. Every face number below uses `oct19-face-census.csv`: 27 within-planet pairs, same-viewpoint labels, 13 yes, 13 no, 1 unsure. Because it is a census, the yes rate is 13/27 = **0.481481**, which is **0.1215 duplicate face pairs per planet** (13/107). Yes or unsure is 14/27 = **0.518519**, **0.1308 pairs per planet**.

The MiniLM ≥ 0.70 proxy is not a headline. On the planet sample it under-calls 12 rows and over-calls 2. On the face census it under-calls 4 and over-calls 6. The old "26 under, 3 over" figure was the leaked face sample and is withdrawn. The proxy's misses sit mostly at cosine 0.48–0.69 (chitchat, campus politics, Trump geopolitics, anti-AI and oil faces). Its over-calls are high-cosine pairs the stance label calls different (greeting planets, Brewers/Dodgers, French protests/stereotypes, Iran war/ships, Good Wishes/Night Time).

`headline = Σ (labeled rate in band b) × (band b's share of that population)`. An average of the 60 rows is a different number and is not reported.

### Planet bands (composer-2.5, 480 pairs, 60-row sample)

| Band | Cosine | Sample n | Yes | Unsure | No | Share | Yes contribution |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | −1.01 – 0.40 | 17 | 1 | 0 | 16 | 0.735417 | 0.043260 |
| B1 | 0.40 – 0.55 | 17 | 4 | 0 | 13 | 0.112500 | 0.026471 |
| B2 | 0.55 – 0.70 | 16 | 7 | 2 | 7 | 0.095833 | 0.041927 |
| B3 | 0.70 – 0.85 | 9 | 7 | 0 | 2 | 0.054167 | 0.042130 |
| B4 | 0.85 – 1.01 | 1 | 1 | 0 | 0 | 0.002083 | 0.002083 |

Yes contributions sum to 0.15587. B2's yes-or-unsure contribution is 0.053906. The B0 yes is p019, Thirty Thousand | The Article, cosine 0.148. The B4 yes is p010, Great Day | Happy Sunday, cosine 0.852.

### Face census bands (composer-2.5, 27 pairs)

| Band | Pairs | Yes | Unsure | No | Share | Yes contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B1 | 3 | 1 | 0 | 2 | 0.111111 | 0.037037 |
| B2 | 8 | 3 | 0 | 5 | 0.296296 | 0.111111 |
| B3 | 14 | 8 | 1 | 5 | 0.518519 | 0.296296 |
| B4 | 2 | 1 | 0 | 1 | 0.074074 | 0.037037 |

The B3 unsure is c016, Cold Weather, Weather Changes | Weather Reports, cosine 0.818. The B4 no is c027, Good Wishes | Night Time, cosine 0.856: the label says those are different stances.

### What the 0.48–0.69 band still needs

Fixes 1 and 2 do not clear this band. Fix 1's bar is 0.80. Fix 2's measured join is the `{ai}` allowlist at cosine ≥ 0.55, which on this sample is one pair (p041). Lowering cosine is not the missing change. Labeled-no pairs sit in the same band, and a raw `specific_stems` join already false-merges them.

Planet yes rows in 0.48–0.69 that the three fixes leave published: p007 Good Day | Great Time 0.675, p015 Billionaire Power | Ultra Rich 0.577, p038 Radical Professors | College Republicans 0.647, p048 US Ukraine War | US Iran War 0.602. p011 AI Control | AI Adoption 0.530 shares `ai` and both sides have 5 posts, and it stays because 0.530 is under `FOLD_COSINE` 0.55. Waiving 0.55 only for the `{ai}` allowlist would also take p011, and no labeled-no row in the sample shares `ai`. That is a narrower change than lowering the global cosine. It is not in the measured fix-2 rate. p009 US Iran War | US Unreliable 0.496, p050 Musk Accountability | Trump Corruption 0.478, and p058 Climate Crisis | Fires 0.416 are the same shape at the bottom of B1: the label says same story, and no safe stem joins them. p019 at 0.148 is a meta-link, not a similarity miss.

p038 is a labeled yes that a raw stem join would take (`student`, `colleg`). The same rule joins labeled-no p013 Radical Professors | School Medical Care (`dumb`) and p046 Radical Professors | Voucher Program (`stat`, `student`). Those are `unsafe_raw_stem_ids`. They are not removed from the rate.

Face yes rows the 0.80 bar does not touch: c001 High Oil | Oil Prices 0.577, c003 Thirty Thousand | Debt Impact 0.479, c018 Asthma Fatal | Asthma Ban 0.691, c023 AI Art Rejected | Bad Writing 0.607. `local_faces_disagree` did not fire on any of the 27 census pairs, including the labeled disagreements. `local_faces_fold` is true on labeled-no pairs below 0.80 (c002 Tesla, c005 French protests, c009 and c010 voice, c026 Iran). Using the lexicon as the fold signal would raise the over-merge count. A different upstream change is needed for the mid band. The label "same stance" is wider than a subject stem.

## Merge bar

Guards stay off: the #266 floor, the #264 junk filter, the #268 stance gate, and the #235 title fold. A fix has to drop duplicates on **both** the Oct 19 labeled set and the Oct 20 set once grok-4.7 has labeled it, and it fails if either of these rises:

- **(b)** labeled-different pairs that the fix joins or removes (the over-merge count).
- **(c)** posts or planets moved to Other, or dropped, per section. #280 is the shape: the Oct 20 run moved Politics' Fascism (201 posts) and Wealth Inequality (164) to Other, next to Cat Behavior. College Football Playoff (5) and Notre Dame Miami Game (5) leaving Politics was the right move. Fascism and Wealth Inequality were not. Texas (21) and Texas Derogatory (6) moved in the same pass.

**(a)** is the good count: labeled-duplicate pairs removed or joined. (a) and (b) are blank on purpose. grok-4.7 fills them. composer-2.5 does not.

The sheet is `docs/evidence/275/merge-bar.csv`.

| Fix | Day | (a) good | (b) over-merge | Moved to Other | Dropped | Per section | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 paraphrase face | Oct 19 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| 1 paraphrase face | Oct 20 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| 2 attach stem | Oct 19 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| 2 attach stem | Oct 20 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| 3 keep dropped-face posts | Oct 19 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| 3 keep dropped-face posts | Oct 20 | awaiting grok-4.7 | awaiting grok-4.7 | 0 planets, 0 posts | 0 | — | awaiting labels; (c) does not rise |
| Daypart planet gate | Oct 19 | awaiting grok-4.7 | awaiting grok-4.7 | 0 | 5 planets, 433 posts | global Good Morning 383; Other Good Morning 22, Hope For The Day 14, wonderful day 8, Happy Sunday 6 | **fails (c)** |
| Daypart planet gate | Oct 20 | awaiting grok-4.7 | awaiting grok-4.7 | 0 | 1 planet, 349 posts | global Good Sunday 349 | **fails (c)** |
| Published edition, not a #275 fix | Oct 20 | — | — | 6 planets, 402 posts | 0 | Politics → Other: Fascism 201, Wealth Inequality 164, Texas 21, Texas Derogatory 6, College Football Playoff 5, Notre Dame Miami Game 5 (#280, Actions `39417351709`) | baseline already has the (c) shape |

Fixes 1–3 do not call `partition_politics_planets`. They add nothing to the #280 moves. A folded face or a joined planet is (a) or (b) once labeled, not a section move. Fix 3 puts stayed-off posts back on the surviving face, so drops do not rise.

The daypart gate fails (c) on both days because it drops planets. It does not move a Politics planet to Other. Pretty Flowers (Oct 19, daypart share 0.333), Account Security (0.017), and Fall Foliage Season (Oct 20, 0.036) stay. The gate's drops are the greeting planets in the per-section column.

### Files the grok-4.7 pass labels

Leave `is_duplicate` empty until that pass. Do not copy composer-2.5 answers onto Oct 20.

| Path | What it is |
| --- | --- |
| `docs/evidence/275/oct19-pairs.csv` | Oct 19 planet rows only. The face rows leaked. Do not regenerate this file. |
| `docs/evidence/275/oct19-face-census.csv` | 27 within-planet face pairs. Face before/after uses this, not the 60-row face sample. |
| `docs/evidence/275/oct20-pairs.csv` | Oct 20 stratified sample. 60 planet pairs, 36 within-planet face pairs. Unlabeled. |
| `docs/evidence/275/oct20-face-census.csv` | 38 within-planet face pairs, two distinct titles. Unlabeled. |
| `docs/evidence/275/oct20-sample-design.json` | Seed 275, band shares, cosine. Not for the labeler. |
| `docs/evidence/275/merge-bar.csv` | (a) (b) (c) per fix per day. (a) and (b) empty. |

Oct 20 was drawn with the same seed, the same bands, and `validate_label_sheet` before either CSV was written. The face draw is within-planet only. Two hand-picked faces (#278 Bad Jobs, #279 Trump Putin Ukraine) are in the census and out of the 36-row draw. Four hand-picked planet pairs (AI Use / AI Use 2, Data Centers / AI Data Centres, Tesla Flying Roadster / Elon Flying Cars, Cat Behavior / Kitten Behavior) are out of the planet draw. Population behind the draw: 514 same-section planet pairs, 38 labelable within-planet face pairs, 108 planets. Business Stock Market's two faces are both titled Market Volatility (10 and 4 posts). The checker rejects equal titles, so that pair is `held_out_same_title` on the design file and is absent from the census.

## Sampler check

`validate_label_sheet` in `scripts/replay_275_oct19.py` runs before any CSV is written. A face row must have `same_planet` true, one planet on both sides, and two different face titles. A planet row must be two different planets in one section, and must not have `same_planet` true. Sorted endpoints may not repeat, so a face row that copies a planet row fails. Pair ids may not repeat. The Oct 19 sheet was already labeled, and the script refuses to overwrite `oct19-pairs.csv` or `oct19-sample-design.json`.

`tests/test_replay_275_sample.py` covers a valid sheet, the f018 cross-planet leak, equal face titles, a missing `same_planet` flag, one planet named twice, a section string that contains `|`, a face row that copies a planet row, a repeated pair id, the within-planet census order, the overwrite guard, and the empty grok-4.7 columns on the merge bar.

## Good Sunday and the greeting matcher (#277, #208)

Twelve representative posts of global Good Sunday (Oct 20, 349 posts) all get `pleasantry_reason` None. The junk filter on those 12 returns None. `density_labels` made one ball of 349, the floor cannot drop 349, and `catalog_size` keeps the second-largest global planet. None of fixes 1–3 removes it. The Oct 20 run (Actions `39417351709`, 11:51 UTC) finished before #264 merged at 14:43 UTC.

`_greeting` returns false when the post is over 60 words, or `_news` or `_work_topic` matches, or neither `_greeting_wish_body` nor `_standalone_day_wish_body` matches. The wish body only runs when the post opens with a daypart (`_DAYPART_OPEN_RE`). The tail then has to pass `_greeting_tail_only_allowlisted_content`: every substantive token on the allowlist, at most one unknown name-like token, and any token in `_GREETING_NEVER_NAME` rejects the post (`outside`, `frost`, `fall`, `start`, `legs`, `blast`, `wait`, `update`, `downtown`, and the rest of that set). The standalone path needs `_DAY_WISH_PHRASE_RE` ("hope you have a good day", "happy thursday", and a short list like them) and at most 45 words, and the same allowlist.

Which check misses each representative:

| Post | Check that returns false |
| --- | --- |
| "Good morning Kelly… chilly outside… first little frost of the fall." | Opens with a daypart. `kelly` is allowlisted. Hard tokens `outside`, `frost`, `fall`. |
| "Good night everynyan! … work week ahead… stream schedule." | More than one unknown name-like token (`everynyan`, `hopefully`, `ahead`, `schedule`). The rule allows one. |
| "Good morning, Seima! … serene and relaxing Sunday." | Two name-like unknowns (`seima`, `serene`). |
| "Good morning Bob and little ladies… breakfast… laundry… great start." | Hard token `start`, plus many unknowns. 59 words, so the 60-word cap is not the miss. |
| "Have a good rest of your evening. See you in the morning." | Does not open with a daypart. The day-wish phrase regex does not match. |
| "A very good and happy Thursday night… from Liverpool." | The phrase regex matches. The standalone allowlist then fails. |
| "I hope you feel good today." | No daypart. The phrase regex does not match "feel good today". |
| "Good morning… yes the legs… Happy Sinful Sunday." | Hard token `legs`. |
| "good afternoon my friends… madoka goodies… can't wait." | Hard token `wait`. |
| "Good morning… last night was such a blast… wait to update you." | Hard tokens `blast`, `wait`, `update`. |
| "Hope your day was productive… Good evening from downtown Toronto." | The daypart is not the opening. `downtown` is in `_GREETING_NEVER_NAME`. The phrase regex does not match. |
| "Please stay safe…" | No daypart and no day-wish phrase. |

### Upstream rule that was replayed

Drop a planet when at least half of its representative posts have a daypart greeting in the first 8 words, are at most 60 words, and do not trip `_news`, `_work_topic`, or `_GREETING_HARD_TOPIC_RE`. The tail allowlist is not consulted. This is a planet gate after clustering, not a wider ingest drop. Replay is on representative posts, guards off, $0. Runtime of the whole scoring pass is 17.83 seconds.

Oct 19, gate drops: global Good Morning (share 0.605, 383 posts; the junk filter also drops it), Other Good Morning (0.80, 22), Hope For The Day (0.60, 14), wonderful day (1.0, 8), Happy Sunday (1.0, 6). One Happy Sunday card is "HAPPY Monday AFTER the #NoKings #4 March". That planet is already a greeting planet the junk filter drops. It is not a real-story false positive.

Oct 19, gate does not drop: Great Day (share 0.417). The junk filter does drop Great Day (75% chit-chat). Good Day, Great Time, and Glad Returns have no daypart opener in the reps ("Good for you!", "Have a great time!", "Glad you're back") and the junk filter returns None on them. p007 Good Day | Great Time (yes, 0.675) and p033 Good Day | Great Day (yes, 0.766) survive the gate. p033 survives because Great Day is under 0.50 and Good Day is not a daypart planet.

Oct 20, gate drops: global Good Sunday, share 0.667, 349 posts, junk filter None. The frost post above is one of the cards the ingest matcher misses and the planet gate catches.

False positives of this planet gate: none on the two editions. Pretty Flowers is 1 of 3 reps ("Good morning, beautiful Stella! … Possible frost…"), share 0.333, planet stays. Account Security is 1 of 59. Fall Foliage Season is 1 of 28 ("Good morning North Carolinians… bring your outside plants in"). Both stay.

Widening ingest so every daypart opener is chit-chat is not safe. Pretty Flowers, Account Security, and Fall Foliage each have one such representative. Widening it further to catch "good for you" and "have a great time" collides with ordinary replies. The #208 tests require `Thank you, veterans.` to stay (`tests/test_chitchat_guard.py`).

The junk filter stays as the stopgap for pleasantries the daypart gate misses, on purpose, because of that gap and because of #208. It is not a substitute for the planet gate. The gate is what catches Good Sunday. The filter is what still catches Great Day, which the gate's 0.50 line leaves. Neither one catches Good Day, Great Time, or Glad Returns. On the composer-2.5 reading the gate takes the planet headline from 6.8016 pairs per section to 4.6122 (yes) and from 7.3243 to 4.8736 (yes or unsure). That reading is not the scorer. Under the merge bar the gate already fails (c), because those removals are drops.

## Guards on (secondary, cosine proxy)

Applying the 30-post floor (#266) or `planet_chitchat_reason` on representative posts (#264) drops 54 of 107 Oct 19 planets. The reweighted planet proxy falls to 0 pairs per section. The face proxy rises to 0.2407 pairs per planet, because the large-planet face duplicates stay in a smaller denominator. The floor alone drops 53 planets and 548 published posts. #264 on representative posts drops 6 planets: global Good Morning 383, and Other Good Morning 22, Great Day 16, Hope For The Day 14, wonderful day 8, Happy Sunday 6. It does not drop Good Sunday's 12 representatives. #235 finds 0 exact duplicate face titles on Oct 19. On Oct 20, Business Stock Market has two faces both titled Market Volatility. #268's local gate on representative posts folds 11 multi-face planets and leaves The Show at cosine 0.849.

`main` has since taken both guards. #266 set `MIN_PLANET_POSTS = 30` (`ce1564a`). #268 folded same-subject faces that do not disagree (`21736d1`). Oct 19 was produced with the floor at 5 and without that gate. The headlines above are the published edition with both guards held off.

## Where the duplicates are made

Clustering is `density_labels` → `_cohesive_balls` (`pipeline/grouping.py`). Above 12,000 posts the centers come from a 12,000-post sample, seed 0 (`_density_from_sample`). The grid is about one seed per `min_cluster_size` posts (5 on the Oct 19 run). `_BALL_MEMBER` 0.50 peels outliers, `_BALL_MERGE` 0.72 folds centers, `_BALL_MEAN` 0.60 drops a loose ball, then groups under the floor become noise. The author cap is 3 (`_cap_author_posts`). Sections are clustered again on their own posts (`live.py` `_cluster_sections`), same seed and same floor. Section labels are one Jev category call per candidate (`stamp_candidate_sections`); that call was not repeated here.

Attach is `attach_same_story` (`pipeline/story_attach.py`). A sibling folds only into a strictly larger parent of at least `BIG_PLANET` 20 posts, centroid cosine ≥ `FOLD_COSINE` 0.55, and ≥ `SIBLING_MAJORITY` 0.60 of its posts passing `post_matches` on the parent's top stem. Noise joins a parent of at least 20 posts at cosine ≥ `ATTACH_COSINE` 0.42 when `post_matches` passes and a second parent is not within `AMBIGUITY` 0.03. `specific_stems` drops tokens under 4 characters, so "ai", "ps5", and "ps6" never become stems. Do not lower `_BALL_MERGE` or `FOLD_COSINE`.

Faces are `split_perspectives` (`pipeline/perspectives.py`). k-means for k = 2..6, seed 0, three restarts. A cut is invalid when any face is under `MIN_FACE_POSTS` 2 or `MIN_FACE_SHARE` 0.05, when two face centroids are closer than `_FACE_COSINE` 0.90, or when a face is looser than the planet. If no k passes, the planet is one face. The module docstring still mentions a forced second face; `split_perspectives` does not force one. `_draft_planet` (`live.py`) applies the post floor before any name exists, then `_label_faces` drops a face that fails the shared-claim check. `return_same_story_posts` puts a dropped face's posts back only when `post_matches` says they belong to the kept face.

`post_matches` requires the parent's top stem. It then rejects the post when the longest stem in the post is a similar length and is not part of the story (`len(longest) > len(longest_match) + 1` is the only way a longer extra word is ignored).

Section placement after labeling is `partition_politics_planets` (`pipeline/section_sanity.py`, #228). A Politics planet whose member posts miss a fixed keyword list moves to Culture or Other. That is the #280 path. Fixes 1–3 do not go through it.

### Planets (#272, adopted)

Same story, more than one planet, all inside one section:

- Technology. Six planets of 5 posts: AI Generated Articles, AI bots, AI Adoption, AI Creative Effort, Crazy, AI Art. Representative cosine 0.706–0.781. Joined they are 30 posts. Stage: `_merge_same_subject` only merges at 0.72, so the full centers stayed apart, then `_fold_targets` refuses them. None has 20 posts, a parent must be strictly larger, and `specific_stems` drops "ai". AI Control (5 posts, cosine 0.652) does not join on that reading. The composer-2.5 labels call AI Control | AI bots and AI Control | AI Adoption duplicates anyway.
- Culture. Tax Movie Titles (177) and Tax Purposes (25), cosine 0.701. The representative sample passes today's fold. The published edition still has two planets, so the full membership failed a gate this sample passes.
- Health. ADHD Struggles (29) and ADHD Struggles 2 (15). `titles_alike` treats the names as one title. The second planet's posts do not say "adhd". Representative cosine 0.541, under 0.55.
- Education. School Surgeries (33) and School Medical Care (8), cosine 0.701, shared stem "school". `post_matches` hits 3 of 6 representative posts, under the 0.60 majority.

Sports console planets (cosine 0.739–0.820) fail the same attach gates and are not one story. "ps5" and "ps6" are three characters, so they are not stems, and they are not on the allowlist.

Near in embedding, different stories, do not fold: Business Trump Gas Prices / Brent Oil Prices 0.623, Millionaire Definition / Ultra Rich 0.695; World US Ukraine War / Russia Sanctions 0.601; Sports College Football Playoff / BYU vs Notre Dame 0.648; Environment Fires / Coffee Building Fire 0.628; Education Bar Exam / Bits Limited Neighborhood 0.489 (both say "bar"). Lowering `_BALL_MERGE` or `FOLD_COSINE` on cosine alone is the wrong change.

The Other greeting family (Good Day, Good Morning, Great Day, Hope For The Day, wonderful day, Great Time, Glad Returns, Happy Sunday) is one pleasantry family, pairwise cosine about 0.61–0.85, and 14 of the 27 planet pairs at cosine ≥ 0.70. Joining them by cosine would publish one pleasantry planet. They are not a fold candidate.

### Faces

`_FACE_COSINE` 0.90 treats 0.80–0.89 as two views. On Oct 19 the published within-planet pairs at cosine ≥ 0.80 are:

| Section | Planet | Faces | Posts | Cosine | Census | composer-2.5 |
| --- | --- | --- | ---: | ---: | --- | --- |
| Culture | Twitch Streamers | Stream Plans / Burnout | 223 / 10 | 0.895 | c008 | yes |
| global | Good Morning | Good Wishes / Night Time | 376 / 7 | 0.856 | c027 | no |
| Culture | The Show | Show Quality / Show Enjoyment | 111 / 89 | 0.849 | c007 | yes |
| Technology | Account Security | Account Suspensions / Account Deletions | 60 / 33 | 0.824 | c024 | yes |
| Environment | Cold Weather | Weather Changes / Weather Reports | 72 / 61 | 0.818 | c016 | unsure |

`local_faces_disagree` is false on all five. `local_faces_fold` is false only on The Show. The 0.80 bar, which does not consult the lexicon, marks all five `paraphrase_bar`. That includes c027, the labeled different pair. On the composer-2.5 reading the bar takes the face rate from 0.481481 to 0.37037 (0.1215 to 0.0935 pairs per planet) by clearing c007, c008, and c024, and it also clears the unsure c016, so yes-or-unsure falls to the same 0.37037. c027 was already no, so the rate does not show the false fold. If grok-4.7 also calls c027 different, (b) rises and fix 1 fails.

### Posts that stayed off the published face

The Oct 19 log has 53 "stayed off" lines: 1,856 of 7,619 posts in those planets (24.4%). Global membership with no perspective row:

| Planet | Off the published face | Kept | Kept stem | Mean cosine to the kept face | `post_matches` hits |
| --- | ---: | ---: | --- | ---: | ---: |
| Trump Ukraine Sanctions | 257 of 1,116 | 859 | ukrain | 0.559 | 0 |
| Early Voting | 375 of 710 | 335 | early | 0.532 | 0 |
| Good Morning | 62 of 445 | 383 | good | 0.581 | 0 |
| Musk | 16 of 395 | 379 | musk | — | 0 |
| Halloween | 38 of 333 | 295 | halloween | — | 0 |

All 257 Ukraine posts and 373 of 375 Early Voting posts are still within cosine 0.42 of the kept face. Seven of the 257 Ukraine posts contain the substring "ukrain". Stage: `split_perspectives` can open a second face under the 0.90 gate, `_label_faces` drops the face that fails the shared-claim check, and `return_same_story_posts` / `post_matches` does not put the posts back. Those posts were already inside the planet ball. The same veto shrinks a ball under the floor after the face step (Cat Cats 226 → 17 in the log; Early Voting 710 → 335).

### Unassigned and `_attach_noise`

A global replay of `density_labels` (min cluster 5, seed 0) plus the author cap plus `attach_same_story` on the stored 100,000 posts, ordered by `created_at`, with no Jev call:

| | Replay | Oct 19 run log |
| --- | ---: | ---: |
| Candidate planets before attach | 818 | 795 |
| Folded planets | 22 | 22 |
| Folded posts | 706 | 706 |
| Posts attached from noise | 8,952 | 8,568 |
| Noise after attach | 59,162 | 59,553 excluded |

The fold counts match the run. Noise gate, against 338 parents of at least 20 posts that have a stem: would attach 8,983; ambiguous 439; cosine ≥ 0.42 and stem fail 28,047 (2,026 of them at cosine ≥ 0.55); stem matches but cosine 0.35–0.42 is 2,551; cosine under 0.42 is 30,645.

Sibling gate: 204 pairs at cosine ≥ 0.55 with both sides under 20 posts, 16 pairs blocked because the parent is not strictly larger, 2,227 pairs under the sibling majority. The majority examples are dominated by one 158-post ball whose top stem is empty. That is not a missed duplicate.

### Oct 20 trace

These rows are on `handpicked-pairs.csv` only. They are not in the Oct 20 baseline draw. Cosines are representative centroids.

| Section | Pair | Posts | Cosine | Stage |
| --- | --- | ---: | ---: | --- |
| Technology | AI Use / AI Use 2 | 5 / 5 | 0.754 | Same attach failure as the Oct 19 AI fragments. Faces: AI Use, and AI Not Welcome. |
| Technology | Data Centers / AI Data Centres | 120 / 5 | 0.709 | Parent is already over 20. Data Centers faces Harm 108 / Data Collection 12, cosine 0.740. |
| Business | Tesla Flying Roadster / Elon Flying Cars | 112 / 9 | 0.616 | Above 0.55, parent larger. Stem or the 0.60 majority held. Tesla faces Fails 90 / Overhyped 22, cosine 0.846. |
| Other | Cat Behavior / Kitten Behavior | 37 / 12 | 0.753 | Parent clears 20. Kitten faces Kitten Behavior 9 / Kitten Lessons 3, cosine 0.693. |

#278. Global Bad Jobs, 344 posts. Faces Bad Jobs 258 and Short Lived Jobs 86, cosine 0.752. The Business-section planet is Bad First Jobs, 329 posts, one face. #279. Global Trump Putin Ukraine, 1,038 posts. Faces Trump Helps Russia 1,019 and Trump Supports Putin 19, representative cosine 0.939. The World-section planet is 835 posts and one face. Representative centroids sit past `_FACE_COSINE` 0.90. Full-membership centroids were not replayed. #277 is the greeting section above.

## What each root fix retires

| Guard | Attach / stem (#272) | Face cut inside `split_perspectives` | Keep dropped-face posts | Daypart planet gate |
| --- | --- | --- | --- | --- |
| #266 30-post floor | Retires it for the AI fragments only. Bar Exam (23), BYU (17), and genuine small stories still need a floor. | No | Shrinks the set of stories the floor drops after a face was discarded. Does not retire the floor. | No |
| #264 junk / pleasantry | No. Joining greetings by cosine would publish the pleasantry. | No | No | Does not retire it. The gate misses Great Day (0.417) and misses Good Day / Great Time / Glad Returns. The filter stays for that residue. See #208. |
| #268 stance gate | No | Only for pairs at or above 0.80 whose posts do not disagree. It misses the 0.48–0.69 band, and on this census it also marks the labeled-no Night Time pair. | No | No |
| #235 exact-title face fold | No | The second face is not published, so a duplicate title is not minted. Oct 19 had 0. Oct 20 Stock Market has two faces titled Market Volatility; that run did not have #235. | No | No |
| #265 label guard | No | No | No | No |
| #280 Politics → Other | No. Attach does not move a section. | No | No | No. The gate drops greeting planets. It does not move Fascism or Wealth Inequality. |

## Method changes

Ranked by the composer-2.5 drop, which is the first reading, not the pass/fail. The pass/fail is the merge bar: both days, guards off, (b) does not rise, (c) does not rise. All three proposals are local. None adds a model call. The Oct 19 producing run spent $0.118 on DeepInfra (1,046 calls) and $0.032 on Jev (795 calls). The Oct 20 scheduled run spent $0.129 and $0.031. These changes add $0 a day. The scoring pass that produced the first reading took 17.83 seconds and $0.

The daypart planet gate moves the planet headline more than fix 2 on the composer-2.5 reading, and it already fails (c). It is specified in the greeting section. It is not one of the three method changes.

### 1. Refuse a paraphrase face in the split

In `split_perspectives`, a second face is a paraphrase when the face centroids are at or above 0.80, unless the posts disagree. The disagreement check replayed here is `local_faces_disagree` on the census sample texts. It fired on none of the 27 pairs. Do not add a paid stance pass. Do not treat `local_faces_fold` as the fold signal: it is true on labeled-no pairs below 0.80.

Composer-2.5 effect, guards off: faces yes 0.481481 → 0.37037 (0.1215 → 0.0935 pairs per planet). Yes or unsure 0.518519 → 0.37037 (0.1308 → 0.0935). Planets do not move. Resolved census ids: c007 The Show (yes, lexicon fold false), c008 Twitch (yes), c024 Account Security (yes), c016 Cold Weather (unsure), c027 Good Wishes | Night Time (no). The mid-band face yes rows (c001, c003, c018, c023) stay. (c) does not rise on either day. (a) and (b) are awaiting grok-4.7. If that pass agrees that c027 is different, (b) rises and this fix fails.

Risk: Night Time is 7 posts against Good Wishes, and the census already calls them different stances. The geometric bar folds that minority because the disagreement check does not see it.

### 2. Let same-subject fragments join before the floor

This is #272's change. #275 does not carry a second attach implementation.

`_fold_targets` requires a strictly larger parent of at least 20 posts, and `specific_stems` drops any token under 4 characters. Two sub-20 balls may join when they share an allowlisted short stem and the centroid cosine is at least 0.55. The allowlist is `{ai}`. It is not `bar`, `ps5`, or `ps6`. Do not lower `_BALL_MERGE` or `FOLD_COSINE`.

A raw `specific_stems` intersection on the sample texts is not this fix. It joins labeled-no p013 and p046, and it joins p038 and the greeting pair p010. Those ids are `unsafe_raw_stem_ids`.

Composer-2.5 effect, guards off: the measured fix resolves p041 AI Control | AI bots (yes, 0.640, both 5 posts). Planets yes 0.15587 → 0.149881 (6.8016 → 6.5403 pairs per section). Yes or unsure 0.167849 → 0.16186 (7.3243 → 7.063). Faces do not move. p011 stays, because its cosine is 0.530. (c) does not rise on either day. (a) and (b) are awaiting grok-4.7.

Risk: a longer allowlist over-merges. The stem list is the control. Console fragments and the greeting family stay off it.

### 3. Keep a dropped face's posts on the surviving face

When `_label_faces` drops a face, posts already inside the planet ball should remain on the surviving face unless they are a different story. `return_same_story_posts` currently requires the kept face's top stem, and the longest-stem veto then rejects a post that contains the subject and another word of similar length. On the global membership that veto hit 0 of 257 Ukraine posts and 0 of 375 Early Voting posts.

Composer-2.5 effect on the pair rates: none. Those posts are not rows in the sample or the census. The indirect effect is the floor (Cat Cats 226 → 17; Early Voting 710 → 335). The same `post_matches` path blocks `_attach_noise` (28,047 posts at cosine ≥ 0.42 fail the stem). Loosening it for noise is a different, larger change. Do it only for posts that were members of the planet and lost their face. (c) does not rise: the change restores posts, and it does not move a planet to Other. (a) and (b) are awaiting grok-4.7.

Risk: the veto exists so a second story inside the ball does not attach. Zionism posts in a Gaza planet are the case `story_of` already documents. A restore that ignores stems pulls that second story in.

## Overlap with #272

#272 (builder `bc-ac9dba54`) is the grouping fix so real stories clear the 30-post floor. Its planet trace is the planet section above. No grouping code from that builder was available to replay here.

Proposal 2 is #272's work. #275 should not land a parallel attach change. What #275 adds is the face cut, the stayed-off posts, the noise-gate counts, the greeting-matcher trace, and the Oct 20 out-of-sample sheets. The face change and the attach change do not touch the same function. They meet at the floor: joining the AI fragments makes #266 unnecessary for those planets, and restoring stayed-off posts makes #266 drop fewer stories the face step had shrunk. The greeting family is not a fold candidate in either spec.

## Out of scope

No pipeline edit in this change. No Jev call, no section labeling, no workflow dispatch. `is_duplicate` on `oct19-pairs.csv`, `oct20-pairs.csv`, and `oct20-face-census.csv` stays empty. The hand-picked pairs are not mixed into the baseline rate. composer-2.5 does not fill the merge bar.
