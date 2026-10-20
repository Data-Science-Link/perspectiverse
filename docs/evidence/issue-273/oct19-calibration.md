# Oct 19 duplicate-threshold calibration

Planet yes/no labels from cursor/root-cause-duplicates-3988 docs/evidence/275/oct19-pairs-labeled.csv. Face yes/no labels from docs/evidence/275/oct19-face-census.csv, the within-planet census. The 60-row face sample is not used: 51 of those rows were planet pairs. The labeler is composer-2.5, not Michael. spot-check-20.md has an empty Michael column, so those ids use the composer label and stay out of the tune split. Unsure is excluded. Planet bands and shares come from oct19-sample-design.json. A face percentage is withheld below 30 held-out pairs.

Source commit: 2082bf1.
Edition date: 2026-10-19.

## Planets

Tuned threshold: title similarity >= 0.5, centroid cosine >= 0.9 (tune F1 0.1517, seed 273).

A band with no predicted positive in the held-out rows has no precision, so it is left out of the precision average. Its share is still listed below.

Band-weighted held-out agreement: precision 0.3251, recall 0.0512.

Per band:

- B0 (real share 73.5%): precision None, recall None, matched 7
- B1 (real share 11.2%): precision 0.0, recall 0.0, matched 8
- B2 (real share 9.6%): precision None, recall 0.0, matched 6
- B3 (real share 5.4%): precision 1.0, recall 0.25, matched 5
- B4 (real share 0.2%): precision None, recall 0.0, matched 1

Tuned on 31 rows, held out 19, spot-check ids in the agreement set 8. Matched 27, unmatched 0.

## Faces

Tuned threshold: title similarity >= 0.5, centroid cosine >= 0.55 (tune F1 0.8889, seed 273).

Held-out agreement: 9 of 16 agree.
Held-out set is 17, under 30. No face percentage. Pooling more days of face pairs is the path to a real rate.

Per band:

- B1 (real share 11.1%): 1 of 2 agree
- B2 (real share 29.6%): 3 of 5 agree
- B3 (real share 51.8%): 5 of 8 agree
- B4 (real share 7.4%): 0 of 1 agree

Tuned on 9 rows, held out 7, spot-check ids in the agreement set 10. Matched 16, unmatched 1.

## Recall by duplicate kind

Every model-labeled duplicate on the Oct 19 planet sheet and the face census. The nightly check flags a pair when titles look alike or the TF-IDF centroid cosine is at least 0.90. Counts are raw. `planet_leak` rows are not included.

- Greeting/chit-chat planets (#288): 0 of 11
  The nightly check can't track this fix. The kind count uses per-post agreement, not a greeting-title list.
- Same-story fragments (#287): 1 of 9
  Flagged: US Ukraine War | US Iran War.
  The nightly check can't track this fix. The kind count uses shared surface entities, not stems.
- Paraphrase faces (#286): 0 of 13
  The nightly check can't track this fix. The kind count uses per-post agreement, not the face centroid.
- Other: 0 of 0

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
