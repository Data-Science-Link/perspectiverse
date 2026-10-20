# Pair sheets for issue #275

Two days, same draw. `is_duplicate` on a sheet handed to a labeler is empty. The sheet has no cosine, no band, and no similarity column. Those live in the design JSON.

## Oct 19

`oct19-pairs.csv` is the planet yardstick. Seed 275, 60 planet pairs and 60 face rows, cut from `data-snapshot` `44a537b` (`last_updated` 2026-10-19) before any method change. Do not regenerate it. The planet pair ids are the labeled yardstick.

The face rows in that file leaked. 51 of 60 are cross-planet pairs, and six copy a planet row (`f008`=`p023`, `f018`=`p001`, `f019`=`p016`, `f025`=`p004`, `f038`=`p017`, `f042`=`p010`). Face numbers use `oct19-face-census.csv`, the 27 within-planet pairs. See `label-definitions.md`.

The labels on `oct19-pairs-labeled.csv` and `oct19-face-census.csv` are composer-2.5 only. Michael is not spot-checking them. The merge bar waits for a blind grok-4.7 re-label.

## Oct 20

`oct20-pairs.csv` is the out-of-sample sheet: seed 275, the same bands, guards off, from `data-snapshot` `b049731` (`last_updated` 2026-10-20). 60 planet pairs and 36 within-planet face pairs. `is_duplicate` is empty.

`oct20-face-census.csv` is every within-planet pair with two distinct face titles (38 rows), also unlabeled. The face sample is a subset. #278 and #279 stay in the census and are left out of the 36-row draw. Business Stock Market has two faces that share the title Market Volatility (10 and 4 posts). The pre-label check rejects a row whose titles match, so that pair is not on the census. It is recorded on `oct20-sample-design.json` as `held_out_same_title`.

`validate_label_sheet` in `scripts/replay_275_oct19.py` runs before either Oct 20 CSV is written. A face row must have `same_planet` true and two distinct faces of one planet. A planet row must be two different planets in one section. No row may repeat another row's endpoints. Tests live in `tests/test_replay_275_sample.py`.

## Draw

Seed `275`. Each level starts its own `random.Random(275)`. Bands:

| Band | Cosine |
| --- | --- |
| B0 | −1.01 ≤ cosine < 0.40 |
| B1 | 0.40 ≤ cosine < 0.55 |
| B2 | 0.55 ≤ cosine < 0.70 |
| B3 | 0.70 ≤ cosine < 0.85 |
| B4 | 0.85 ≤ cosine < 1.01 |

Planet rows are two planets in one solar system (global is one scope). Face rows are two faces of one planet. Hand-picked pairs stay on `handpicked-pairs.csv` and out of the stratified draw. Band shares still count the full population.

## Headline and merge bar

`headline = Σ (labeled rate in band b) × (band b's share of that population)`. The unweighted mean of the sample is not the headline. `unsure` is its own count, held out of yes, and included in yes-or-unsure.

Planet pairs per section use the 480 Oct 19 same-section pairs and 11 sections. Face pairs per planet on Oct 19 use the 27-row census and 107 planets.

The merge bar is `merge-bar.csv`. For each fix and each day it has (a) labeled duplicates removed or joined, (b) labeled-different pairs joined or removed, planets and posts pushed to Other, and posts removed from the edition. Removed posts do not show up in Other. (a) and (b) are empty until grok-4.7 labels them. Each row names its build issue: #286, #287, #288, or needs a new issue. A fix fails if (b) rises or if anything new is pushed to Other. #288 removes posts. Guards stay off.

`handpicked-pairs.csv` is scored on its own. It is not added to the baseline rate.
