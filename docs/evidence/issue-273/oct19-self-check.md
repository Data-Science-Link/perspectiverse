# Edition self-check

Pass rate **41.1%** (44 of 107 planets, 63 failed).

- Edition date: 2026-10-19
- Source: /tmp/oct19/data.json
- Snapshot commit: 44a537b
- Post floor (`min_planet_posts`): 30
- Face signal: local_faces_fold+titles_alike
- This check does not change the edition.

## Duplicate rate

Near-duplicate when titles_alike, or when representative-post TF-IDF centroid cosine >= 0.9.

Before is the grouping. After reapplies the floor, the junk filter, the stance gate, and the face fold on a copy. The edition is not changed.

### Before the guards

- Planets (clustering/attach): 0.1% (5 of 5460 pairs). Day-over-day +0.0 pp from 2026-10-18.
- Faces (faces/stance): 0.0% (0 of 26 pairs). Day-over-day -4.5 pp from 2026-10-18.

### After the guards

- Planets (clustering/attach): 0.2% (3 of 1326 pairs). Day-over-day +0.1 pp from 2026-10-18.
- Faces (faces/stance): 0.0% (0 of 7 pairs). Day-over-day 0.0 pp from 2026-10-18.

Guards removed 53 planets under the floor, 1 junk planets, folded 9 faces at the stance gate, and 0 more by title.

The labeled sample is not in the tree yet, so the threshold stays at the default and precision and recall are not computed. When it lands, the headline weights each similarity band by that band's real share of pairs. This rate does not grade itself.

## Kind counts

Report only. These counts do not change the edition and do not replace the duplicate score. Each signal is different from the fix it is watching, so the fix cannot zero the count by being the same rule.

- Greeting planets: 11. Per-post sparsity or pairwise agreement inside the planet. Not the greeting matcher, the daypart gate, or a title list.
- Fragments: 16 same-section pairs whose titles share an acronym or a digit token, both under the tuned post cap. Not stem overlap and not the attach gate's 20-post parent.
- Face agreement: 21 within-planet pairs. Highest cosine between one post on each face. Not the face centroid and not the stance fold.

Held-out recall, seed 273. Tuned on two-thirds of each band. Recall is the held-out third plus spot-check ids.

- Greeting planets: 6 of 6 labeled yes, 0 false flags on 16 labeled no.
- Fragments: 1 of 5 labeled yes, 0 false flags on 16 labeled no.
- Face agreement: 8 of 8 labeled yes, 7 false flags on 9 labeled no.

Weekly blind sample is off: 20 planet pairs and 10 face pairs, seed 27343 (273 plus the ISO week). Expected second-model cost at $0.042 per million input tokens (2026-10-08): $0.000907 per week, $0.000130 per day. The daily budget is $0.25 to $0.30. No paid call is made in this check.

## Where to fix

- ingest: 6 planets
- clustering/attach: 53 planets
- faces/stance: 11 planets
- labeling: 17 planets

## Failures by check

- post_floor: 53 planets
- faces_different: 11 planets
- title_fit: 11 planets
- label: 7 planets
- junk: 6 planets

## Thin sections

- World (clustering/attach): 7 published planets, solar system holds 10; 3 planets clear the 30-post floor, solar system holds 10
- Politics (clustering/attach): 7 published planets, solar system holds 10
- Business (clustering/attach): 4 planets clear the 30-post floor, solar system holds 10
- Technology (clustering/attach): 3 planets clear the 30-post floor, solar system holds 10
- Sports (clustering/attach): 5 planets clear the 30-post floor, solar system holds 10
- Culture (clustering/attach): 9 planets clear the 30-post floor, solar system holds 10
- Health (clustering/attach): 4 planets clear the 30-post floor, solar system holds 10
- Environment (clustering/attach): 4 planets clear the 30-post floor, solar system holds 10
- Education (clustering/attach): 1 planets clear the 30-post floor, solar system holds 10
- Other (clustering/attach): 4 planets clear the 30-post floor, solar system holds 10

## Top failing planets

- Education / Cafeteria Duty (6 posts): title_fit → labeling, label → labeling, post_floor → clustering/attach
- Business / Trump Regime (9 posts): title_fit → labeling, post_floor → clustering/attach
- Culture / Tax Purposes (25 posts): title_fit → labeling, post_floor → clustering/attach
- Culture / Twitch Streamers (233 posts): title_fit → labeling, faces_different → faces/stance
- Education / Bits Limited Neighborhood (9 posts): label → labeling, post_floor → clustering/attach
- Education / Bully Bullies Bullying (6 posts): label → labeling, post_floor → clustering/attach
- Education / School Medical Care (8 posts): title_fit → labeling, post_floor → clustering/attach
- Environment / Angeles Cities Heat (8 posts): label → labeling, post_floor → clustering/attach
- Environment / Pretty Flowers (6 posts): title_fit → labeling, post_floor → clustering/attach
- Health / ADHD Struggles (29 posts): faces_different → faces/stance, post_floor → clustering/attach
- Health / ADHD Struggles 2 (15 posts): title_fit → labeling, post_floor → clustering/attach
- Health / Medical Appointments (11 posts): title_fit → labeling, post_floor → clustering/attach
- Health / Mental Health Struggles (17 posts): title_fit → labeling, post_floor → clustering/attach
- Other / Good Morning (22 posts): junk → ingest, post_floor → clustering/attach
- Other / Great Day (16 posts): junk → ingest, post_floor → clustering/attach
- … 48 more in the JSON report
