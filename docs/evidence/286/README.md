# 286 — paraphrase-face replay (guards off)

Offline replay of `refused_paraphrase_pairs` on published representative posts. A within-planet pair merges only when its representative-centroid cosine is at least 0.80 and both faces' posts take the same side of the same named actors. A face with no poled posts is not agreement. The same sign aimed at different named actors is not agreement. Merged posts stay on the larger face. Planets do not change section.

Not applied: the 30-post floor (#266), the junk filter (#264), the post-hoc stance fold (#268), the exact-title fold (#235). No Jev call, no section labeling, no label model, no workflow dispatch.

Editions: `data-snapshot` `44a537b` (`last_updated` 2026-10-19) and `b049731` (`last_updated` 2026-10-20). `b049731` was still the latest published edition when this ran. Later scheduled runs that UTC day did not move `data-snapshot`.

Oct 19 `is_duplicate` is joined from the #275 face census (`oct19-face-census-labels.csv`, 27/27 pairs matched). c027 Good Wishes / Night Time stays `no`. It is not relabeled. Oct 20 `is_duplicate` is empty on `oct20-face-pairs-unlabeled.csv` for a blind labeler. `repeat_merged` and `different_merged` on that edition are blank until those labels exist.

The replay uses up to 36 published representative posts per face. These snapshots have no member embeddings and no member texts, so it cannot be re-run on live full membership.

`forced_cut_planets_changed` is 0 on both days. `split_perspectives` on main already returns one face when no k passes, with `forced` false. It does not call `force_two_labels`. The module docstring on main still described that cut; the function body did not. This change does not add or remove one. `planets_two_to_one` below is only the paraphrase gate.

## Per section

`repeat_merged` is a labeled repeat that merged (good). `different_merged` is a labeled different pair that merged (bad).

| Edition | Section | Faces before | Faces after | Repeat merged / pairs | Different merged / pairs | Unsure merged / pairs | Unlabeled merged / pairs | Posts dropped | Moved to Other | Planets 2 to 1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-10-19 | global | 11 | 11 | 0/0 | 0/1 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | World | 8 | 8 | 0/0 | 0/1 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Politics | 7 | 7 | 0/0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Business | 14 | 14 | 0/2 | 0/2 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Technology | 13 | 13 | 0/3 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Sports | 14 | 14 | 0/1 | 0/3 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Culture | 16 | 16 | 0/4 | 0/3 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Health | 12 | 12 | 0/2 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Environment | 11 | 11 | 0/0 | 0/0 | 0/1 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Education | 14 | 14 | 0/1 | 0/3 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | Other | 13 | 13 | 0/0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 |
| 2026-10-19 | all | 133 | 133 | 0/13 | 0/13 | 0/1 | 0/0 | 0 | 0 | 0 |
| 2026-10-20 | global | 14 | 14 |  |  |  | 0/4 | 0 | 0 | 0 |
| 2026-10-20 | World | 12 | 12 |  |  |  | 0/2 | 0 | 0 | 0 |
| 2026-10-20 | Politics | 5 | 5 |  |  |  | 0/1 | 0 | 0 | 0 |
| 2026-10-20 | Business | 16 | 15 |  |  |  | 1/7 | 0 | 0 | 1 |
| 2026-10-20 | Technology | 12 | 12 |  |  |  | 0/2 | 0 | 0 | 0 |
| 2026-10-20 | Sports | 15 | 15 |  |  |  | 0/5 | 0 | 0 | 0 |
| 2026-10-20 | Culture | 14 | 14 |  |  |  | 0/4 | 0 | 0 | 0 |
| 2026-10-20 | Health | 16 | 16 |  |  |  | 0/6 | 0 | 0 | 0 |
| 2026-10-20 | Environment | 12 | 12 |  |  |  | 0/2 | 0 | 0 | 0 |
| 2026-10-20 | Education | 11 | 11 |  |  |  | 0/3 | 0 | 0 | 0 |
| 2026-10-20 | Other | 19 | 19 |  |  |  | 0/3 | 0 | 0 | 0 |
| 2026-10-20 | all | 146 | 145 |  |  |  | 1/39 | 0 | 0 | 1 |

Posts dropped: 0. Moved to Other: 0. Posts kept on the surviving face: 0 on Oct 19, 22 on Oct 20.

Oct 19 labeled repeats at or above 0.80 stay split. Their representative posts do not hold one shared pole, so there is no positive evidence they are the same stance: Technology Account Suspensions / Account Deletions (0.824), Culture Stream Plans / Burnout (0.895), Culture Show Quality / Show Enjoyment (0.849). The other 10 labeled repeats sit under 0.80 (highest is ADHD Struggles / ADHD Effects at 0.798) and stay two faces for that reason. c027 Good Wishes / Night Time (0.856) stays labeled `no` and stays split. Environment Weather Changes / Weather Reports (0.818, unsure) stays split.

Oct 20 unlabeled merge: Business Tesla Fails / Tesla Overhyped (0.846). Both faces condemn (8/36 and 3/10) and neither cue attaches to a named actor in the lexicon, so the gate treats them as the same side. 22 posts stay on the surviving face. The planet goes from 2 faces to 1. The blind sheet does not say whether that merge is good.

Pairs the review named, all kept:

| Pair | Cosine | Poles | Why the split stays |
| --- | ---: | --- | --- |
| u001 Trump Helps Russia / Trump Supports Putin | 0.939 | -1 / 0 | Accusatory "supporting Putin" is not the speaker endorsing. Two endorse posts out of 19 do not hold a pole. No pole is not agreement. |
| u002 Trans Hate / Trans Rights | 0.871 | 0 / 0 | Both faces mix advocacy. Trans Hate is 3 condemn and 3 endorse out of 36. Trans Rights is 4 condemn and 2 endorse out of 36. Quoted and attributed endorse cues are not the speaker's. Neither face holds a pole, so mixed advocacy is not positive evidence of one shared side. |
| u003 Israel Condemned / Israel Influence | 0.869 | -1 / 0 | Influence does not hold a pole (4 endorse and 1 condemn out of 36). |
| u005 Israel Condemned / Israel Defends | 0.832 | -1 / -1 | Both condemn, and the cues attach to different actors (Israel, Hamas). Same sign, different actor, is not the same stance. |

## Not measured

- Full-membership re-cluster. The snapshots have no member embeddings and no member texts. The replay is the published representatives, at most 36 per face.
- Whether the Oct 20 Tesla merge is good or bad. The blind sheet has empty `is_duplicate`.
- Whether Oct 19 repeats such as The Show are the same stance in a reading the lexicon cannot see. They stay split because neither face holds a pole.
- Posts that never sat on a published face.
- Independent grok-4.7 labels for c027. `oct19-face-census-grok.csv` was not on this branch. c027 is reported as the existing census label, `no`.
