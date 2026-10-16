# Issue #182 — Measured cost split and 100K projection (flat ~110 planets)

**Sources:** `costs/ledger.csv` on `data-snapshot` (no new paid calls). Runs [38894377011](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38894377011) (2026-10-16 steady) and [38677894812](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38677894812) (2026-10-15 shortfall top-up).

**Projection assumption (not a pipeline cap):** DeepInfra labeling is projected as **flat** at roughly **110 published planets** (~10 global + ~100 section), matching the Oct 16 edition. The live job does **not** cap how many planets grouping may publish; this is only a **planning** line for 100K math.

**300-planet line in this PR:** `$0.70067962/day` at 100K is **not** “more planets because the window grew.” It is **steady scaled new-post Jev** plus labeling scaled as if **300** planets were labeled each day: `$0.38124519` Jev + `$0.11712596 × (300/110)` labeling ≈ `$0.70067962`. Grouping quality rules unchanged.

**R2:** Cloudflare R2 on these runs is **&lt; $0.00002/day** (ledger `computed`); omitted from the three-way split below.

---

## Three-way split (new-post scoring · top-up/shortfall Jev · labeling)

| Part | Meaning |
|------|---------|
| **New-post scoring** | Jev spend for the steady **1/7 refresh quota** (`refresh_floor` ≈ 1,427 posts at a 9,985-post window). On Oct 16 this is **all** Jev ($1,362 calls ≤ quota; no top-up). |
| **Top-up / shortfall Jev** | Extra Jev rounds when search must fill the window beyond that quota (Oct 15 push run: 10,230 calls). Attributed as **total Jev − new-post scoring** on that run. |
| **Labeling** | DeepInfra ledger `deepinfra` rows (planet/face/topic/brief calls). |

### Measured @ ~10K (ledger)

| Day type | Run | Posts | Planets | New-post Jev | Top-up Jev | Labeling | **Paid total** |
|----------|-----|------:|--------:|-------------:|-----------:|---------:|---------------:|
| **Steady (Oct 16 UTC)** | 38894377011 | 9,985 | 110 | **$0.038082** | **$0** | **$0.117126** | **$0.155208** |
| **Shortfall (Oct 15 top-up run)** | 38677894812 | 9,688 | 109 | **$0.038082** | **$0.246325** | **$0.110220** | **$0.394627** |

New-post Jev on the shortfall run uses the **same steady-quota dollars** as Oct 16 ($0.038082), not a re-measured slice of the 10,230 calls. Top-up is the remainder of that run’s Jev ($0.284407 − $0.038082).

### Projected @ 100K window (flat ~110 planets labeling)

Scale for **new-post Jev only:** `100,000 / 9,985 = 10.01121233` (same as PR #182: `refresh_floor(100,000) / refresh_floor(9,985)`).

**Labeling** stays at the **measured 10K-day** dollars (projection assumption: ~110 planets, not scaled with window size).

| Day type | New-post Jev | Top-up Jev | Labeling (~110, assumption) | **Total** |
|----------|-------------:|-----------:|----------------------------:|----------:|
| **Steady** | $0.381245 | $0 | $0.117126 | **$0.498371** |
| **Shortfall (Oct 15 pattern)** | $0.381245 | $2.554474 | $0.110220 | **$3.045939** |

Shortfall **total** matches the PR #182 shortfall line ($3.04593876/day). Top-up at 100K is the residual after steady scaled new-post Jev and **flat** Oct 15 labeling; it embeds the PR rule that top-up days are priced with **steady quota $/call** for extras rather than inflating labeling with window size.

---

## UTC day 2026-10-16 (before any cheaper-labeler test)

| Run | Status (2026-10-16) | Paid |
|-----|---------------------|------|
| [38894377011](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38894377011) schedule | complete | $0.155208 |
| [38930594047](https://github.com/Data-Science-Link/perspectiverse/actions/runs/38930594047) merge #181 | **no ledger row yet** (workflow still `in_progress` when checked) | **$0** |

**UTC-day paid total (ledger):** **$0.155208** (Jev $0.038082 + labeling $0.117126; R2 negligible).

---

## Cheaper DeepInfra labeler test

**On hold.** No paid labeling calls in this agent run. Spend-cap halt was verified with a **mocked** tiny stop via `record_jev_attempt` / `apply_jev` before any production labeling.
