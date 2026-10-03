# Improvement requests

Living log of requested changes. The six requests below are now built. Keep adding requests until told the list is done.

The same list is on GitHub: https://github.com/Data-Science-Link/perspectiverse/issues/35

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

## 2. One mobile-length reading screen, same at every depth

Replace the cube as the way a planet is read. The reading screen is about one mobile screen tall and is split into three bands. The same screen is used at every depth so the interface stays familiar. At solar-system depth the bars are the planets. Inside a planet the bars are that planet’s perspectives.

### Top third — 3D bar chart

A horizontal bar chart. Each bar has a percentage and a label.

- Solar-system depth: one bar per planet.
- Planet depth: one bar per perspective.

Bars are 3D, shiny, and carry effects. They use the exact planet skin colors already used on the solar-system bodies.

Clicking a bar highlights it and drives the middle band. The highlighted bar is the one the rest of the screen is about.

### Middle third — summary, then a longer defense

A tight summary of no more than 4 sentences, with a **read more …** control.

Read more expands that into a multi-paragraph summary and a defense of the selected item.

What the middle shows:

- Inside a planet, before a perspective is chosen, the planet’s own summary.
- After a perspective bar is clicked, that perspective’s summary, and the bar stays highlighted.
- On the solar-system screen, the selected planet’s summary.

The LLM has to prepare both lengths at every level:

| Level | Short | Expanded |
| --- | --- | --- |
| Planet | Summary, at most 4 sentences | Multi-paragraph summary and defense |
| Perspective | Summary, at most 4 sentences | Multi-paragraph summary and defense |

### Bottom third — example posts

Example posts for whatever is selected (the highlighted planet, or the highlighted perspective). This band scrolls.

### Logged reading, open to correction

- “Instead of the cubes” replaces the spiky cube. The orbiting solar system is still the other view; this screen is how that view is read, with planets as the bars. Say if the 3D orrery should go away too.
- At planet depth every bar wears that planet’s skin. At solar-system depth each bar wears its own planet’s skin.
- A summary of the whole solar system, above the planet level, was not requested. The solar-system screen’s middle band is the selected planet.
- How many example posts, and what the middle shows before any planet bar is highlighted, are not specified.

## 3. Welcome notification on one mobile page, mostly graphical

The welcome informational notification fits on one mobile page and is mostly graphical.

Today it is a dialog with a tagline, a paragraph, a three-step “What to do” list, and two small figures (planet size, and the cube). That stack is more text than graphic and is taller than one phone screen.

## 4. Cut language that is not the idea or the navigation

Remove copy that is not needed to communicate the ideas or to navigate. The percentage lectures are the example: they read as leftovers from the building process.

Keep names, labels, the percentages themselves, and the controls. Drop the explanations of what a percentage means.

Examples of that leftover voice:

- “This planet is N% of the attention among the planets in view — those shares always add up to 100%. That is attention, not importance…”
- “of this planet’s conversation — darkest and longest if this is the most common view…”
- “N% of attention” captions, and the mobile home line that explains bigger planets and the darkest spike
- “A steelman of this view…” and “the raw talk behind the steelman.”

### Logged reading, open to correction

- This is a pass over the product chrome, not a rewrite of the planet and perspective summaries from request 2.
- The welcome dialog is request 3. This request still applies to explanatory sentences inside it.

## 5. Email of the top planets, their arguments, and their disagreements

Assemble an email of the top planets and their core arguments and disagreements.

Each planet in the email carries:

- The planet
- Its core arguments
- The disagreements inside it

### Logged reading, open to correction

- “Top planets” means the published planets, largest first.
- Who receives it, when it sends, and whether it is a sent message or a draft are not specified.

## 6. Recluster the full 10,000 every day

Every day, cluster the full 10,000 again from scratch.

The day’s planets come from that fresh clustering of the whole threshold, not from a sample, not from only the posts fetched that morning, and not from yesterday’s cluster labels.

### Logged reading, open to correction

- The 10,000 is the same threshold as request 1: the filtered claims kept for the day.
- The daily job already calls the clusterer on the claim set it has, then keeps the largest groups. This request is that the input of that fresh run is the full 10,000, every day.
