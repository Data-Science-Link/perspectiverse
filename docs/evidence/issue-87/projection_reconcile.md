# Issue #87 — 100K claim-window projection reconciliation

**Purpose:** Explain why a “~$0.53/day with 45% cache” summary and a “~$0.52/day at 0% cache hits” summary are almost the same, and pick **one** planning total for 100K that uses **true** `jev_verdicts` cache hits (not retained-corpus dedup).

**Sources:** GitHub issue [#87](https://github.com/Data-Science-Link/perspectiverse/issues/87) comment (revised projection, agent bc-3c68fae9); Actions run [37934685683](https://github.com/Data-Science-Link/perspectiverse/actions/runs/37934685683) ledger; `pipeline/costs.py` (`JEV_USD_PER_MILLION_INPUT_TOKENS = 0.042`).

---

## Side-by-side inputs

| Input | (a) #87 **Row 1** “Today” (table total **~$0.52/day**) | (b) #87 **Row 2** “+ #92” (**45% true cache**, total **~$0.34/day**) | (c) Agent **0% `jev_cache_hits`** post (bc-25a1b537, **~$0.52/day**) |
| --- | --- | --- | --- |
| **Claim window** | 100,000 retained claims | 100,000 | 100,000 |
| **New claim slots / day** | 100,000 ÷ 7 ≈ **14,286** | 14,286 | 14,286 |
| **Jev paid calls / day (model)** | ≈ **14,286** (1 call per new slot; dedup already in calibration) | 14,286 × (1 − 0.45) ≈ **7,857** | ≈ **14,286** |
| **Tokens / Jev call** | **663** (measured: 946,951 ÷ 1,428 on 10K run) | 663 | 663 |
| **Jev $ / M input tokens** | **$0.042** | $0.042 | $0.042 |
| **Jev $ / day** | **$0.40** (0.0398 × 10) | **$0.22** (0.40 × 0.55) | **$0.40** |
| **True `jev_verdicts` cache-hit assumption** | **0%** (row 1; no #92 discount) | **45%** central (±20 pp in sensitivity table) | **0%** on ledger field `jev_cache_hits` only |
| **Retained-corpus dedup (`posts.section`)** | **Yes** — baked into measured 1,428 calls @ 10K, not an extra multiplier | Same base; cache applies on top of slots that still reach Jev | **Yes** — same as row 1; agent conflated “0% ledger hits” with “0% cost reduction” |
| **DeepInfra labeling $ / day** | **~$0.12** (catalog-bounded; ~1.2k calls) | **~$0.12** | **~$0.12** |
| **DeepInfra calls / day** | ~1,244 (measured @ 10K) | ~1,244 | ~1,244 |
| **Total $ / day** | **~$0.52** | **~$0.34** | **~$0.52** |
| **R2** | ~$0.0001 (omitted) | ~$0.0001 | ~$0.0001 |

### Exact calibration check (Jev only)

| Step | Value |
| --- | --- |
| Measured @ 10K (run 37934685683) | $0.039772 / day; 1,428 calls; 946,951 input tokens |
| Scale to 100K (×10 slots) | $0.39772 / day ≈ **$0.40** |
| Row 2 @ 45% true cache | $0.39772 × 0.55 ≈ **$0.22** / day |

### Where “~$0.53/day with 45% cache” comes from

The **published #87 table does not list $0.53 with 45% cache.** Row 2 at 45% true cache is **~$0.34/day** total ($0.22 Jev + $0.12 labeling).

The **~$0.52–0.53 band** matches **Row 1** (no true-cache discount):

- $0.40 + $0.12 = **$0.52** (rounded table).
- Measured labeling on the calibration run is **$0.1172** → $0.40 + $0.1172 = **$0.517** → rounds to **$0.52** or **$0.53** depending on rounding.

So if a verbal summary paired **“45% cache”** with **~$0.53/day**, it **mixed Row 2’s cache assumption with Row 1’s total** (or rounded Row 1 labeling up). **Row 2’s arithmetic is internally consistent:** removing the 45% discount raises Jev from **$0.22 → $0.40** and total from **~$0.34 → ~$0.52**, not $0.53 → $0.52.

| Which is right? | Use |
| --- | --- |
| **45% true cache on new slots @ 100K** | **Row 2:** **~$0.34/day** total (planning until measured) |
| **0% true cache on new slots @ 100K** | **Row 1:** **~$0.52/day** total |
| **0% `jev_cache_hits` in ledger with full corpus** | **Not a third scenario** — at 10K scale, dedup via `posts.section` already limits paid calls; that is **not** the same as `jev_verdicts` hit rate (see PR #137 `jev_dedup_skips` vs `jev_cache_hits`). |

---

## One planning number @ 100K (true cache only)

**Planning total: ~$0.34/day** at a **100,000-claim** window.

| Component | $ / day | Basis |
| --- | ---: | --- |
| Jev | **~$0.22** | Ledger-calibrated **$0.40/day** @ 0% true cache × **(1 − 0.45)**; 14,286 slots/day; 663 tokens/call; $0.042/M input |
| DeepInfra labeling | **~$0.12** | Flat vs window size (#87; ~1.2k calls/run) |
| **Total** | **~$0.34** | Row 2 central case |

**Caveat:** The **45%** true `jev_verdicts` hit rate is still an **assumption** (issue #87; not yet proven in production ledger). Until `jev_cache_hits` is non-zero over several days, stress **Row 1 (~$0.52/day)** for budget ceiling and **Row 2 (~$0.34/day)** as the target once cache is validated.

**Do not** add retained-corpus dedup (`posts.section` skips) on top of this number — dedup is already reflected in the **$0.40** calibrated base (measured ~one Jev call per daily claim slot, not per post in the window).
