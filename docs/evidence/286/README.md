# 286 — paraphrase-face replay (guards off)

Offline replay of `refused_paraphrase_pairs` on published representative posts. A within-planet pair merges when its representative-centroid cosine is at least 0.80 and the posts do not take opposite sides on the free #268 lexicon. Merged posts stay on the larger face. Planets do not change section.

Not applied: the 30-post floor (#266), the junk filter (#264), the post-hoc stance fold (#268), the exact-title fold (#235). No Jev call, no section labeling, no label model, no workflow dispatch.

Editions: `data-snapshot` `44a537b` (`last_updated` 2026-10-19) and `b049731` (`last_updated` 2026-10-20). `b049731` was still the latest published edition when this ran. Later scheduled runs that UTC day did not move `data-snapshot`.

Oct 19 `is_duplicate` is joined from the #275 face census (`oct19-face-census-labels.csv`, 27/27 pairs matched). Oct 20 `is_duplicate` is empty on `oct20-face-pairs-unlabeled.csv` for a blind labeler. `repeat_merged` and `different_merged` on that edition are blank until those labels exist.

Cosines are MiniLM centroids of the published representative posts (at most 36 per face). They are not the full-membership vectors the live split scored.

## Per section

`repeat_merged` is a labeled repeat that merged (good). `different_merged` is a labeled different pair that merged (bad).

| Edition | Section | Faces before | Faces after | Repeat merged / pairs | Different merged / pairs | Unsure merged / pairs | Unlabeled merged / pairs | Posts dropped | Moved to Other |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-10-19 | global | 11 | 10 | 0/0 | 1/1 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | World | 8 | 8 | 0/0 | 0/1 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Politics | 7 | 7 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Business | 14 | 14 | 0/2 | 0/2 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Technology | 13 | 12 | 1/3 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Sports | 14 | 14 | 0/1 | 0/3 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Culture | 16 | 14 | 2/4 | 0/3 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Health | 12 | 12 | 0/2 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Environment | 11 | 10 | 0/0 | 0/0 | 1/1 | 0 | 0 | 0 |
| 2026-10-19 | Education | 14 | 14 | 0/1 | 0/3 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Other | 13 | 13 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | all | 133 | 128 | 3/13 | 1/13 | 1/1 | 0 | 0 | 0 |
| 2026-10-20 | global | 14 | 12 |  |  |  | 2/4 | 0 | 0 |
| 2026-10-20 | World | 12 | 11 |  |  |  | 1/2 | 0 | 0 |
| 2026-10-20 | Politics | 5 | 5 |  |  |  | 0/1 | 0 | 0 |
| 2026-10-20 | Business | 16 | 15 |  |  |  | 1/7 | 0 | 0 |
| 2026-10-20 | Technology | 12 | 12 |  |  |  | 0/2 | 0 | 0 |
| 2026-10-20 | Sports | 15 | 14 |  |  |  | 1/5 | 0 | 0 |
| 2026-10-20 | Culture | 14 | 14 |  |  |  | 0/4 | 0 | 0 |
| 2026-10-20 | Health | 16 | 16 |  |  |  | 0/6 | 0 | 0 |
| 2026-10-20 | Environment | 12 | 12 |  |  |  | 0/2 | 0 | 0 |
| 2026-10-20 | Education | 11 | 11 |  |  |  | 0/3 | 0 | 0 |
| 2026-10-20 | Other | 19 | 18 |  |  |  | 1/3 | 0 | 0 |
| 2026-10-20 | all | 146 | 140 |  |  |  | 6/39 | 0 | 0 |

Oct 19 repeats that merged: Technology Account Suspensions / Account Deletions (0.824); Culture Stream Plans / Burnout (0.895); Culture Show Quality / Show Enjoyment (0.849). The other 10 labeled repeats sit under 0.80 (highest is ADHD Struggles / ADHD Effects at 0.798) and stay two faces.

Oct 19 different pair that merged: global Good Wishes / Night Time (0.856). The lexicon does not see a disagreement. This is the Night Time risk named in the #275 spec. Unsure pair that merged: Environment Weather Changes / Weather Reports (0.818).

200 Oct 19 posts and 375 Oct 20 posts leave a merged-away face and stay on the surviving face. None are dropped. None move to Other.

## Not measured

- Full-membership re-cluster. Member texts are not in the snapshot.
- Whether Oct 20 merges are good or bad. The blind sheet has empty `is_duplicate`.
- Posts that never sat on a published face.
