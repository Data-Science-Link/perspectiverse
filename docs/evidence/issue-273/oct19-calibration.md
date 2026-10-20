# Oct 19 duplicate-threshold calibration

Yes/no labels from cursor/root-cause-duplicates-3988 docs/evidence/275/oct19-pairs-labeled.csv at 2082bf1. The perspective-definition pass is b62ec0d; planet yes/no did not change after that, and 2c1c384 only reclassified 51 leaked face rows as planet_leak. Those 51 are not in the face score. The labeler is composer-2.5, not Michael. spot-check-20.md has an empty Michael column, so the spot-check ids use the composer label and are kept out of the tune split. Unsure is excluded. Bands and population shares come from oct19-sample-design.json.

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

Tuned threshold: title similarity >= 0.5, centroid cosine >= 0.9 (tune F1 0.8, seed 273).

A band with no predicted positive in the held-out rows has no precision, so it is left out of the precision average. Its share is still listed below.

Band-weighted held-out agreement withheld. Population bands with no yes/no label: B1

Per band:

- B2 (real share 29.6%): precision None, recall None, matched 1
- B3 (real share 51.8%): precision None, recall 0.0, matched 2
- B4 (real share 7.4%): precision None, recall 0.0, matched 1

Tuned on 5 rows, held out 4, spot-check ids in the agreement set 0. Matched 4, unmatched 0.
