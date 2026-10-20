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

| Fix | Day | (a) | (b) | Other / posts removed | Verdict |
| --- | --- | ---: | ---: | --- | --- |
| 1 paraphrase face, cosine ≥ 0.80 unless `local_faces_disagree` | Oct 19 | 2 | 3 | 0 pushed, 0 removed | fails (b) |
| 1 | Oct 20 | 4 | 3 | 0 pushed, 0 removed | fails (b) |
| 2 `{ai}` allowlist, both sides under 20 posts, cosine ≥ 0.55 | Oct 19 | 1 | 0 | 0 pushed, 0 removed | passes |
| 2 | Oct 20 | 0 | 13 | 0 pushed, 0 removed | fails (b) |
| 3 keep dropped-face posts | Oct 19 | 0 | 0 | 0 pushed, 0 removed | passes |
| 3 | Oct 20 | 0 | 0 | 0 pushed, 0 removed | passes |
| Daypart planet gate (#288) | Oct 19 | 9 | 3 | 0 pushed, 433 removed | fails (b) and removes posts |
| Daypart planet gate (#288) | Oct 20 | 0 | 0 | 0 pushed, 349 removed | removes posts; (b) does not rise |

Fix 1 resolved ids. Oct 19 (a) c007 The Show, c008 Twitch. (b) c016 Cold Weather, c024 Account Security, c027 Good Wishes | Night Time. `local_faces_disagree` fired on none of the 27. Oct 20 (a) c002 Tesla, c025 Trans Rights Debate, c037 Trans Rights, c038 Trump Putin Ukraine. (b) c023 Social Media Blocks, c028 Dragon Design, c036 Gaza Conflict. Six labeled paraphrase faces on Oct 19 and eight on Oct 20 sit under 0.80, so the bar does not take them.

Fix 2's only Oct 19 join is p041 AI Control | AI bots (yes, 0.640). On Oct 20 the same rule joins 13 pairs, all labeled no: p002, p004, p007, p017, p020, p021, p025, p040, p043, p044, p045, p057, p059. They are the small AI planets, including Funny Bsky, and they share the token `ai`. A raw `specific_stems` join is not this fix. It would also take Oct 19 p010 (yes), p013 (no), p038 (no), p046 (no) and Oct 20 p037 (yes), p053 (no). Those ids stay out of (a) and (b).

Fix 3 moves no sample or census row. Stayed-off posts are not pairs, so (a) and (b) are zero. It pushes nothing to Other and removes no posts.

The daypart gate drops Oct 19 global Good Morning (383), Other Good Morning (22), Hope For The Day (14), wonderful day (8), and Happy Sunday (6). Labeled pairs it unpublishes: (a) p006, p010, p028, p030, p031, p040, p045, p049, p051; (b) p005 Good Morning | JD Vance, p016 Good Morning | Glad Returns, p029 wonderful day | Glad Returns. p002 is unsure and is also unpublished; it is not in (a) or (b). Great Day, Good Day, Great Time, and Glad Returns stay, so p001, p007, p033, and p043 stay published. On Oct 20 the gate drops global Good Sunday (349) and no labeled pair contains that planet, so (a) and (b) are zero. The 349 posts still leave the edition.

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
