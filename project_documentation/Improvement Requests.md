# Improvement requests

Living log of requested changes. Nothing in this file is implemented. Keep adding requests until told the list is done.

## 1. Morning Bluesky quantity loop

The north star for how many Bluesky posts we keep is the threshold: **10,000**.

Each morning, run one fetch loop, then retire. The loop pulls fresh posts until both of these are true:

- The retained set can reach the threshold (10,000).
- Today’s new posts are at least **1/7 of the threshold** (10,000 / 7, about 1,429).

Keep fetching while the eligible set is still under 10,000 **or** today’s additions are still under 1/7 of the threshold. A large shortfall already covers the daily minimum, so the loop just fills to 10,000. A small shortfall does not: still pull the full 1/7.

Then retire:

1. Drop posts older than 7 days.
2. If the 1/7 refresh (plus whatever was still eligible) leaves the set **over** the threshold, scrap the oldest posts until it is back at 10,000. Those posts can be younger than 7 days.

Posts older than 7 days are not part of the 10,000. The loop should finish the morning at the threshold when Bluesky can supply the posts, with at least 1/7 of the threshold fetched that day, and with nothing older than 7 days left in the set.

### How a morning ends

| Starting eligible posts (already under 7 days) | Fetch at least | Then |
| --- | --- | --- |
| 0 | 10,000 | Stop at 10,000. The daily minimum is already covered. |
| 8,000 | 2,000 | Stop at 10,000. The shortfall is larger than 1/7. |
| 9,500 | 1,429 | Land near 10,929, then scrap the oldest ~929, even if they are under 7 days, back to 10,000. |
| 10,000 | 1,429 | Land near 11,429, then scrap the oldest ~1,429 back to 10,000. |

### Logged reading, open to correction

- “Posts” here means the same 10,000 the pipeline already targets: filtered claims (`CLAIM_TARGET` in `pipeline/corpus.py`). Non-claims do not fill a slot. Say if the threshold should count raw fetched posts instead.
- One-seventh stays a fraction of the threshold, so a different threshold would move the daily minimum with it. Rounding of 10,000 / 7 is not specified.
- If search cannot supply enough posts to hit 10,000 or the daily 1/7, that shortfall case is not specified here.
- Today’s job does not do this. It tops up toward 10,000, skips a UTC day it has already fetched, and does not drop in-window posts to make room. Extra claims are sampled out at random, not by age.
