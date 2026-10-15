# Edition baseline metrics

Rerunnable checks on a **published** `public/data.json` (from a `data-snapshot` commit) plus, for hidden volume, that run's Daily Discourse Pipeline job log.

Script: `scripts/baseline_metrics.py`

```bash
python scripts/baseline_metrics.py --log /path/to/pipeline.log public/data.json
```

The script makes **no model or LLM calls**.

## 1. `total_posts`

The top-level `total_posts` field in `data.json`: posts that survived cleaning and count toward the edition denominator after noise removal. This is the number shown as the edition size, not the raw ingest window count.

## 2. Hidden posts (from pipeline log)

Hidden volume is **not** reconstructible from `data.json` alone.

The pipeline logs the global pass (`All topics`) and then each section pass. The same posts can appear in both, so summing every line double-counts. **End-of-run unique lines win when they exist.** Otherwise the global pass is left out when a section pass logged the same kind of line.

| Part | What is counted | Source, in order |
|------|-----------------|------------------|
| `noise` | Posts dropped as noise before the published snapshot | Last `Live snapshot: ... N excluded as noise` line. One snapshot line is the end-of-run figure. |
| `thin_fragments` | Posts held because a fragment was below the thin threshold | Last `(N in thin fragments held below 8 posts)` line (URI-deduped in `report_coherence_stats`). If that line is absent, sum `held K thin fragments (N posts)`. |
| `catch_all_leftover` | Posts the story catch-all could not place, plus sub-floor drops that share the unique leftover bucket | Last `Leftovers: N` minus `thin_fragments`. That unique bucket is catch-all leftovers ∪ thin fragments ∪ sub-floor drops, deduped by URI, so thin is subtracted to keep the parts additive. If `Leftovers:` is absent, sum `INFO {section}: catch-all leftover N posts`, omitting `All topics` when any other section also logged a leftover. |
| `stayed_off_face` | Posts on a dropped face that did not match a kept face | No URI-deduped line exists. When `Timing: N global planet(s) labeled` is present, sum the first number of `N of M posts stayed off the published face count` **after** that marker (the section pass). The global pass before the marker is omitted. If the marker is absent, sum every such line. |

**Grouping controls** = `catch_all_leftover` + `stayed_off_face` + `thin_fragments`.

**Hidden total** = `noise` + grouping controls.

The stderr near-miss `(5 in thin fragments held below 8 posts)` is the unique thin line. It is not the per-pass `held K thin fragments (N posts)` line. On the Oct 13 log those per-pass lines say 5 posts for All topics and 5 again for Technology; the unique line says 5.

## 3. `informational_unsupported_title_posts`

**Not a done bar.** It does not detect same-side faces or a missing opposing side (#162, #163, #164). It is a lexical overlap figure, printed so a rerun can still see it.

Among published faces (every `perspectives` entry under global `topics` and under `sections`), count `post_count` for faces whose title is poorly supported by representative post text.

**Per face:**

1. Let `representative_posts` be the face's list in `data.json` (skip faces with no representatives).
2. Tokenize the face `title` and each representative's `text` with the same rules.
3. A representative **hits** if its token set intersects the title token set.
4. If fewer than **40%** of representatives hit, add this face's `post_count` (and count one face).

A title that tokenizes to nothing is skipped. An empty title is not treated as unsupported.

**Tokenization:**

- Lowercase the string.
- Extract **whole words** with `re.findall(r"[a-z0-9']+", text)`.
- Keep tokens with **length ≥ 3**.
- Drop **stopwords**: `the a an of and or to in on for is are be by with vs not no`.

## 4. Same side, or a title that contradicts the posts

Planet-level check. **No model and no LLM.** A fixed lexicon scores published fields only: face `title`, `summary`, `arguments` (the claims), and `representative_posts`. `stance_check` and `opposing_note` are printed as context when the lexicon already flagged the planet. They do not flag a planet by themselves.

**Cue words** (whole words; a negation in the three words before the cue flips it):

- Condemn: `condemn`, `condemned`, `accusation`/`accused`, `racist`/`racism`, `genocide`/`genocidal`, `kill`/`kills`/`killing`/`killed`, `murder`/`murdered`, `inhumane`, `fascist`/`fascism`, `despise`/`despised`, `abuse`/`abused`, `cruel`/`cruelty`, `appalled`, `barbaric`, `repugnant`, `cowardly`, `oppose`/`opposed`/`opposition`, `reject`/`rejected`, `hate`/`hated`/`hatred`, `threat`/`threats`, `poorly`, `illegal`/`illegally`, `propaganda`, `harm`/`harms`/`harmful`, `flawed`, `terrorism`/`terrorist`, `disproportionate`, `violence`/`violent`, `horrific`/`horror`, `sick`, `wrong`, `idiot`/`idiots`, `moron`/`moronic`, `pedophile`/`pedophiles`, `piss`, `liar`/`lies`/`lying`, `corrupt`/`corruption`, `ashamed`, `garbage`, `stupid`, `evil`, `criminal`/`criminals`, `apartheid`.
- Endorse: `support`/`supports`/`supported`/`supporters`/`supporting`, `defend`/`defends`/`defending`, `deserve`/`deserves`/`deserved`, `success`/`successful`, `worth`, `protect`/`protection`/`protecting`, `boost`, `effective`, `favor`/`favour`, `endorse`/`endorsed`.
- Negation: `not no never nor neither without cannot dont doesnt didnt cant wont`. `against` is not treated as a negator, so "against … racist" does not flip `racist`.

`back` is not an endorse cue. "Go back" is not support.

**Pole:** condemn cues versus endorse cues. The larger side wins. A tie, or no cue, is unscored.

**`same_side`:** the planet publishes two or more faces, and every face's claim text (title + summary + arguments) scores the **same** nonzero pole. That is two faces on one side and no scored opposing side.

**`title_contradicts_posts`:** the title itself has a nonzero pole, at least two representative posts score a pole, and more of those posts take the opposite pole than the title's pole (at least two opposite). This is the missing-or-mislabeled side: the published title is the side the quotes are not. One-face planets are not flagged merely because `opposing_note` is set. A single clear face is a normal edition.

Unscored faces are not guessed. A real opposition written without these cues is not flagged. Two condemnatory angles that a reader might still separate (for example attack reports versus opposition to backing a war) can flag; that is a false-alarm risk of the lexicon, not a special case.

On data-snapshot `ad4e6f3` this flags global **Gaza Genocide** and **Public Execution** as `same_side`, and **Maga Movement** / **MAGA Support** as `title_contradicts_posts`.

The unflagged sample is `random.Random(0)` over unflagged planets with two or more faces, after sorting by scope, name, and id. Default sample size is 10.
