# Oct 19 blind pair sheet

`oct19-pairs.csv` is the yardstick for issue #275. It was cut from the published Oct 19 edition (`data-snapshot` `44a537b`, `last_updated` 2026-10-19, 100,000 posts) before any method change in `docs/specs/275-root-cause-duplicates.md`.

`is_duplicate` is empty on every row. A reviewer on a different model fills that column from the titles and the sample posts. Those labels are the before/after measure. The sheet has no cosine, no band, and no similarity column.

## Draw

Seed `275`. Each level starts its own `random.Random(275)`. Bands are fixed cosine cuts on MiniLM (`all-MiniLM-L6-v2`) centroids of representative posts:

| Band | Cosine |
| --- | --- |
| B0 | −1.01 ≤ cosine < 0.40 |
| B1 | 0.40 ≤ cosine < 0.55 |
| B2 | 0.55 ≤ cosine < 0.70 |
| B3 | 0.70 ≤ cosine < 0.85 |
| B4 | 0.85 ≤ cosine < 1.01 |

Planet rows are pairs of planets inside one solar system (global is one scope). Face rows are pairs of faces inside one solar system, including faces on different planets. The draw takes about 60 rows at each level. Oct 19 planet pairs named in the #272 trace are removed before the planet draw. They are only on `handpicked-pairs.csv`.

`oct19-sample-design.json` records the seed, the band boundaries, each band's share of every same-section pair, the allocation, and the pair id joined back to its cosine. The labeler does not need that file.

## Headline

The sample over-represents rare bands. The duplicate rate is not the share of the 60 rows.

For a population (all same-section planet pairs, or all within-planet face pairs):

`headline = Σ (near-dup rate inside band b) × (band b's share of that population)`

Planet pairs per section divide that reweighted pair count by the 11 solar systems. Face pairs per planet divide the within-planet reweighted pair count by the 107 planets. Cross-planet face pairs stay in the face sample and stay out of the faces-per-planet rate.

Until `is_duplicate` is labeled, the similarity stand-in is representative-centroid cosine ≥ 0.70, applied to the full census and then reweighted. That figure is secondary. Guards-on numbers (30-post floor or `planet_chitchat_reason` on representative posts) are secondary too. The 30-post floor, the junk filter, the stance gate, and the exact-title fold are off for the sample and for the headline.

`handpicked-pairs.csv` is the #272 pairs plus the Oct 20 examples. It is scored on its own. It is not added into the baseline rate. #277 Good Sunday is one planet, so it is in the trace only.

Rebuild:

```bash
python scripts/replay_275_oct19.py \
  --edition /path/to/data_2026-10-19.json \
  --oct20 /path/to/data_2026-10-20.json
```

The script does not call Jev or a label model and does not dispatch a workflow.
