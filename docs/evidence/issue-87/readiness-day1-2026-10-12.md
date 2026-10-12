Part of #87

Paid Jetstream readiness attempt (Michael approved 2026-10-12, “That 50k test sounds good”). Cloud agent [bc-51cdea34-ae4c-5bd1-8943-e303cb6e8efa](https://cursor.com/agents/bc-51cdea34-ae4c-5bd1-8943-e303cb6e8efa) · model **composer-2.5-fast**.

**Status:** Day 1 on the agent VM was **invalid** ($0.812, ~5.5K claims, no Jetstream on `main`). PR [#145](https://github.com/Data-Science-Link/perspectiverse/pull/145) is **parked until #27**; hard preflight now refuses paid work without Jetstream supply and disables top-up chasing.

**Non-publishing path:** `Jetstream readiness test (#87)` remains `workflow_dispatch` only — no `data-snapshot`, production R2 key, `public/data.json`, or Pages.

---

## Day 1 (2026-10-12 UTC)

| Field | Value |
|--------|--------|
| **Run ID** | `local-day1-bc-51cdea34` (VM); Actions TBD after [#145](https://github.com/Data-Science-Link/perspectiverse/pull/145) merge |
| **Window target** | `PERSPECTIVERSE_SAMPLE_SIZE=50000` |
| **Claims retained** | **5,541** (5,546 posts in window) — search + top-up **stopped at ~5.5K**, not 50K (#27 Jetstream ingest is **not on `main`**) |
| **Section labeling wall time** | **799.5 s** (10 section systems, 84 section planets) |
| **Total pipeline wall time** | **~3,920 s (~65 min)** (`05:24:07` → `06:29:27` UTC) |
| **Spend cap ($0.50/day)** | **FAILED — $0.812** total (see breakdown) |

### Cost breakdown (day 1)

| Component | USD | Notes |
|-----------|-----|--------|
| **Jev** (`jev-1.13.0`) | **$0.714** | 25,542 calls, 16.0M input tokens — driven by **6 top-up rounds** trying to reach 50K claims |
| **Labeling** (DeepInfra) | **$0.099** | 1,085 calls |
| **Stance** | (in labeling) | — |
| **Total** | **$0.812** | Preflight steady-state projection was ~$0.32; **top-up Jev** blew the cap |

Also logged **314 failed** `jev-latest` calls ($0) — production secret may alias a preview model; successful spend is on `jev-1.13.0`.

### Jev cache (day 1)

| Metric | Value |
|--------|--------|
| **`jev_cache_hits` (TRUE)** | **0** |
| **Dedup skips** | **0** |
| **Pre-filter skips** | **1,146** (short/language/link/dup) |
| **Hit rate vs 5% break-even** | **0%** (day 1 baseline; day 2 is for cache) |

Test corpus uploaded to R2 as `live_corpus_jetstream_readiness_50k.db` (isolated from production `live_corpus.db`).

### Planets / faces vs live run [38174510918](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38174510918)

| | Run 38174510918 (live) | Day 1 readiness |
|--|------------------------|-----------------|
| Claims clustered | 9,884 | 5,541 |
| Global planets / faces | 10 / (log) | 10 / **13** |
| Section planets / faces | **97** / — | **84** / **126** |
| Section label wall time | **880.6 s** | **799.5 s** |

### “Dropping … no face kept a shared claim”

| | Run 38174510918 | Day 1 readiness |
|--|------------------|-----------------|
| Drop count | **17** | **22** |
| Posts on dropped planets (40+) | (baseline **360 posts** on 17 planets) | Not logged per planet at drop time; **22** names in log |
| AI catch-alls (#104) | **Companies**, **Think** | **Think** (×2 incl. “Think Trans Bluesky”) |

### Stance

| | Count |
|--|------:|
| **`Stance check failed`** | **0** (`cost_run.json`) |
| **`second side not coherent`** | **4** (`cost_run.json`) |

---

## Day 2

**Not run in this session.** Needs a **new UTC fetch day** so `fetched_days` advances and Jev cache is exercised (~24h after day 1).

After [#145](https://github.com/Data-Science-Link/perspectiverse/pull/145) merges:

1. **Actions → Jetstream readiness test (#87) → Run workflow**
2. Input **`test_day=2`** (restores `live_corpus_jetstream_readiness_50k.db` from R2, then live pipeline)
3. Best time: **first UTC morning on 2026-10-13** (or ≥24h after day 1 end), when production pipeline is idle.

**Caution:** Day 1 already exceeded the **$0.50** cap because search top-up kept calling Jev; day 2 should cost less if cache hits land, but re-validate postflight before treating as passed.

---

## Section labeling — slowest among the last 7 **`Daily Discourse Pipeline`** runs on `main`

| Run ID | Section wall time | Notes |
|--------|------------------:|--------|
| [38174510918](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38174510918) | **880.6 s** | Full run (merge #129) |
| [38168021541](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38168021541) | 640.8 s | |
| [38166951457](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38166951457) | 545.2 s | |
| [38160752230](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38160752230) | — | Schedule guard no-op |
| [38155381611](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38155381611) | — | Schedule guard no-op |
| [38155196354](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38155196354) | 561.9 s | |
| [38152323558](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38152323558) | — | Schedule guard no-op |

Among the **four runs that actually labeled** in that window, the slowest is **880.6 s** (881 s) on **38174510918** — **not higher** within those four. (Older full runs on `main` still include **1072.6 s** on [38067170954](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38067170954) and **1352.0 s** on [37946621071](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37946621071).)

---

## Takeaways for #27 / #87

1. **`main` cannot fill a 50K claim window** with neutral search alone; top-up stopped at **5,546** posts and spend **> $0.50**.
2. **True 50K/day Jetstream readiness** needs the #27 ingest path (or a merged workflow on `main`) before the approved economics test is meaningful.
3. [#145](https://github.com/Data-Science-Link/perspectiverse/pull/145) is ready for review/merge so day 2 can run in Actions with artifacts and a real **`github.run_id`**.
