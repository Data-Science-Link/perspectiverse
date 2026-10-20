# Blind duplicate labeling definitions (issue #275)

## Planet pairs

Are these two planets really the same story / same perspective, such that showing both looks like a duplicate?

Judge from titles and representative posts only. Answer **yes**, **no**, or **unsure**, with a one-line reason.

## Face pairs (within one planet)

Faces on one planet are always about the same story. The question is not whether the topic matches, but whether the two faces repeat the same take:

Would a reader see these two faces as the SAME viewpoint or stance on the planet's story (a repeated perspective), not just the same topic?

Judge from face titles and representative posts only. Answer **yes**, **no**, or **unsure**, with a one-line reason.

## `f018` / `p001` and planet-pair leaks in the face sample

`f018` is **not** a within-planet face pair. In `oct19-sample-design.json` it has `same_planet: false`, with `planet_a` = Great Day and `planet_b` = Glad Returns (two different planets in Other). The row is **byte-identical** to planet pair `p001` (same titles, post counts, and sample texts). The face draw pools cross-planet face pairs (any two faces in the same solar system); when each planet has a single perspective whose title matches the planet name, that cross-planet face pair collides with the corresponding planet pair in the CSV columns. It is a **planet-pair leak into the face sample**, not two faces on one planet.

Face rows that duplicate a planet row exactly (same section, planets, titles, and sample texts):

| Face id | Duplicate planet id |
| --- | --- |
| f008 | p023 |
| f018 | p001 |
| f019 | p016 |
| f025 | p004 |
| f038 | p017 |
| f042 | p010 |

Only **nine** of sixty face sample rows have `same_planet: true` (`f009`, `f024`, `f026`, `f028`, `f032`, `f035`, `f037`, `f047`, `f060`). The stratified face **sample** is not used for face measurement. The full **within-planet census** is in `oct19-face-census.csv` (every `same_planet` face pair on planets with two or more faces on the Oct 19 edition). Rows marked `planet_leak` in `oct19-pairs-labeled.csv` are the other fifty-one face-sample rows.
