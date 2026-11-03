# Grok-4.7 blind scores for issue #275

Scorer: grok-4.7, after a blind pass. Labels were written from titles and representative posts only. Cosine, band, composer-2.5 `is_duplicate`, and the merge-bar rates were applied only after those files existed. No Jev call, no section labeling, no workflow dispatch, no `--run`.

Sheets:

| File | Rows |
| --- | --- |
| `oct20-pairs-grok.csv` | 60 planet + 36 face |
| `oct20-face-census-grok.csv` | 38 |
| `oct19-planet-pairs-grok.csv` | 60 planet rows. Leaked face rows in `oct19-pairs.csv` were not labeled. |
| `oct19-face-census-grok.csv` | 27 |

A planet pair is a duplicate when a newcomer would see the same story twice. A face pair is a duplicate when the two faces make the same point and do not disagree. Each yes is tagged `greeting/chit-chat`, `same-story fragment`, `paraphrase face`, or `other`. No yes row used `other`.

`unsure` counted as no is the yes rate. `unsure` counted as yes is the yes-or-unsure rate. Planet headlines are band-weighted: labeled rate inside the band, times that band's share of the same-section population. Face headlines use the census, so the band-weighted rate equals the census rate. Pairs per section = rate × population pairs / 11. Pairs per planet = rate × census pairs / planets, which is the yes count (or yes-or-unsure count) divided by the planet count.

## Rates

| Day | Level | Yes / no / unsure | Unsure as no | Unsure as yes |
| --- | --- | --- | ---: | ---: |
| Oct 19 | Planet pairs / section | 14 / 45 / 1 | 0.080749 → **3.5236** | 0.086768 → **3.7862** |
| Oct 19 | Face pairs / planet | 6 / 21 / 0 | 0.222222 → **0.0561** (6/107) | **0.0561** |
| Oct 20 | Planet pairs / section | 2 / 58 / 0 | 0.006337 → **0.2961** | **0.2961** |
| Oct 20 | Face pairs / planet | 12 / 26 / 0 | 0.315789 → **0.1111** (12/108) | **0.1111** |

Populations: Oct 19 planets 480 pairs and 107 planets; Oct 20 planets 514 pairs and 108 planets. The Oct 20 face census is the 38 pairs with two distinct titles. Business Stock Market's two faces titled Market Volatility are `held_out_same_title` and are not in the numerator or the 38. The 36-row face draw is a subset of the census (it leaves out Bad Jobs and Trump Putin Ukraine) and is not the face rate.

These are the weighted rates. The raw pair counts each fix changes, written next to the before and after rates, are in the merge-bar section below and in `merge-bar.csv`.

Oct 19 planet bands (sample n, yes, unsure, no, contribution to the yes rate):

| Band | n | Yes | Unsure | No | Yes contribution | Yes-or-unsure contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 17 | 0 | 0 | 17 | 0 | 0 |
| B1 | 17 | 1 | 0 | 16 | 0.006618 | 0.006618 |
| B2 | 16 | 6 | 0 | 10 | 0.035937 | 0.035937 |
| B3 | 9 | 6 | 1 | 2 | 0.036111 | 0.042130 |
| B4 | 1 | 1 | 0 | 0 | 0.002083 | 0.002083 |

The only unsure is p002, Good Day | Hope For The Day, in B3. Oct 20 planet yes rows are p035 (B3) and p037 (B2). Oct 20 has no B4 planet pairs in the population.

## Agreement with composer-2.5 on Oct 19

Planet rows: **51 of 60** agree. Faces: **19 of 27** agree. Composer-2.5 had 20/38/2 on the planet rows and 13/13/1 on the census. This pass has 14/45/1 and 6/21/0.

Disagreeing planet ids (grok, composer):

| Id | Grok | Composer-2.5 | Pair |
| --- | --- | --- | --- |
| p002 | unsure | yes | Good Day \| Hope For The Day |
| p006 | yes | unsure | Great Time \| Happy Sunday |
| p009 | no | yes | US Iran War \| US Unreliable |
| p019 | no | yes | Thirty Thousand \| The Article |
| p038 | no | yes | Radical Professors \| College Republicans |
| p048 | no | yes | US Ukraine War \| US Iran War |
| p050 | no | yes | Musk Accountability \| Trump Corruption |
| p058 | no | yes | Climate Crisis \| Fires |
| p060 | no | unsure | US Iran War \| Russia Sanctions |

Disagreeing face ids:

| Id | Grok | Composer-2.5 | Pair |
| --- | --- | --- | --- |
| c003 | no | yes | Thirty Thousand \| Debt Impact |
| c006 | no | yes | Hair Preferences \| Hair Remarks |
| c011 | no | yes | Voice Care \| Voice Acting |
| c016 | no | unsure | Weather Changes \| Weather Reports |
| c019 | no | yes | Wrestling Appeal \| Wrestle Dream |
| c023 | no | yes | AI Art Rejected \| Bad Writing |
| c024 | no | yes | Account Suspensions \| Account Deletions |
| c025 | no | yes | Twitter Sucks \| Bluesky vs Twitter |

## Merge bar (a) and (b)

(a) is labeled yes pairs the fix joins or removes. (b) is labeled no pairs the fix joins or removes. Unsure is neither. Pushed-to-Other and posts removed from the edition were already filled and were not recomputed. Guards stay off. `replay_275_score.py` still writes blank (a) and (b) from `merge_bar_rows`; the numbers below are the ones written onto `merge-bar.csv`. Build issues are #286 (fix 1), #287 (fix 2), and #288 (the daypart gate). Keeping dropped-face posts has no build issue yet.

The pass rule is a count across both days. A fix passes (a) only if it resolves at least one labeled-yes pair on each day. It fails if (b) is at least 1 on either day. None of the four fixes pass.

Next to each weighted rate is the raw, unweighted count of labeled pairs that day. Yes resolved, yes still present, and labeled-no pairs wrongly joined or removed are each `N of M` with the pair ids. M is the labeled yes count for the first two, and the labeled no count for the third. Unsure stays out of all three.

A weighted change is flagged when it is smaller than the weight of one label in the band that moved. That change is within the noise of a single label. One label's weight is that band's population share divided by the sample size in the band, then scaled the same way as the headline (× population pairs / 11 for planets, × census pairs / planets for faces). On the face census every pair is one label, so the weight is 1/107 = 0.0093 pairs/planet on Oct 19 and 1/108 = 0.0093 on Oct 20. A change of zero is smaller than every band's one-label weight. A change that equals one label is the noise of that label; fix 2 on Oct 19 is that case (0.2614 pairs/section, B2).

| Fix | Day | Weighted rate | Yes resolved | Yes still present | No wrongly joined or removed | Within one-label noise | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 paraphrase face, cosine ≥ 0.80 unless `local_faces_disagree` | Oct 19 | 0.0561 → 0.0374 face pairs/planet | 2 of 6: c007, c008 | 4 of 6: c001, c015, c017, c018 | 3 of 21: c016, c024, c027 | no (0.0187 is two labels) | fails (b) |
| 1 | Oct 20 | 0.1111 → 0.0741 face pairs/planet | 4 of 12: c002, c025, c037, c038 | 8 of 12: c001, c006, c007, c015, c017, c022, c030, c035 | 3 of 26: c023, c028, c036 | no (0.0370 is four labels) | fails (b) |
| 2 `{ai}` allowlist, both sides under 20 posts, cosine ≥ 0.55 | Oct 19 | 3.5236 → 3.2623 planet pairs/section | 1 of 14: p041 | 13 of 14: p006, p007, p010, p011, p015, p028, p030, p031, p033, p040, p045, p049, p051 | 0 of 45 | yes (equals one B2 label, 0.2614) | fails (a) and (b) |
| 2 | Oct 20 | 0.2961 → 0.2961 planet pairs/section | 0 of 2 | 2 of 2: p035, p037 | 13 of 58: p002, p004, p007, p017, p020, p021, p025, p040, p043, p044, p045, p057, p059 | yes (change 0; one B2 label is 0.1711, one B3 label is 0.125) | fails (a) and (b) |
| 3 keep dropped-face posts | Oct 19 | 3.5236 → 3.5236 planet pairs/section | 0 of 14 | 14 of 14: p006, p007, p010, p011, p015, p028, p030, p031, p033, p040, p041, p045, p049, p051 | 0 of 45 | yes (change 0) | fails (a) |
| 3 | Oct 20 | 0.2961 → 0.2961 planet pairs/section | 0 of 2 | 2 of 2: p035, p037 | 0 of 58 | yes (change 0; smallest planet one-label weight that day is B3 at 0.125) | fails (a) |
| Daypart planet gate (#288) | Oct 19 | 3.5236 → 1.3355 planet pairs/section | 9 of 14: p006, p010, p028, p030, p031, p040, p045, p049, p051 | 5 of 14: p007, p011, p015, p033, p041 | 3 of 45: p005, p016, p029 | no (2.1881 is larger than one label in B2 0.2614, B3 0.2626, or B4 0.0909) | fails (a) and (b); 433 posts removed; 0 pushed to Other |
| Daypart planet gate (#288) | Oct 20 | 0.2961 → 0.2961 planet pairs/section | 0 of 2 | 2 of 2: p035, p037 | 0 of 58 | yes (change 0) | fails (a) and (b); 349 posts removed; 0 pushed to Other |

Fix 1 meets (a) on each day and still fails, because (b) is 3 on both days. `local_faces_disagree` fired on none of the 27 Oct 19 pairs. Six labeled paraphrase faces on Oct 19 and eight on Oct 20 sit under 0.80, so they stay in the still-present count.

Fix 2's only Oct 19 join is p041 AI Control | AI bots (yes, 0.640). That is one labeled-yes pair, so this day alone would meet (a), and (b) is 0 of 45 here. Oct 20 resolves 0 of 2 and wrongly joins 13 of 58, all labeled no. Those thirteen are the small AI planets, including Funny Bsky, and they share the token `ai`. The weighted yes rate does not move on Oct 20 because every joined pair is a no. A raw `specific_stems` join is not this fix. It would also take Oct 19 p010 (yes), p013 (no), p038 (no), p046 (no) and Oct 20 p037 (yes), p053 (no). Those ids stay out of the counts.

Fix 3 moves no sample or census row. Stayed-off posts are not pairs, so it resolves 0 labeled-yes pairs on each day and (b) is 0. It fails (a). It pushes nothing to Other and removes no posts.

The daypart gate drops Oct 19 global Good Morning (383), Other Good Morning (22), Hope For The Day (14), wonderful day (8), and Happy Sunday (6). It resolves 9 of 14 labeled-yes pairs and wrongly removes 3 of 45 labeled-no pairs: p005 Good Morning | JD Vance, p016 Good Morning | Glad Returns, p029 wonderful day | Glad Returns. p002 is unsure and is also unpublished; it is not in any of the three counts. Great Day, Good Day, Great Time, and Glad Returns stay, so p007 and p033 stay published. p011, p015, and p041 are not greeting planets, so they stay in the still-present count too. On Oct 20 the gate drops global Good Sunday (349) and no labeled pair contains that planet, so it resolves 0 of 2. The 349 posts still leave the edition. (b) is already 3 on Oct 19, so the gate fails on both clauses.

## MiniLM ≥ 0.70 and check #276

Of the yes rows, how many the representative-centroid cosine ≥ 0.70 flags. Face sample rows are not counted again; the face census is.

| Kind | Yes rows | Flagged ≥ 0.70 | Missed |
| --- | ---: | ---: | --- |
| greeting/chit-chat | 11 | 7 | p006 0.588, p007 0.675, p028 0.685, p040 0.614 |
| same-story fragment | 5 | 1 | p011 0.530, p015 0.577, p041 0.640, p037 0.564 |
| paraphrase face | 18 | 11 | c001 0.577 and c018 0.691 (Oct 19); c001 0.674, c007 0.672, c015 0.605, c017 0.691, c022 0.693 (Oct 20) |
| other | 0 | 0 | — |

The 0.70 check can see the pairs fix 1 actually joins: every (a) and (b) id for fix 1 is at or above 0.80. It cannot see the paraphrase yeses under 0.70, and fix 1 does not join those either. It does not separate fix 1's good joins from its false joins.

It cannot see fix 2's one good join. p041 is 0.640. The same check does flag several Oct 20 pairs the allowlist joins and this pass called different (p004, p007, p017, p021, p025, p043, p045, all ≥ 0.72). A nightly 0.70 count would move when those planets were merged, and it would be counting labeled-different pairs.

It sees 7 of 11 greeting duplicates and misses four between 0.59 and 0.68, including pairs the daypart gate removes (p006, p028, p040). Fix 3 has no pair row for the check to track.
