# Edition baseline metrics

Rerunnable checks on a **published** `public/data.json` (from a `data-snapshot` commit) plus, for hidden volume, that run's Daily Discourse Pipeline job log.

Script: `scripts/baseline_metrics.py`

```bash
python scripts/baseline_metrics.py --log /path/to/pipeline.log public/data.json
```

## 1. `total_posts`

The top-level `total_posts` field in `data.json`: posts that survived cleaning and count toward the edition denominator after noise removal. This is the number shown as the edition size, not the raw ingest window count.

## 2. Hidden posts (from pipeline log)

Hidden volume is **not** reconstructible from `data.json` alone. Parse the job log:

| Part | Log pattern | Meaning |
|------|-------------|---------|
| `noise` | `Live snapshot: ... N excluded as noise` | Posts dropped as noise before the published snapshot (Jev / cleaning). |
| `catch_all_leftover` | Every `catch-all leftover N posts` | Story catch-all could not place posts in a specific story. |
| `stayed_off_face` | First number in every `N of M posts stayed off the published face count` line (after `INFO`) | Posts on a dropped face that did not match a kept face. |
| `thin_fragments` | Every `held K thin fragments (N posts)` | Posts held back because a fragment was below the thin threshold. |

**Grouping controls** = `catch_all_leftover` + `stayed_off_face` + `thin_fragments`.

**Hidden total** = `noise` + grouping controls.

Oct 13 and Oct 14 reference totals (data-snapshot `ad4e6f3` / `6f2e23a`, runs `38412331802` / `38560730640`): hidden **5,146** and **5,075**; grouping controls **619** and **878**.

## 3. `unsupported_title_posts`

Among **published faces** (every `perspectives` entry under global `topics` and under `sections`), count `post_count` for faces whose title is poorly supported by representative post text.

**Per face:**

1. Let `representative_posts` be the face's list in `data.json` (skip faces with no representatives).
2. Tokenize the face `title` and each representative's `text` with the same rules.
3. A representative **hits** if its token set intersects the title token set.
4. If fewer than **40%** of representatives hit, add this face's `post_count` to the metric (and count one face).

**Tokenization** (fixed baseline; not the legacy ~870 figure):

- Lowercase the string.
- Extract **whole words** with `re.findall(r"[a-z0-9']+", text)`.
- Keep tokens with **length ≥ 3**.
- Drop **stopwords**: `the a an of and or to in on for is are be by with vs not no`.

Implementation: `tokenize()` in `scripts/baseline_metrics.py`.
