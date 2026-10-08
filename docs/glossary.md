# Domain glossary

Words used in the README, the pipeline, and the frontend. The published JSON contract is [`pipeline/schema.py`](../pipeline/schema.py).

**Planet.** One topic in a snapshot (`topics[]`, or a list inside `sections`). At most ten (`SYSTEM_SIZE` and `catalog_size`). [`pipeline/topics.py`](../pipeline/topics.py) ranks candidate groups by distinct authors, then by post count. The site sorts the published list by `total_volume_percent` and draws the largest as the Sun, then Mercury through Pluto ([`src/lib/planets.js`](../src/lib/planets.js), [`src/lib/categories.js`](../src/lib/categories.js)). Planet ids are 1–N for that file and are not a durable key across days.

**Face / perspective.** One stance on a planet. In JSON the list is `perspectives`. Ids look like `1A` ([`pipeline/assemble.py`](../pipeline/assemble.py) `face_id`). Opening a planet turns it into a cube; spike length is that face's `volume_percent`. The cube has six sides. A side with no perspective is drawn dashed ([`src/lib/spikes.js`](../src/lib/spikes.js)). A published planet must have 2–6 perspectives (`MIN_FACES` / `MAX_FACES`). Older prose that says "one to six" is out of date with the schema.

**Solar system.** The view of those planets. "All topics" is one clustering of the whole window. The dropdown filters by newspaper section ([`src/lib/categories.js`](../src/lib/categories.js)). The README calls that control the Solar System dropdown. The label string in [`src/lib/copy.js`](../src/lib/copy.js) is `Filter topics`.

**Section.** A newspaper category: World, Politics, Business, Technology, Sports, Culture, Health, Environment, Education, or Other (`CATEGORIES`). Jev assigns one section per post. A planet's category is the majority section of its members, or a keyword map when posts have no section. When `data.sections` is present, choosing a section shows that section's own planets, not a filter of the global ten.

**Steelman.** A short argument for a face, stored as `arguments` (2–6 strings when the field is present). [`pipeline/label.py`](../pipeline/label.py) writes them. Jev does not.

**Volume.** Share of the posts that made it into the published planets. A planet's `total_volume_percent` values, and a face's `volume_percent` values inside that planet, must each sum to within 0.15 of 100. Topic -1 is excluded (`noise_policy` in the schema). The README describes planet size as share of public attention and spike length as that view's share of the conversation. This repo does not use the word "prevalence".

**Claim.** A public position on an event, policy, institution, or shared issue. Jev keeps a post when the claim score is at least 0.5 (`CLAIM_THRESHOLD` in [`pipeline/jev.py`](../pipeline/jev.py)). The field on a stored post is `is_claim`. Personal asides, jokes, and small talk are not claims. On a live Bluesky run they are not written into the corpus.

**Corpus window.** The retained posts: up to 10,000 claims (`CLAIM_TARGET` in [`pipeline/corpus.py`](../pipeline/corpus.py)) from the last 168 hours (`WINDOW_HOURS`). Stored as SQLite `pipeline/data/live_corpus.db`. Each later day drops posts older than the window and searches only the new day. The file lives in private R2 when the `R2_*` secrets are set; otherwise it is committed on `data-snapshot`.

**Jev.** The decision model in [`pipeline/jev.py`](../pipeline/jev.py) (`api.typesafe.ai`, default model `jev-latest`). One call per post can return a spam score, a section, and a claim score. It does not name planets or write steelmans. Turned on with `TYPESAFE_API_KEY`.

**`data.json`.** The file the site loads. Written to `public/data.json` by [`pipeline/assemble.py`](../pipeline/assemble.py). Fields include `last_updated`, `total_posts`, `window_hours`, `source`, `mode` (`live` or `demo`), `topics`, optional `sections`, and `noise_policy`.

**`data-snapshot`.** The git branch the daily workflow pushes `public/data.json` to. GitHub Pages copies that file over the `main` copy at build time ([`.github/workflows/pages.yml`](../.github/workflows/pages.yml)). The daily job does not commit the snapshot to `main`. The branch also keeps `costs/ledger.csv` and `costs/README.md` (DeepInfra and Jev spend). Those files are not copied onto the Pages site.
