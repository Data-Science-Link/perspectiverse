# Edition self-check

Pass rate **81.3%** (87 of 107 planets, 20 failed).

- Edition date: 2026-10-19
- Source: /tmp/oct19/data.json
- Snapshot commit: 44a537b
- Post floor (`min_planet_posts`): 5
- Face signal: titles_alike
- This check does not change the edition.

## Duplicate rate

Near-duplicate when titles_alike, or when representative-post TF-IDF centroid cosine >= 0.9.

Before is the grouping. After reapplies the floor, the junk filter, and the face fold on a copy. The edition is not changed.

### Before the guards

- Planets (clustering/attach): 0.1% (5 of 5460 pairs). Day-over-day +0.0 pp from 2026-10-18.
- Faces (faces/stance): 0.0% (0 of 26 pairs). Day-over-day -4.5 pp from 2026-10-18.

### After the guards

- Planets (clustering/attach): 0.1% (5 of 5253 pairs). Day-over-day +0.0 pp from 2026-10-18.
- Faces (faces/stance): 0.0% (0 of 26 pairs). Day-over-day 0.0 pp from 2026-10-18.

Guards removed 0 planets under the floor, 3 junk planets, and folded 0 faces.

The labeled sample is not in the tree yet, so the threshold stays at the default and precision and recall are not computed. When it lands, the headline weights each similarity band by that band's real share of pairs. This rate does not grade itself.

## Where to fix

- ingest: 3 planets
- clustering/attach: 0 planets
- faces/stance: 0 planets
- labeling: 17 planets

## Failures by check

- title_fit: 11 planets
- label: 7 planets
- junk: 3 planets
- faces_different: 0 planets
- post_floor: 0 planets

## Thin sections

- World (clustering/attach): 7 published planets, solar system holds 10
- Politics (clustering/attach): 7 published planets, solar system holds 10

## 30-post floor revisit (not a failure yet)

min_planet_posts is 5, so these are not failures and this check does not drop them. #266 sets the floor to 30 in clustering/attach.
- 53 published planets have fewer than 30 posts. Stage: clustering/attach.
- Sections that would look thin at that floor: World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, Other.

## Top failing planets

- Education / Cafeteria Duty (6 posts): title_fit → labeling, label → labeling
- Business / Trump Regime (9 posts): title_fit → labeling
- Culture / Funny (90 posts): label → labeling
- Culture / Tax Purposes (25 posts): title_fit → labeling
- Culture / Twitch Streamers (233 posts): title_fit → labeling
- Education / Bits Limited Neighborhood (9 posts): label → labeling
- Education / Bully Bullies Bullying (6 posts): label → labeling
- Education / School Medical Care (8 posts): title_fit → labeling
- Environment / Angeles Cities Heat (8 posts): label → labeling
- Environment / Pretty Flowers (6 posts): title_fit → labeling
- Health / ADHD Struggles 2 (15 posts): title_fit → labeling
- Health / Medical Appointments (11 posts): title_fit → labeling
- Health / Mental Health Struggles (17 posts): title_fit → labeling
- Other / Good Morning (22 posts): junk → ingest
- Other / Pet Benefits (17 posts): title_fit → labeling
- … 5 more in the JSON report
