# Summary rubric (Refs #237, PR #241)

Score the rows in `docs/evidence/241/summary-sample.csv`. One row is one item (a planet or one perspective). The file has 40 rows: the original 26, unchanged, plus one face for each of the 14 planets that did not already have one. Every sampled planet has exactly one face row. None of the 20 planets has zero faces. For each item, read that row's `summary`, `brief`, `detail`, and `top_posts` (up to 8 posts, separated by ` || `). Do not look up other planets. Do not score from memory of the pipeline.

This file is the question sheet. It is not a score. The builder does not fill it in. A separate blind scorer on a different model answers it, once on this before-state file and once on the after-state from the replay.

The headline before/after is every row: all 20 planets and every face. Do not skip a row whose label may not match its top posts. Those mismatches are tracked in #290. They stay in this score. The locked question in the next section is the score. Any note about whether a dossier can fix the label is secondary and is not a reason to drop an item.

## Primary question

Answer this first, word for word, once per item. Show the item's summary, brief, detail, and its top 8 posts next to the answer.

Does this text accurately say what these posts argue, with their specifics, in a way that tells a newcomer something useful?

Answer: **yes** / **no** / **unsure**.

## Secondary questions

These do not replace the primary question. Answer each **yes** or **no** for the same item.

1. Does the brief add facts or arguments not in the summary?
2. Does the detail add beyond the brief?
3. Is it specific (names the actual claims or events, not generic)?
4. Is it faithful to the posts (no claim absent from the sampled posts)?
5. Is it free of filler and of copying the planet/first-face text?

Then one number, 1 to 5: would a newcomer find this informative?

Sentence-overlap counts from `python -m pipeline.dossier quality` are a mechanical before-state check. They are not this score.
