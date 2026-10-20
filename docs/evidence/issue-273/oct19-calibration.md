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
